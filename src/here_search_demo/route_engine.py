###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from __future__ import annotations

from typing import Any, Awaitable, Callable

from flexpolyline import decode, encode

from here_search_demo.auth import Credentials
from here_search_demo.http import HTTPSession, IS_BROWSER_RUNTIME
from here_search_demo.ranking import RankingMode
from here_search_demo.widgets.route_geometry import (
    elapsed_sec_at_position,
    position_at_x_sec_ahead,
    simplify_polyline,
)


class RouteEngine:
    """Head-agnostic route state and routing retrieval service.

    This class intentionally has no widget dependencies. It stores route/ranking
    state, computes derived search context, manages route cache, and retrieves
    route geometry from the HERE Routing API.
    """

    routing_api_tpl = (
        "https://router.hereapi.com/v8/routes"
        "?origin={start_lat},{start_lon}"
        "&destination={stop_lat},{stop_lon}"
        "&return=polyline,summary&spans=duration,dynamicSpeedInfo,length"
        "&transportMode=car"
    )
    max_waypoints_count = 2000

    def __init__(
        self,
        credentials: Credentials,
        *,
        on_routing_request=None,
        route_cache: dict | None = None,
        width: int = 100,
        retrieve_route_fn: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        self.credentials = credentials
        self.on_routing_request = on_routing_request
        self._route_cache = route_cache if route_cache is not None else {}
        self._default_width = width
        self._retrieve_route = retrieve_route_fn or self.retrieve_route
        self._init_route_attributes()

    def _init_route_attributes(self) -> None:
        self.has_route = False
        self.start_position: tuple[float, float] | None = None
        self.stop_position: tuple[float, float] | None = None
        self.current_position: tuple[float, float] | None = None
        self.future_position: tuple[float, float] | None = None
        self.width = self._default_width
        self.mins_from_pos: int = 0
        self.ranking_mode = RankingMode()
        self.route_flexpolyline: str | None = None
        self.search_flexpolyline: str | None = None
        self.waypoints_count: int | None = None
        self.route_summary_length: int | None = None
        self._current_waypoints: list | None = None
        self._cached_spans: list | None = None

    @property
    def all_along(self) -> bool:
        return self.ranking_mode.all_along

    @all_along.setter
    def all_along(self, value: bool) -> None:
        self.ranking_mode = RankingMode(all_along=value, travel_time=self.ranking_mode.travel_time)

    @property
    def minimal_detour(self) -> bool:
        return self.ranking_mode.travel_time

    @minimal_detour.setter
    def minimal_detour(self, value: bool) -> None:
        self.ranking_mode = RankingMode(all_along=self.ranking_mode.all_along, travel_time=value)

    @property
    def search_at_position(self) -> tuple[float, float] | None:
        return self.future_position or self.current_position

    def set_route_start(self, latlon: tuple[float, float]) -> None:
        self.start_position = latlon
        self._current_waypoints = None
        self._cached_spans = None

    def set_route_stop(self, latlon: tuple[float, float]) -> None:
        self.stop_position = latlon
        self._current_waypoints = None
        self._cached_spans = None

    def set_current_position(self, latlon: tuple[float, float] | None) -> None:
        self.current_position = latlon
        self._apply_mins_from_pos()

    def set_mins_from_pos(self, mins: int | None) -> None:
        self.mins_from_pos = mins or 0
        self._apply_mins_from_pos()

    def set_route_width(self, width: int | None) -> None:
        self.width = width

    def _apply_mins_from_pos(self) -> None:
        if self.current_position is None:
            self.future_position = None
            return
        if (self.mins_from_pos or 0) > 0 and self._cached_spans and self._current_waypoints:
            elapsed = elapsed_sec_at_position(self._cached_spans, self._current_waypoints, *self.current_position)
            self.future_position = position_at_x_sec_ahead(
                self._cached_spans, self._current_waypoints, elapsed, self.mins_from_pos * 60
            )
            return
        self.future_position = None

    def build_flexpolyline(self, flexpolyline: str, waypoints: list[tuple[float, float]]) -> None:
        self.route_flexpolyline = encode(waypoints)
        if len(waypoints) > RouteEngine.max_waypoints_count:
            simplified_waypoints = simplify_polyline(waypoints, RouteEngine.max_waypoints_count)
            flexpolyline = encode(simplified_waypoints)
        self.search_flexpolyline = flexpolyline

    async def update_route_attributes(self) -> dict:
        if self.start_position is None or self.stop_position is None:
            raise ValueError("start_position and stop_position must be set before update_route_attributes()")

        start_lat, start_lon = self.start_position
        stop_lat, stop_lon = self.stop_position
        cache_key = ("route", start_lat, start_lon, stop_lat, stop_lon)
        if cache_key not in self._route_cache:
            route = await self._retrieve_route(
                start_position=self.start_position,
                stop_position=self.stop_position,
                credentials=self.credentials,
            )
            if self.on_routing_request is not None:
                self.on_routing_request()

            # TODO: Check if we should not take more sections....
            section = route["routes"][0]["sections"][0]
            route_flexpolyline = section["polyline"]
            waypoints = decode(route_flexpolyline)
            summary = section.get("summary", {})
            self._route_cache[cache_key] = {
                "flexpolyline_raw": route_flexpolyline,
                "waypoints": waypoints,
                "route_summary_length": summary.get("length"),
                "spans": section.get("spans", []),
            }
            # Pre-populate the summary key so DetourRanker reuses this fetch
            # when at_pos == start_position (the common default).
            self._route_cache[("summary", start_lat, start_lon, stop_lat, stop_lon)] = (
                summary.get("duration"),
                summary.get("length"),
                route_flexpolyline,
            )

        cached = self._route_cache[cache_key]
        self._current_waypoints = cached["waypoints"]
        self.waypoints_count = len(cached["waypoints"])
        self.route_summary_length = cached["route_summary_length"]
        self._cached_spans = cached.get("spans", [])
        self.build_flexpolyline(cached["flexpolyline_raw"], cached["waypoints"])
        self.has_route = True
        return cached

    @staticmethod
    async def retrieve_route(start_position, stop_position, credentials) -> Any:  # pragma: no cover
        # Runtime HTTP/browser-token path is validated in integration environments; unit tests inject mocks.
        routing_url = RouteEngine.routing_api_tpl.format(
            start_lat=start_position[0],
            start_lon=start_position[1],
            stop_lat=stop_position[0],
            stop_lon=stop_position[1],
        )
        if IS_BROWSER_RUNTIME:
            token = await credentials.atoken
        else:
            token = credentials.token
        headers = {"Authorization": f"Bearer {token}"}

        async with HTTPSession() as session:
            async with session.get(routing_url, headers=headers) as get_response:
                get_response.raise_for_status()
                route = await get_response.json()
        return route
