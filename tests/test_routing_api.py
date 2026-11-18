###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Tests for here_search_demo.routing_api.RoutingAPI."""

from unittest.mock import MagicMock, patch

import pytest
from flexpolyline import decode, encode

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.response import Response
from here_search_demo.routing_api import (
    RouteSection,
    RoutingAPI,
    RoutingOptions,
    Waypoint,
    as_waypoints,
)

_ROUTE_PAYLOAD = {
    "routes": [
        {
            "sections": [
                {"summary": {"duration": 30, "length": 500}, "polyline": "p1", "spans": [{"offset": 0}]},
                {"summary": {"duration": 45, "length": 700}, "polyline": "p2"},
            ]
        }
    ]
}


def _api(**kwargs) -> RoutingAPI:
    return RoutingAPI(credentials=MagicMock(token="test-token"), **kwargs)


# ---------------------------------------------------------------------------
# Waypoints
# ---------------------------------------------------------------------------


def test_waypoint_str_without_name_hint():
    assert str(Waypoint(52.5, 13.4)) == "52.5,13.4"


def test_waypoint_str_with_name_hint():
    assert str(Waypoint(52.5, 13.4, "Main Street")) == "52.5,13.4;nameHint=Main Street"


def test_waypoint_make_from_tuples():
    assert Waypoint.make((52.5, 13.4)) == Waypoint(52.5, 13.4)
    assert Waypoint.make((52.5, 13.4, "Main Street")) == Waypoint(52.5, 13.4, "Main Street")
    waypoint = Waypoint(1.0, 2.0)
    assert Waypoint.make(waypoint) is waypoint


def test_as_waypoints_accepts_single_and_sequences():
    assert as_waypoints(None) == []
    assert as_waypoints((52.5, 13.4)) == [Waypoint(52.5, 13.4)]
    assert as_waypoints(Waypoint(52.5, 13.4)) == [Waypoint(52.5, 13.4)]
    assert as_waypoints([(52.5, 13.4), Waypoint(52.6, 13.5, "X")]) == [
        Waypoint(52.5, 13.4),
        Waypoint(52.6, 13.5, "X"),
    ]


# ---------------------------------------------------------------------------
# Request building
# ---------------------------------------------------------------------------


def test_build_routes_request_defaults():
    request = _api()._build_routes_request((52.5, 13.4), (52.4, 13.0))

    assert request.endpoint == Endpoint.ROUTES
    assert request.base_url == "https://router.hereapi.com/v8/routes"
    assert request.params == {
        "origin": "52.5,13.4",
        "destination": "52.4,13.0",
        "transportMode": "car",
        "routingMode": "fast",
        "return": "summary,polyline",
    }


def test_build_routes_request_options_and_overrides():
    api = _api(options=RoutingOptions(transport_mode="truck", return_fields=("summary",), spans=("duration",)))

    request = api._build_routes_request((52.5, 13.4), (52.4, 13.0))
    assert request.params["transportMode"] == "truck"
    assert request.params["return"] == "summary"
    assert request.params["spans"] == "duration"

    request = api._build_routes_request(
        (52.5, 13.4), (52.4, 13.0), transport_mode="car", return_fields=("polyline",), spans=("length",), lang="en"
    )
    assert request.params["transportMode"] == "car"
    assert request.params["return"] == "polyline"
    assert request.params["spans"] == "length"
    assert request.params["lang"] == "en"


def test_build_routes_request_with_multiple_vias():
    request = _api()._build_routes_request(
        (52.5, 13.4), (52.4, 13.0), via=[(52.48, 13.3, "Main Street"), Waypoint(52.45, 13.2)]
    )

    assert request.params["via"] == ["52.48,13.3;nameHint=Main Street", "52.45,13.2"]
    assert request.full.count("via=") == 2


def test_query_repeats_multi_valued_params():
    query = RoutingAPI.query({"origin": "52.5,13.4", "via": ["a", "b"]})

    assert query == [("origin", "52.5,13.4"), ("via", "a"), ("via", "b")]


