###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from flexpolyline import encode as fp_encode

from here_search_demo.route_engine import RouteEngine
from here_search_demo.widgets.route import RouteController
from here_search_demo.widgets.route_geometry import (
    simplify_polyline,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_map():
    m = MagicMock()
    m.center = [48.8, 2.3]
    m.collection = None
    return m


@pytest.fixture
def mock_credentials():
    creds = MagicMock()
    creds.token = "test-token"
    creds.atoken = AsyncMock(return_value="test-token")
    return creds


@pytest.fixture
def controller(mock_map, mock_credentials):
    return RouteController(mock_map, mock_credentials)


# ---------------------------------------------------------------------------
# _init_route_attributes / construction
# ---------------------------------------------------------------------------


def test_initial_state(controller):
    assert controller.start_position is None
    assert controller.stop_position is None
    assert controller.current_position is None
    assert controller.width == 100
    assert controller.all_along is False
    assert controller.minimal_detour is False
    assert controller.route_summary_length is None
    assert controller.search_flexpolyline is None
    assert controller.waypoints_count is None
    assert controller.geojson_w is None
    assert controller.start_w is None
    assert controller.stop_w is None
    assert controller.at_w is None
    assert controller.acquisition_task is None


# ---------------------------------------------------------------------------
# has_any_route_property / has_all_route_properties
# ---------------------------------------------------------------------------


def test_has_any_route_property_false_when_all_none(controller):
    controller.start_position = None
    controller.stop_position = None
    controller.width = None
    assert controller.has_any_route_property() is False


def test_has_any_route_property_true_when_start_set(controller):
    controller.start_position = (48.8, 2.3)
    assert controller.has_any_route_property() is True


def test_has_all_route_properties_false_when_missing_stop(controller):
    controller.start_position = (48.8, 2.3)
    controller.stop_position = None
    controller.width = 100
    assert controller.has_all_route_properties() is False


def test_has_all_route_properties_true(controller):
    controller.start_position = (48.8, 2.3)
    controller.stop_position = (51.5, 0.1)
    controller.width = 100
    assert controller.has_all_route_properties() is True


# ---------------------------------------------------------------------------
# set_route_start / set_route_stop / set_route_width
# ---------------------------------------------------------------------------


def test_set_route_start_does_not_draw_without_stop(controller):
    controller.set_route_start((48.8, 2.3))
    assert controller.start_position == (48.8, 2.3)
    assert controller.acquisition_task is None


def test_set_route_start_delegates_to_engine_setter(controller):
    with patch.object(controller.engine, "set_route_start", wraps=controller.engine.set_route_start) as mock_set:
        controller.set_route_start((48.8, 2.3))
    mock_set.assert_called_once_with((48.8, 2.3))
    assert controller.engine.start_position == (48.8, 2.3)
    assert controller.start_position == (48.8, 2.3)


def test_set_route_stop_does_not_draw_without_start(controller):
    controller.set_route_stop((51.5, 0.1))
    assert controller.stop_position == (51.5, 0.1)
    assert controller.acquisition_task is None


@pytest.mark.asyncio
async def test_set_route_start_triggers_draw_when_complete(controller):
    controller.set_route_stop((51.5, 0.1))
    with patch.object(controller, "draw_corridor", new_callable=AsyncMock) as mock_draw:
        controller.set_route_start((48.8, 2.3))
        assert controller.acquisition_task is not None
        await controller.acquisition_task
        mock_draw.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_route_stop_triggers_draw_when_complete(controller):
    controller.set_route_start((48.8, 2.3))
    with patch.object(controller, "draw_corridor", new_callable=AsyncMock) as mock_draw:
        controller.set_route_stop((51.5, 0.1))
        assert controller.acquisition_task is not None
        await controller.acquisition_task
        mock_draw.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_route_width_triggers_draw_when_complete(controller):
    controller.set_route_start((48.8, 2.3))
    controller.set_route_stop((51.5, 0.1))
    with patch.object(controller, "draw_corridor", new_callable=AsyncMock) as mock_draw:
        controller.set_route_width(200)
        assert controller.width == 200
        await controller.acquisition_task
        mock_draw.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_route_width_modifies_corridor_without_refetching_when_drawn(controller):
    """When a route is already drawn, changing the width redraws the corridor
    (keeping results) instead of fetching the route again via draw_corridor."""
    controller.set_route_start((48.8, 2.3))
    controller.set_route_stop((51.5, 0.1))
    controller._current_waypoints = [(48.8, 2.3), (51.5, 0.1)]

    with (
        patch.object(controller, "draw_corridor", new_callable=AsyncMock) as mock_draw,
        patch.object(controller, "_render_route_widgets", new_callable=AsyncMock) as mock_render,
    ):
        controller.set_route_width(250)
        assert controller.width == 250
        await controller.acquisition_task
        mock_draw.assert_not_awaited()
        mock_render.assert_awaited_once()


@pytest.mark.asyncio
async def test_modify_corridor_width_rebuilds_search_flexpolyline_from_cache(controller):
    """modify_corridor_width rebuilds the search polyline from the cached raw
    route so a subsequent search reflects the current geometry."""
    controller.set_route_start((48.8, 2.3))
    controller.set_route_stop((48.9, 2.4))
    pts = [(48.8, 2.3), (48.9, 2.4)]
    raw = fp_encode(pts)
    controller._current_waypoints = pts
    controller._route_cache[("route", 48.8, 2.3, 48.9, 2.4)] = {"flexpolyline_raw": raw, "waypoints": pts}

    with patch.object(controller, "_render_route_widgets", new_callable=AsyncMock):
        controller.modify_corridor_width()
        await controller.acquisition_task

    assert controller.search_flexpolyline == raw


# ---------------------------------------------------------------------------
# set_route_at
# ---------------------------------------------------------------------------


def test_set_route_at_stores_position(controller):
    controller.set_current_position((49.0, 2.5))
    assert controller.current_position == (49.0, 2.5)


def test_set_route_at_delegates_to_engine_setter(controller):
    with patch.object(
        controller.engine, "set_current_position", wraps=controller.engine.set_current_position
    ) as mock_set:
        controller.set_current_position((49.0, 2.5))
    mock_set.assert_called_once_with((49.0, 2.5))
    assert controller.engine.current_position == (49.0, 2.5)
    assert controller.current_position == (49.0, 2.5)


def test_set_route_at_calls_draw_current_position_when_geojson_present(controller):
    controller.geojson_w = MagicMock()
    with patch.object(controller, "draw_current_position") as mock_draw_current_position:
        controller.set_current_position((49.0, 2.5))
        mock_draw_current_position.assert_called_once()


def test_set_route_at_skips_draw_current_position_without_geojson(controller):
    controller.geojson_w = None
    with patch.object(controller, "draw_current_position") as mock_draw_current_position:
        controller.set_current_position((49.0, 2.5))
        mock_draw_current_position.assert_not_called()


# ---------------------------------------------------------------------------
# all_along option
# ---------------------------------------------------------------------------


def test_all_along_default_is_false(controller):
    assert controller.all_along is False


def test_set_all_along_option(controller):
    controller.all_along = True
    assert controller.all_along is True


# ---------------------------------------------------------------------------
# remove_route_widgets / remove_route_attributes
# ---------------------------------------------------------------------------


def test_remove_route_widgets_clears_widgets(controller, mock_map):
    controller.geojson_w = MagicMock()
    controller.start_w = MagicMock()
    controller.stop_w = MagicMock()
    controller.at_w = MagicMock()

    controller.remove_route_widgets()

    assert mock_map.remove.call_count == 4
    assert controller.geojson_w is None
    assert controller.start_w is None
    assert controller.stop_w is None
    assert controller.at_w is None


def test_remove_route_widgets_is_idempotent_when_empty(controller, mock_map):
    controller.remove_route_widgets()
    mock_map.remove.assert_not_called()


def test_remove_route_attributes_resets_state(controller):
    controller.start_position = (48.8, 2.3)
    controller.stop_position = (51.5, 0.1)
    controller.search_flexpolyline = "abc"
    controller.width = 100
    controller.waypoints_count = 42

    controller.remove_route_attributes()

    assert controller.start_position is None
    assert controller.stop_position is None
    assert controller.search_flexpolyline is None
    assert controller.waypoints_count is None


def test_remove_route_attributes_triggers_removed_callbacks(controller):
    called = []
    controller.on_removed(lambda route: called.append(route))

    controller.remove_route_attributes()

    assert called == [controller]


# ---------------------------------------------------------------------------
# get_route_select_options / get_route_checkbox_options
# ---------------------------------------------------------------------------


def test_get_route_select_options_keys(controller):
    options = controller.get_route_select_options()
    assert set(options) == {"route start", "route stop", "pos on route", "remove route"}


def test_get_route_checkbox_options_keys(controller):
    options = controller.get_route_checkbox_options()
    assert "all along" in options
    get_fn, set_fn = options["all along"]
    assert get_fn() is False
    set_fn(True)
    assert get_fn() is True


def test_get_route_checkbox_options_minimal_detour(controller):
    options = controller.get_route_checkbox_options()
    assert "travel time" in options
    get_fn, set_fn = options["travel time"]
    assert get_fn() is False
    set_fn(True)
    assert get_fn() is True


# ---------------------------------------------------------------------------
# simplify
# ---------------------------------------------------------------------------


def test_simplify_reduces_to_max_points():
    # A large straight line — should collapse to 2 points
    points = [(float(i), 0.0) for i in range(500)]
    result = simplify_polyline(points, max_points=10)
    assert len(result) <= 10


def test_simplify_preserves_endpoints():
    points = [(float(i), float(i % 5)) for i in range(100)]
    result = simplify_polyline(points, max_points=20)
    assert result[0] == points[0]
    assert result[-1] == points[-1]


def test_simplify_returns_original_when_below_max():
    points = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)]
    result = simplify_polyline(points, max_points=50)
    assert result == points


