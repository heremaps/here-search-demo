###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from collections.abc import Callable, Mapping, Sequence
from typing import Literal, cast
from urllib.parse import parse_qsl, urlparse, urlunparse, urlencode

from here_search_demo.api_options import APIOptions
from here_search_demo.auth import Credentials
from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.request import Request
from here_search_demo.entity.response import Response
from here_search_demo.entity.response_data import ResponseData, make_response
from here_search_demo.http import HTTPSession, IS_BROWSER_RUNTIME

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
    https://docs.here.com/geocoding-and-search/reference
    """

    cache: dict[str, Response]
    options: dict
    lookup_has_more_details: bool
    raise_for_status: bool

    BASE_URL = base_url

    def __init__(
        self,
        credentials: Credentials | None = None,
        cache: dict | None = None,
        raise_for_status: bool = True,
        options: APIOptions | None = None,
        log_fn: Callable[[str, list | None], None] | None = None,
    ):
        """
        Creates a HERE search API instance.
        :param credentials: a :class:`Credentials` instance; one is created automatically when omitted
        :param cache: a Cache object supporting the MutableMapping protocol. By default, set to a dict
        :param raise_for_status: set to True to raise HTTPResponseError if HTTP status code is not 200
        :param options: a set of APIOptions objects
        :param log_fn: optional logging callback, e.g. ``TableLogWidget.log``
        """
        self._credentials: Credentials = credentials or Credentials()

        self.cache = cache or {}
        self.raise_for_status = raise_for_status
        self.log_fn: Callable[[str, list | None], None] | None = log_fn
        if options:
            self.options = options.endpoint
            self.lookup_has_more_details = options.lookup_has_more_details
        else:
            self.options = {}
            self.lookup_has_more_details = False

    @property
    def api_key(self) -> str | None:
        """Return the current API key from credentials."""
        return self._credentials.api_key

    @property
    def credentials(self) -> Credentials:
        """Return the credentials object."""
        return self._credentials

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

        _, payload, rsp_headers = await self.do_send(
            session,
            method,
            request.base_url,
            request.params,
            request.data,
            request.x_headers,
        )
        rsp_x_headers = self.get_x_headers(rsp_headers)
        immutable_payload = make_response(cast(ResponseData, payload)) if isinstance(payload, dict) else payload
        response = Response(data=immutable_payload, req=request, x_headers=rsp_x_headers)
        self.cache[cache_key] = response
        self.do_log(request)
        return response

    def _build_display_urls(self, request: Request) -> tuple[str, str]:
        """Build log_url (Markdown label) and browser_url (clickable href) for a request."""
        params = request.params or {}
        endpoint_str = (request.base_url or "").rsplit("/", 1)[-1]

        log_parts: list[str] = []
        browser_params: dict[str, str] = {}
        for k, v in params.items():
            if k == "route":
                log_parts.append("route=...")
                browser_params["route"] = v
            elif k == "show" and "fuelPrices" in v:
                stripped = v.replace("fuelPrices,", "").replace(",fuelPrices", "").replace("fuelPrices", "")
                if stripped:
                    log_parts.append(f"show={stripped}")
                    browser_params["show"] = stripped
            else:
                log_parts.append(f"{k}={v}")
                browser_params[k] = v

        log_url = f"/{endpoint_str}?{'&'.join(log_parts)}" if log_parts else f"/{endpoint_str}"

        api_key = self._credentials.api_key
        browser_qs = urlencode(browser_params)
        if api_key:
            browser_qs += f"&apiKey={api_key}"
        browser_url = f"{request.base_url}?{browser_qs}" if browser_qs else request.base_url

        return log_url, browser_url

    def get_x_headers(self, headers: Mapping[str, str]) -> dict:
        """Extract X-* headers from a full headers dict."""
        return {k: v for k, v in headers.items() if k.lower().startswith("x-")}

    def auth_headers(self) -> dict:
        """Return HTTP request headers with Bearer token in ``Authorization`` field.

        :return: authorization tokens
        """
        return {"Authorization": f"Bearer {self._credentials.token}"}

    async def do_send(
        self,
        session: HTTPSession,
        method: Literal["GET", "POST"],
        url: str,
        params: dict,
        data: str | None,
        headers: dict,
    ) -> tuple[str | URL, dict, Mapping[str, str]]:  # pragma: no cover
        if IS_BROWSER_RUNTIME:
            token = await self._credentials.atoken
        else:
            token = self._credentials.token
        req_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            req_headers.update(headers)

        async with session.request(method, url, params=params, data=data, headers=req_headers) as get_response:
            rsp_headers: Mapping[str, str] = get_response.headers
            text = await get_response.text()
            self.raise_for_status and get_response.raise_for_status()
            payload = orjson.loads(text)
        return get_response.url, payload, rsp_headers

    def do_log(self, request: Request, extra_columns: list | None = None) -> None:
        """Build display URLs for the request and send a log entry to the configured sink, if any."""
        if self.log_fn is not None:
            log_url, browser_url = self._build_display_urls(request)
            self.log_fn(f"[{log_url}]({browser_url})", extra_columns)

    def __uncache(self, cache_key):
        cached_response = self.cache[cache_key]
        response = Response(data=cached_response.data, x_headers=cached_response.x_headers, req=cached_response.req)
        self.do_log(cached_response.req, extra_columns=["(cached)"])
        return response

    async def autosuggest(
        self,
        session: HTTPSession,
        q: str,
        latitude: float,
        longitude: float,
        route: str | None = None,
        all_along: bool | None = None,
        x_headers: dict | None = None,
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
            base_url=type(self).BASE_URL[Endpoint.AUTOSUGGEST],
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
        x_headers: dict | None = None,
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
            base_url=urlunparse(href_details._replace(query="")),  # TODO: fix bytes/str incoonsisteny
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
        x_headers: dict | None = None,
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
            base_url=type(self).BASE_URL[Endpoint.DISCOVER],
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
        x_headers: dict | None = None,
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
            base_url=type(self).BASE_URL[Endpoint.BROWSE],
            params=params,
            data=data,
            x_headers=x_headers,
        )
        return await self.send(session, method, request)

    async def lookup(self, session: HTTPSession, id: str, x_headers: dict | None = None, **kwargs) -> Response:
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
            base_url=type(self).BASE_URL[Endpoint.LOOKUP],
            params=params,
            x_headers=x_headers,
        )
        return await self.send(session, "GET", request)

    async def reverse_geocode(
        self, session: HTTPSession, latitude: float, longitude: float, x_headers: dict | None = None, **kwargs
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
            base_url=type(self).BASE_URL[Endpoint.REVGEOCODE],
            params=params,
            x_headers=x_headers,
        )
        return await self.send(session, "GET", request)
