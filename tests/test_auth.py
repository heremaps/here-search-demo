###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from here_search_demo.auth import Credentials


_HERE_CREDENTIAL_VARS = (
    "HERE_ACCESS_KEY_ID",
    "HERE_ACCESS_KEY_SECRET",
    "HERE_TOKEN_ENDPOINT_URL",
    "HERE_TOKEN_SCOPE",
)


def _clear_here_env(monkeypatch):
    """Remove HERE credential env vars so file-based or API_KEY credentials take precedence."""
    for var in _HERE_CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)


def _make_creds_file(tmp_path, monkeypatch, content):
    """Write a credentials file to tmp_path and fully isolate the search paths.

    Credentials._config() searches several directories for credentials files.
    We must block every path that could reach the developer's real credentials:
      - Path.cwd()  -> monkeypatch.chdir(tmp_path)
      - Path("")    -> same as cwd, covered above
      - Path.home() -> patched via monkeypatch on the module-level name
      - Path(os.environ["HOME"]) / ".here" -> monkeypatch.setenv("HOME", tmp_path)
      - Path("/drive") -> does not exist on macOS/Linux dev machines
    """
    f = tmp_path / "credentials.properties"
    f.write_text(content)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    # Patch the Path class used inside the auth module so Path.home() returns
    # tmp_path. We patch the module-level name rather than the class itself to
    # avoid cross-worker interference when running with pytest-xdist.
    import here_search_demo.auth as auth_module

    class _PatchedPath(type(tmp_path)):
        @classmethod
        def home(cls):
            return tmp_path

    monkeypatch.setattr(auth_module, "Path", _PatchedPath)
    _clear_here_env(monkeypatch)
    return f


@pytest.fixture()
def creds_file_with_scope(tmp_path, monkeypatch):
    return _make_creds_file(
        tmp_path,
        monkeypatch,
        (
            "here.access.key.id=dummy_id\n"
            "here.access.key.secret=dummy_secret\n"
            "here.token.endpoint.url=https://example.com/oauth2/token\n"
            "here.token.scope=hrn:here:authorization::project/1234:read\n"
        ),
    )


@pytest.fixture()
def creds_file_no_scope(tmp_path, monkeypatch):
    return _make_creds_file(
        tmp_path,
        monkeypatch,
        (
            "here.access.key.id=dummy_id\n"
            "here.access.key.secret=dummy_secret\n"
            "here.token.endpoint.url=https://example.com/oauth2/token\n"
        ),
    )


def _mock_https_connection(expected_status=200, token_payload=None, capture=None):
    if token_payload is None:
        token_payload = {"accessToken": "abc", "expiresIn": 3600}
    mock_conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = expected_status
    mock_resp.read.return_value = json.dumps(token_payload).encode()

    def request(method, path, body=None, headers=None):
        if capture is not None:
            capture["method"] = method
            capture["path"] = path
            capture["body"] = body
            capture["headers"] = headers

    mock_conn.request.side_effect = request
    mock_conn.getresponse.return_value = mock_resp
    return mock_conn


@patch("here_search_demo.auth.http.client.HTTPSConnection")
def test_token_scope_included(mock_https, creds_file_with_scope):
    capture = {}
    mock_https.return_value = _mock_https_connection(capture=capture)

    creds = Credentials()
    token = creds.token

    # Validate body sent
    sent_body = json.loads(capture["body"])
    assert sent_body["scope"] == "hrn:here:authorization::project/1234:read"
    assert sent_body["clientId"] == "dummy_id"

    # token returns the access token string
    assert token == "abc"


@patch("here_search_demo.auth.http.client.HTTPSConnection")
def test_token_scope_optional(mock_https, creds_file_no_scope):
    capture = {}
    mock_https.return_value = _mock_https_connection(capture=capture)

    creds = Credentials()
    token = creds.token

    sent_body = json.loads(capture["body"])
    assert "scope" not in sent_body
    assert sent_body["clientId"] == "dummy_id"
    assert token == "abc"


