###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Tests for here_search_demo.detour.DetourRanker."""

from unittest.mock import MagicMock, patch

import pytest

from here_search_demo.detour import DetourRanker
from here_search_demo.entity.response import Response
from here_search_demo.entity.request import Request


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_response(items: list[dict]) -> Response:
    req = Request()
    return Response(req=req, data={"items": items}, x_headers={})


def _make_ranker() -> DetourRanker:
    creds = MagicMock()
    creds.token = "test-token"
    return DetourRanker(
        credentials=creds,
        at_pos=(52.40, 12.80),
        stop_pos=(52.06, 11.93),
    )


@pytest.mark.asyncio
async def test_detour_ranker_counts_actual_routing_requests():
    calls = []
    ranker = DetourRanker(
        credentials=MagicMock(token="test-token"),
        at_pos=(52.40, 12.80),
        stop_pos=(52.06, 11.93),
        on_routing_request=lambda: calls.append("routing"),
    )

    payloads = [
        {"routes": [{"sections": [{"summary": {"duration": 60, "length": 1000}, "polyline": "p0"}]}]},
        {
            "routes": [
                {
                    "sections": [
                        {"summary": {"duration": 30, "length": 500}, "polyline": "p1"},
                        {"summary": {"duration": 45, "length": 700}, "polyline": "p2"},
                    ]
                }
            ]
        },
    ]

    async def fake_fetch_route(session, url, headers):
        return payloads.pop(0)

    session = MagicMock()
    with patch.object(ranker, "_fetch_route", side_effect=fake_fetch_route):
        await ranker._get_route_summary(session, 52.0, 13.0, 52.1, 13.1, headers={})
        await ranker.get_route_with_via(session, 52.0, 13.0, 52.05, 13.05, 52.1, 13.1, headers={})

    assert calls == ["routing", "routing"]


# ---------------------------------------------------------------------------
# rerank: empty / no-position items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rerank_empty_items_returns_original():
    ranker = _make_ranker()
    resp = _make_response([])
    result = await ranker.rerank(resp)
    assert result is resp


@pytest.mark.asyncio
async def test_rerank_no_position_items_returns_original():
    ranker = _make_ranker()
    items = [{"title": "A"}, {"title": "B"}]
    resp = _make_response(items)
    result = await ranker.rerank(resp)
    assert result is resp


# ---------------------------------------------------------------------------
# rerank: items with positions are reordered by travel time
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rerank_routing_sorts_by_dur_to_when_not_all_along():
    """Without all_along, lower dur_to sorts first."""
    ranker = _make_ranker()
    # Item 0 "Far":  dur_to=240s→4min, dist_to=110000; dur_from=120s→2min, dist_from=100000 → +10km
    # Item 1 "Near": dur_to=60s→1min,  dist_to=100000; dur_from=60s→1min,  dist_from=102000 → +2km
    # Baseline at→stop: dist=200_000
    items = [
        {"title": "Far", "position": {"lat": 52.3, "lng": 12.5}},
        {"title": "Near", "position": {"lat": 52.4, "lng": 12.6}},
    ]
    resp = _make_response(items)

    # Mock _get_route_summary for baseline (at → stop)
    async def fake_get_route_summary(session, start_lat, start_lon, stop_lat, stop_lon, headers):
        return (0, 200_000, "poly_baseline")

    # Mock get_route_with_via for each result (at → via(result) → stop)
    async def fake_get_route_with_via(
        session, start_lat, start_lon, via_lat, via_lon, stop_lat, stop_lon, headers, name_hint=None
    ):
        if via_lat == 52.3 and via_lon == 12.5:
            # Far: dur_to=240s, dist_to=110000, dur_from=120s, dist_from=100000
            return (240, 110_000, "poly_far_to", 120, 100_000, "poly_far_from")
        elif via_lat == 52.4 and via_lon == 12.6:
            # Near: dur_to=60s, dist_to=100000, dur_from=60s, dist_from=102000
            return (60, 100_000, "poly_near_to", 60, 102_000, "poly_near_from")

    with (
        patch.object(ranker, "_get_route_summary", side_effect=fake_get_route_summary),
        patch.object(ranker, "get_route_with_via", side_effect=fake_get_route_with_via),
        patch("here_search_demo.detour.HTTPSession"),
    ):
        result = await ranker.rerank(resp, all_along=False)

    reranked = result.data["items"]
    assert reranked[0]["title"] == "Near"
    assert reranked[1]["title"] == "Far"
    assert reranked[0]["_detour"]["label"] == "Near (1min, 1min, +2km)"
    assert reranked[1]["_detour"]["label"] == "Far (4min, 2min, +10km)"
    assert reranked[0]["_detour"]["polyline_to"] == "poly_near_to"
    assert reranked[0]["_detour"]["polyline_from"] == "poly_near_from"
    assert reranked[1]["_detour"]["polyline_to"] == "poly_far_to"
    assert reranked[1]["_detour"]["polyline_from"] == "poly_far_from"


