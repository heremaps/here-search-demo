from aiohttp import ClientSession
from json import loads

from .entities import (Request, Response, Endpoint, ResponseItem, PlaceTaxonomyItem, SearchContext, AutosuggestConfig,
                       EndpointConfig, DiscoverConfig, BrowseConfig, LookupConfig, NoConfig)
from .util import logger

from typing import Dict, Sequence, Optional, Callable, Tuple, Union
import os
from getpass import getpass
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
import asyncio


base_url = {
    ep: f"https://{eps}.search.hereapi.com/v1/{eps}"
    for ep, eps in {
        Endpoint.AUTOSUGGEST: "autosuggest",
        Endpoint.AUTOSUGGEST_HREF: "discover",
        Endpoint.DISCOVER: "discover",
        Endpoint.LOOKUP: "lookup",
        Endpoint.BROWSE: "browse",
        Endpoint.REVGEOCODE: "revgeocode",
    }.items()
}


class API:
    """
    https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html
    """

    api_key: str
    cache: Dict[str, Tuple[str, Response]]

    def __init__(self, api_key: str = None, cache: dict = None, url_format_fn: Callable[[str], str] = None):
        self.api_key = api_key or os.environ.get("API_KEY") or getpass(prompt="api key: ")
        self.cache = cache or {}
        self.format_url = url_format_fn or (lambda x: x)

    async def uncache_or_get(self, request: Request, session: ClientSession) -> Response:
        """
        Returns from HERE Search backend the response for a specific Request, or from the cache if it has been cached.
        Cache the Response if returned by the HERE Search backend.

        :param session: instance of ClientSession
        :param request: Search Request object
        :return: a Response object
        """
        cache_key = request.key
        if cache_key in self.cache:
            return self.__uncache(cache_key)

        request.params["apiKey"] = self.api_key
        params = {k: ",".join(v) if isinstance(v, list) else v for k, v in request.params.items()}
        async with session.get(request.url, params=params, headers=request.x_headers or {}) as get_response:
            return await self.restrieve_response(get_response, request, cache_key)

    def __uncache(self, cache_key):
        actual_url, cached_response = self.cache[cache_key]
        data = cached_response.data.copy()
        response = Response(data=data, x_headers=cached_response.x_headers, req=cached_response.req)
        formatted_msg = self.format_url(actual_url)
        logger.info(f"{formatted_msg} (cached)")
        return response

    async def restrieve_response(self, get_response, request, cache_key):
        human_url = get_response.url.human_repr()
        formatted_msg = self.format_url(human_url)
        logger.info(formatted_msg)
        x_headers = {
            "X-Request-Id": get_response.headers["X-Request-Id"],
            "X-Correlation-ID": get_response.headers["X-Correlation-ID"],
        }
        payload = await get_response.json(loads=loads)
        response = Response(data=payload, req=request, x_headers=x_headers)
        self.cache[cache_key] = human_url, response
        return response

    async def autosuggest(
        self, q: str, latitude: float, longitude: float, x_headers: dict = None, session: ClientSession = None, **kwargs
    ) -> Response:
        """
        Calls HERE Search Autosuggest endpoint

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = {"q": q.strip(), "at": f"{latitude},{longitude}"}
        params.update(kwargs)
        request = Request(
            endpoint=Endpoint.AUTOSUGGEST, url=base_url[Endpoint.AUTOSUGGEST], params=params, x_headers=x_headers
        )
        return await self.get(request, session)

    async def get(self, request, session: ClientSession = None):
        if session:
            response = await self.uncache_or_get(request, session)
        else:
            async with ClientSession(raise_for_status=True) as session:
                response = await self.uncache_or_get(request, session)
        return response

    async def autosuggest_href(
        self, href: str, x_headers: dict = None, session: ClientSession = None, **kwargs
    ) -> Response:
        """
        Calls HERE Search Autosuggest href follow-up

        Blindly calls Autosuggest href
        :param session: instance of ClientSession
        :param href: href value returned in Autosuggest categoryQyery/chainQuery results
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        request = Request(endpoint=Endpoint.AUTOSUGGEST_HREF, url=href, params=kwargs, x_headers=x_headers)
        return await self.get(request, session)

    async def discover(
        self, q: str, latitude: float, longitude: float, x_headers: dict = None, session: ClientSession = None, **kwargs
    ) -> Response:
        """
        Calls HERE Search Discover endpoint

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :return: a Response object
        """
        params = {"q": q.strip(), "at": f"{latitude},{longitude}"}
        params.update(kwargs)
        request = Request(
            endpoint=Endpoint.DISCOVER, url=base_url[Endpoint.DISCOVER], params=params, x_headers=x_headers
        )
        return await self.get(request, session)

    async def browse(
        self,
        latitude: float,
        longitude: float,
        categories: Optional[Sequence[str]] = None,
        food_types: Optional[Sequence[str]] = None,
        chains: Optional[Sequence[str]] = None,
        x_headers: dict = None,
        session: ClientSession = None,
        **kwargs,
    ) -> Response:
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
        params = {"at": f"{latitude},{longitude}"}
        if categories:
            params["categories"] = ",".join(sorted(set(categories or [])))
        if food_types:
            params["foodTypes"] = ",".join(sorted(set(food_types or [])))
        if chains:
            params["chains"] = ",".join(sorted(set(chains or [])))
        params.update(kwargs)
        request = Request(endpoint=Endpoint.BROWSE, url=base_url[Endpoint.BROWSE], params=params, x_headers=x_headers)
        return await self.get(request, session)

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
        request = Request(endpoint=Endpoint.LOOKUP, url=base_url[Endpoint.LOOKUP], params=params, x_headers=x_headers)
        return await self.get(request, session)

    async def reverse_geocode(
        self, latitude: float, longitude: float, x_headers: dict = None, session: ClientSession = None, **kwargs
    ) -> Response:
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
        request = Request(
            endpoint=Endpoint.REVGEOCODE, url=base_url[Endpoint.REVGEOCODE], params=params, x_headers=x_headers
        )
        return await self.get(request, session)


