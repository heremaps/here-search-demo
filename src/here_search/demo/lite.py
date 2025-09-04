###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from typing import Any, Coroutine, Generator, Tuple
from urllib.parse import urlencode

import orjson as json
from pyodide.ffi import JsProxy
from pyodide.http import FetchResponse, pyfetch


class HTTPConnectionError(Exception):
    pass


class HTTPResponseError(Exception):
    pass


class URL:
    def __init__(self, url: str):
        self._url = url

    def human_repr(self):
        return self._url


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

    js_response: JsProxy
    status: int

    def __init__(self, url: str, js_response: JsProxy, status: int):
        super().__init__(url, js_response)

    @property
    def url(self) -> URL:
        return URL(self.js_response.url)

    @property
    def headers(self):
        return self.js_response.headers

    @property
    def status(self):
        return self.js_response.status

    async def read(self) -> str:
        return await self.js_response.bytes()

    async def text(self) -> str:
        return await self.js_response.text()

    async def json(self, **kwargs: Any) -> Any:
        return json.loads(await self.text(), **kwargs)

    def raise_for_status(self):
        if 400 <= self.status < 600:
            raise HTTPResponseError(f"HTTP error: {self.status}")


class HTTPSession(_ContextManagerMixing):
    """
    A context manager using pyodide pyfetch and mimicking aiohttp ClientSession interface.
    Reference:
    https://pyodide.org/en/stable/usage/api/python-api/http.html
    https://github.com/pyodide/pyodide/tree/main/src/py/pyodide

    >>> session = await HTTPSession()
    >>> get_response = await session.get(url, params=params, headers={})
    >>> resp.raise_for_status()
    >>> resp = await get_response.json()

    >>> async with HTTPSession() as session:
    >>>     async with session.get(url, params=params, headers={}) as get_response:
    >>>         resp.raise_for_status()
    >>>         resp = await get_response.json()

    >>> async with HTTPSession() as session:
    >>>     async with session.get(image_url) as get_response:
    >>>         image_data = await get_response.read()

    >>> async with HTTPSession() as session:
    >>>     async with session.post(url, params=params, data=data, headers={}) as post_response:
    >>>         resp.raise_for_status()
    >>>         resp = await post_response.text()
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _aget(self, url: str, **kwargs) -> ClientResponse:
        encoded_url, data, headers, kwargs = HTTPSession.prepare(url, kwargs)
        res = await pyfetch(encoded_url, **kwargs)
        return ClientResponse(encoded_url, res.js_response, res.status)

    async def _apost(self, url: str, **kwargs) -> ClientResponse:
        # https://pyodide.org/en/stable/usage/faq.html
        encoded_url, data, headers, kwargs = HTTPSession.prepare(url, kwargs)
        res = await pyfetch(
            encoded_url,
            method="POST",
            body=data,
            credentials="same-origin",
            **kwargs,
        )
        return ClientResponse(encoded_url, res.js_response, res.status)

    def get(self, url: str, *args, **kwargs: Any) -> FetchResponseCM:
        return FetchResponseCM(self._aget(url, **kwargs))

    def post(self, url: str, *args, **kwargs: Any) -> FetchResponseCM:
        return FetchResponseCM(self._apost(url, **kwargs))

    @staticmethod
    def prepare(url, kwargs) -> Tuple[str, dict, dict, dict]:
        params = kwargs.pop("params", {})
        data = kwargs.pop("data", {})
        headers = kwargs.pop("headers", None)
        if headers:
            kwargs.setdefault("options", {}).setdefault("headers", {}).update(headers)
        encoded_url = f"{url}?{urlencode(params or {}, doseq=False)}"
        return encoded_url, data, headers, kwargs
