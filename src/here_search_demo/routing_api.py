###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""HERE Routing API client.

:class:`RoutingAPI` is to the `HERE Routing API v8`_ what
:class:`here_search_demo.api.API` is to the HERE Geocoding & Search API: a thin
asynchronous wrapper that

* builds a :class:`~here_search_demo.entity.request.Request`,
* authenticates it with a :class:`~here_search_demo.auth.Credentials` token,
* caches and returns a :class:`~here_search_demo.entity.response.Response`.

It has no widget and no application dependency, so it can be used on its own::

    routing_api = RoutingAPI()
    async with HTTPSession() as session:
        response = await routing_api.routes(
            session=session,
            origin=(52.51604, 13.37691),
            destination=(52.39058, 13.06451),
            via=Waypoint(52.47, 13.30, name_hint="Hauptstrasse"),
        )
    to_leg, from_leg = RoutingAPI.split_at(RoutingAPI.sections(response), 52.47, 13.30)

.. _HERE Routing API v8: https://www.here.com/docs/bundle/routing-api-v8-api-reference/page/index.html
"""

import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

import orjson
from flexpolyline import decode, encode

from here_search_demo import __version__
from here_search_demo.auth import Credentials
from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.request import Request
from here_search_demo.entity.response import Response
from here_search_demo.entity.response_data import ResponseData, make_response
from here_search_demo.http import IS_BROWSER_RUNTIME, HTTPSession

_CLIENT_PREFIX = f"hsd/{__version__}/{sys.platform}"

base_url = {Endpoint.ROUTES: "https://router.hereapi.com/v8/routes"}


@dataclass(frozen=True)
class Waypoint:
    """A Routing API waypoint.

    :ivar latitude: waypoint latitude
    :ivar longitude: waypoint longitude
    :ivar name_hint: optional street name passed as the ``nameHint`` waypoint
        option; it helps the router pick the right side of a complex intersection
    """

    latitude: float
    longitude: float
    name_hint: str | None = None

    def __str__(self) -> str:
        """Return the waypoint formatted as a Routing API parameter value."""
        text = f"{self.latitude},{self.longitude}"
        if self.name_hint:
            text = f"{text};nameHint={self.name_hint}"
        return text

    @classmethod
    def make(cls, value) -> "Waypoint":
        """Return *value* as a :class:`Waypoint`.

        :param value: a ``Waypoint``, a ``(lat, lon)`` or a ``(lat, lon, name_hint)`` tuple
        :return: a ``Waypoint`` instance
        """
        if isinstance(value, Waypoint):
            return value
        latitude, longitude, *rest = value
        return cls(latitude, longitude, rest[0] if rest else None)


@dataclass(frozen=True)
class RouteSection:
    """One ``sections[]`` entry of a routing response.

    :ivar duration: travel duration in seconds
    :ivar length: travel distance in meters
    :ivar polyline: encoded `flexible polyline <https://github.com/heremaps/flexible-polyline>`_
        of the section geometry
    :ivar spans: the section ``spans[]`` when they were requested
    """

    duration: int
    length: int
    polyline: str
    spans: list = field(default_factory=list)


@dataclass
class RoutingOptions:
    """Default request parameters of a :class:`RoutingAPI` instance.

    :ivar transport_mode: value of the ``transportMode`` parameter
    :ivar return_fields: values joined into the ``return`` parameter
    :ivar spans: values joined into the ``spans`` parameter, or ``None``
    """

    transport_mode: str = "car"
    routing_mode: str = "fast"
    return_fields: Sequence[str] = ("summary", "polyline")
    spans: Sequence[str] | None = None


def _decode_points(polyline: str) -> list:
    """Return the points of a flexible *polyline*, or ``[]`` when unreadable."""
    if not polyline:
        return []
    try:
        return decode(polyline)
    except (ValueError, IndexError):
        return []


def as_waypoints(value) -> list[Waypoint]:
    """Return *value* as a list of :class:`Waypoint`.

    Accepts a single waypoint, a single ``(lat, lon[, name_hint])`` tuple, or a
    sequence of either.

    :param value: waypoint, coordinates tuple, sequence of those, or ``None``
    :return: list of ``Waypoint`` instances
    """
    if value is None:
        return []
    if isinstance(value, Waypoint):
        return [value]
    if isinstance(value, (tuple, list)) and value and isinstance(value[0], (int, float)):
        return [Waypoint.make(value)]
    return [Waypoint.make(item) for item in value]


class RoutingAPI:
    """
    https://www.here.com/docs/bundle/routing-api-v8-api-reference/page/index.html
    """

    cache: dict[str, Response]
    options: RoutingOptions
    raise_for_status: bool

    BASE_URL = base_url

    def __init__(
        self,
        credentials: Credentials | None = None,
        cache: dict | None = None,
        raise_for_status: bool = True,
        options: RoutingOptions | None = None,
        log_fn: Callable[[str, list | None], None] | None = None,
        on_request_sent: Callable[[Request], None] | None = None,
    ):
        """
        Creates a HERE Routing API instance.

        :param credentials: a :class:`Credentials` instance; one is created automatically when omitted
        :param cache: a Cache object supporting the MutableMapping protocol. By default, set to a dict
        :param raise_for_status: set to True to raise HTTPResponseError if HTTP status code is not 200
        :param options: default request parameters
        :param log_fn: optional logging callback, e.g. ``TableLogWidget.log``
        :param on_request_sent: optional callback called for each request actually sent
        """
        self._credentials: Credentials = credentials or Credentials()
        self.cache = cache if cache is not None else {}
        self.raise_for_status = raise_for_status
        self.options = options or RoutingOptions()
        self.log_fn = log_fn
        self.on_request_sent = on_request_sent

    @property
    def api_key(self) -> str | None:
        """Return the current API key from credentials."""
        return self._credentials.api_key

    @property
    def credentials(self) -> Credentials:
        """Return the credentials object."""
        return self._credentials

    def _build_routes_request(
        self,
        origin,
        destination,
        via=None,
        transport_mode: str | None = None,
        return_fields: Sequence[str] | None = None,
        spans: Sequence[str] | None = None,
        x_headers: dict | None = None,
        **kwargs,
    ) -> Request:
        """Build the :class:`Request` of a ``/v8/routes`` call."""
        params: dict[str, Any] = {
            "origin": str(Waypoint.make(origin)),
            "destination": str(Waypoint.make(destination)),
            "transportMode": transport_mode or self.options.transport_mode,
            "routingMode": self.options.routing_mode,
            "return": ",".join(return_fields if return_fields is not None else self.options.return_fields),
        }
        spans = spans if spans is not None else self.options.spans
        if spans:
            params["spans"] = ",".join(spans)
        via_waypoints = as_waypoints(via)
        if via_waypoints:
            params["via"] = [str(waypoint) for waypoint in via_waypoints]
        params.update(kwargs)
        return Request(
            endpoint=Endpoint.ROUTES,
            base_url=type(self).BASE_URL[Endpoint.ROUTES],
            params=params,
            x_headers=x_headers,
        )

    async def routes(
        self,
        session: HTTPSession,
        origin,
        destination,
        via=None,
        transport_mode: str | None = None,
        return_fields: Sequence[str] | None = None,
        spans: Sequence[str] | None = None,
        x_headers: dict | None = None,
        **kwargs,
    ) -> Response:
        """
        Calls the HERE Routing ``/v8/routes`` endpoint.

        :param session: instance of HTTPSession
        :param origin: route origin, a :class:`Waypoint` or a ``(lat, lon[, name_hint])`` tuple
        :param destination: route destination, in the same formats as *origin*
        :param via: optional intermediate waypoint(s), in the same formats as *origin*
        :param transport_mode: overrides the instance ``transportMode`` option
        :param return_fields: overrides the instance ``return`` option
        :param spans: overrides the instance ``spans`` option
        :param x_headers: Optional X-* headers (X-Request-Id, ...)
        :param kwargs: additional request URL parameters
        :return: a Response object whose ``data`` is the routing payload
        """
        request = self._build_routes_request(
            origin, destination, via, transport_mode, return_fields, spans, x_headers, **kwargs
        )
        return await self.send(session, request)

    async def send(self, session: HTTPSession, request: Request) -> Response:
        """Return the Routing API response for *request*, from the cache when possible.

        :param session: instance of HTTPSession
        :param request: Routing Request object
        :return: a Response object
        """
        cache_key = request.key
        if cache_key in self.cache:
            return self.__uncache(cache_key)

        req_headers = self._make_request_headers(request.x_headers)

        if self.on_request_sent is not None:
            self.on_request_sent(request)

        _, payload, rsp_text, rsp_headers = await self.do_send(
            session,
            request.base_url,
            request.params,
            req_headers,
        )
        rsp_x_headers = self.get_x_headers(rsp_headers)
        immutable_payload = make_response(cast(ResponseData, payload)) if isinstance(payload, dict) else payload
        response = Response(data=immutable_payload, req=request, x_headers=rsp_x_headers, raw=rsp_text)
        self.cache[cache_key] = response
        self.do_log(request)
        return response

    def __uncache(self, cache_key) -> Response:
        cached_response = self.cache[cache_key]
        response = Response(
            data=cached_response.data,
            x_headers=cached_response.x_headers,
            req=cached_response.req,
            raw=cached_response.raw,
        )
        self.do_log(cached_response.req, extra_columns=["(cached)"])
        return response

    def auth_headers(self, token: str) -> dict:
        """Return HTTP request headers with the bearer *token* in the ``Authorization`` field.

        :param token: an OAuth2 access token
        :return: authorization headers
        """
        return {"Authorization": f"Bearer {token}"}

    def _make_request_headers(self, x_headers: dict | None = None) -> dict:
        """Build outgoing request headers, adding a fresh ``X-Request-Id`` when absent."""
        headers = dict(x_headers or {})
        headers.setdefault("X-Request-Id", f"{_CLIENT_PREFIX}/{uuid.uuid4()}")
        return headers

    def get_x_headers(self, headers: Mapping[str, str]) -> dict:
        """Extract the ``X-*`` headers of a full headers mapping."""
        return {k: v for k, v in headers.items() if k.lower().startswith("x-")}

    @staticmethod
    def query(params: Mapping[str, Any]) -> Any:
        """Return *params* in the form expected by the runtime HTTP session.

        ``lite.HTTPSession`` encodes the query with ``doseq=True`` and therefore
        accepts list values, while ``aiohttp`` requires repeated two-tuples.
        """
        if IS_BROWSER_RUNTIME:  # pragma: no cover
            return dict(params)
        flat: list[tuple[str, str]] = []
        for key, value in params.items():
            if isinstance(value, (list, tuple)):
                flat.extend((key, str(item)) for item in value)
            else:
                flat.append((key, str(value)))
        return flat

    async def do_send(
        self,
        session: HTTPSession,
        url: str,
        params: Mapping[str, Any],
        headers: dict,
    ) -> tuple[Any, dict, str, Mapping[str, str]]:  # pragma: no cover
        if IS_BROWSER_RUNTIME:
            token = await self._credentials.atoken
        else:
            token = self._credentials.token
        req_headers = self.auth_headers(token)
        if headers:
            req_headers.update(headers)

        async with session.get(url, params=type(self).query(params), headers=req_headers) as get_response:
            rsp_headers: Mapping[str, str] = get_response.headers
            text = await get_response.text()
            self.raise_for_status and get_response.raise_for_status()
            content_type = rsp_headers.get("content-type") or rsp_headers.get("Content-Type", "")
            payload = orjson.loads(text) if "application/json" in content_type else text
        return get_response.url, payload, text, rsp_headers

    def do_log(self, request: Request, extra_columns: list | None = None) -> None:
        """Send a log entry for *request* to the configured sink, if any."""
        if self.log_fn is None:
            return
        params = request.params or {}
        parts = []
        for key, value in params.items():
            if isinstance(value, (list, tuple)):
                parts.extend(f"{key}={item}" for item in value)
            else:
                parts.append(f"{key}={value}")
        self.log_fn(f"/routes?{'&'.join(parts)}", extra_columns)

    @staticmethod
    def sections(response: Response, route_index: int = 0) -> list[RouteSection]:
        """Return the sections of one route of a routing *response*.

        The Routing API starts a new section at each via waypoint **and**
        wherever the journey changes transport mode -- a Berlin/London route
        is split by the channel ferry, for instance. Callers that need the
        ``at → result`` and ``result → stop`` legs must therefore group these
        sections with :meth:`split_at` and :meth:`merge_sections` rather than
        assume one section per leg.

        :param response: a :class:`Response` returned by :meth:`routes`
        :param route_index: index in the ``routes[]`` array
        :return: list of :class:`RouteSection`
        """
        route = response.data["routes"][route_index]
        return [
            RouteSection(
                duration=section["summary"]["duration"],
                length=section["summary"]["length"],
                polyline=section.get("polyline", ""),
                spans=list(section.get("spans", [])),
            )
            for section in route["sections"]
        ]

    @staticmethod
    def merge_sections(sections: Sequence[RouteSection]) -> RouteSection:
        """Combine consecutive *sections* into the single :class:`RouteSection` of a leg.

        Durations and lengths are summed, geometries are concatenated (dropping
        the duplicated point shared by two consecutive sections) and span
        offsets are rebased onto the concatenated geometry.

        :param sections: consecutive sections belonging to the same leg
        :return: one :class:`RouteSection` covering the whole leg
        """
        if not sections:
            raise ValueError("cannot merge an empty section sequence")
        if len(sections) == 1:
            return sections[0]

        points: list = []
        spans: list = []
        previous_point = None
        offset_base = 0
        for section in sections:
            section_points = _decode_points(section.polyline)
            skip_first = 1 if previous_point is not None and section_points[:1] == [previous_point] else 0
            # The dropped point stays reachable at ``offset_base - skip_first``.
            span_base = offset_base - skip_first
            for span in section.spans:
                span_copy = dict(span)
                if span_copy.get("offset") is not None:
                    span_copy["offset"] = max(0, span_base + int(span_copy["offset"]))
                spans.append(span_copy)
            section_points = section_points[skip_first:]
            if section_points:
                points.extend(section_points)
                previous_point = section_points[-1]
                offset_base += len(section_points)

        if points:
            polyline = encode(points)
        else:
            # Geometries were absent or unreadable: keep the first one available.
            polyline = next((section.polyline for section in sections if section.polyline), "")

        return RouteSection(
            duration=sum(section.duration for section in sections),
            length=sum(section.length for section in sections),
            polyline=polyline,
            spans=spans,
        )

    @staticmethod
    def split_at(
        sections: Sequence[RouteSection], latitude: float, longitude: float
    ) -> tuple[list[RouteSection], list[RouteSection]]:
        """Split *sections* into the legs before and after a via waypoint.

        The boundary is the section end point closest to ``(latitude, longitude)``,
        which makes the split immune to the extra sections the Routing API
        inserts on transport-mode changes (ferries, car trains, ...).

        :param sections: the sections of a route built with one via waypoint
        :param latitude: via waypoint latitude
        :param longitude: via waypoint longitude
        :return: the ``(to_leg, from_leg)`` section groups
        """
        if len(sections) < 2:
            raise ValueError("a route split at a via waypoint has at least two sections")

        best_index, best_distance = 1, None
        for index, section in enumerate(sections[:-1], start=1):
            points = _decode_points(section.polyline)
            if not points:
                continue
            end_lat, end_lon = points[-1][0], points[-1][1]
            # Squared degrees are enough to rank candidate boundaries.
            distance = (end_lat - latitude) ** 2 + (end_lon - longitude) ** 2
            if best_distance is None or distance < best_distance:
                best_index, best_distance = index, distance

        return list(sections[:best_index]), list(sections[best_index:])
