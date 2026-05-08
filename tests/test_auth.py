###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import json
from unittest.mock import patch, MagicMock
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


@pytest.fixture()
def creds_file_with_scope(tmp_path, monkeypatch):
    content = (
        "here.access.key.id=dummy_id\n"
        "here.access.key.secret=dummy_secret\n"
        "here.token.endpoint.url=https://example.com/oauth2/token\n"
        "here.token.scope=hrn:here:authorization::project/1234:read\n"
    )
    f = tmp_path / "credentials.properties"
    f.write_text(content)
    monkeypatch.chdir(tmp_path)
    _clear_here_env(monkeypatch)
    return f


@pytest.fixture()
def creds_file_no_scope(tmp_path, monkeypatch):
    content = (
        "here.access.key.id=dummy_id\n"
        "here.access.key.secret=dummy_secret\n"
        "here.token.endpoint.url=https://example.com/oauth2/token\n"
    )
    f = tmp_path / "credentials.properties"
    f.write_text(content)
    monkeypatch.chdir(tmp_path)
    _clear_here_env(monkeypatch)
    return f


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
    mock_https.return_value = _mock_https_connection(token_payload={"accessToken": "abc", "expiresIn": 3600})
    creds = Credentials()
    with patch.object(creds, "_schedule_refresh") as mock_schedule:
        _ = creds.token
        mock_schedule.assert_called_once_with(3600, use_async=False)


@patch("here_search_demo.auth.http.client.HTTPSConnection")
def test_schedule_refresh_not_called_when_cached(mock_https, creds_file_no_scope):
    mock_https.return_value = _mock_https_connection(token_payload={"accessToken": "abc", "expiresIn": 7200})
    creds = Credentials()
    _ = creds.token
    with patch.object(creds, "_schedule_refresh") as mock_schedule:
        _ = creds.token  # cached, no refresh scheduled
        mock_schedule.assert_not_called()


def test_token_returns_none_without_credentials(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    _clear_here_env(monkeypatch)
    creds = Credentials()
    assert creds.token is None
