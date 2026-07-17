###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from unittest.mock import AsyncMock, MagicMock

import pytest
from flexpolyline import encode as fp_encode

from here_search_demo.ranking import RankingMode
from here_search_demo.route_engine import RouteEngine


@pytest.fixture
def mock_credentials():
    creds = MagicMock()
    creds.token = "test-token"
    creds.atoken = AsyncMock(return_value="test-token")
    return creds


@pytest.fixture
def engine(mock_credentials):
    return RouteEngine(credentials=mock_credentials)


def test_route_engine_initial_state(engine):
    assert engine.start_position is None
    assert engine.stop_position is None
    assert engine.current_position is None
    assert engine.future_position is None
    assert engine.width == 100
    assert engine.mins_from_pos == 0
    assert engine.ranking_mode == RankingMode()
    assert engine.route_flexpolyline is None
    assert engine.search_flexpolyline is None
    assert engine.route_summary_length is None
    assert engine.waypoints_count is None
    assert engine.has_route is False


def test_route_engine_search_at_position_prefers_future(engine):
    engine.current_position = (48.8, 2.3)
    engine.future_position = (49.1, 2.7)

    assert engine.search_at_position == (49.1, 2.7)


def test_route_engine_search_at_position_falls_back_to_current(engine):
    engine.current_position = (48.8, 2.3)
    engine.future_position = None

    assert engine.search_at_position == (48.8, 2.3)


def test_route_engine_all_along_and_travel_time_options(engine):
    assert engine.all_along is False
    assert engine.minimal_detour is False

    engine.all_along = True
    engine.minimal_detour = True

    assert engine.all_along is True
    assert engine.minimal_detour is True
    assert engine.ranking_mode.server_ranking == "excursionDistance"
    assert engine.ranking_mode.needs_client_rerank is True


def test_route_engine_build_flexpolyline_short_route(engine):
    points = [(48.8, 2.3), (48.9, 2.4)]
    raw = fp_encode(points)

    engine.build_flexpolyline(raw, points)

    assert engine.search_flexpolyline == raw
    assert engine.route_flexpolyline is not None


@pytest.mark.asyncio
async def test_route_engine_update_route_attributes_caches_and_counts_calls(engine):
    route_response = {
        "routes": [
            {
                "sections": [
                    {
                        "polyline": fp_encode([(48.8, 2.3), (48.9, 2.4)]),
                        "summary": {"length": 12345},
                        "spans": [],
                    }
                ]
            }
        ]
    }

    calls = []
    engine.on_routing_request = lambda: calls.append("routing")
    engine.start_position = (48.8, 2.3)
    engine.stop_position = (48.9, 2.4)
    engine._retrieve_route = AsyncMock(return_value=route_response)

    first = await engine.update_route_attributes()
    second = await engine.update_route_attributes()

    assert first["route_summary_length"] == 12345
    assert second["route_summary_length"] == 12345
    assert calls == ["routing"]
    engine._retrieve_route.assert_awaited_once()


@pytest.mark.asyncio
async def test_route_engine_uses_injected_retrieve_callable(mock_credentials):
    route_response = {
        "routes": [
            {
                "sections": [
                    {
                        "polyline": fp_encode([(48.8, 2.3), (48.9, 2.4)]),
                        "summary": {"length": 12345},
                        "spans": [],
                    }
                ]
            }
        ]
    }
    retrieve = AsyncMock(return_value=route_response)
    engine = RouteEngine(credentials=mock_credentials, retrieve_route_fn=retrieve)
    engine.start_position = (48.8, 2.3)
    engine.stop_position = (48.9, 2.4)

    await engine.update_route_attributes()

    retrieve.assert_awaited_once()


def test_route_engine_module_is_headless():
    import inspect

    source = inspect.getsource(RouteEngine)
    assert "ipyleaflet" not in source
    assert "ipywidgets" not in source