# ---------------------------------------------------------------------------
# build_flexpolyline
# ---------------------------------------------------------------------------


def test_build_flexpolyline_short_route(controller):
    points = [(48.8, 2.3), (48.9, 2.4)]

    raw = fp_encode(points)
    controller.build_flexpolyline(raw, points)
    assert controller.search_flexpolyline == raw


def test_build_flexpolyline_long_route_is_simplified(controller):
    """When waypoints exceed max_waypoints_count the polyline is re-encoded."""
    points = [(float(i) * 0.0001, float(i) * 0.0001) for i in range(RouteEngine.max_waypoints_count + 10)]

    raw = fp_encode(points)
    controller.build_flexpolyline(raw, points)
    # The stored polyline must differ from the original (it was simplified)
    assert controller.search_flexpolyline != raw


# ---------------------------------------------------------------------------
# draw_corridor (integration-style with mocked HTTP)
# ---------------------------------------------------------------------------


@pytest.fixture
def route_response():
    """Minimal HERE routing API response with a short flex-polyline."""

    waypoints = [(48.8, 2.3), (48.85, 2.35), (48.9, 2.4)]
    return {
        "routes": [
            {
                "sections": [
                    {
                        "polyline": fp_encode(waypoints),
                        "summary": {"length": 12345},
                    }
                ]
            }
        ]
    }


