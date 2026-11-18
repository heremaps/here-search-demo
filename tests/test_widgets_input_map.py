###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################


import asyncio
from unittest.mock import MagicMock

import pytest

from here_search_demo.auth import Credentials
from here_search_demo.widgets.input_map import PositionMap


@pytest.fixture
def credentials():
    return Credentials()


def test_positionmap_set_position_handler(credentials):
    called = []

    def handler(latlon):
        called.append(latlon)

    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0), position_handler=handler)
    map_obj.center = (3.0, 4.0)
    assert tuple(called[-1]) == (3.0, 4.0)


@pytest.mark.parametrize("api_key", [None, ""])
def test_positionmap_mapnik_without_api_key(credentials, monkeypatch, api_key):
    monkeypatch.setattr(credentials, "_api_key", api_key)
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))

    assert map_obj.base_layer.url == "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    assert "https://www.openstreetmap.org/copyright" in map_obj.base_layer.attribution
    assert "CARTO" not in map_obj.base_layer.attribution

    map_obj.set_base_layer_style("satellite.day")
    assert map_obj.base_layer.url == "https://tile.openstreetmap.org/{z}/{x}/{y}.png"


def test_positionmap_refresh_switches_between_mapnik_and_here(credentials, monkeypatch):
    monkeypatch.setattr(credentials, "_api_key", None)
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))
    opacity = map_obj.base_layer.opacity
    mapnik_attribution = map_obj.base_layer.attribution

    monkeypatch.setattr(credentials, "_api_key", "test-api-key")
    map_obj.refresh_base_layer()
    assert map_obj.base_layer.url.startswith("https://maps.hereapi.com/v3/")
    assert "apiKey=test-api-key" in map_obj.base_layer.url
    assert "style=lite.day" in map_obj.base_layer.url
    assert map_obj.base_layer.attribution == map_obj._here_attribution()
    assert map_obj.base_layer.opacity == opacity

    map_obj.set_base_layer_style("satellite.day")
    assert "style=satellite.day" in map_obj.base_layer.url

    monkeypatch.setattr(credentials, "_api_key", None)
    map_obj.refresh_base_layer()
    assert map_obj.base_layer.url == "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    assert map_obj.base_layer.attribution == mapnik_attribution
    assert map_obj.base_layer.opacity == opacity


def test_positionmap_set_position_handler_zoom(monkeypatch, credentials):
    called = []

    def handler(latlon):
        called.append(latlon)

    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))
    observers = []

    def fake_observe(fn, names=None):
        observers.append(fn)

    monkeypatch.setattr(map_obj, "observe", fake_observe)
    map_obj.bind_position_handler(handler)

    class Change:
        type = "change"
        name = "zoom"
        new = 15

    observers[0](Change())
    assert tuple(called[-1]) == (1.0, 2.0)


def test_positionmap_observer_registration(monkeypatch, credentials):
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))
    called = []

    def handler(lat, lon):
        called.append((lat, lon))

    observed = []

    def fake_observe(fn, names=None):
        observed.append(fn)

    monkeypatch.setattr(map_obj, "observe", fake_observe)
    map_obj.bind_position_handler(handler)
    assert len(observed) == 1
    assert callable(observed[0])


def test_positionmap_has_no_api_key_attribute(credentials):
    """api_key must not leak onto the map instance; it belongs to the route controller."""
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))
    assert not hasattr(map_obj, "api_key")


def test_bind_position_handler_none_handler_skips_dispatch(credentials, monkeypatch):
    """When position_handler is None the observe callback must early-return without error."""
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))
    observers = []

    def fake_observe(fn, names=None):
        observers.append(fn)

    monkeypatch.setattr(map_obj, "observe", fake_observe)
    map_obj.bind_position_handler(None)

    class Change:
        name = "center"
        new = (5.0, 6.0)

    # Must not raise despite no position_handler
    observers[0](Change())


def test_positionmap_set_state_filters_none_bounds(credentials):
    """Test that set_state filters out None values for bound traits."""
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))
    sync_data = {
        "center": (2.0, 3.0),
        "east": None,
        "west": None,
        "north": None,
        "south": None,
    }
    # Should not raise TraitError
    map_obj.set_state(sync_data)
    assert tuple(map_obj.center) == (2.0, 3.0)


def test_positionmap_set_state_sets_bounds_ready_event(credentials):
    """set_state resolves _bounds_ready_event when valid bounds arrive."""
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))
    assert not map_obj._bounds_ready_event.is_set()
    map_obj.set_state({"south": 0.0, "west": 0.0, "north": 1.0, "east": 1.0})
    assert map_obj._bounds_ready_event.is_set()


@pytest.mark.asyncio
async def test_positionmap_recenter():
    """Test recenter method."""
    credentials = Credentials()
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))

    # Mock wait_for_change to avoid hanging
    import here_search_demo.widgets.input_map_viewport as input_module

    original_wait = input_module.wait_for_change

    async def mock_wait(widget, attr):
        pass

    input_module.wait_for_change = mock_wait
    try:
        await map_obj.recenter(3.0, 4.0)
        assert tuple(map_obj.center) == (3.0, 4.0)
    finally:
        input_module.wait_for_change = original_wait


@pytest.mark.asyncio
async def test_positionmap_recenter_same_position():
    """Test recenter when position is already correct."""
    credentials = Credentials()
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))

    # Should not change center if already at target
    await map_obj.recenter(1.0, 2.0)
    assert tuple(map_obj.center) == (1.0, 2.0)


