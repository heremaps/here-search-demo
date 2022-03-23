from aiohttp import ClientSession
from ujson import loads

from collections import OrderedDict
from typing import Tuple, Dict
import os
from dataclasses import dataclass
from enum import IntEnum, auto
from getpass import getpass


class Endpoint(IntEnum):
    AUTOSUGGEST = auto()
    AUTOSUGGEST_HREF = auto()
    DISCOVER = auto()
    LOOKUP = auto()
    REVGEOCODE = auto()
    SIGNALS = auto()


base_url = {ep: f'https://{eps}.search.hereapi.com/v1/{eps}'
            for ep, eps in {Endpoint.AUTOSUGGEST:'autosuggest',
                            Endpoint.AUTOSUGGEST_HREF:'discover',
                            Endpoint.DISCOVER:'discover',
                            Endpoint.LOOKUP:'lookup',
                            Endpoint.REVGEOCODE:'revgeocode',
                            Endpoint.SIGNALS:'signals'}.items()}

@dataclass
class Request:
    endpoint: Endpoint=None
    url: str=None
    params: Dict[str, str]=None
    x_headers: dict=None
    post: bool=False

    def key(self) -> Tuple[Endpoint, Tuple[str]]:
        return self.endpoint, tuple(self.params.items())


@dataclass
class Response:
    req: Request=None
    data: dict=None
    x_headers: dict=None


@dataclass
class ResponseItem:
    resp: Response=None
    data: dict=None
    rank: int=None
    
    
class API:
    """
    https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html
    """
    api_key: str
    cache: Dict[tuple, Response]

    def __init__(self, api_key: str=None, cache: dict=None):
        self.api_key = api_key or os.environ.get('API_KEY') or getpass(prompt="api key: ")
        self.cache = cache or {}

    async def uncache_or_get(self, session: ClientSession, req: Request) -> Response:
        """
        Returns from HERE Search backend the response for a specific Request, or from the cache if it has been cached.
        Cache the Response if returned by the HERE Search backend.

        :param session: instance of ClientSession
        :param req: Search Request object
        :return: a Response object
        """
        cache_key = req.key()
        if cache_key in self.cache:
            cached_response = self.cache[cache_key]
            data = cached_response.data.copy()
            response = Response(data=data,
                                x_headers=cached_response.x_headers,
                                req=cached_response.req)
            return response

        async with session.get(req.url, params=req.params, headers=req.x_headers) as get_response:
            x_headers = {"X-Request-Id": get_response.headers["X-Request-Id"],
                         "X-Correlation-ID": get_response.headers["X-Correlation-ID"]}
            response = Response(data=await get_response.json(loads=loads),
                              req=req,
                              x_headers=x_headers)
            self.cache[cache_key] = response
            return response

    async def autosuggest(self, session: ClientSession,
                          q: str, latitude: float, longitude: float,
                          x_headers: dict=None,
                          **kwargs) -> Response:
        """
        Calls HERE Search Autosuggest endpoint

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = OrderedDict(q=q, at=f'{latitude},{longitude}', apiKey=self.api_key)
        params.update(kwargs)
        return await self.uncache_or_get(session, Request(endpoint=Endpoint.AUTOSUGGEST,
                                                          url=base_url[Endpoint.AUTOSUGGEST],
                                                          params=params,
                                                          x_headers=x_headers))

    async def autosuggest_href(self, session: ClientSession,
                               href: str,
                               x_headers: dict=None,
                               **kwargs) -> Response:
        """
        Calls HERE Search Autosuggest href follow-up

        Blindly calls Autosuggest href
        :param session: instance of ClientSession
        :param href: href value returned in Autosuggest categoryQyery/chainQuery results
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = {'apiKey': self.api_key}
        params.update(kwargs)
        return await self.uncache_or_get(session, Request(endpoint=Endpoint.AUTOSUGGEST_HREF,
                                                          url=href, params=params, x_headers=x_headers))

    async def discover(self, session: ClientSession,
                       q: str, latitude: float, longitude: float,
                       x_headers: dict=None,
                       **kwargs) -> Response:
        """
        Calls HERE Search Discover endpoint

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = OrderedDict(q=q, at=f'{latitude},{longitude}', apiKey=self.api_key)
        params.update(kwargs)
        return await self.uncache_or_get(session, Request(endpoint=Endpoint.DISCOVER,
                                                          url=base_url[Endpoint.DISCOVER],
                                                          params=params,
                                                          x_headers=x_headers))

    async def lookup(self, session: ClientSession,
                     id: str,
                     x_headers: dict=None,
                     **kwargs) -> Response:
        """
        Calls HERE Search Lookup for a specific id

        :param session: instance of ClientSession
        :param id: location record ID
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = OrderedDict(id=id, apiKey=self.api_key)
        params.update(kwargs)
        return await self.uncache_or_get(session, Request(endpoint=Endpoint.LOOKUP,
                                                          url=base_url[Endpoint.LOOKUP],
                                                          params=params,
                                                          x_headers=x_headers))

    async def reverse_geocode(self, session: ClientSession,
                              latitude: float, longitude: float,
                              x_headers: dict=None,
                              **kwargs) -> Response:
        """
        Calls HERE Reverese Geocode for a geo position

        :param session: instance of ClientSession
        :param latitude: input position latitude
        :param longitude: input position longitude
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = OrderedDict(at=f"{latitude},{longitude}", apiKey=self.api_key)
        params.update(kwargs)
        return await self.uncache_or_get(session, Request(endpoint=Endpoint.REVGEOCODE,
                                                          url=base_url[Endpoint.REVGEOCODE],
                                                          params=params,
                                                          x_headers=x_headers))

    async def signals(self, session: ClientSession,
                      resource_id: str,
                      correlation_id: str,
                      rank: int,
                      action: str,
                      x_headers: dict=None,
                      **kwargs) -> None:
        """
        Calls HERE signals endpoint with some user action

        :param session: instance of ClientSession
        :param resource_id: the HERE result id on which the action is performed
        :param rank: the rank of the result in its result list
        :param action: the action performed by the user on the result
        :param x_headers: Optional X-* headers (X-Request-Id, ...)
        :return: a Response object
        """
        data = OrderedDict(version=1,
                           resourceId=resource_id,
                           correlationId=correlation_id,
                           rank=rank, action=action)
        data.update(kwargs)
        async with session.post(base_url[Endpoint.SIGNALS],
                                params=OrderedDict(apiKey=self.api_key),
                                data=data,
                                headers=x_headers) as response:
            await response.text()
