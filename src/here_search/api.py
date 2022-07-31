from aiohttp import ClientSession
from ujson import loads

from .entities import Request, Response, Endpoint
from .util import logger

from collections import namedtuple
from typing import Tuple, Dict, Sequence, Optional
import os, sys
import urllib.parse
from getpass import getpass


base_url = {ep: f'https://{eps}.search.hereapi.com/v1/{eps}'
            for ep, eps in {Endpoint.AUTOSUGGEST: 'autosuggest',
                            Endpoint.AUTOSUGGEST_HREF: 'discover',
                            Endpoint.DISCOVER: 'discover',
                            Endpoint.LOOKUP: 'lookup',
                            Endpoint.BROWSE: 'browse',
                            Endpoint.REVGEOCODE: 'revgeocode',
                            Endpoint.SIGNALS: 'signals'}.items()}


class API:
    """
    https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html
    """
    api_key: str
    options: "APIOptions"
    cache: Dict[tuple, Response]

    def __init__(self, api_key: str=None, options: "APIOptions"=None, cache: dict=None):
        self.api_key = api_key or os.environ.get('API_KEY') or getpass(prompt="api key: ")
        self.options = options or {}
        self.cache = cache or {}

    async def get(self, session: ClientSession, req: Request) -> Response:
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

        req.params["apiKey"] = self.api_key
        params = {k: ",".join(v) if isinstance(v, list) else v for k, v in req.params.items()}
        async with session.get(req.url, params=params, headers=req.x_headers) as get_response:
            endpoint = get_response.url.path.split("/")[-1]
            params = dict(get_response.url.query)
            params.pop("apiKey", None)
            params = urllib.parse.unquote(urllib.parse.urlencode(params))
            log_url = f'<a href="{str(get_response.url)}">/{endpoint}?{params}</a>'
            if req.x_headers and 'X-AS-Session-ID' in req.x_headers:
                logger.info(f"{log_url} | {req.x_headers['X-AS-Session-ID']}")
            else:
                logger.info(log_url)
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
        params = {"q": q, "at": f'{latitude},{longitude}'}
        params.update(self.options.get(Endpoint.AUTOSUGGEST, {}))
        params.update(kwargs)
        return await self.get(session, Request(endpoint=Endpoint.AUTOSUGGEST,
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
        return await self.get(session, Request(endpoint=Endpoint.AUTOSUGGEST_HREF,
                                                url=href, params=kwargs, x_headers=x_headers))

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
        params = {"q": q, "at": f'{latitude},{longitude}'}
        params.update(self.options.get(Endpoint.DISCOVER, {}))
        params.update(kwargs)
        return await self.get(session, Request(endpoint=Endpoint.DISCOVER,
                                                url=base_url[Endpoint.DISCOVER],
                                                params=params,
                                                x_headers=x_headers))

    async def browse(self, session: ClientSession,
                     latitude: float, longitude: float,
                     categories: Optional[Sequence[str]],
                     food_types: Optional[Sequence[str]],
                     chains: Optional[Sequence[str]],
                     x_headers: dict=None,
                     **kwargs) -> Response:
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
            params["categories"] = ",".join(sorted(set(categories)))
        if food_types:
            params["foodTypes"] = ",".join(sorted(set(food_types)))
        if chains:
            params["categories"] = ",".join(sorted(set(chains)))
        params.update(self.options.get(Endpoint.BROWSE, {}))
        params.update(kwargs)
        return await self.get(session, Request(endpoint=Endpoint.BROWSE,
                                               url=base_url[Endpoint.BROWSE],
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
        params = {"id": id}
        params.update(self.options.get(Endpoint.LOOKUP, {}))
        params.update(kwargs)
        return await self.get(session, Request(endpoint=Endpoint.LOOKUP,
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
        params = {"at": f"{latitude},{longitude}"}
        params.update(self.options.get(Endpoint.REVGEOCODE, {}))
        params.update(kwargs)
        return await self.get(session, Request(endpoint=Endpoint.REVGEOCODE,
                                                url=base_url[Endpoint.REVGEOCODE],
                                                params=params,
                                                x_headers=x_headers))

    async def signals(self, session: ClientSession,
                      resource_id: str,
                      correlation_id: str,
                      rank: int,
                      action: str,
                      x_headers: dict=None,
                      **kwargs) -> Response:
        """
        Calls HERE signals endpoint with some user action

        :param session: instance of ClientSession
        :param resource_id: the HERE result id on which the action is performed
        :param rank: the rank of the result in its result list
        :param action: the action performed by the user on the result
        :param x_headers: Optional X-* headers (X-Request-Id, ...)
        :return: a Response object
        """
        data = dict(version=1,
                    resourceId=resource_id,
                    correlationId=correlation_id,
                    rank=rank, action=action)
        data.update(kwargs)

        async with session.post(base_url[Endpoint.SIGNALS],
                                params={"apiKey": self.api_key},
                                data=data,
                                headers=x_headers) as post_response:
            x_headers = {"X-Request-Id": post_response.headers["X-Request-Id"],
                         "X-Correlation-ID": post_response.headers["X-Correlation-ID"]}
            logger.info(f"/signals | {data}")
            response = Response(data={"text": await post_response.text()},
                                req=Request(endpoint=Endpoint.SIGNALS,
                                            url=base_url[Endpoint.SIGNALS],
                                            params=data,
                                            x_headers=x_headers),
                                x_headers=x_headers)

            return response


class Option:
    key: str
    values: Sequence[str]


class FuelPreference(Option):
    types = ("biodiesel", "diesel", "e85", "e10", "cng", "lpg", "lng", "hydrogen", "truck_diesel", "truck_cng", "truck_lpg", "truck_hydrogen")
    types = namedtuple("types", types)(*types)
    endpoints = (Endpoint.AUTOSUGGEST, Endpoint.DISCOVER, Endpoint.BROWSE)

    def __init__(self, *fuel_types):
        assert all(t in FuelPreference.types for t in fuel_types)
        self.key = "fuelStation[fuelTypes]"
        self.values = fuel_types


class TruckClassPreference(Option):
    classes = ("heavy", "medium")
    classes = namedtuple("classes", classes)(*classes)
    endpoints = (Endpoint.AUTOSUGGEST, Endpoint.DISCOVER, Endpoint.BROWSE)

    def __init__(self, *classes):
        assert all(c in TruckClassPreference.classes for c in classes)
        self.key = "fuelStation[minimumTruckClass]"
        self.values = classes


class FuelDetails(Option):
    endpoints = (Endpoint.AUTOSUGGEST, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)

    def __init__(self):
        self.key = "show"
        self.values = ["fuel"]


class TruckDetails(Option):
    endpoints = (Endpoint.AUTOSUGGEST, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)

    def __init__(self):
        self.key = "show"
        self.values = ["truck"]


class TripadvisorDetails(Option):
    endpoints = (Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)

    def __init__(self):
        self.key = "show"
        self.values = ["tripadvisor"]


class APIOptions(dict):
    def __init__(self, options: dict):
        _options = {}
        for endpoint, ep_options in options.items():
            for option in ep_options:
                assert endpoint in option.endpoints, f"Option {option.__class__.__name__} illegal for endpoint {endpoint}"
                _options.setdefault(endpoint, {}).setdefault(option.key, []).extend(option.values)
        super().__init__(_options)


fuelDetails = FuelDetails()
truckDetails = TruckDetails()
tripadvisorDetails = TripadvisorDetails()