@dataclass
class SearchIntent:
    materialization: Union[None, str, PlaceTaxonomyItem, ResponseItem]


@dataclass
class FormulatedIntent(SearchIntent):
    pass


@dataclass
class NoIntent(SearchIntent):
    materialization: Optional[None] = None


class UnsupportedIntentMaterialization(Exception):
    pass

@dataclass
class SearchEvent(metaclass=ABCMeta):
    context: SearchContext

    @abstractmethod
    async def get_response(self, api: API, config: EndpointConfig, session: ClientSession) -> Response:
        raise NotImplementedError()


@dataclass
class PartialTextSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey key strokes in the one box search Text form to an App waiting loop
    """
    query_text: str

    async def get_response(self, api: API, config: AutosuggestConfig, session: ClientSession) -> Response:
        return await asyncio.ensure_future(
            api.autosuggest(
                self.query_text,
                self.context.latitude,
                self.context.longitude,
                x_headers=None,
                session=session,
                lang=self.context.language,
                limit=config.limit,
                termsLimit=config.terms_limit
            )
        )


@dataclass
class TextSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey text submissions from the one box search Text form to an App waiting loop
    """
    query_text: str

    async def get_response(self, api: API, config: DiscoverConfig, session: ClientSession) -> Response:
        return await asyncio.ensure_future(
            api.discover(
                self.query_text,
                self.context.latitude,
                self.context.longitude,
                x_headers=None,
                session=session,
                lang=self.context.language,
                limit=config.limit
            )
        )


@dataclass
class TaxonomySearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey taxonomy selections to an App waiting loop
    """
    item: PlaceTaxonomyItem

    async def get_response(self, api: API, config: BrowseConfig, session: ClientSession) -> Response:
        return await asyncio.ensure_future(
            api.browse(
                self.context.latitude,
                self.context.longitude,
                x_headers=None,
                session=session,
                lang=self.context.language,
                limit=config.limit,
                **self.item.mapping
            )
        )


@dataclass
class DetailsSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey location response items selections to an App waiting loop
    """
    item: ResponseItem

    async def get_response(self, api: API, config: LookupConfig, session: ClientSession) -> Response:
        return await asyncio.ensure_future(
            api.lookup(
                self.item.data["id"],
                x_headers=None,
                lang=self.context.language,
                session=session
            )
        )


@dataclass
class FollowUpSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey query response items selections to an App waiting loop
    """
    item: ResponseItem

    async def get_response(self, api: API, config: DiscoverConfig, session: ClientSession) -> Response:
        return await asyncio.ensure_future(
            api.autosuggest_href(
                self.item.data["href"],
                x_headers=None,
                limit=config.limit,
                session=session
            )
        )


@dataclass
class EmptySearchEvent(SearchEvent):
    context: Optional[None] = None

    async def get_response(self, api: API, config: LookupConfig, session: ClientSession) -> Response:
        pass


class UnsupportedSearchEvent(Exception):
    pass
