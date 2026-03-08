###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import json
import os
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal, cast
from urllib.parse import parse_qsl, urlparse, urlunparse

from here_search_demo.api_options import APIOptions
from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.request import Request
from here_search_demo.entity.response import Response
from here_search_demo.entity.response_data import ResponseData, make_response
from here_search_demo.http import HTTPSession

import orjson
from yarl import URL


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
    cache: dict[str, tuple[str, Response, str]]
    options: dict
    lookup_has_more_details: bool
    raise_for_status: bool

    BASE_URL = base_url
    CONFIG_FILES = ["demo-config.json", ".demo-config.json"]
    CONFIG_FILE_PATHS = [
        Path("/drive"),  # Jupyterlite default root directory for artifacts
        Path.cwd(),  # Current working directory, to allow config file next to notebooks
        Path(""),  # Current working directory (".")
        Path.home(),  # User home directory
    ]
    if Path.cwd().parts[-1] == "notebooks":
        CONFIG_FILE_PATHS.append(Path.cwd().parents[1])

    def __init__(
        self,
        api_key: str = None,
        cache: dict | None = None,
        raise_for_status: bool = True,
        options: APIOptions | None = None,
        log_fn: Callable[[str, bool | None, list | None], None] | None = None,
        url_format_fn: Callable[[str], str] | None = None,
    ):
        """
        Creates a HERE search API instance.
        :param api_key: your HERE API key
        :param cache: a Cache object supporting the MutableMapping protocol. By default, set to a dict
        :param raise_for_status: set to True to raise HTTPResponseError if HTTP status code is not 200
        :param options: a set of APIOptions objects
        :param log_fn: optional logging callback, e.g. ``TableLogWidget.log``
        :param url_format_fn: optional URL formatting callback used for caching formatted URLs,
                              e.g. ``TableLogWidget.url_to_md_link``; defaults to identity
        """
        if api_key is not None:
            self.api_key = api_key
        elif os.environ.get("API_KEY") is not None:
            self.api_key = os.environ["API_KEY"]
        else:
            self.api_key = self._load_config()["apiKey"]

        self.cache = cache or {}
        self.raise_for_status = raise_for_status
        self.log_fn: Callable[[str, bool | None, list | None], None] | None = log_fn
        self.url_format_fn: Callable[[str], str] = url_format_fn or (lambda u: u)
        if options:
            self.options = options.endpoint
            self.lookup_has_more_details = options.lookup_has_more_details
        else:
            self.options = {}
            self.lookup_has_more_details = False

    @classmethod
    def _load_config(cls) -> dict:
        for config_dir in cls.CONFIG_FILE_PATHS:
            for config_file in cls.CONFIG_FILES:
                config_path = config_dir / config_file
                if config_path.exists():
                    with config_path.open("r") as f:
                        config = json.loads(f.read())
                        return config
        raise FileNotFoundError("No configuration file found in expected locations.")

    async def send(self, session: HTTPSession, method: Literal["GET", "POST"], request: Request) -> Response:
        """Returns from HERE Search backend the response for a specific Request, or from the cache if it has been cached.
        Cache the Response if returned by the HERE Search backend.

        :param session: instance of ClientSession
        :param request: Search Request object
        :return: a Response object
        """
        cache_key = request.key
        if cache_key in self.cache:
            return self.__uncache(cache_key)

        params = {k: ",".join(v) if isinstance(v, list) else v for k, v in request.params.items()}
        params["apiKey"] = self.api_key

        url, payload, headers = await self.do_send(
            session, method, request.url, params, request.data, request.x_headers
        )
        formatted_url = self.url_format_fn(url)
        x_headers = self.get_x_headers(headers)
        self.do_log(formatted_url, formatted=True)

        # Preserve full response headers in Response.x_headers so callers/tests
        # can access all values (including X-* headers) directly.
        immutable_payload = make_response(cast(ResponseData, payload)) if isinstance(payload, dict) else payload
        response = Response(data=immutable_payload, req=request, x_headers=x_headers)

        self.cache[cache_key] = (url, response, formatted_url)
        return response

    def get_x_headers(self, headers: Mapping[str, str]) -> dict:
        """Extract X-* headers from a full headers dict."""
        return {k: v for k, v in headers.items() if k.lower().startswith("x-")}

    async def do_send(
        self,
        session: HTTPSession,
        method: Literal["GET", "POST"],
        url: str,
        params: dict,
        data: str | None,
        headers: dict,
    ) -> tuple[str | URL, dict, Mapping[str, str]]:  # pragma: no cover
        headers = headers or {}
        async with session.request(method, url, params=params, data=data, headers=headers or {}) as get_response:
            headers: Mapping[str, str] = get_response.headers
            text = await get_response.text()
            self.raise_for_status and get_response.raise_for_status()
            payload = orjson.loads(text)
        return get_response.url, payload, headers

    def do_log(self, url: str, formatted: bool | None = None, extra_columns: list | None = None) -> None:
        """Send a log message to the configured sink, if any."""
        if self.log_fn is not None:
            self.log_fn(url, formatted, extra_columns)

    def __uncache(self, cache_key):
        actual_url, cached_response, formatted_url = self.cache[cache_key]
        response = Response(data=cached_response.data, x_headers=cached_response.x_headers, req=cached_response.req)
        self.do_log(formatted_url, formatted=True, extra_columns=["(cached)"])
        return response

    async def autosuggest(
        self,
        session: HTTPSession,
        q: str,
        latitude: float,
        longitude: float,
        route: str | None = None,
        all_along: bool | None = None,
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
        params.update(q=q, at=f"{latitude},{longitude}")
        method: Literal["GET", "POST"] = "GET"
        data = None
        if route:
            method = "POST"
            data = f"route={route}"
            x_headers = x_headers or {}
            x_headers.update({"Content-Type": "application/x-www-form-urlencoded"})
            if all_along:
                params["ranking"] = "excursionDistance"

        params.update(kwargs)
        request = Request(
            endpoint=Endpoint.AUTOSUGGEST,
            url=type(self).BASE_URL[Endpoint.AUTOSUGGEST],
            params=params,
            data=data,
            x_headers=x_headers,
        )
        return await self.send(session, method, request)

    async def autosuggest_href(
        self,
        session: HTTPSession,
        href: str,
        route: str | None = None,
        all_along: bool | None = None,
        x_headers: dict = None,
        **kwargs,
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
        params = self.options.get(Endpoint.AUTOSUGGEST_HREF, {}).copy()
        params.update(parse_qsl(href_details.query))
        method: Literal["GET", "POST"] = "GET"
        data = None
        if route:
            method = "POST"
            data = f"route={route}"
            x_headers = x_headers or {}
            x_headers.update({"Content-Type": "application/x-www-form-urlencoded"})
            if all_along:
                params["ranking"] = "excursionDistance"

        request = Request(
            endpoint=Endpoint.AUTOSUGGEST_HREF,
            url=urlunparse(href_details._replace(query="")),  # TODO: fix bytes/str incoonsisteny
            params=dict(params),
            data=data,
            x_headers=x_headers,
        )
        return await self.send(session, method, request)

    async def discover(
        self,
        session: HTTPSession,
        q: str,
        latitude: float,
        longitude: float,
        route: str | None = None,
        all_along: bool | None = None,
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
        params.update(q=q, at=f"{latitude},{longitude}")
        method: Literal["GET", "POST"] = "GET"
        data = None
        if route:
            method = "POST"
            data = f"route={route}"
            x_headers = x_headers or {}
            x_headers.update({"Content-Type": "application/x-www-form-urlencoded"})
            if all_along:
                params["ranking"] = "excursionDistance"

        params.update(kwargs)
        request = Request(
            endpoint=Endpoint.DISCOVER,
            url=type(self).BASE_URL[Endpoint.DISCOVER],
            params=params,
            data=data,
            x_headers=x_headers,
        )
        return await self.send(session, method, request)

    async def browse(
        self,
        session: HTTPSession,
        latitude: float,
        longitude: float,
        categories: Sequence[str] | None = None,
        food_types: Sequence[str] | None = None,
        chains: Sequence[str] | None = None,
        route: str | None = None,
        all_along: bool | None = None,
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

        method: Literal["GET", "POST"] = "GET"
        data = None
        if route:
            method = "POST"
            data = f"route={route}"
            x_headers = x_headers or {}
            x_headers.update({"Content-Type": "application/x-www-form-urlencoded"})
            if all_along:
                params["ranking"] = "excursionDistance"

        params.update(_params)
        params.update(kwargs)
        request = Request(
            endpoint=Endpoint.BROWSE,
            url=type(self).BASE_URL[Endpoint.BROWSE],
            params=params,
            data=data,
            x_headers=x_headers,
        )
        return await self.send(session, method, request)

    async def lookup(self, session: HTTPSession, id: str, x_headers: dict = None, **kwargs) -> Response:
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
        return await self.send(session, "GET", request)

    async def reverse_geocode(
        self, session: HTTPSession, latitude: float, longitude: float, x_headers: dict = None, **kwargs
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
        params.update(at=f"{latitude},{longitude}")
        params.update(kwargs)
        request = Request(
            endpoint=Endpoint.REVGEOCODE,
            url=type(self).BASE_URL[Endpoint.REVGEOCODE],
            params=params,
            x_headers=x_headers,
        )
        return await self.send(session, "GET", request)
