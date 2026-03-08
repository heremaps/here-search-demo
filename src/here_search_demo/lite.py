###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from typing import Any, Coroutine, Generator, Literal, cast
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

try:  # At runtime this succeeds only in pyodide/python-xeus environments
    import js  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - plain CPython / tests / JupyterLab
    js = None  # type: ignore[assignment]


class HTTPConnectionError(Exception):
    pass


class HTTPResponseError(Exception):
    pass


class HTTPNetworkError(HTTPConnectionError):
    pass


_SUPPORTED_FETCH_OPTIONS = {"mode", "cache", "redirect", "referrer", "referrerPolicy"}


class _BrowserFetchResponse:
    """Minimal wrapper around the JS Response returned by js.fetch."""

    def __init__(self, url: str, js_response):
        self._url = url
        self.js_response = js_response
        self._status = int(js_response.status)

    @property
    def url(self) -> str:
        return self._url

    @property
    def status(self) -> int:
        return self._status

    async def text(self) -> str:
        return await self.js_response.text()

    async def bytes(self) -> bytes:
        buf = await self.js_response.arrayBuffer()
        return bytes(list(js.Uint8Array.new(buf)))  # type: ignore[attr-defined]

    async def json(self):
        return await self.js_response.json()


async def _browser_pyfetch(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    body: bytes | str | None = None,
    credentials: str | None = None,
    **kwargs,
):
    init = js.Object.new()
    init.method = method

    if headers:
        h = js.Object.new()
        for k, v in headers.items():
            setattr(h, k, v)
        init.headers = h

    if body is not None:
        init.body = body

    if credentials is not None:
        init.credentials = credentials

    for k, v in (kwargs or {}).items():
        if k in _SUPPORTED_FETCH_OPTIONS:
            setattr(init, k, v)

    try:
        resp = await js.fetch(url, init)
    except Exception as exc:  # pragma: no cover - exercised only in browser
        raise HTTPNetworkError(
            f"Browser fetch failed for {url!r}. "
            "This usually means a CORS or network restriction in the "
            "browser prevented the request from reaching the server. "
            f"Original error: {exc!r}"
        ) from exc

    return _BrowserFetchResponse(url, resp)


FetchResponse = _BrowserFetchResponse
pyfetch = _browser_pyfetch

try:  # Prefer native Pyodide implementation when available
    from pyodide.http import (  # type: ignore[import]
        FetchResponse as _PyodideFetchResponse,
        pyfetch as _pyodide_pyfetch,
    )
except ImportError:  # pragma: no cover - executed outside Pyodide
    pass
else:  # pragma: no cover - exercised only inside Pyodide
    FetchResponse = _PyodideFetchResponse  # type: ignore[assignment]
    pyfetch = _pyodide_pyfetch  # type: ignore[assignment]


class _ContextManagerMixing:
    # https://docs.python.org/3/library/contextlib.html#contextlib.contextmanager
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self) -> "_ContextManagerMixing":
        return self

    async def __aexit__(self, *args, **kwargs) -> None:
        pass

    def __await__(self):
        async def closure():
            return self

        return closure().__await__()

    def __iter__(self) -> Generator:
        return self.__await__()


class FetchResponseCM(_ContextManagerMixing):
    """
    A context manager mimicking aiohttp _RequestContextManager.
    """

    def __init__(self, coro: Coroutine) -> None:
        super().__init__()
        self._coro = coro

    async def __aenter__(self) -> FetchResponse:
        return await self._coro

    def __await__(self) -> Generator:
        return self._coro.__await__()


class ClientResponse(FetchResponse, _ContextManagerMixing):
    """
    Async context manager around pyodide FetchResponse
    Reference:
    https://pyodide.org/en/stable/usage/type-conversions.html#type-translations-jsproxy
    https://developer.mozilla.org/en-US/docs/Web/API/fetch
    https://developer.mozilla.org/en-US/docs/Web/API/Response
    """

    js_response: Any
    status: int

    def __init__(self, url: str, js_response: Any, status: int):
        # status argument kept for compatibility; actual status taken from js_response
        super().__init__(url, js_response)

    @property
    def url(self) -> str:
        return self.js_response.url

    @property
    def headers(self) -> dict[str, str]:
        """Return response headers as a plain Python dict."""
        raw = self.js_response.headers
        return dict(raw.entries())

    @property
    def status(self):
        return self.js_response.status

    async def read(self) -> str:
        return await self.js_response.bytes()

    async def text(self) -> str:
        return await self.js_response.text()

    def raise_for_status(self):
        if 400 <= self.status < 600:
            raise HTTPResponseError(f"HTTP error: {self.status}")