# ---------------------------------------------------------------------------
# send / cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routes_returns_response_and_caches_it():
    sent = []
    api = _api(on_request_sent=lambda request: sent.append(request))

    async def fake_do_send(session, url, params, headers):
        return url, dict(_ROUTE_PAYLOAD), "raw", {"X-Request-Id": "abc", "Content-Type": "application/json"}

    with patch.object(api, "do_send", side_effect=fake_do_send):
        first = await api.routes(MagicMock(), (52.5, 13.4), (52.4, 13.0))
        second = await api.routes(MagicMock(), (52.5, 13.4), (52.4, 13.0))

    assert isinstance(first, Response)
    assert first.data["routes"][0]["sections"][0]["polyline"] == "p1"
    assert first.x_headers == {"X-Request-Id": "abc"}
    assert second.data == first.data
    assert len(sent) == 1  # the second call was served from the cache


@pytest.mark.asyncio
async def test_send_adds_a_request_id_header():
    seen = {}

    async def fake_do_send(session, url, params, headers):
        seen.update(headers)
        return url, dict(_ROUTE_PAYLOAD), "raw", {}

    api = _api()
    with patch.object(api, "do_send", side_effect=fake_do_send):
        await api.routes(MagicMock(), (52.5, 13.4), (52.4, 13.0), x_headers={"X-Correlation-ID": "cid"})

    assert seen["X-Correlation-ID"] == "cid"
    assert seen["X-Request-Id"].startswith("hsd/")


def test_auth_headers():
    assert _api().auth_headers("t") == {"Authorization": "Bearer t"}


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------


def test_sections_maps_summary_polyline_and_spans():
    response = Response(req=None, data=_ROUTE_PAYLOAD, x_headers={})

    sections = RoutingAPI.sections(response)

    assert sections == [
        RouteSection(duration=30, length=500, polyline="p1", spans=[{"offset": 0}]),
        RouteSection(duration=45, length=700, polyline="p2", spans=[]),
    ]


# ---------------------------------------------------------------------------
# split_at / merge_sections: routes crossing a transport-mode change
# ---------------------------------------------------------------------------


def _sec(points, duration, length, spans=None):
    return RouteSection(duration=duration, length=length, polyline=encode(points), spans=spans or [])


def test_split_at_groups_sections_around_the_via_waypoint():
    """A ferry adds sections, so a leg is not always a single section."""
    via = (51.05, 3.72)
    sections = [
        _sec([(52.52, 13.40), (52.0, 10.0), via], 3600, 100000),  # Berlin -> via
        _sec([via, (50.95, 2.37)], 1800, 50000),  # via -> Calais
        _sec([(50.95, 2.37), (51.13, 1.31)], 5400, 40000),  # channel ferry
        _sec([(51.13, 1.31), (51.51, -0.13)], 2400, 60000),  # Dover -> London
    ]

    to_leg, from_leg = RoutingAPI.split_at(sections, *via)

    assert len(to_leg) == 1
    assert len(from_leg) == 3


def test_merge_sections_sums_totals_and_concatenates_geometry():
    first = _sec([(52.0, 13.0), (51.5, 12.0)], 100, 1000, spans=[{"offset": 0}])
    second = _sec([(51.5, 12.0), (51.0, 11.0)], 200, 2000, spans=[{"offset": 0}])

    merged = RoutingAPI.merge_sections([first, second])

    assert merged.duration == 300
    assert merged.length == 3000
    # The point shared by both sections must not be duplicated.
    assert decode(merged.polyline) == [(52.0, 13.0), (51.5, 12.0), (51.0, 11.0)]
    # Span offsets are rebased onto the concatenated geometry.
    assert [span["offset"] for span in merged.spans] == [0, 1]


def test_merge_sections_returns_single_section_unchanged():
    section = _sec([(52.0, 13.0), (51.5, 12.0)], 100, 1000)

    assert RoutingAPI.merge_sections([section]) is section


def test_split_at_rejects_a_single_section():
    with pytest.raises(ValueError, match="at least two sections"):
        RoutingAPI.split_at([_sec([(52.0, 13.0), (51.5, 12.0)], 100, 1000)], 52.0, 13.0)