@pytest.mark.asyncio
async def test_rerank_routing_sorts_by_total_time_when_all_along():
    """With all_along=True, lower dur_to + dur_from sorts first."""
    ranker = _make_ranker()
    # Item 0 "Quick":  dur_to=120s→2min, dur_from=60s→1min  → total 3min, dist excursion +2km
    # Item 1 "Nearby": dur_to=60s→1min,  dur_from=180s→3min → total 4min, dist excursion +2km
    # Sorted by total: "Quick" (3min) < "Nearby" (4min)
    items = [
        {"title": "Quick", "position": {"lat": 52.3, "lng": 12.5}},
        {"title": "Nearby", "position": {"lat": 52.4, "lng": 12.6}},
    ]
    resp = _make_response(items)

    # Mock _get_route_summary for baseline (at → stop)
    async def fake_get_route_summary(session, start_lat, start_lon, stop_lat, stop_lon, headers):
        return (0, 200_000, "poly_baseline")

    # Mock get_route_with_via for each result
    async def fake_get_route_with_via(
        session, start_lat, start_lon, via_lat, via_lon, stop_lat, stop_lon, headers, name_hint=None
    ):
        if via_lat == 52.3 and via_lon == 12.5:
            # Quick: dur_to=120s, dist_to=101000, dur_from=60s, dist_from=101000
            return (120, 101_000, "poly_quick_to", 60, 101_000, "poly_quick_from")
        elif via_lat == 52.4 and via_lon == 12.6:
            # Nearby: dur_to=60s, dist_to=101000, dur_from=180s, dist_from=101000
            return (60, 101_000, "poly_nearby_to", 180, 101_000, "poly_nearby_from")

    with (
        patch.object(ranker, "_get_route_summary", side_effect=fake_get_route_summary),
        patch.object(ranker, "get_route_with_via", side_effect=fake_get_route_with_via),
        patch("here_search_demo.detour.HTTPSession"),
    ):
        result = await ranker.rerank(resp, all_along=True)

    reranked = result.data["items"]
    assert reranked[0]["title"] == "Quick"
    assert reranked[1]["title"] == "Nearby"