@pytest.mark.asyncio
async def test_positionmap_fit_bounds_waits_for_bounds_then_zooms(credentials):
    """fit_bounds waits for frontend bounds, then computes correct zoom."""
    import here_search_demo.widgets.input_map_viewport as input_module

    original_wait = input_module.wait_for_change

    async def mock_wait(widget, attr):
        pass

    input_module.wait_for_change = mock_wait
    try:
        map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))
        target_bounds = ((38.9, -5.9), (54.0, 15.5))

        # Simulate bounds arriving from frontend shortly after fit_bounds is called
        async def _simulate_bounds():
            await asyncio.sleep(0)
            map_obj.set_state({"south": 45.0, "west": -10.0, "north": 55.0, "east": 20.0, "zoom": 5.0})

        asyncio.create_task(_simulate_bounds())
        await map_obj.fit_bounds(target_bounds)

        # Zoom should be reasonable (not 0 or 1)
        assert map_obj.zoom >= 3
    finally:
        input_module.wait_for_change = original_wait


@pytest.mark.asyncio
async def test_positionmap_fit_bounds_immediate_when_bounds_ready(credentials):
    """fit_bounds proceeds immediately when bounds are already available."""
    import here_search_demo.widgets.input_map_viewport as input_module

    original_wait = input_module.wait_for_change

    async def mock_wait(widget, attr):
        pass

    input_module.wait_for_change = mock_wait
    try:
        map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))
        # Pre-populate bounds
        map_obj.set_state({"south": 45.0, "west": -10.0, "north": 55.0, "east": 20.0, "zoom": 5.0})
        target_bounds = ((38.9, -5.9), (54.0, 15.5))

        await map_obj.fit_bounds(target_bounds)
        assert map_obj.zoom >= 3
    finally:
        input_module.wait_for_change = original_wait


@pytest.mark.asyncio
async def test_positionmap_fit_bounds_timeout_uses_deterministic_zoom(credentials):
    """When bounds never arrive, fit_bounds uses deterministic zoom after timeout."""

    # Patch the timeout to be very short so the test doesn't wait 5s
    original_fit = PositionMap.fit_bounds

    async def fast_timeout_fit(self, bounds):
        # Temporarily monkey-patch asyncio.wait_for timeout
        original_wait_for = asyncio.wait_for

        async def short_wait_for(coro, timeout=None):
            return await original_wait_for(coro, timeout=0.01)

        asyncio.wait_for = short_wait_for
        try:
            return await original_fit(self, bounds)
        finally:
            asyncio.wait_for = original_wait_for

    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))
    target_bounds = ((38.9, -5.9), (54.0, 15.5))

    await fast_timeout_fit(map_obj, target_bounds)
    assert map_obj.zoom >= 3


def test_positionmap_mercator_y():
    """Test _mercator_y static method."""
    # Test equator
    y_eq = PositionMap._mercator_y(0)
    assert abs(y_eq - 0) < 0.01

    # Test positive latitude
    y_pos = PositionMap._mercator_y(45)
    assert y_pos > 0

    # Test negative latitude
    y_neg = PositionMap._mercator_y(-45)
    assert y_neg < 0

    # Test extreme latitudes (should be clamped)
    y_extreme = PositionMap._mercator_y(90)
    assert -float("inf") < y_extreme < float("inf")


def test_positionmap_close_popups(credentials):
    """Test close_popups method."""
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))

    # Create mock popups

    map_obj.long_press_popup = MagicMock()
    map_obj.short_press_popup = MagicMock()

    map_obj.close_popups()

    assert map_obj.long_press_popup is None
    assert map_obj.short_press_popup is None


def test_positionmap_close_long_press_popup(credentials):
    """Test close_long_press_popup method."""
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))

    mock_popup = MagicMock()
    map_obj.long_press_popup = mock_popup

    map_obj.close_long_press_popup()
    assert map_obj.long_press_popup is None


def test_positionmap_close_short_press_popup(credentials):
    """Test close_short_press_popup method."""
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))

    mock_popup = MagicMock()
    map_obj.short_press_popup = mock_popup

    map_obj.close_short_press_popup()
    assert map_obj.short_press_popup is None


def test_positionmap_long_press_handler(credentials):
    """Test long_press_handler method."""
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))

    position = (52.5, 13.4)
    select_options = {"Option 1": lambda pos: None}
    checkbox_options = {"Check 1": (lambda: True, lambda v: None)}

    map_obj.long_press_handler(position, select_options, checkbox_options)

    assert map_obj.long_press_popup is not None
    expected_location = map_obj.popup_anchor_location(position, x_pixels=map_obj.long_press_popup_anchor_x_pixels)
    assert tuple(map_obj.long_press_popup.location) == expected_location


def test_positionmap_set_short_press_interaction(credentials):
    """Test set_short_press_interaction method."""
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))

    # Test with empty options
    map_obj.set_short_press_interaction({})

    # Test that it doesn't crash with click event
    # We need to trigger the interact callback
    # This is a basic smoke test
    assert True  # Method executed without error


def test_positionmap_set_center(credentials):
    """Test set_center method."""
    map_obj = PositionMap(credentials=credentials, center=(1.0, 2.0))
    map_obj.set_center((3.0, 4.0))
    assert tuple(map_obj.center) == (3.0, 4.0)
