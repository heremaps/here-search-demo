###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import here_search_demo.lite as lite
from here_search_demo.lite import (
    _BrowserFetchResponse,
    _ContextManagerMixing,
    ClientResponse,
    FetchResponseCM,
    HTTPConnectionError,
    HTTPNetworkError,
    HTTPResponseError,
    HTTPSession,
)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


def test_http_network_error_is_connection_error():
    assert issubclass(HTTPNetworkError, HTTPConnectionError)


def test_http_response_error_is_exception():
    assert issubclass(HTTPResponseError, Exception)


# ---------------------------------------------------------------------------
# _BrowserFetchResponse
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_js_response():
    resp = MagicMock()
    resp.status = 200
    resp.text = AsyncMock(return_value="hello")
    resp.json = AsyncMock(return_value={"key": "value"})
    return resp


def test_browser_fetch_response_url(mock_js_response):
    r = _BrowserFetchResponse("https://example.com/", mock_js_response)
    assert r.url == "https://example.com/"


def test_browser_fetch_response_status(mock_js_response):
    r = _BrowserFetchResponse("https://example.com/", mock_js_response)
    assert r.status == 200


@pytest.mark.asyncio
async def test_browser_fetch_response_text(mock_js_response):
    r = _BrowserFetchResponse("https://example.com/", mock_js_response)
    assert await r.text() == "hello"


@pytest.mark.asyncio
async def test_browser_fetch_response_json(mock_js_response):
    r = _BrowserFetchResponse("https://example.com/", mock_js_response)
    assert await r.json() == {"key": "value"}


# ---------------------------------------------------------------------------
# _browser_pyfetch — patches the module-level `js` object
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_browser_pyfetch_basic_get():
    fake_js_resp = MagicMock()
    fake_js_resp.status = 200

    mock_js = MagicMock()
    mock_js.Object.new.return_value = MagicMock()
    mock_js.fetch = AsyncMock(return_value=fake_js_resp)

    with patch.object(lite, "js", mock_js):
        result = await lite._browser_pyfetch("https://example.com/")

    assert isinstance(result, _BrowserFetchResponse)
    assert result.status == 200
    mock_js.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_browser_pyfetch_sets_headers():
    fake_js_resp = MagicMock()
    fake_js_resp.status = 204

    init_obj = MagicMock()
    mock_js = MagicMock()
    mock_js.Object.new.return_value = init_obj
    mock_js.fetch = AsyncMock(return_value=fake_js_resp)

    with patch.object(lite, "js", mock_js):
        await lite._browser_pyfetch("https://example.com/", headers={"Authorization": "Bearer tok"})

    # headers object was created and assigned
    assert mock_js.Object.new.call_count >= 2


@pytest.mark.asyncio
async def test_browser_pyfetch_sets_body():
    fake_js_resp = MagicMock()
    fake_js_resp.status = 201

    init_obj = MagicMock()
    mock_js = MagicMock()
    mock_js.Object.new.return_value = init_obj
    mock_js.fetch = AsyncMock(return_value=fake_js_resp)

    with patch.object(lite, "js", mock_js):
        await lite._browser_pyfetch("https://example.com/", method="POST", body=b"data")

    assert init_obj.body == b"data"


@pytest.mark.asyncio
async def test_browser_pyfetch_sets_credentials():
    fake_js_resp = MagicMock()
    fake_js_resp.status = 200

    init_obj = MagicMock()
    mock_js = MagicMock()
    mock_js.Object.new.return_value = init_obj
    mock_js.fetch = AsyncMock(return_value=fake_js_resp)

    with patch.object(lite, "js", mock_js):
        await lite._browser_pyfetch("https://example.com/", credentials="same-origin")

    assert init_obj.credentials == "same-origin"


# ---------------------------------------------------------------------------
# _ContextManagerMixing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_manager_mixin_aenter_returns_self():
    obj = _ContextManagerMixing()
    result = await obj.__aenter__()
    assert result is obj


@pytest.mark.asyncio
async def test_context_manager_mixin_aexit_returns_none():
    obj = _ContextManagerMixing()
    result = await obj.__aexit__(None, None, None)
    assert result is None


@pytest.mark.asyncio
async def test_context_manager_mixin_await_returns_self():
    obj = _ContextManagerMixing()
    result = await obj
    assert result is obj


def test_context_manager_mixin_iter_is_generator():
    import warnings

    obj = _ContextManagerMixing()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        gen = iter(obj)
        # gen is a generator wrapping an inner coroutine; close it before GC
        # to avoid "coroutine was never awaited" ResourceWarning.
        gen.close()
    assert True  # if we got here iter() returned a generator without raising


# ---------------------------------------------------------------------------
# FetchResponseCM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_response_cm_aenter_awaits_coroutine(mock_js_response):
    expected = _BrowserFetchResponse("https://example.com/", mock_js_response)

    async def coro():
        return expected

    cm = FetchResponseCM(coro())
    async with cm as resp:
        assert resp is expected


@pytest.mark.asyncio
async def test_fetch_response_cm_await_returns_result(mock_js_response):
    expected = _BrowserFetchResponse("https://example.com/", mock_js_response)

    async def coro():
        return expected

    result = await FetchResponseCM(coro())
    assert result is expected


# ---------------------------------------------------------------------------
# ClientResponse
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client_js_response():
    resp = MagicMock()
    resp.url = "https://example.com/"
    resp.status = 200
    resp.text = AsyncMock(return_value="body text")
    resp.bytes = AsyncMock(return_value=b"raw bytes")
    headers_mock = MagicMock()
    headers_mock.entries.return_value = [("Content-Type", "application/json")]
    resp.headers = headers_mock
    return resp


