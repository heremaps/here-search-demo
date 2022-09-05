from aiohttp import ClientSession
from json import loads

from .entities import Request, Response, Endpoint
from .util import logger

from typing import Dict, Sequence, Optional
import os
import urllib.parse
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

    def __init__(self, api_key: str = None, cache: dict = None):
        self.api_key = api_key or os.environ.get('API_KEY') or getpass(prompt="api key: ")
        self.cache = cache or {}

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
            return await self.__uncache(cache_key, request)

        request.params["apiKey"] = self.api_key
        params = {k: ",".join(v) if isinstance(v, list) else v for k, v in request.params.items()}
        if session:
            async with session.get(request.url, params=params, headers=request.x_headers or {}) as get_response:
                return await self.__get(get_response, request, cache_key)
        else:
            async with ClientSession(raise_for_status=True) as session:
                async with session.get(request.url, params=params, headers=request.x_headers or {}) as get_response:
                    return await self.__get(get_response, request, cache_key)

    async def __uncache(self, cache_key, request):
        cached_response = self.cache[cache_key]
        data = cached_response.data.copy()
        response = Response(data=data,
                            x_headers=cached_response.x_headers,
                            req=cached_response.req)
        endpoint_str = response.req.url.split("/")[-1]
        params = {k: (",".join(v) if isinstance(v, list) else v) for k, v in response.req.params.items()}
        params.pop("apiKey", None)
        params_str = urllib.parse.unquote(urllib.parse.urlencode(params))
        log_msg = await self._get_log_msg(endpoint_str, response.req.url, params_str, request.x_headers)
        logger.info(f"{log_msg} | (cached)")
        return response

    async def __get(self, get_response, request, cache_key):
        endpoint_str = get_response.url.path.split("/")[-1]
        params = dict(get_response.url.query)
        params.pop("apiKey", None)
        params_str = urllib.parse.unquote(urllib.parse.urlencode(params))
        log_msg = await self._get_log_msg(endpoint_str, get_response.url.human_repr(), params_str, request.x_headers)
        logger.info(log_msg)
        x_headers = {"X-Request-Id": get_response.headers["X-Request-Id"],
                     "X-Correlation-ID": get_response.headers["X-Correlation-ID"]}
        response = Response(data=await get_response.json(loads=loads),
                            req=request,
                            x_headers=x_headers)
        self.cache[cache_key] = response
        return response

    async def _get_log_msg(self, endpoint_str: str, url: str, params_str: str, x_headers: dict=None):
        log_msg = f'<a href="{url}">/{endpoint_str}?{params_str}</a>'
        if x_headers and 'X-AS-Session-ID' in x_headers:
            log_msg = f"{log_msg} | {x_headers['X-AS-Session-ID']}"
        return log_msg

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