@pytest.mark.asyncio
async def test_rerank_label_shows_minus_sign_when_excursion_is_negative():
    """A result that lies on the direct path shows a '-' excursion."""
    ranker = _make_ranker()
    items = [{"title": "OnTheWay", "position": {"lat": 52.3, "lng": 12.5}}]
    resp = _make_response(items)

    # dist_to + dist_from < dist_at_to_stop → negative excursion
    # excursion = 80_000 + 110_000 - 200_000 = -10_000 → -10km

    # Mock _get_route_summary for baseline (at → stop)
    async def fake_get_route_summary(session, start_lat, start_lon, stop_lat, stop_lon, headers):
        return (0, 200_000, "poly_baseline")

    # Mock get_route_with_via for the result
    async def fake_get_route_with_via(
        session, start_lat, start_lon, via_lat, via_lon, stop_lat, stop_lon, headers, name_hint=None
    ):
        return (30, 80_000, "poly_to", 60, 110_000, "poly_from")

    with (
        patch.object(ranker, "_get_route_summary", side_effect=fake_get_route_summary),
        patch.object(ranker, "get_route_with_via", side_effect=fake_get_route_with_via),
        patch("here_search_demo.detour.HTTPSession"),
    ):
        result = await ranker.rerank(resp)

    label = result.data["items"][0]["_detour"]["label"]
    assert "-10km" in label
    assert "+-" not in label


@pytest.mark.asyncio
async def test_rerank_routing_filters_by_max_excursion():
    """Items beyond max_excursion are dropped."""
    ranker = _make_ranker()
    items = [
        {"title": "OK", "position": {"lat": 52.3, "lng": 12.5}},
        {"title": "TooFar", "position": {"lat": 51.0, "lng": 11.0}},
    ]
    resp = _make_response(items)

    # Baseline at→stop: dist=200_000
    # OK:     dist_to=102500, dist_from=102500 → excursion=5000  → kept
    # TooFar: dist_to=115000, dist_from=105000 → excursion=20000 → dropped

    # Mock _get_route_summary for baseline (at → stop)
    async def fake_get_route_summary(session, start_lat, start_lon, stop_lat, stop_lon, headers):
        return (0, 200_000, "p_baseline")

    # Mock get_route_with_via for each result
    async def fake_get_route_with_via(
        session, start_lat, start_lon, via_lat, via_lon, stop_lat, stop_lon, headers, name_hint=None
    ):
        if via_lat == 52.3 and via_lon == 12.5:
            # OK: excursion = 102500 + 102500 - 200000 = 5000
            return (60, 102_500, "p1", 60, 102_500, "p2")
        elif via_lat == 51.0 and via_lon == 11.0:
            # TooFar: excursion = 115000 + 105000 - 200000 = 20000
            return (60, 115_000, "p3", 60, 105_000, "p4")

    with (
        patch.object(ranker, "_get_route_summary", side_effect=fake_get_route_summary),
        patch.object(ranker, "get_route_with_via", side_effect=fake_get_route_with_via),
        patch("here_search_demo.detour.HTTPSession"),
    ):
        result = await ranker.rerank(resp, max_excursion=15_000)

    reranked = result.data["items"]
    assert len(reranked) == 1
    assert reranked[0]["title"] == "OK"


@pytest.mark.asyncio
async def test_rerank_routing_preserves_response_metadata():
    """req and x_headers are passed through unchanged."""
    ranker = _make_ranker()
    items = [{"title": "A", "position": {"lat": 52.3, "lng": 12.5}}]
    original_req = Request()
    original_headers = {"x-foo": "bar"}
    resp = Response(req=original_req, data={"items": items}, x_headers=original_headers)

    # Mock _get_route_summary for baseline (at → stop)
    async def fake_get_route_summary(session, start_lat, start_lon, stop_lat, stop_lon, headers):
        return (120, 5_000, "poly")

    # Mock get_route_with_via for the result
    async def fake_get_route_with_via(
        session, start_lat, start_lon, via_lat, via_lon, stop_lat, stop_lon, headers, name_hint=None
    ):
        return (120, 5_000, "poly_to", 120, 5_000, "poly_from")

    with (
        patch.object(ranker, "_get_route_summary", side_effect=fake_get_route_summary),
        patch.object(ranker, "get_route_with_via", side_effect=fake_get_route_with_via),
        patch("here_search_demo.detour.HTTPSession"),
    ):
        result = await ranker.rerank(resp)

    assert result.req is original_req
    assert result.x_headers is original_headers