def test_client_response_url(mock_client_js_response):
    cr = ClientResponse("https://example.com/", mock_client_js_response, 200)
    assert cr.url == "https://example.com/"


def test_client_response_status(mock_client_js_response):
    cr = ClientResponse("https://example.com/", mock_client_js_response, 200)
    assert cr.status == 200


def test_client_response_headers(mock_client_js_response):
    cr = ClientResponse("https://example.com/", mock_client_js_response, 200)
    headers = cr.headers
    assert dict(headers) == {"Content-Type": "application/json"}


def test_client_response_raise_for_status_ok(mock_client_js_response):
    mock_client_js_response.status = 200
    cr = ClientResponse("https://example.com/", mock_client_js_response, 200)
    cr.raise_for_status()  # must not raise


@pytest.mark.parametrize("status", [400, 404, 500, 503])
def test_client_response_raise_for_status_error(mock_client_js_response, status):
    mock_client_js_response.status = status
    cr = ClientResponse("https://example.com/", mock_client_js_response, status)
    with pytest.raises(HTTPResponseError):
        cr.raise_for_status()


@pytest.mark.asyncio
async def test_client_response_text(mock_client_js_response):
    cr = ClientResponse("https://example.com/", mock_client_js_response, 200)
    assert await cr.text() == "body text"


@pytest.mark.asyncio
async def test_client_response_read(mock_client_js_response):
    cr = ClientResponse("https://example.com/", mock_client_js_response, 200)
    assert await cr.read() == b"raw bytes"


# ---------------------------------------------------------------------------
# HTTPSession.prepare — pure static method
# ---------------------------------------------------------------------------


def test_prepare_plain_url():
    url, data, headers, kwargs = HTTPSession.prepare("https://example.com/")
    assert url == "https://example.com/"
    assert data is None
    assert headers is None


def test_prepare_merges_params():
    url, data, headers, kwargs = HTTPSession.prepare("https://example.com/search", params={"q": "pizza", "at": "52,13"})
    assert "q=pizza" in url
    assert "at=52%2C13" in url or "at=52,13" in url


def test_prepare_existing_query_plus_params():
    url, data, headers, kwargs = HTTPSession.prepare("https://example.com/search?existing=1", params={"q": "burger"})
    assert "existing=1" in url
    assert "q=burger" in url


def test_prepare_extracts_data_and_headers():
    url, data, headers, kwargs = HTTPSession.prepare(
        "https://example.com/",
        data='{"key": "value"}',
        headers={"Authorization": "Bearer tok"},
    )
    assert data == '{"key": "value"}'
    assert headers == {"Authorization": "Bearer tok"}


def test_prepare_unknown_kwargs_are_passed_through():
    url, data, headers, kwargs = HTTPSession.prepare("https://example.com/", timeout=30)
    assert kwargs == {"timeout": 30}


# ---------------------------------------------------------------------------
# HTTPSession — get / post / request return FetchResponseCM
# ---------------------------------------------------------------------------


def test_session_get_returns_fetch_response_cm():
    import warnings

    session = HTTPSession()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = session.get("https://example.com/")
        result._coro.close()
    assert isinstance(result, FetchResponseCM)


def test_session_post_returns_fetch_response_cm():
    import warnings

    session = HTTPSession()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = session.post("https://example.com/")
        result._coro.close()
    assert isinstance(result, FetchResponseCM)


def test_session_request_get_returns_fetch_response_cm():
    import warnings

    session = HTTPSession()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = session.request("GET", "https://example.com/")
        result._coro.close()
    assert isinstance(result, FetchResponseCM)


def test_session_request_post_returns_fetch_response_cm():
    import warnings

    session = HTTPSession()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        result = session.request("POST", "https://example.com/")
        result._coro.close()
    assert isinstance(result, FetchResponseCM)


# ---------------------------------------------------------------------------
# HTTPSession._arequest / _aget / _apost — mock pyfetch
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_pyfetch(mock_js_response):
    fake_fetch_resp = _BrowserFetchResponse("https://example.com/", mock_js_response)
    fake_fetch_resp.js_response = mock_js_response
    mock = AsyncMock(return_value=fake_fetch_resp)
    with patch("here_search_demo.lite.pyfetch", mock):
        yield mock


@pytest.mark.asyncio
async def test_aget_calls_pyfetch(patched_pyfetch):
    session = HTTPSession()
    result = await session._aget("https://example.com/")
    patched_pyfetch.assert_awaited_once()
    assert isinstance(result, ClientResponse)


@pytest.mark.asyncio
async def test_apost_calls_pyfetch_with_post(patched_pyfetch):
    session = HTTPSession()
    await session._apost("https://example.com/", data='{"x":1}')
    call_kwargs = patched_pyfetch.call_args
    assert call_kwargs.kwargs.get("method") == "POST" or "POST" in call_kwargs.args


@pytest.mark.asyncio
async def test_arequest_passes_headers(patched_pyfetch):
    session = HTTPSession()
    await session._arequest("https://example.com/", method="GET", headers={"X-Custom": "value"})
    call_kwargs = patched_pyfetch.call_args.kwargs
    assert call_kwargs.get("headers") == {"X-Custom": "value"}


# ---------------------------------------------------------------------------
# HTTPSession.__aenter__ — warmup fetch is swallowed on error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_aenter_swallows_warmup_error():
    session = HTTPSession()
    with patch.object(session, "_arequest", side_effect=Exception("warmup failed")):
        result = await session.__aenter__()
    assert result is session


@pytest.mark.asyncio
async def test_session_aenter_returns_self_on_success(patched_pyfetch):
    session = HTTPSession()
    result = await session.__aenter__()
    assert result is session
