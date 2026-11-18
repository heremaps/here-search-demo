###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Minimal-detour reranking for HERE Search results.

Uses the HERE Routing API to compute the excursion distance
(extra distance to detour to a result and back to the main route)
for each result item, then reranks results by ascending excursion distance.

The excursion distance for a given result is:

    dist(at → result) + dist(result → stop) − route_length

The polylines for both legs are stored on each reranked item so they can be
displayed without an additional routing call.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from here_search_demo.auth import Credentials
from here_search_demo.entity.response import Response
from here_search_demo.http import HTTPSession
from here_search_demo.routing_api import RoutingAPI, Waypoint

logger = logging.getLogger(__name__)


@dataclass
class _DetourLegs:
    """Routing result for a single ``at → via(item) → stop`` excursion.

    Field units:

    * ``dur_*``  – travel duration in seconds
    * ``dist_*`` – travel distance in metres
    * ``poly_*`` – encoded polyline for the leg
    """

    dur_to: int
    dist_to: int
    poly_to: str
    dur_from: int
    dist_from: int
    poly_from: str

    def excursion_m(self, direct_dist_m: int) -> int:
        """Extra distance vs. the direct ``at → stop`` route, in metres."""
        return self.dist_to + self.dist_from - direct_dist_m

    def sort_key(self, all_along: bool) -> float:
        """Ranking key in minutes: round-trip time when *all_along*, else time to reach."""
        seconds = self.dur_to + self.dur_from if all_along else self.dur_to
        return seconds / 60