@pytest.mark.asyncio
async def test_draw_corridor_calls_map_add(controller, mock_map, route_response):
    mock_response = AsyncMock()
    mock_response.raise_for_status = Mock()
    mock_response.json = AsyncMock(return_value=route_response)

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = Mock(return_value=mock_session_ctx)

    mock_http_ctx = MagicMock()
    mock_http_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_http_ctx.__aexit__ = AsyncMock(return_value=None)

    controller.engine.set_route_start((48.8, 2.3))
    controller.engine.set_route_stop((48.9, 2.4))

    with (
        patch("here_search_demo.route_engine.HTTPSession", return_value=mock_http_ctx),
        patch("here_search_demo.route_engine.IS_BROWSER_RUNTIME", False),
        patch.object(controller.map_instance, "fit_bounds", new_callable=AsyncMock),
    ):
        await controller.draw_corridor()

    # start, stop and geojson markers must have been added
    assert mock_map.add.call_count >= 3
    assert controller.geojson_w is not None
    assert controller.start_w is not None
    assert controller.stop_w is not None
    assert controller.waypoints_count == 3
    assert controller.search_flexpolyline is not None
    assert controller.route_summary_length == 12345
    assert controller.current_position == (48.8, 2.3)


@pytest.mark.asyncio
async def test_draw_corridor_counts_routing_api_calls(mock_map, mock_credentials, route_response):
    calls = []
    controller = RouteController(mock_map, mock_credentials, routing_api_call_handler=lambda: calls.append("routing"))

    mock_response = AsyncMock()
    mock_response.raise_for_status = Mock()
    mock_response.json = AsyncMock(return_value=route_response)

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = Mock(return_value=mock_session_ctx)

    mock_http_ctx = MagicMock()
    mock_http_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_http_ctx.__aexit__ = AsyncMock(return_value=None)

    controller.engine.set_route_start((48.8, 2.3))
    controller.engine.set_route_stop((48.9, 2.4))

    with (
        patch("here_search_demo.route_engine.HTTPSession", return_value=mock_http_ctx),
        patch("here_search_demo.route_engine.IS_BROWSER_RUNTIME", False),
        patch.object(controller.map_instance, "fit_bounds", new_callable=AsyncMock),
    ):
        await controller.draw_corridor()
        await controller.draw_corridor()  # cached route: no additional routing request

    assert calls == ["routing"]


