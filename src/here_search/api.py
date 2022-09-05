from aiohttp import ClientSession
from json import loads

from .entities import Request, Response, Endpoint
from .util import logger

from typing import Dict, Sequence, Optional, Callable
import os
from getpass import getpass

base_url = {ep: f'https://{eps}.search.hereapi.com/v1/{eps}'
            for ep, eps in {Endpoint.AUTOSUGGEST: 'autosuggest',
                            Endpoint.AUTOSUGGEST_HREF: 'discover',
                            Endpoint.DISCOVER: 'discover',
                            Endpoint.LOOKUP: 'lookup',
                            Endpoint.BROWSE: 'browse',
                            Endpoint.REVGEOCODE: 'revgeocode'
                            }.items()}


class API:
    """
    https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html
    """
    api_key: str
    cache: Dict[str, Response]

    def __init__(self, api_key: str = None, cache: dict = None, url_format_fn: Callable[[str], str] = None):
        self.api_key = api_key or os.environ.get('API_KEY') or getpass(prompt="api key: ")
        self.cache = cache or {}
        self.format_url = url_format_fn or (lambda x: x)

    async def get(self, request: Request, session: ClientSession = None) -> Response:
        """
        Returns from HERE Search backend the response for a specific Request, or from the cache if it has been cached.
        Cache the Response if returned by the HERE Search backend.

        :param session: instance of ClientSession
        :param request: Search Request object
        :return: a Response object
        """
        cache_key = request.key()
        if cache_key in self.cache:
            return self.__uncache(cache_key)

        request.params["apiKey"] = self.api_key
        params = {k: ",".join(v) if isinstance(v, list) else v for k, v in request.params.items()}
        if session:
            async with session.get(request.url, params=params, headers=request.x_headers or {}) as get_response:
                return await self.__get(get_response, request, cache_key)
        else:
            async with ClientSession(raise_for_status=True) as session:
                async with session.get(request.url, params=params, headers=request.x_headers or {}) as get_response:
                    return await self.__get(get_response, request, cache_key)

    def __uncache(self, cache_key):
        actual_url, cached_response = self.cache[cache_key]
        data = cached_response.data.copy()
        response = Response(data=data,
                            x_headers=cached_response.x_headers,
                            req=cached_response.req)
        formatted_msg = self.format_url(actual_url)
        logger.info(f"{formatted_msg} (cached)")
        return response

    async def __get(self, get_response, request, cache_key):
        formatted_msg = self.format_url(get_response.url.human_repr())
        logger.info(formatted_msg)
        x_headers = {"X-Request-Id": get_response.headers["X-Request-Id"],
                     "X-Correlation-ID": get_response.headers["X-Correlation-ID"]}
        response = Response(data=await get_response.json(loads=loads),
                            req=request,
                            x_headers=x_headers)
        self.cache[cache_key] = get_response.url.human_repr(), response
        return response

    async def autosuggest(self, q: str, latitude: float, longitude: float, x_headers: dict = None,
                          session: ClientSession = None, **kwargs) -> Response:
        """
        Calls HERE Search Autosuggest endpoint

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = {"q": q, "at": f'{latitude},{longitude}'}
        params.update(kwargs)
        request = Request(endpoint=Endpoint.AUTOSUGGEST,
                          url=base_url[Endpoint.AUTOSUGGEST],
                          params=params,
                          x_headers=x_headers)
        if session:
            response = await self.get(request, session)
        else:
            async with ClientSession(raise_for_status=True) as session:
                response = await self.get(request, session)
        return response

    async def autosuggest_href(self, href: str, x_headers: dict = None, session: ClientSession = None, **kwargs) -> Response:
        """
        Calls HERE Search Autosuggest href follow-up

        Blindly calls Autosuggest href
        :param session: instance of ClientSession
        :param href: href value returned in Autosuggest categoryQyery/chainQuery results
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        request = Request(endpoint=Endpoint.AUTOSUGGEST_HREF,
                          url=href, params=kwargs, x_headers=x_headers)
        if session:
            response = await self.get(request, session)
        else:
            async with ClientSession(raise_for_status=True) as session:
                response = await self.get(request, session)
        return response

    async def discover(self, q: str, latitude: float, longitude: float, x_headers: dict = None,
                       session: ClientSession = None, **kwargs) -> Response:
        """
        Calls HERE Search Discover endpoint

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = {"q": q, "at": f'{latitude},{longitude}'}
        params.update(kwargs)
        request = Request(endpoint=Endpoint.DISCOVER,
                          url=base_url[Endpoint.DISCOVER],
                          params=params,
                          x_headers=x_headers)
        if session:
            response = await self.get(request, session)
        else:
            async with ClientSession(raise_for_status=True) as session:
                response = await self.get(request, session)
        return response

    async def browse(self,
                     latitude: float, longitude: float,
                     categories: Optional[Sequence[str]] = None,
                     food_types: Optional[Sequence[str]] = None,
                     chains: Optional[Sequence[str]] = None,
                     x_headers: dict = None,
                     session: ClientSession = None, **kwargs) -> Response:
        """
        Calls HERE Search Browse endpoint

        :param session: instance of ClientSession
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param categories: Places category ids for filtering
        :param food_types: Places cuisine ids for filtering
        :param chains: Places chain ids for filtering
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = {"at": f'{latitude},{longitude}'}
        if categories:
            params["categories"] = ",".join(sorted(set(categories or [])))
        if food_types:
            params["foodTypes"] = ",".join(sorted(set(food_types or [])))
        if chains:
            params["chains"] = ",".join(sorted(set(chains or [])))
        params.update(kwargs)
        request = Request(endpoint=Endpoint.BROWSE,
                          url=base_url[Endpoint.BROWSE],
                          params=params,
                          x_headers=x_headers)
        if session:
            response = await self.get(request, session)
        else:
            async with ClientSession(raise_for_status=True) as session:
                response = await self.get(request, session)
        return response

    async def lookup(self, id: str, x_headers: dict = None, session: ClientSession = None, **kwargs) -> Response:
        """
        Calls HERE Search Lookup for a specific id

        :param session: instance of ClientSession
        :param id: location record ID
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = {"id": id}
        params.update(kwargs)
        request = Request(endpoint=Endpoint.LOOKUP,
                          url=base_url[Endpoint.LOOKUP],
                          params=params,
                          x_headers=x_headers)
        if session:
            response = await self.get(request, session)
        else:
            async with ClientSession(raise_for_status=True) as session:
                response = await self.get(request, session)
        return response

    async def reverse_geocode(self, latitude: float, longitude: float, x_headers: dict = None,
                              session: ClientSession = None, **kwargs) -> Response:
        """
        Calls HERE Reverese Geocode for a geo position

        :param session: instance of ClientSession
        :param latitude: input position latitude
        :param longitude: input position longitude
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = {"at": f"{latitude},{longitude}"}
        params.update(kwargs)
        request = Request(endpoint=Endpoint.REVGEOCODE,
                          url=base_url[Endpoint.REVGEOCODE],
                          params=params,
                          x_headers=x_headers)
        if session:
            response = await self.get(request, session)
        else:
            async with ClientSession(raise_for_status=True) as session:
                response = await self.get(request, session)
        return response