class DetourRanker:
    """Reranks search result items by minimal excursion distance from a route.

    Parameters
    ----------
    credentials:
        HERE API credentials used to authenticate Routing requests.
    at_pos:
        ``(latitude, longitude)`` of the current position on the route.
        Used as the origin for routing calculations.
    stop_pos:
        ``(latitude, longitude)`` of the route destination.
    on_routing_request:
        Optional callback invoked before each Routing request that is not
        served by *route_cache*.
    route_cache:
        Route cache shared with :class:`~here_search_demo.route_engine.RouteEngine`,
        so an already fetched ``at → stop`` route is reused as the baseline.
    routing_api:
        Optional :class:`~here_search_demo.routing_api.RoutingAPI` instance;
        one is created from *credentials* when omitted.
    """

    routing_return_fields = ("summary", "polyline")

    def __init__(
        self,
        credentials: Credentials,
        at_pos: tuple[float, float],
        stop_pos: tuple[float, float],
        on_routing_request: Callable[[], None] | None = None,
        route_cache: dict | None = None,
        routing_api: RoutingAPI | None = None,
    ):
        self.credentials = credentials
        self.at_pos = at_pos
        self.stop_pos = stop_pos
        self.on_routing_request = on_routing_request
        self._route_cache = route_cache if route_cache is not None else {}
        self.routing_api = routing_api or RoutingAPI(credentials=credentials)

    async def _get_route_summary(
        self,
        session: HTTPSession,
        start_lat: float,
        start_lon: float,
        stop_lat: float,
        stop_lon: float,
        headers: dict,
    ) -> tuple[int, int, str]:
        """Call the Routing API and return ``(duration_s, length_m, polyline)``.

        Both ``summary`` and ``polyline`` are requested so the polyline can be
        displayed directly when the user interacts with the result.
        """

        cache_key = ("summary", start_lat, start_lon, stop_lat, stop_lon)
        cached = self._route_cache.get(cache_key)
        if cached:
            return cached
        if self.on_routing_request is not None:
            self.on_routing_request()
        response = await self.routing_api.routes(
            session=session,
            origin=(start_lat, start_lon),
            destination=(stop_lat, stop_lon),
            return_fields=type(self).routing_return_fields,
            x_headers=headers,
        )
        # A direct route can still hold several sections (ferry crossings, ...).
        section = RoutingAPI.merge_sections(RoutingAPI.sections(response))
        result = section.duration, section.length, section.polyline
        self._route_cache[cache_key] = result
        return result

    async def get_route_with_via(
        self,
        session: HTTPSession,
        start_lat: float,
        start_lon: float,
        via_lat: float,
        via_lon: float,
        stop_lat: float,
        stop_lon: float,
        headers: dict,
        name_hint: str | None = None,
    ) -> tuple[int, int, str, int, int, str]:
        """Call the Routing API with a via waypoint and return route segments.

        Returns:
            (dur_to, dist_to, poly_to, dur_from, dist_from, poly_from)
            where:
            - dur_to, dist_to, poly_to: segment from start to via
            - dur_from, dist_from, poly_from: segment from via to stop
        """
        cache_key = "via", start_lat, start_lon, via_lat, via_lon, stop_lat, stop_lon
        cached = self._route_cache.get(cache_key)
        if cached:
            return cached

        if self.on_routing_request is not None:
            self.on_routing_request()
        response = await self.routing_api.routes(
            session=session,
            origin=(start_lat, start_lon),
            destination=(stop_lat, stop_lon),
            via=Waypoint(via_lat, via_lon, name_hint),
            return_fields=type(self).routing_return_fields,
            x_headers=headers,
        )
        # The via waypoint splits the route in two legs, but each leg can span
        # several sections when the journey changes transport mode (ferry, ...).
        to_leg, from_leg = RoutingAPI.split_at(RoutingAPI.sections(response), via_lat, via_lon)
        section_to = RoutingAPI.merge_sections(to_leg)
        section_from = RoutingAPI.merge_sections(from_leg)

        result = (
            section_to.duration,
            section_to.length,
            section_to.polyline,
            section_from.duration,
            section_from.length,
            section_from.polyline,
        )
        self._route_cache[cache_key] = result
        return result

    async def rerank(
        self,
        resp: Response,
        all_along: bool = False,
        max_excursion: int | None = None,
    ) -> Response:
        """Return a new :class:`~here_search_demo.entity.response.Response`
        whose items are sorted by ascending travel time.

        * When *all_along* is ``True`` items are ranked by
          ``dur_to + dur_from`` (minimise total round-trip time).
        * When *all_along* is ``False`` items are ranked by ``dur_to`` only
          (minimise time to reach the result from the current position;
          the return leg is shown in the label but does not affect order).

        Items whose excursion distance exceeds ``max_excursion`` metres are
        filtered out.  Each surviving item gains a ``_detour`` annotation, whose
        most useful keys are:

        * ``_detour["label"]``         – ``<title> (<dur_to>min, <dur_from>min, +<detour_km>km)``
        * ``_detour["rank_before"]``   – 0-based position of the item in *resp*, before reranking
        * ``_detour["polyline_to"]``   – encoded polyline for the ``at → item`` leg
        * ``_detour["polyline_from"]`` – encoded polyline for the ``item → stop`` leg

        The excursion distance is computed relative to the direct ``at → stop``
        route (not the full route from its origin), so it correctly reflects
        the extra distance added to the remaining journey.

        Parameters
        ----------
        resp:
            The original search response.
        max_excursion:
            Maximum allowed excursion in metres.  Items beyond this threshold
            are dropped from the reranked response.
        """
        items = list(resp.data.get("items", []))
        if not items:
            return resp

        positioned_indices = [i for i, item in enumerate(items) if "position" in item]
        if not positioned_indices:
            return resp

        detours_waypoints = [
            (items[i]["position"]["lat"], items[i]["position"]["lng"], items[i].get("address", {}).get("street"))
            for i in positioned_indices
        ]

        summary, detours_routes = await self.retrieve_detours(detours_waypoints)
        _, direct_dist_m, _ = summary

        scored_items: list[tuple[float, int, dict]] = []
        for orig_idx, route_details in zip(positioned_indices, detours_routes):
            legs = _DetourLegs(*route_details)
            excursion = legs.excursion_m(direct_dist_m)
            if max_excursion is not None and excursion > max_excursion:
                logger.debug(
                    "Dropping item %d (%s): excursion %dm > max %dm",
                    orig_idx,
                    items[orig_idx].get("title", ""),
                    excursion,
                    max_excursion,
                )
                continue
            annotated = self._annotate_item(items[orig_idx], legs, excursion, orig_idx)
            scored_items.append((legs.sort_key(all_along), orig_idx, annotated))

        scored_items.sort(key=lambda x: x[0])
        reranked_data = dict(resp.data)
        reranked_data["items"] = [item for _, _, item in scored_items]
        return Response(req=resp.req, data=reranked_data, x_headers=resp.x_headers)

    @staticmethod
    def _annotate_item(item: dict, legs: _DetourLegs, excursion_m: int, rank_before: int) -> dict:
        """Return a copy of *item* with a ``_detour`` annotation attached."""
        dur_to_min = int(legs.dur_to / 60)
        dur_from_min = int(legs.dur_from / 60)
        excursion_km = abs(int(excursion_m / 1000))
        excursion_sign = "+" if excursion_m >= 0 else "-"
        annotated = dict(item)
        annotated["_detour"] = {
            "label": f"{item.get('title', '')} ({dur_to_min}min, {dur_from_min}min, {excursion_sign}{excursion_km}km)",
            "rank_before": rank_before,
            "dur_to_sec": legs.dur_to,
            "dur_from_sec": legs.dur_from,
            "dist_to_m": legs.dist_to,
            "dist_from_m": legs.dist_from,
            "excursion_m": excursion_m,
            "polyline_to": legs.poly_to,
            "polyline_from": legs.poly_from,
        }
        return annotated

    async def retrieve_detours(self, detours_waypoints: list[tuple[Any, Any, Any]]) -> tuple[tuple[int, int, str], Any]:
        # Authorization is now handled by RoutingAPI; only X-* headers are forwarded.
        headers: dict = {}

        at_lat, at_lon = self.at_pos
        stop_lat, stop_lon = self.stop_pos

        async with HTTPSession() as session:
            all_results = await asyncio.gather(
                # Baseline: direct route from at_pos to stop_pos
                self._get_route_summary(session, at_lat, at_lon, stop_lat, stop_lon, headers),
                # Per-item: at_pos → via(item) → stop_pos in a single call
                *(
                    self.get_route_with_via(
                        session,
                        at_lat,
                        at_lon,
                        detour_waypoint[0],
                        detour_waypoint[1],
                        stop_lat,
                        stop_lon,
                        headers,
                        name_hint=detour_waypoint[2],
                    )
                    for detour_waypoint in detours_waypoints
                ),
            )
        summary, detours_routes = all_results[0], all_results[1:]
        return summary, detours_routes
