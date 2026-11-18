###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Autosuggest, discover and browse endpoints of the HERE Geocoding & Search API client."""

from collections.abc import Sequence
from typing import Literal
from urllib.parse import parse_qsl, urlparse, urlunparse

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.request import Request
from here_search_demo.entity.response import Response
from here_search_demo.http import HTTPSession


class SearchEndpointsMixin:
    """Autosuggest, discover and browse endpoints of the HERE Geocoding & Search API client."""

    def _build_autosuggest_request(
        self,
        q: str,
        latitude: float,
        longitude: float,
        polyline: str | None = None,
        width: int | None = None,
        all_along: bool | None = None,
        x_headers: dict | None = None,
        **kwargs,
    ) -> tuple[Literal["GET", "POST"], Request]:
        params = self.options.get(Endpoint.AUTOSUGGEST, {}).copy()
        params.update(q=q, at=f"{latitude},{longitude}")
        method, data, x_headers = self._apply_route(polyline, width, all_along, x_headers, params)
        params.update(kwargs)
        return method, Request(
            endpoint=Endpoint.AUTOSUGGEST,
            base_url=type(self).BASE_URL[Endpoint.AUTOSUGGEST],
            params=params,
            data=data,
            x_headers=x_headers,
        )

    async def autosuggest(
        self,
        session: HTTPSession,
        q: str,
        latitude: float,
        longitude: float,
        polyline: str | None = None,
        width: int = None,
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
        method, request = self._build_autosuggest_request(
            q, latitude, longitude, polyline, width, all_along, x_headers, **kwargs
        )
        return await self.send(session, method, request)

    def _build_autosuggest_href_request(
        self,
        href: str,
        polyline: str | None = None,
        width: int | None = None,
        all_along: bool | None = None,
        x_headers: dict | None = None,
        **kwargs,
    ) -> tuple[Literal["GET", "POST"], Request]:
        href_details = urlparse(href)
        params = dict(parse_qsl(href_details.query))
        params.update(self.options.get(Endpoint.AUTOSUGGEST_HREF, {}))
        method, data, x_headers = self._apply_route(polyline, width, all_along, x_headers, params)
        return method, Request(
            endpoint=Endpoint.AUTOSUGGEST_HREF,
            base_url=urlunparse(href_details._replace(query="")),
            params=dict(params),
            data=data,
            x_headers=x_headers,
        )

    async def autosuggest_href(
        self,
        session: HTTPSession,
        href: str,
        polyline: str | None = None,
        width: int | None = None,
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
        method, request = self._build_autosuggest_href_request(href, polyline, width, all_along, x_headers, **kwargs)
        return await self.send(session, method, request)

    def _build_discover_request(
        self,
        q: str,
        latitude: float,
        longitude: float,
        polyline: str | None = None,
        width: int | None = None,
        all_along: bool | None = None,
        x_headers: dict | None = None,
        **kwargs,
    ) -> tuple[Literal["GET", "POST"], Request]:
        params = self.options.get(Endpoint.DISCOVER, {}).copy()
        params.update(q=q, at=f"{latitude},{longitude}")
        method, data, x_headers = self._apply_route(polyline, width, all_along, x_headers, params)
        params.update(kwargs)
        return method, Request(
            endpoint=Endpoint.DISCOVER,
            base_url=type(self).BASE_URL[Endpoint.DISCOVER],
            params=params,
            data=data,
            x_headers=x_headers,
        )

    async def discover(
        self,
        session: HTTPSession,
        q: str,
        latitude: float,
        longitude: float,
        polyline: str | None = None,
        width: int | None = None,
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
        method, request = self._build_discover_request(
            q, latitude, longitude, polyline, width, all_along, x_headers, **kwargs
        )
        return await self.send(session, method, request)

    def _build_browse_request(
        self,
        latitude: float,
        longitude: float,
        categories: Sequence[str] | None = None,
        food_types: Sequence[str] | None = None,
        chains: Sequence[str] | None = None,
        polyline: str | None = None,
        width: int | None = None,
        all_along: bool | None = None,
        x_headers: dict | None = None,
        **kwargs,
    ) -> tuple[Literal["GET", "POST"], Request]:
        params = self.options.get(Endpoint.BROWSE, {}).copy()
        _params: dict = {"at": f"{latitude},{longitude}"}
        if categories:
            _params["categories"] = ",".join(sorted(set(categories)))
        if food_types:
            _params["foodTypes"] = ",".join(sorted(set(food_types)))
        if chains:
            _params["chains"] = ",".join(sorted(set(chains)))
        method, data, x_headers = self._apply_route(polyline, width, all_along, x_headers, params)
        params.update(_params)
        params.update(kwargs)
        return method, Request(
            endpoint=Endpoint.BROWSE,
            base_url=type(self).BASE_URL[Endpoint.BROWSE],
            params=params,
            data=data,
            x_headers=x_headers,
        )

    async def browse(
        self,
        session: HTTPSession,
        latitude: float,
        longitude: float,
        categories: Sequence[str] | None = None,
        food_types: Sequence[str] | None = None,
        chains: Sequence[str] | None = None,
        polyline: str | None = None,
        width: int | None = None,
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
        method, request = self._build_browse_request(
            latitude, longitude, categories, food_types, chains, polyline, width, all_along, x_headers, **kwargs
        )
        return await self.send(session, method, request)
