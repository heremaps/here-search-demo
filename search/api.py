from aiohttp import ClientSession
import nest_asyncio
from ujson import loads

from dataclasses import dataclass
import asyncio
from collections import OrderedDict
from typing import Mapping
import os
from dataclasses import dataclass
from enum import IntEnum, Enum, auto


class Endpoint(IntEnum):
    AUTOSUGGEST = auto()
    AUTOSUGGEST_HREF = auto()
    DISCOVER = auto()
    LOOKUP = auto()
    REVGEOCODE = auto()

base_url = {ep:f'https://{eps}.search.hereapi.com/v1/{eps}'
            for ep, eps in {Endpoint.AUTOSUGGEST:'autosuggest',
                            Endpoint.AUTOSUGGEST_HREF:'discover',
                            Endpoint.DISCOVER:'discover',
                            Endpoint.LOOKUP:'lookup',
                            Endpoint.REVGEOCODE:'revgeocode'}.items()}
@dataclass
class Request:
    endpoint: Endpoint
    url: str
    params: dict
    x_headers: dict

    def key(self):
        return (self.endpoint, tuple(self.params.items()))

@dataclass
class Response:
    req: Request
    data: dict
    x_headers: dict

@dataclass
class ResponseItem:
    resp: Response=None
    data: dict=None
    rank: int=None
    
    
class API:
    api_key: str
    cache: Mapping[str, str]

    def __init__(self, api_key: str=None, cache: Mapping[str, str]=None):
        self.api_key = api_key or os.environ.get('API_KEY')
        self.cache = cache or {}

    async def uncache_or_get(self, session: ClientSession, req: Request) -> Response:
        cache_key = req.key()
        if cache_key in self.cache:
            return self.cache[cache_key]

        async with session.get(req.url, params=req.params, headers=req.x_headers) as response:
            x_headers = {"X-Request-Id": response.headers["X-Request-Id"],
                         "X-Correlation-ID": response.headers["X-Correlation-ID"]}
            result = Response(data=await response.json(loads=loads),
                              req=req,
                              x_headers = {"X-Request-Id": response.headers["X-Request-Id"],
                                           "X-Correlation-ID": response.headers["X-Correlation-ID"]})
            self.cache[cache_key] = result
            return result

    async def autosuggest(self, session: ClientSession,
                          q: str, latitude: float, longitude: float,
                          x_headers: dict=None,
                          **kwargs) -> Response:
        """
        Calls HERE Search Autosuggest endpoint
        https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :return: a tuple made of the input query text and the response dictionary
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
        Blindly calls Autosuggest href
        :param session:
        :param href:
        :param params:
        :return:
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
        https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :return: a response dictionary
        """
        params = OrderedDict(q=q, at=f'{latitude},{longitude}', apiKey=self.api_key)
        params.update(params)
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
        :param session:
        :param id:
        :param params:
        :return:
        """
        params = OrderedDict(id=id, apiKey=self.api_key)
        params.update(params)
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
        :param session:
        :param latitude:
        :param longitude:
        :param language:
        :param params:
        :return:
        """
        params = OrderedDict(at=f"{latitude},{longitude}", apiKey=self.api_key)
        params.update(params)
        return await self.uncache_or_get(session, Request(endpoint=Endpoint.REVGEOCODE,
                                                          url=base_url[Endpoint.REVGEOCODE],
                                                          params=params,
                                                          x_headers=x_headers))
    