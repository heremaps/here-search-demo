###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Tests for here_search_demo.stratified_search."""

import math
from unittest.mock import MagicMock

import pytest

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.request import Request, RequestContext
from here_search_demo.entity.response import Response
from here_search_demo.stratified_search import (
    build_merged_response,
    compute_slice_ranges,
    corridor_search,
    should_stratify,
    trim_to_remaining_route,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_response(items: list[dict], endpoint: Endpoint = Endpoint.DISCOVER) -> Response:
    return Response(req=Request(endpoint=endpoint), data={"items": items}, x_headers={})


def _line_waypoints(n: int, lat_step: float = 0.01, lon: float = 0.0, start_lat: float = 0.0):
    """A straight synthetic route: ``n`` points stepping north by ``lat_step`` degrees."""
    return [(start_lat + i * lat_step, lon) for i in range(n)]


# ---------------------------------------------------------------------------
# should_stratify
# ---------------------------------------------------------------------------


def test_should_stratify_boundary():
    assert should_stratify(10_000, 10) is False  # exactly at the 1km/result threshold
    assert should_stratify(10_010, 10) is True  # just above
    assert should_stratify(10_000_000, 1) is False  # limit<=1 never stratifies
    assert should_stratify(None, 10) is False
    assert should_stratify(0, 10) is False


# ---------------------------------------------------------------------------
# trim_to_remaining_route / compute_slice_ranges
# ---------------------------------------------------------------------------


def test_trim_to_remaining_route_drops_waypoints_behind_car():
    waypoints = _line_waypoints(10)
    trimmed = trim_to_remaining_route(waypoints, *waypoints[4])
    assert trimmed == waypoints[4:]


def test_compute_slice_ranges_partitions_by_distance_not_count():
    # 5 points tightly clustered (negligible distance), then 4 points far apart.
    cluster = _line_waypoints(5, lat_step=0.00001)
    far = _line_waypoints(4, lat_step=0.5, start_lat=cluster[-1][0])[1:]
    waypoints = cluster + far
    last_index = len(waypoints) - 1

    ranges = compute_slice_ranges(waypoints, 2)

    # A count-based split of 9 points into two halves would end the first slice around
    # index 4; a distance-based split should swallow the whole (near-zero-length) cluster
    # into the first half, ending well past it.
    assert ranges[0][1] > 4
    assert ranges[-1][1] == last_index


# ---------------------------------------------------------------------------
# corridor_search: fallback parity with today's single-call behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_corridor_search_no_route_falls_back_to_single_call():
    context = RequestContext(latitude=1.0, longitude=2.0, polyline=None, route_waypoints=None, all_along=True)
    calls = []

    async def _call(session, polyline, lat, lon, limit):
        calls.append((polyline, lat, lon, limit))
        return _make_response([{"id": "a"}])

    resp = await corridor_search(context=context, limit=20, single_call=_call, session=MagicMock())

    assert calls == [(None, 1.0, 2.0, 20)]
    assert resp.data["items"] == [{"id": "a"}]


@pytest.mark.asyncio
async def test_corridor_search_short_route_falls_back_to_single_call():
    waypoints = _line_waypoints(5, lat_step=0.001)  # ~444m total, far under threshold
    context = RequestContext(
        latitude=waypoints[0][0],
        longitude=waypoints[0][1],
        polyline="full-route-poly",
        route_waypoints=waypoints,
        all_along=True,
    )
    calls = []

    async def _call(session, polyline, lat, lon, limit):
        calls.append((polyline, lat, lon, limit))
        return _make_response([{"id": "a"}])

    await corridor_search(context=context, limit=20, single_call=_call, session=MagicMock())

    assert calls == [("full-route-poly", waypoints[0][0], waypoints[0][1], 20)]


@pytest.mark.asyncio
async def test_corridor_search_does_not_stratify_when_all_along_is_false():
    # Long enough to stratify if all_along were on, but it isn't.
    waypoints = _line_waypoints(600, lat_step=0.01)  # ~666km
    context = RequestContext(
        latitude=waypoints[0][0], longitude=waypoints[0][1], polyline="full", route_waypoints=waypoints, all_along=False
    )
    calls = []

    async def _call(session, polyline, lat, lon, limit):
        calls.append((polyline, lat, lon, limit))
        return _make_response([{"id": "a"}])

    await corridor_search(context=context, limit=5, single_call=_call, session=MagicMock())

    assert calls == [("full", waypoints[0][0], waypoints[0][1], 5)]


@pytest.mark.asyncio
async def test_corridor_search_uses_remaining_length_not_full_route():
    # The full route is long, but the car is one short hop from the destination.
    waypoints = _line_waypoints(2000, lat_step=0.01)  # ~2226km total
    at_lat, at_lon = waypoints[-2]
    context = RequestContext(
        latitude=at_lat, longitude=at_lon, polyline="full", route_waypoints=waypoints, all_along=True
    )
    calls = []

    async def _call(session, polyline, lat, lon, limit):
        calls.append((polyline, lat, lon, limit))
        return _make_response([{"id": "a"}])

    await corridor_search(context=context, limit=20, single_call=_call, session=MagicMock())

    assert calls == [("full", at_lat, at_lon, 20)]


# ---------------------------------------------------------------------------
# corridor_search: stratified path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_corridor_search_long_route_all_slices_hit_one_per_slice():
    waypoints = _line_waypoints(600, lat_step=0.01)  # ~666km
    context = RequestContext(
        latitude=waypoints[0][0], longitude=waypoints[0][1], polyline="full", route_waypoints=waypoints, all_along=True
    )
    limit = 5
    calls = []

    async def _call(session, polyline, lat, lon, over_fetch):
        idx = len(calls)
        calls.append((polyline, lat, lon, over_fetch))
        return _make_response([{"id": f"slice{idx}-item0"}])

    resp = await corridor_search(context=context, limit=limit, single_call=_call, session=MagicMock())

    assert len(calls) == limit
    assert [lat for _, lat, _, _ in calls] == sorted(lat for _, lat, _, _ in calls)  # route-ordered anchors
    assert len({lat for _, lat, _, _ in calls}) == limit  # each slice anchored at a distinct point
    items = resp.data["items"]
    assert [item["id"] for item in items] == [f"slice{i}-item0" for i in range(limit)]


@pytest.mark.asyncio
async def test_corridor_search_redistributes_when_some_slices_empty():
    waypoints = _line_waypoints(600, lat_step=0.01)
    context = RequestContext(
        latitude=waypoints[0][0], longitude=waypoints[0][1], polyline="full", route_waypoints=waypoints, all_along=True
    )
    limit = 5
    calls = []

    async def _call(session, polyline, lat, lon, over_fetch):
        idx = len(calls)
        calls.append(idx)
        if idx in (1, 3):  # slices 1 and 3 return nothing
            return _make_response([])
        return _make_response([{"id": f"slice{idx}-item{k}"} for k in range(over_fetch)])

    resp = await corridor_search(context=context, limit=limit, single_call=_call, session=MagicMock())

    assert len(calls) == limit  # exactly one call per slice, no second round
    items = resp.data["items"]
    assert len(items) == limit
    assert not any(item["id"].startswith(("slice1-", "slice3-")) for item in items)


@pytest.mark.asyncio
async def test_corridor_search_returns_fewer_than_n_when_redistribution_exhausted():
    waypoints = _line_waypoints(600, lat_step=0.01)
    context = RequestContext(
        latitude=waypoints[0][0], longitude=waypoints[0][1], polyline="full", route_waypoints=waypoints, all_along=True
    )
    limit = 5
    calls = []

    async def _call(session, polyline, lat, lon, over_fetch):
        idx = len(calls)
        calls.append(idx)
        if idx == 0:
            return _make_response([{"id": "only-item"}])
        return _make_response([])

    resp = await corridor_search(context=context, limit=limit, single_call=_call, session=MagicMock())

    assert len(calls) == limit  # still no extra round-trip
    assert resp.data["items"] == [{"id": "only-item"}]


@pytest.mark.asyncio
async def test_corridor_search_caps_slices_at_20_when_limit_exceeds_20():
    waypoints = _line_waypoints(2000, lat_step=0.01)  # ~2226km, D/50 > 30km
    context = RequestContext(
        latitude=waypoints[0][0], longitude=waypoints[0][1], polyline="full", route_waypoints=waypoints, all_along=True
    )
    calls = []

    async def _call(session, polyline, lat, lon, over_fetch):
        calls.append(over_fetch)
        return _make_response([{"id": f"item{len(calls)}"}])

    await corridor_search(context=context, limit=50, single_call=_call, session=MagicMock())

    assert len(calls) == 20


@pytest.mark.asyncio
async def test_over_fetch_limit_scales_so_target_is_reachable():
    waypoints = _line_waypoints(4000, lat_step=0.01)  # ~4452km, D/100 > 30km
    context = RequestContext(
        latitude=waypoints[0][0], longitude=waypoints[0][1], polyline="full", route_waypoints=waypoints, all_along=True
    )
    calls = []

    async def _call(session, polyline, lat, lon, over_fetch):
        idx = len(calls)
        calls.append(over_fetch)
        return _make_response([{"id": f"slice{idx}-item{k}"} for k in range(over_fetch)])

    resp = await corridor_search(context=context, limit=100, single_call=_call, session=MagicMock())

    assert len(calls) == 20
    expected_min_over_fetch = math.ceil(100 / 20) + 2  # REDISTRIBUTION_BUFFER
    assert all(c >= expected_min_over_fetch for c in calls)
    assert len(resp.data["items"]) == 100


@pytest.mark.asyncio
async def test_merge_dedups_overlapping_slice_items_by_id():
    waypoints = _line_waypoints(600, lat_step=0.01)
    context = RequestContext(
        latitude=waypoints[0][0], longitude=waypoints[0][1], polyline="full", route_waypoints=waypoints, all_along=True
    )
    limit = 3
    calls = []

    async def _call(session, polyline, lat, lon, over_fetch):
        idx = len(calls)
        calls.append(idx)
        if idx == 0:
            return _make_response([{"id": "shared"}, {"id": "slice0-backup"}])
        if idx == 1:
            return _make_response([{"id": "shared"}])  # duplicate of slice 0's top pick
        return _make_response([{"id": f"slice{idx}-item"}])

    resp = await corridor_search(context=context, limit=limit, single_call=_call, session=MagicMock())

    ids = [item["id"] for item in resp.data["items"]]
    assert ids.count("shared") == 1
    assert len(ids) == limit


@pytest.mark.asyncio
async def test_corridor_search_slice_failure_is_treated_as_empty_slice():
    waypoints = _line_waypoints(600, lat_step=0.01)
    context = RequestContext(
        latitude=waypoints[0][0], longitude=waypoints[0][1], polyline="full", route_waypoints=waypoints, all_along=True
    )
    limit = 3
    calls = []

    async def _call(session, polyline, lat, lon, over_fetch):
        idx = len(calls)
        calls.append(idx)
        if idx == 1:
            raise RuntimeError("boom")
        return _make_response([{"id": f"slice{idx}-item"}])

    resp = await corridor_search(context=context, limit=limit, single_call=_call, session=MagicMock())

    ids = [item["id"] for item in resp.data["items"]]
    assert "slice1-item" not in ids
    assert len(ids) == 2


@pytest.mark.asyncio
async def test_corridor_search_total_failure_propagates():
    waypoints = _line_waypoints(600, lat_step=0.01)
    context = RequestContext(
        latitude=waypoints[0][0], longitude=waypoints[0][1], polyline="full", route_waypoints=waypoints, all_along=True
    )

    async def _call(session, polyline, lat, lon, over_fetch):
        raise RuntimeError("all down")

    with pytest.raises(RuntimeError, match="all down"):
        await corridor_search(context=context, limit=5, single_call=_call, session=MagicMock())


# ---------------------------------------------------------------------------
# build_merged_response
# ---------------------------------------------------------------------------


def test_build_merged_response_preserves_endpoint_for_bbox_titles():
    resp0 = _make_response([{"id": "a", "title": "A"}], endpoint=Endpoint.BROWSE)
    merged = [(0, {"id": "a", "title": "A"})]

    result = build_merged_response([resp0], merged)

    assert result.req.endpoint == Endpoint.BROWSE
    assert result.titles == ["A"]


def test_build_merged_response_raises_when_every_slice_failed():
    with pytest.raises(RuntimeError):
        build_merged_response([None, None], [])