class HTTPSession(_ContextManagerMixing):
    """
    A context manager using pyodide pyfetch and mimicking aiohttp ClientSession interface.
    Reference:
    https://pyodide.org/en/stable/usage/api/python-api/http.html
    https://github.com/pyodide/pyodide/tree/main/src/py/pyodide

    Examples (illustrative, not executed by doctest):

    - Basic GET
      async def demo_get(url):
          session = await HTTPSession()
          get_response = await session.get(url)
          get_response.raise_for_status()
          resp = await get_response.json()
          return resp

    - Context-managed GET
      async def demo_ctx_get(url):
          async with HTTPSession() as session:
              async with session.get(url) as get_response:
                  get_response.raise_for_status()
                  resp = await get_response.json()
                  return resp

    - Reading bytes (e.g., image)
      async def demo_read(image_url):
          async with HTTPSession() as session:
              async with session.get(image_url) as get_response:
                  image_data = await get_response.read()
                  return image_data

    - Basic POST
      async def demo_post(url):
          async with HTTPSession() as session:
              async with session.post(url) as post_response:
                  post_response.raise_for_status()
                  resp = await post_response.text()
                  return resp
    """

    warmup_url = "https://example.com/"  # lightweight HEAD/GET target

    def __init__(self, *args, warmup: bool | None = None, **kwargs):
        super().__init__(*args, **kwargs)

    async def __aenter__(self) -> "HTTPSession":
        # Perform a one-off warm-up fetch to pay connection/TLS cost up front.
        try:
            resp = await self._arequest(self.warmup_url, method="HEAD")
            _ = resp.status
        except Exception:
            pass
        return self

    async def _arequest(self, url: str, **kwargs) -> ClientResponse:
        """
        Generic async HTTP request (GET, HEAD, etc). Use method=... in kwargs.
        """
        encoded_url, data, headers, kwargs = HTTPSession.prepare(url, **kwargs)
        res = await pyfetch(encoded_url, **kwargs)
        return ClientResponse(encoded_url, res.js_response, res.status)

    async def _apost(self, url: str, **kwargs) -> ClientResponse:
        # https://pyodide.org/en/stable/usage/faq.html
        encoded_url, data, headers, kwargs = HTTPSession.prepare(url, **kwargs)
        res = await pyfetch(
            encoded_url,
            method="POST",
            body=data,
            credentials="same-origin",
            headers=headers,
            **kwargs,
        )
        return ClientResponse(encoded_url, res.js_response, res.status)

    async def _aget(self, url: str, **kwargs) -> ClientResponse:
        return await self._arequest(url, method="GET", **kwargs)

    def get(self, url: str, *args, **kwargs: Any) -> FetchResponseCM:
        return FetchResponseCM(self._aget(url, **kwargs))

    def post(self, url: str, *args, **kwargs: Any) -> FetchResponseCM:
        return FetchResponseCM(self._apost(url, **kwargs))

    def request(self, method: Literal["GET", "POST"], url: str, *args, **kwargs: Any) -> FetchResponseCM:
        fn = {"GET": self.get, "POST": self.post}[method]
        return fn(url, *args, **kwargs)

    @staticmethod
    def prepare(url: str, **kwargs) -> tuple[str, str | None, dict | None, dict]:
        params = kwargs.pop("params", {})
        data = kwargs.pop("data", None)
        headers = kwargs.pop("headers", None)
        if params:
            parsed = urlparse(url)
            query: dict[str, list[str]] = parse_qs(parsed.query)
            query.update(params)
            encoded_url = cast(str, urlunparse(parsed._replace(query=urlencode(query, doseq=True))))
            return encoded_url, data, headers, kwargs
        else:
            return url, data, headers, kwargs
