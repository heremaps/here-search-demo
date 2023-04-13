###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from here_search.demo.http import HTTPSession
from here_search.demo.entity.request import Request, Response
from here_search.demo.entity.endpoint import Endpoint
from here_search.demo.util import logger
from here_search.demo.api_options import APIOptions

from typing import Dict, Sequence, Optional, Callable, Tuple, Mapping
from urllib.parse import urlparse, parse_qsl, urlunparse
import os


def url_builder(ep_template: str):
    return {
        ep_enum: ep_template.format(endpoint=endpoint)
        for ep_enum, endpoint in {
            Endpoint.AUTOSUGGEST: "autosuggest",
            Endpoint.AUTOSUGGEST_HREF: "discover",
            Endpoint.DISCOVER: "discover",
            Endpoint.LOOKUP: "lookup",
            Endpoint.BROWSE: "browse",
            Endpoint.REVGEOCODE: "revgeocode",
        }.items()
    }


base_url = url_builder("https://{endpoint}.search.hereapi.com/v1/{endpoint}")


class API:
    """
    https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html
    """
    api_key: str
    cache: Dict[str, Response]
    options: APIOptions

    BASE_URL = base_url

    def __init__(
            self,
            api_key: str = None,
            cache: dict = None,
            url_format_fn: Callable[[str], str] = None,
            options: APIOptions = None
    ):
        self.api_key = api_key or os.environ.get("API_KEY")
        self.cache = cache or {}
        self.format_url = url_format_fn or (lambda x: x)
        self.options = options or {}

    async def get(self, request: Request, session: HTTPSession) -> Response:
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

        params = {
            k: ",".join(v) if isinstance(v, list) else v
            for k, v in request.params.items()
        }
        params["apiKey"] = self.api_key
        human_url, payload, headers = await self.do_get(request.url, params, request.x_headers, session)

        formatted_msg = self.format_url(human_url)
        self.do_log(formatted_msg)

        x_headers = {
            "X-Request-Id": headers.get("X-Request-Id"),
            "X-Correlation-ID": headers.get("X-Correlation-ID"),
        }
        response = Response(data=payload, req=request, x_headers=x_headers)

        self.cache[cache_key] = human_url, response  # Not a pure function...
        return response

    async def do_get(self, url: str, params: dict, headers: dict, session: HTTPSession) -> Tuple[
        str, dict, Mapping]:  # pragma: no cover
        # I/O coupling isolation
        headers = headers or {}
        # headers.update({"Access-Control-Allow-Headers": "Accept"})
        async with session.get(
                url, params=params, headers=headers or {}
        ) as get_response:
            payload = await get_response.json()
            human_url = get_response.url.human_repr()
            headers = get_response.headers
        return human_url, payload, headers

    def do_log(self, msg) -> None:
        logger.info(msg)

    def __uncache(self, cache_key):
        actual_url, cached_response = self.cache[cache_key]
        data = cached_response.data.copy()
        response = Response(
            data=data, x_headers=cached_response.x_headers, req=cached_response.req
        )
        formatted_msg = self.format_url(actual_url)
        logger.info(f"{formatted_msg} (cached)")
        return response

    async def autosuggest(
            self,
            q: str,
            latitude: float,
            longitude: float,
            session: HTTPSession,
            x_headers: dict = None,
            **kwargs,
    ) -> Response:
        """
        Calls HERE Search Autosuggest endpoint

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :param: kwargs: additional request URL parameters
        :return: a Response object
        """
        params = self.options.get(Endpoint.AUTOSUGGEST, {}).copy()
        params.update(q=q, at=f'{latitude},{longitude}')
        params.update(kwargs)
        request = Request(
            endpoint=Endpoint.AUTOSUGGEST,
            url=type(self).BASE_URL[Endpoint.AUTOSUGGEST],
            params=params,
            x_headers=x_headers,
        )
        return await self.get(request, session)

    async def autosuggest_href(
            self,
            href: str,
            session: HTTPSession,
            x_headers: dict = None,
            **kwargs
    ) -> Response:
        """
        Calls HERE Search Autosuggest href follow-up

        Blindly calls Autosuggest href
        :param session: instance of HTTPSession
        :param href: href value returned in Autosuggest categoryQyery/chainQuery results
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :param: kwargs: additional request URL parameters
        :return: a Response object
        """

        href_details = urlparse(href)
        params = parse_qsl(href_details.query)

        request = Request(
            endpoint=Endpoint.AUTOSUGGEST_HREF,
            url=urlunparse(href_details._replace(query='')),
            params=dict(params),
            x_headers=x_headers,
        )
        return await self.get(request, session)

    async def discover(
            self,
            q: str,
            latitude: float,
            longitude: float,
            session: HTTPSession,
            x_headers: dict = None,
            **kwargs,
    ) -> Response:
        """
        Calls HERE Search Discover endpoint

        :param session: instance of HTTPSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :param: kwargs: additional request URL parameters
        :return: a Response object
        """
        params = self.options.get(Endpoint.DISCOVER, {}).copy()
        params.update(q=q, at=f'{latitude},{longitude}')
        params.update(kwargs)
        request = Request(
            endpoint=Endpoint.DISCOVER,
            url=type(self).BASE_URL[Endpoint.DISCOVER],
            params=params,
            x_headers=x_headers,
        )
        return await self.get(request, session)

    async def browse(
            self,
            latitude: float,
            longitude: float,
            session: HTTPSession,
            categories: Optional[Sequence[str]] = None,
            food_types: Optional[Sequence[str]] = None,
            chains: Optional[Sequence[str]] = None,
            x_headers: dict = None,
            **kwargs,
    ) -> Response:
        """
        Calls HERE Search Browse endpoint

        :param session: instance of HTTPSession
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param categories: Places category ids for filtering
        :param food_types: Places cuisine ids for filtering
        :param chains: Places chain ids for filtering
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :param: kwargs: additional request URL parameters
        :return: a Response object
        """
        params = self.options.get(Endpoint.BROWSE, {}).copy()
        _params = {"at": f"{latitude},{longitude}"}
        if categories:
            _params["categories"] = ",".join(sorted(set(categories or [])))
        if food_types:
            _params["foodTypes"] = ",".join(sorted(set(food_types or [])))
        if chains:
            _params["chains"] = ",".join(sorted(set(chains or [])))
        params.update(_params)
        params.update(kwargs)
        request = Request(
            endpoint=Endpoint.BROWSE,
            url=type(self).BASE_URL[Endpoint.BROWSE],
            params=params,
            x_headers=x_headers,
        )
        return await self.get(request, session)

    async def lookup(
            self,
            id: str,
            session: HTTPSession,
            x_headers: dict = None,
            **kwargs) -> Response:
        """
        Calls HERE Search Lookup for a specific id

        :param session: instance of HTTPSession
        :param id: location record ID
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :param: kwargs: additional request URL parameters
        :return: a Response object
        """
        params = self.options.get(Endpoint.LOOKUP, {}).copy()
        params.update(id=id)
        params.update(kwargs)
        request = Request(
            endpoint=Endpoint.LOOKUP,
            url=type(self).BASE_URL[Endpoint.LOOKUP],
            params=params,
            x_headers=x_headers,
        )
        return await self.get(request, session)

    async def reverse_geocode(
            self,
            latitude: float,
            longitude: float,
            session: HTTPSession,
            x_headers: dict = None,
            **kwargs
    ) -> Response:
        """
        Calls HERE Reverse Geocode for a geo position

        :param session: instance of HTTPSession
        :param latitude: input position latitude
        :param longitude: input position longitude
        :param x_headers: Optional X-* headers (X-Request-Id, X-AS-Session-ID, ...)
        :param: kwargs: additional request URL parameters
        :return: a Response object
        """
        params = self.options.get(Endpoint.REVGEOCODE, {}).copy()
        params.update(at=f'{latitude},{longitude}')
        params.update(kwargs)
        request = Request(
            endpoint=Endpoint.REVGEOCODE,
            url=type(self).BASE_URL[Endpoint.REVGEOCODE],
            params=params,
            x_headers=x_headers,
        )
        return await self.get(request, session)
