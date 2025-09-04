###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################


import sys
import pytest
from unittest.mock import AsyncMock, MagicMock

sys.modules["pyodide"] = MagicMock()
sys.modules["pyodide.ffi"] = MagicMock()
sys.modules["pyodide.http"] = MagicMock()


class DummyFetchResponse:
    def __init__(self, url, js_response):
        self.js_response = js_response


sys.modules["pyodide.http"].FetchResponse = DummyFetchResponse
sys.modules["pyodide.http"].pyfetch = MagicMock()

# ruff: noqa: E402
from src.here_search.demo.lite import (
    HTTPConnectionError,
    HTTPResponseError,
    URL,
    ClientResponse,
    HTTPSession,
)


@pytest.mark.asyncio
async def test_url_human_repr():
    url = URL("https://example.com")
    assert url.human_repr() == "https://example.com"


def test_http_response_error():
    with pytest.raises(HTTPResponseError):
        raise HTTPResponseError("error")


def test_http_connection_error():
    with pytest.raises(HTTPConnectionError):
        raise HTTPConnectionError("error")


@pytest.mark.asyncio
async def test_client_response_properties():
    js_response = MagicMock()
    js_response.url = "https://test.com"
    js_response.headers = {"X-Test": "1"}
    js_response.status = 200
    js_response.text = AsyncMock(return_value='{"key": "value"}')
    js_response.bytes = AsyncMock(return_value=b"abc")

    resp = ClientResponse("https://test.com", js_response, 200)
    assert resp.url.human_repr() == "https://test.com"
    assert resp.headers == {"X-Test": "1"}
    assert resp.status == 200
    assert await resp.text() == '{"key": "value"}'
    assert await resp.read() == b"abc"
    assert await resp.json() == {"key": "value"}


@pytest.mark.asyncio
async def test_client_response_raise_for_status():
    js_response = MagicMock()
    js_response.status = 404
    js_response.url = "https://test.com"
    js_response.headers = {}
    resp = ClientResponse("https://test.com", js_response, 404)
    with pytest.raises(HTTPResponseError):
        resp.raise_for_status()


@pytest.mark.asyncio
async def test_httpsession_get(monkeypatch):
    mock_pyfetch = AsyncMock()
    mock_js_response = MagicMock()
    mock_js_response.url = "https://test.com"
    mock_js_response.headers = {}
    mock_js_response.status = 200
    mock_pyfetch.return_value = MagicMock(js_response=mock_js_response, status=200)
    monkeypatch.setattr("src.here_search.demo.lite.pyfetch", mock_pyfetch)

    session = HTTPSession()
    response_cm = session.get("https://test.com")
    response = await response_cm
    assert isinstance(response, ClientResponse)
    assert response.status == 200


@pytest.mark.asyncio
async def test_httpsession_post(monkeypatch):
    mock_pyfetch = AsyncMock()
    mock_js_response = MagicMock()
    mock_js_response.url = "https://test.com"
    mock_js_response.headers = {}
    mock_js_response.status = 201
    mock_pyfetch.return_value = MagicMock(js_response=mock_js_response, status=201)
    monkeypatch.setattr("src.here_search.demo.lite.pyfetch", mock_pyfetch)

    session = HTTPSession()
    response_cm = session.post("https://test.com", data={"foo": "bar"})
    response = await response_cm
    assert isinstance(response, ClientResponse)
    assert response.status == 201


def test_httpsession_prepare():
    url = "https://test.com"
    kwargs = {"params": {"a": 1}, "data": {"foo": "bar"}, "headers": {"X": "1"}}
    encoded_url, data, headers, new_kwargs = HTTPSession.prepare(url, kwargs)
    assert encoded_url.startswith(url)
    assert "a=1" in encoded_url
    assert data == {"foo": "bar"}
    assert headers == {"X": "1"}
    assert "options" in new_kwargs
    assert "headers" in new_kwargs["options"]
