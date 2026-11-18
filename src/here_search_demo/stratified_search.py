###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Route-stratified corridor ("all along the route") search.

A plain ``ranking=excursionDistance`` corridor search ranks matches purely by
distance from the route, which can bunch every result near the start of a
long remaining trip. :func:`corridor_search` splits the *remaining* route
(from the search position to the destination) into equal-distance slices,
fires one corridor search per slice in parallel, and merges the results with
an equal-allocation, quota-redistributing selection so results spread across
the whole remaining journey instead of clustering at one end.

For short remaining routes (or no route at all) :func:`corridor_search` is a
no-op wrapper around a single call, identical to today's behavior.
"""

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from flexpolyline import encode

from here_search_demo.entity.request import RequestContext
from here_search_demo.entity.response import Response
from here_search_demo.entity.response_data import make_response
from here_search_demo.http import HTTPSession
from here_search_demo.widgets.route_geometry import haversine_m

logger = logging.getLogger(__name__)

DEFAULT_STRATIFY_THRESHOLD_M = 1_000
DEFAULT_SLICE_OVER_FETCH_LIMIT = 4
MAX_SLICES = 20
REDISTRIBUTION_BUFFER = 2

#: ``(session, polyline_or_None, at_lat, at_lon, limit) -> Response``
SingleSliceCall = Callable[[HTTPSession, "str | None", float, float, int], Awaitable[Response]]


def nearest_waypoint_index(waypoints: Sequence[tuple[float, float]], lat: float, lon: float) -> int:
    """Return the index of the waypoint closest to ``(lat, lon)`` (squared-distance proxy)."""
    best_idx = 0
    best_d2 = float("inf")
    for i, (wp_lat, wp_lon) in enumerate(waypoints):
        d2 = (lat - wp_lat) ** 2 + (lon - wp_lon) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_idx = i
    return best_idx


def trim_to_remaining_route(
    waypoints: Sequence[tuple[float, float]] | None, at_lat: float, at_lon: float
) -> list[tuple[float, float]]:
    """Return the part of *waypoints* from the point closest to ``(at_lat, at_lon)`` onward."""
    if not waypoints:
        return []
    idx = nearest_waypoint_index(waypoints, at_lat, at_lon)
    return list(waypoints[idx:])


def cumulative_distances_m(waypoints: Sequence[tuple[float, float]]) -> list[float]:
    """Return cumulative great-circle distance in metres at each waypoint; ``cum[0] == 0``."""
    cum = [0.0]
    for (lat1, lon1), (lat2, lon2) in zip(waypoints, waypoints[1:]):
        cum.append(cum[-1] + haversine_m(lat1, lon1, lat2, lon2))
    return cum


def should_stratify(
    remaining_length_m: float | None, limit: int, threshold_m: float = DEFAULT_STRATIFY_THRESHOLD_M
) -> bool:
    """Whether a corridor search over *remaining_length_m* metres should be split into slices."""
    if not remaining_length_m or limit <= 1:
        return False
    return remaining_length_m / limit > threshold_m


def compute_slice_ranges(waypoints: Sequence[tuple[float, float]], n: int) -> list[tuple[int, int]]:
    """Partition *waypoints* into *n* contiguous, equal-distance ``(start_idx, end_idx)`` ranges.

    Adjacent ranges share their boundary waypoint, so the resulting sub-polylines stay
    geometrically contiguous. If *waypoints* is too sparse to support *n* distinct ranges,
    trailing ranges degenerate to a single point rather than raising.
    """
    cum = cumulative_distances_m(waypoints)
    total = cum[-1]
    last_index = len(waypoints) - 1
    ranges: list[tuple[int, int]] = []
    start_idx = 0
    cursor = 0
    for slice_no in range(1, n + 1):
        boundary = total * slice_no / n
        end_idx = cursor
        while end_idx < last_index and cum[end_idx] < boundary:
            end_idx += 1
        if end_idx <= start_idx:
            end_idx = min(start_idx + 1, last_index)
        ranges.append((start_idx, end_idx))
        start_idx = end_idx
        cursor = end_idx
    return ranges


def build_slice_polylines(waypoints: Sequence[tuple[float, float]], ranges: list[tuple[int, int]]) -> list[str]:
    """Encode each ``(start_idx, end_idx)`` range of *waypoints* into a flexpolyline."""
    return [encode(list(waypoints[start : end + 1])) for start, end in ranges]


def slice_at_positions(
    waypoints: Sequence[tuple[float, float]], ranges: list[tuple[int, int]]
) -> list[tuple[float, float]]:
    """Return each slice's own first waypoint, used as that slice's search anchor."""
    return [waypoints[start] for start, _ in ranges]


async def fetch_all_slices(
    session: HTTPSession,
    slice_specs: list[tuple[str, float, float]],
    single_call: SingleSliceCall,
    over_fetch_limit: int,
) -> tuple[list[list[dict]], list[Response | None]]:
    """Fire one corridor search per slice in parallel.

    A slice whose call raises is logged and treated as empty (0 items) so a single bad
    slice never aborts the whole search. If every slice fails, the first captured
    exception is re-raised instead of silently returning an empty result.
    """
    raw_results = await asyncio.gather(
        *(single_call(session, polyline, at_lat, at_lon, over_fetch_limit) for polyline, at_lat, at_lon in slice_specs),
        return_exceptions=True,
    )

    per_slice_items: list[list[dict]] = []
    slice_responses: list[Response | None] = []
    first_exception: BaseException | None = None
    for i, result in enumerate(raw_results):
        if isinstance(result, BaseException):
            logger.warning("Corridor slice %d failed: %s", i, result)
            if first_exception is None:
                first_exception = result
            per_slice_items.append([])
            slice_responses.append(None)
        else:
            per_slice_items.append(list(result.data.get("items", [])))
            slice_responses.append(result)

    if all(resp is None for resp in slice_responses):
        raise first_exception

    return per_slice_items, slice_responses


def merge_with_quota_redistribution(
    per_slice_items: list[list[dict]],
    limit: int,
    dedup_key: Callable[[dict], Any] = lambda item: item.get("id"),
) -> list[tuple[int, dict]]:
    """Equal-allocation selection with adaptive quota redistribution.

    Tier-synchronized round-robin: every slice's best not-yet-picked candidate is taken
    before any slice's 2nd-best, in route order, so an empty slice's unused quota is
    redistributed across the other slices without favoring whichever slice happens to
    have the most backup candidates. Duplicate ids are skipped in place (pulling that
    slice's next buffered candidate) rather than dropping the slot. Stops once *limit* is
    reached or a full pass makes no progress (fewer than *limit* results is then accepted
    rather than issuing extra requests).

    Returns ``(slice_index, item)`` pairs sorted by *slice_index* (route order), with items
    from the same slice kept in their original (quality) order.
    """
    cursors = [0] * len(per_slice_items)
    picked_keys: set[Any] = set()
    output: list[tuple[int, dict]] = []
    progressed = True
    while len(output) < limit and progressed:
        progressed = False
        for slice_idx, items in enumerate(per_slice_items):
            if len(output) >= limit:
                break
            cursor = cursors[slice_idx]
            while cursor < len(items):
                item = items[cursor]
                cursor += 1
                key = dedup_key(item)
                if key is not None and key in picked_keys:
                    continue
                if key is not None:
                    picked_keys.add(key)
                output.append((slice_idx, item))
                progressed = True
                break
            cursors[slice_idx] = cursor

    output.sort(key=lambda pair: pair[0])
    return output


def build_merged_response(slice_responses: list[Response | None], merged: list[tuple[int, dict]]) -> Response:
    """Synthesize a single :class:`Response` from the merged per-slice items.

    ``req``/``x_headers`` are taken from the first slice that answered successfully, so
    display helpers that branch on ``req.endpoint`` keep working unmodified.
    """
    representative = next((resp for resp in slice_responses if resp is not None), None)
    if representative is None:
        raise RuntimeError("All corridor slice requests failed; no response to base the merge on")
    data = make_response({"items": [item for _, item in merged]})
    return Response(req=representative.req, data=data, x_headers=representative.x_headers, raw=None)


async def corridor_search(
    *,
    context: RequestContext,
    limit: int,
    single_call: SingleSliceCall,
    session: HTTPSession,
    threshold_m: float = DEFAULT_STRATIFY_THRESHOLD_M,
    max_slices: int = MAX_SLICES,
) -> Response:
    """Fetch up to *limit* corridor results, stratifying across route slices when worthwhile.

    Falls back to a single ``single_call`` invocation (today's behavior) when ``all_along``
    ranking isn't requested, there is no route, the remaining route is too short to bother
    slicing, or the result count is too low (:func:`should_stratify`) to need spreading out.
    Stratification only helps ``ranking=excursionDistance`` results, which is the mode prone
    to bunching every result near one end of the route; default-relevance corridor searches
    are left untouched.
    """
    if not context.all_along:
        return await single_call(session, context.polyline, context.latitude, context.longitude, limit)

    waypoints = context.route_waypoints
    if not waypoints:
        return await single_call(session, context.polyline, context.latitude, context.longitude, limit)

    trimmed = trim_to_remaining_route(waypoints, context.latitude, context.longitude)
    if len(trimmed) < 2:
        return await single_call(session, context.polyline, context.latitude, context.longitude, limit)

    remaining_length_m = cumulative_distances_m(trimmed)[-1]
    if not should_stratify(remaining_length_m, limit, threshold_m):
        return await single_call(session, context.polyline, context.latitude, context.longitude, limit)

    num_slices = min(limit, max_slices)
    ranges = compute_slice_ranges(trimmed, num_slices)
    polylines = build_slice_polylines(trimmed, ranges)
    at_positions = slice_at_positions(trimmed, ranges)
    slice_specs = [(polyline, at[0], at[1]) for polyline, at in zip(polylines, at_positions)]
    over_fetch_limit = min(
        100, max(DEFAULT_SLICE_OVER_FETCH_LIMIT, math.ceil(limit / num_slices) + REDISTRIBUTION_BUFFER)
    )

    per_slice_items, slice_responses = await fetch_all_slices(session, slice_specs, single_call, over_fetch_limit)
    merged = merge_with_quota_redistribution(per_slice_items, limit)
    return build_merged_response(slice_responses, merged)
