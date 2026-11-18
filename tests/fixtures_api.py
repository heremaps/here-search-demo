###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################


import orjson
import pytest

from here_search_demo.api import API
from here_search_demo.auth import Credentials


@pytest.fixture
def api(monkeypatch, tmp_path):
    import http.client
    import json
    from unittest.mock import MagicMock

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("HERE_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("HERE_ACCESS_KEY_SECRET", raising=False)
    monkeypatch.delenv("HERE_TOKEN_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("HERE_API_KEY", raising=False)
    monkeypatch.setenv("API_KEY", "api_key")
    monkeypatch.chdir(tmp_path)
    # Credentials._config() only sets _api_key when it finds a credentials
    # file containing all mandatory fields (url, key id, key secret, api key).
    creds_file = tmp_path / "credentials.properties"
    creds_file.write_text(
        "here.token.endpoint.url=https://account.api.here.com/oauth2/token\n"
        "here.access.key.id=dummy_id\n"
        "here.access.key.secret=dummy_secret\n"
        "here.api.key=api_key\n"
    )
    # Patch HTTPS so token() never makes a real network call.
    mock_conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({"accessToken": "test_token", "expiresIn": 3600}).encode()
    mock_conn.getresponse.return_value = mock_resp
    monkeypatch.setattr(http.client, "HTTPSConnection", lambda *a, **kw: mock_conn)
    return API(credentials=Credentials())


@pytest.fixture
def session():
    # Configure a response object with the expected interface.
    class _Response:
        def __init__(self, payload):
            self.headers = {
                "X-Request-Id": "userid",
                "X-Correlation-ID": "correlationId",
                "Content-Type": "application/json",
            }
            self._text = orjson.dumps(payload).decode("utf-8")
            self.url = "url"

        async def text(self) -> str:
            return self._text

        async def bytes(self) -> bytes:
            return self._text.encode("utf-8")

        def raise_for_status(self) -> None:
            # Synchronous no-op for tests
            return None

    payload = {"items": []}
    response = _Response(payload)

    class _CM:
        async def __aenter__(self):
            return response

        async def __aexit__(self, exc_type, exc, tb):
            return False

    # Create a simple object with a request() method that returns an async
    # context manager instance; this mimics the aiohttp/HTTPSession API that
    # api.do_send expects.
    class _Session:
        def __init__(self, cm):
            self._cm = cm

        def request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return self._cm

    return _Session(_CM())
