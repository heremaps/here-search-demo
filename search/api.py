from aiohttp import ClientSession
import nest_asyncio
from ujson import loads

from dataclasses import dataclass
import asyncio
from collections import OrderedDict
from typing import Mapping
import os


class API:
    api_key: str
    cache: Mapping[str, str]

    domain = 'search.hereapi.com'
    autosuggest_url = f'https://autosuggest.{domain}/v1/autosuggest'
    discover_url = f'https://discover.{domain}/v1/discover'
    lookup_url = f'https://lookup.{domain}/v1/lookup'
    revgeocode_url = f'https://revgeocode.{domain}/v1/revgeocode'

    def __init__(self, api_key: str=None, cache: Mapping[str, str]=None):
        self.api_key = api_key or os.environ.get('API_KEY')
        self.cache = cache or {}

    async def uncache_or_get(self, session: ClientSession, url: str, params: OrderedDict) -> dict:
        cache_key = (url, tuple(params.items()))
        if cache_key in self.cache:
            return self.cache[cache_key]

        async with session.get(url, params=params) as response:
            result = await response.json(loads=loads)
            result["_url"] =url
            result["_params"] = params
            self.cache[cache_key] = result
            return result

    async def autosuggest(self, session: ClientSession,
                          q: str, latitude: float, longitude: float,
                          **params) -> dict:
        """
        Calls HERE Search Autosuggest endpoint
        https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :return: a tuple made of the input query text and the response dictionary
        """
        _params = OrderedDict(q=q, at=f'{latitude},{longitude}')
        _params.update(params)
        _params['apiKey'] = self.api_key
        return await self.uncache_or_get(session, self.__class__.autosuggest_url, _params)

    async def autosuggest_href(self, session: ClientSession, href: str, **params) -> dict:
        """
        Blindly calls Autosuggest href
        :param session:
        :param href:
        :param params:
        :return:
        """
        _params.update(params)
        _params['apiKey'] = self.api_key
        return await self.uncache_or_get(session, href, _params)

    async def discover(self, session: ClientSession,
                       q: str, latitude: float, longitude: float,
                       **params) -> dict:
        """
        Calls HERE Search Discover endpoint
        https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :return: a response dictionary
        """
        _params = OrderedDict(q=q, at=f'{latitude},{longitude}')
        _params.update(params)
        _params['apiKey'] = self.api_key
        return await self.uncache_or_get(session, self.__class__.discover_url, _params)

    async def lookup(self, session: ClientSession, id: str, **params) -> dict:
        """
        Calls HERE Search Lookup for a specific id
        :param session:
        :param id:
        :param params:
        :return:
        """
        _params = OrderedDict(id=id)
        _params.update(params)
        _params['apiKey'] = self.api_key
        return await self.uncache_or_get(session, self.__class__.lookup_url, _params)

    async def reverse_geocode(self, session: ClientSession, latitude: float, longitude: float, **params) -> dict:
        """
        Calls HERE Reverese Geocode for a geo position
        :param session:
        :param latitude:
        :param longitude:
        :param language:
        :param params:
        :return:
        """
        _params = OrderedDict(at=f"{latitude},{longitude}")
        _params.update(params)
        _params['apiKey'] = self.api_key
        return await self.uncache_or_get(session, self.__class__.revgeocode_url, _params)