@pytest.mark.asyncio
async def test_draw_corridor_schedules_fit_bounds(controller, mock_map, route_response):
    mock_response = AsyncMock()
    mock_response.raise_for_status = Mock()
    mock_response.json = AsyncMock(return_value=route_response)

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = Mock(return_value=mock_session_ctx)

    mock_http_ctx = MagicMock()
    mock_http_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_http_ctx.__aexit__ = AsyncMock(return_value=None)

    controller.engine.set_route_start((48.8, 2.3))
    controller.engine.set_route_stop((48.9, 2.4))

    fit_bounds_mock = AsyncMock()
    controller.map_instance.fit_bounds = fit_bounds_mock

    with (
        patch("here_search_demo.route_engine.HTTPSession", return_value=mock_http_ctx),
        patch("here_search_demo.route_engine.IS_BROWSER_RUNTIME", False),
    ):
        await controller.draw_corridor()
        # Let the scheduled fit_bounds task run
        await asyncio.sleep(0)

    fit_bounds_mock.assert_awaited_once()
    (south_west, north_east), *_ = fit_bounds_mock.call_args[0]
    # The bounding box must contain the route endpoints
    assert south_west[0] < 48.85  # south of midpoint
    assert north_east[0] > 48.85  # north of midpoint


@pytest.mark.asyncio
async def test_draw_corridor_merges_existing_collection_bbox(controller, mock_map, route_response):
    """The fit bbox should also encompass existing map result features."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = Mock()
    mock_response.json = AsyncMock(return_value=route_response)

    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = Mock(return_value=mock_session_ctx)

    mock_http_ctx = MagicMock()
    mock_http_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_http_ctx.__aexit__ = AsyncMock(return_value=None)

    controller.engine.set_route_start((48.8, 2.3))
    controller.engine.set_route_stop((48.9, 2.4))

    # Simulate a result feature far south of the route
    far_south_lat, far_south_lng = 47.0, 2.0
    mock_collection = MagicMock()
    mock_collection.data = {"features": [{"geometry": {"coordinates": [far_south_lng, far_south_lat]}}]}
    controller.map_instance.collection = mock_collection

    fit_bounds_mock = AsyncMock()
    controller.map_instance.fit_bounds = fit_bounds_mock

    with (
        patch("here_search_demo.route_engine.HTTPSession", return_value=mock_http_ctx),
        patch("here_search_demo.route_engine.IS_BROWSER_RUNTIME", False),
    ):
        await controller.draw_corridor()
        await asyncio.sleep(0)

    fit_bounds_mock.assert_awaited_once()
    (south_west, _north_east) = fit_bounds_mock.call_args[0][0]
    # The south boundary must extend beyond the far-south feature (with padding)
    assert south_west[0] < far_south_lat
