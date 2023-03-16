###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from pyodide.http import pyfetch, FetchResponse, JsProxy

from urllib.parse import urlencode
from typing import Any, Coroutine, Generator, Tuple
import json


class HTTPConnectionError(Exception):
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
    _raise_for_status: bool

    def __init__(self, url: str, js_response: JsProxy, raise_for_status: bool = False):
        self._raise_for_status = raise_for_status
        super().__init__(url, js_response)

    @property
    def url(self) -> URL:
        return URL(self.js_response.url)

    @property
    def headers(self):
        return self.js_response.headers

    async def text(self) -> str:
        if self._raise_for_status:
            self.raise_for_status()
        return await self.js_response.text()

    async def json(self, **kwargs: Any) -> Any:
        return json.loads(await self.text(), **kwargs)

    def raise_for_status(self):
        self._raise_if_failed()


class HTTPSession(_ContextManagerMixing):
    """
    A context manager using pyodide pyfetch and mimicking aiohttp ClientSession interface.
    Reference:
    https://pyodide.org/en/stable/usage/api/python-api/http.html
    https://github.com/pyodide/pyodide/tree/main/src/py/pyodide

    >>> session = await HTTPSession(raise_for_status=True)
    >>> get_response = await session.get(url, params=params, headers={})
    >>> resp = await get_response.json()

    >>> async with HTTPSession(raise_for_status=True) as session:
    >>>     async with session.get(url, params=params, headers={}) as get_response:
    >>>         resp =  await get_response.json()

    >>> async with HTTPSession(raise_for_status=True) as session:
    >>>     async with session.post(url, params=params, data=data, headers={}) as post_response:
    >>>         resp = await post_response.text()
    """

    def __init__(self, *args, **kwargs):
        self.raise_for_status = kwargs.get("raise_for_status", False)
        super().__init__(*args, **kwargs)

    async def _aget(self, url: str, **kwargs) -> ClientResponse:
        encoded_url, data, headers, kwargs = HTTPSession.prepare(url, kwargs)
        return ClientResponse(encoded_url, (await pyfetch(encoded_url, **kwargs)).js_response)

    async def _apost(self, url: str, **kwargs) -> ClientResponse:
        # https://pyodide.org/en/stable/usage/faq.html
        encoded_url, data, headers, kwargs = HTTPSession.prepare(url, kwargs)
        ret = await pyfetch(encoded_url,
                            method="POST",
                            body=data,
                            credentials="same-origin",
                            **kwargs,
                            )
        return ClientResponse(encoded_url, ret.js_response)

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