@patch("here_search_demo.auth.http.client.HTTPSConnection")
def test_token_raises_runtime_error_on_non_200(mock_https, creds_file_no_scope):
    """A non-200 token endpoint response must raise RuntimeError with the status."""
    mock_https.return_value = _mock_https_connection(expected_status=401, token_payload={"error": "unauthorized"})
    creds = Credentials()
    with pytest.raises(RuntimeError, match="Token request failed 401"):
        _ = creds.token


@patch("here_search_demo.auth.http.client.HTTPSConnection")
def test_expires_caching(mock_https, creds_file_no_scope):
    mock_https.return_value = _mock_https_connection(token_payload={"accessToken": "abc", "expiresIn": 7200})
    creds = Credentials()
    token1 = creds.token
    token2 = creds.token
    assert token1 == token2 == "abc"
    # Only one HTTP request should have been made (token is cached)
    mock_https.return_value.request.assert_called_once()


@patch("here_search_demo.auth.http.client.HTTPSConnection")
def test_schedule_refresh_called(mock_https, creds_file_no_scope):
    """Verify that token retrieval returns the correct value and schedules a refresh."""
    mock_https.return_value = _mock_https_connection(token_payload={"accessToken": "abc", "expiresIn": 3600})
    creds = Credentials()
    token = creds.token
    assert token == "abc"
    assert creds._expires is not None
    # With expiresIn=3600, delay = 3600-1800 = 1800 > 0, so a refresh should be scheduled
    assert creds._refresh_handle is not None or creds._refresh_timer is not None


@patch("here_search_demo.auth.http.client.HTTPSConnection")
def test_schedule_refresh_not_called_when_cached(mock_https, creds_file_no_scope):
    """Verify that a second .token access uses cache (no new HTTP request, same token)."""
    mock_https.return_value = _mock_https_connection(token_payload={"accessToken": "abc", "expiresIn": 7200})
    creds = Credentials()
    token1 = creds.token
    expires_after_first = creds._expires
    token2 = creds.token
    assert token1 == token2 == "abc"
    # Expiry unchanged proves the cached path was taken (no re-retrieval)
    assert creds._expires == expires_after_first
    # Only one HTTP request should have been made
    mock_https.return_value.request.assert_called_once()


def test_token_returns_none_without_credentials(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    _clear_here_env(monkeypatch)
    creds = Credentials()
    assert creds.token is None


@pytest.mark.asyncio
async def test_atoken_uses_pyfetch_post_in_emscripten(monkeypatch, tmp_path):
    # _config() only reads HERE_ACCESS_KEY_* env vars inside the file-parsing
    # loop, so a credentials file must exist for _access_key_secret to be set.
    creds_file = tmp_path / "credentials.properties"
    creds_file.write_text(
        "here.token.endpoint.url=https://example.com/oauth2/token\n"
        "here.access.key.id=dummy_id\n"
        "here.access.key.secret=dummy_secret\n"
        "here.api.key=dummy_api_key\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HERE_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("HERE_ACCESS_KEY_SECRET", raising=False)
    monkeypatch.delenv("HERE_TOKEN_ENDPOINT_URL", raising=False)

    class _Resp:
        status = 200

        async def json(self):
            return {"accessToken": "abc", "expiresIn": 3600}

    import here_search_demo.auth as auth_module

    monkeypatch.setattr(auth_module.sys, "platform", "emscripten")

    creds = Credentials()
    pyfetch_mock = AsyncMock(return_value=_Resp())
    with patch("here_search_demo.lite.pyfetch", pyfetch_mock):
        with patch.object(creds, "_schedule_refresh"):
            token = await creds.atoken

    pyfetch_mock.assert_awaited_once()
    _, kwargs = pyfetch_mock.await_args
    assert kwargs["method"] == "POST"
    assert kwargs["credentials"] == "same-origin"
    assert kwargs["body"]
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["headers"]["Authorization"].startswith("OAuth ")
    assert token == "abc"
