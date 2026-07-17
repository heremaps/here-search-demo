###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################
"""Map input widget.

This module contains :class:`PositionMap`, the ipyleaflet-based map widget
that drives position and route interactions.
"""

import asyncio
import math
from typing import Callable, Tuple

from ipyleaflet import (
    FullScreenControl,
    Map,
    Popup,
    ScaleControl,
    TileLayer,
    WidgetControl,
    ZoomControl,
    wait_for_change,
)
from ipywidgets import HTML, Button, Checkbox, HBox, Layout, Select, ToggleButtons, VBox, Widget
from traitlets.utils.bunch import Bunch

from here_search_demo.auth import Credentials
from here_search_demo.widgets.route import RouteController
from here_search_demo.widgets.util import style_html


class PositionMap(Map):
    default_zoom_level = 12
    default_layout = {"height": "600px"}
    default_tile_opacity = 0.6
    long_press_threshold = 0.5
    maximum_zoom_level = 18
    max_tile_opacity = 1.0
    popup_anchor_x_pixels = 10
    long_press_popup_anchor_x_pixels = 16

    def __init__(
        self,
        credentials: Credentials,
        center: Tuple[float, float],
        position_handler: Callable[[tuple[float, float]], None] = None,
        routing_api_call_handler: Callable[[], None] | None = None,
        preferred_language: str | None = None,
        tile_opacity: float | None = None,
        **kvargs,
    ):
        """
        PositionMap instance initializer

        https://github.com/geopandas/xyzservices/blob/main/provider_sources/leaflet-providers-parsed.json

        :param credentials: HERE credentials (provides api_key for basemaps and token for routing)
        :param center:
        :param position_handler:
        :param kvargs:
        """
        # Create HERE tile layers with different styles
        tile_opacity = tile_opacity or PositionMap.default_tile_opacity
        lang = preferred_language or "en"

        # Helper function to generate HERE tile URL
        def here_url(style: str) -> str:
            return (
                f"https://maps.hereapi.com/v3/base/mc/{{z}}/{{x}}/{{y}}/png"
                f"?style={style}&ppi=400&size=512&apiKey={credentials.api_key}&lang={lang}"
            )

        # Initialize map without basemap - we'll add the layer manually
        Map.__init__(
            self,
            center=center,
            zoom=kvargs.pop("zoom", PositionMap.default_zoom_level),
            basemap={},  # Empty basemap
            layout=kvargs.pop("layout", PositionMap.default_layout),
            zoom_control=False,
            scroll_wheel_zoom=True,
            close_popup_on_click=False,
            double_click_zoom=False,
            box_zoom=True,
        )

        # Event set once the frontend has reported valid viewport bounds.
        self._bounds_ready_event = asyncio.Event()
        if PositionMap._bounds_ready(self.bounds):
            self._bounds_ready_event.set()

        # Create single tile layer (default = lite.day)
        self.base_layer = TileLayer(
            url=here_url("lite.day"),
            attribution="© HERE 2026",
            opacity=tile_opacity if tile_opacity != PositionMap.max_tile_opacity else 1.0,
        )
        self.add(self.base_layer)

        # Create toggle widget for switching between Lite and Satellite
        layer_toggle = ToggleButtons(
            options=[("L", "lite.day"), ("S", "satellite.day")],
            value="lite.day",
            layout=Layout(width="fit-content"),
            style={"button_width": "30px"},
        )

        # Update layer URL when toggle changes
        def update_layer_style(change):
            if change["name"] == "value":
                self.base_layer.url = here_url(change["new"])

        layer_toggle.observe(update_layer_style)

        # Wrap in HBox with transparent background and no padding
        toggle_container = HBox(
            [layer_toggle], layout=Layout(width="fit-content", padding="0px", margin="0px", border="none")
        )

        # Add toggle as a widget control
        self.add(WidgetControl(widget=toggle_container, position="topright"))
        self.add(ScaleControl(position="bottomright"))
        self.add(FullScreenControl(position="bottomright"))
        self.add(ZoomControl(position="bottomright"))
        self.bind_position_handler(self.set_center)
        if position_handler:
            self.bind_position_handler(position_handler)

        # Track one long-press and one short-press popup at most.
        self.short_press_popup: Popup | None = None
        self.long_press_popup: Popup | None = None
        self.long_press_task: asyncio.Task | None = None

        # Route-related logic lives in a dedicated controller.
        self.route = RouteController(self, credentials, routing_api_call_handler=routing_api_call_handler)

        # Configure long-press interaction (map options for center / route).
        long_press_select_options = {"map center": self.set_center}
        long_press_select_options.update(self.route.get_route_select_options())
        long_press_checkbox_options = self.route.get_route_checkbox_options()
        long_press_text_widgets = self.route.get_text_widgets()
        self.set_long_press_interaction(
            long_press_select_options, long_press_checkbox_options, *long_press_text_widgets
        )

        if False:

            def observe(change: Bunch):
                print(f"observe: {change.name, change.new}")

            self.observe(observe)

        if False:

            def interact(**change):
                print(f"on_interaction: {change}")

            self.on_interaction(interact)

    # Trait names on ipyleaflet.Map that describe the current viewport bounds.
    _BOUND_TRAITS = frozenset(("east", "west", "north", "south"))

    @staticmethod
    def _bounds_ready(bounds: object) -> bool:
        """Return whether *bounds* is a valid ``((south, west), (north, east))`` pair.

        ipyleaflet initialises ``Map.bounds`` to an empty tuple ``()`` until
        the frontend reports the actual viewport corners.  This helper is
        used to guard code that destructures bounds into two 2-tuples.
        """
        return (
            isinstance(bounds, (tuple, list))
            and len(bounds) == 2
            and all(isinstance(corner, (tuple, list)) and len(corner) == 2 for corner in bounds)
        )

    def set_state(self, sync_data: dict) -> None:
        """Override to silently drop ``None`` bound values.

        During map initialisation the frontend
        can send ``east / west / north / south = null`` before the viewport has
        been computed.  ipyleaflet declares those traits as ``Float``, so
        passing ``None`` raises a ``TraitError``.  We simply skip the update
        for any bound trait that is ``None`` – the correct value will arrive in
        the next state-sync message.

        Also signals ``_bounds_ready_event`` the first time the frontend
        reports valid viewport bounds, unblocking any deferred
        :meth:`fit_bounds` call.
        """
        filtered = {k: v for k, v in sync_data.items() if k not in self._BOUND_TRAITS or v is not None}
        super().set_state(filtered)
        if hasattr(self, "_bounds_ready_event") and not self._bounds_ready_event.is_set():
            if PositionMap._bounds_ready(self.bounds):
                self._bounds_ready_event.set()

    def set_center(self, latlon: tuple[float, float]):
        self.center = latlon

    async def recenter(self, lat: float, lng: float):
        """Pan the map to (lat, lng) without changing the zoom level."""
        await asyncio.sleep(0)
        new_center = (lat, lng)
        if new_center != tuple(self.center):
            self.center = new_center
            await wait_for_change(self, "bounds")

    @staticmethod
    def _mercator_y(lat_deg: float) -> float:
        lat_rad = math.radians(max(-89.9, min(89.9, lat_deg)))
        return math.log(math.tan(math.pi / 4 + lat_rad / 2))

    def _zoom_for_target_bounds(self, bounds: tuple[tuple[float, float], tuple[float, float]]) -> int:
        """Estimate a zoom level that fits *bounds*, independent of the current viewport.

        Assumes a single 256 × 256 tile covers the full world at zoom 0 and
        computes the zoom where the *bounds* extent fills roughly one tile.
        Because the actual map container is always wider than 256 px, this
        is a **conservative lower bound** (the true optimal zoom is typically
        1–2 levels higher).  It is used as a floor when the live viewport
        bounds reported by the frontend are unreliable.
        """
        (b_south, b_west), (b_north, b_east) = bounds
        lng_target = abs(b_east - b_west)
        if lng_target > 180:
            lng_target = 360 - lng_target
        lng_target = max(lng_target, 1e-9)

        mercator_limit = 85.05112878
        north = max(-mercator_limit, min(mercator_limit, b_north))
        south = max(-mercator_limit, min(mercator_limit, b_south))
        lat_target_m = max(abs(PositionMap._mercator_y(north) - PositionMap._mercator_y(south)), 1e-9)
        world_lat_m = PositionMap._mercator_y(mercator_limit) - PositionMap._mercator_y(-mercator_limit)

        zoom_for_lng = math.log2(360.0 / lng_target)
        zoom_for_lat = math.log2(world_lat_m / lat_target_m)
        return max(1, min(self.maximum_zoom_level, int(min(zoom_for_lng, zoom_for_lat))))

    @staticmethod
    def _lng_delta_for_pixels(pixels: int, zoom: int) -> float:
        """Convert a horizontal pixel delta to longitude delta at *zoom*."""
        scale = 256 * (2**zoom)
        return pixels * 360.0 / scale

    def popup_anchor_location(
        self, position: tuple[float, float] | list[float], x_pixels: int | None = None
    ) -> tuple[float, float]:
        """Return a popup anchor adjusted by a small rightward pixel offset."""
        lat, lng = position
        zoom = int(self.zoom) if self.zoom is not None else PositionMap.default_zoom_level
        lng += self._lng_delta_for_pixels(x_pixels if x_pixels is not None else self.popup_anchor_x_pixels, zoom)
        return lat, lng

    # Minimum expected map container width in pixels.  Used by
    # :meth:`fit_bounds` to detect unreliable viewport bounds during
    # container relayout (see *Unreliable-bounds detection* below).
    _MIN_EXPECTED_CONTAINER_PX = 400

    async def fit_bounds(self, bounds: tuple[tuple[float, float], tuple[float, float]]):
        """Adjust center and zoom so that *bounds* is fully visible.

        *bounds* is ``((south, west), (north, east))``.

        Uses Mercator tile-math to jump directly to the correct zoom level.

        **Zoom scale law (Leaflet / XYZ tile convention)**

        Leaflet follows the standard slippy-map tile convention: zoom level 0
        covers the whole world in a single 256 × 256 tile, and every increment
        doubles the tile count in each axis.  As a result the *visible extent*
        in each dimension is halved per zoom-in step::

            visible(Z) = visible(Z₀) / 2^(Z − Z₀)

        Solving for the target zoom that makes ``target`` extent fit within the
        current ``visible`` extent yields::

            new_zoom = current_zoom + log₂(visible / target)

        A ratio > 1 (target smaller than what is currently visible) gives a
        positive delta → zoom in; a ratio < 1 → zoom out.  The latitude axis
        uses Mercator-projected values (``_mercator_y``) instead of raw degrees
        because tile rows are spaced uniformly in Mercator space, not in degrees.
        ``min(zoom_for_lng, zoom_for_lat)`` picks the more restrictive axis so
        that both dimensions fit on screen simultaneously.

        **Unreliable-bounds detection**

        When ipyleaflet relays a centre/zoom change to the Leaflet frontend,
        the browser responds with updated ``east / west / north / south``
        traits.  If the map container is still being laid out (e.g. the
        notebook cell has just been rendered), those bounds can reflect a
        transient, near-zero container size — a few pixels wide instead of
        the actual widget width.

        We detect this by comparing the reported longitude span against
        what a container of at least ``_MIN_EXPECTED_CONTAINER_PX`` pixels
        would show at the current zoom.  If the reported span is less than
        25 % of that expectation, the bounds are considered unreliable and
        the method falls back to :meth:`_zoom_for_target_bounds` — a
        conservative, viewport-independent estimate.  When the fallback
        zoom would zoom *out* relative to what a previous (reliable) call
        already set, we skip the change entirely to avoid overwriting a
        correct result.
        """
        await asyncio.sleep(0)
        (b_south, b_west), (b_north, b_east) = bounds
        center = b_south + (b_north - b_south) / 2, b_west + (b_east - b_west) / 2

        # Wait for the frontend to report valid viewport bounds before
        # computing zoom.  Without this the Mercator math has no reference.
        if not PositionMap._bounds_ready(self.bounds):
            # Set center early so the map pans while we wait for layout.
            if center != tuple(self.center):
                self.center = center
            try:
                await asyncio.wait_for(self._bounds_ready_event.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self.zoom = self._zoom_for_target_bounds(bounds)
                return

        if center != tuple(self.center):
            self.center = center
            await wait_for_change(self, "bounds")

        # Compute the required zoom level from current visible bounds.
        (south, west), (north, east) = self.bounds
        current_zoom = self.zoom

        lng_visible = east - west

        # Sanity-check the reported viewport extent (see docstring above).
        min_expected_lng = self._MIN_EXPECTED_CONTAINER_PX * 360.0 / (256 * (2**current_zoom))
        if lng_visible < min_expected_lng * 0.25:
            new_zoom = self._zoom_for_target_bounds(bounds)
            # Don't zoom out from what a prior (reliable) call already set.
            if new_zoom < current_zoom:
                return
            if new_zoom != current_zoom:
                self.zoom = new_zoom
                await wait_for_change(self, "bounds")
            return

        lng_target = b_east - b_west

        lat_visible_m = PositionMap._mercator_y(north) - PositionMap._mercator_y(south)
        lat_target_m = PositionMap._mercator_y(b_north) - PositionMap._mercator_y(b_south)

        zoom_for_lng = current_zoom + math.log2(lng_visible / lng_target) if lng_target > 0 else current_zoom
        zoom_for_lat = current_zoom + math.log2(lat_visible_m / lat_target_m) if lat_target_m > 0 else current_zoom

        new_zoom = max(1, min(self.maximum_zoom_level, int(min(zoom_for_lng, zoom_for_lat))))

        if new_zoom != current_zoom:
            self.zoom = new_zoom
            await wait_for_change(self, "bounds")

    def long_press_handler(self, position, long_press_select_options, long_press_checkbox_options, *widgets: Widget):
        """Handle a long press at the given position.

        Ensures only a single long-press popup is visible, and closes any
        existing short-press popup to avoid overlapping controls.
        """
        self.close_popups()

        close_btn = self.build_close_btn()

        map_action_selection_w = Select(
            options=long_press_select_options,
            rows=len(long_press_select_options),
            value=None,
            layout=Layout(
                width="155px",
                align_self="flex-start",
            ),
        )

        def action_choice_handler(change: Bunch):
            handler: Callable[[tuple[float, float]], None] = long_press_select_options[change["new"]]
            handler(position)
            self.close_long_press_popup()

        map_action_selection_w.observe(action_choice_handler, names="label")

        checkboxes = []
        for text, (get_function, set_function) in long_press_checkbox_options.items():
            checkbox = Checkbox(
                description=text,
                value=get_function(),
                layout=Layout(width="155px"),
                style={"description_width": "initial"},
            )

            def handler(change: Bunch, _set=set_function):
                _set(change["new"])

            checkbox.observe(handler, names="value")
            checkboxes.append(checkbox)
        map_action_checkbox_w = VBox(checkboxes, layout=Layout(margin="4px 0px 0px 0px"))

        popup_css = style_html("popup.css")

        content = VBox(
            [
                popup_css,
                close_btn,
                map_action_selection_w,
                *widgets,  # width and min from pos widgets
                map_action_checkbox_w,
            ],
            layout=Layout(
                width="160px",
                align_items="flex-start",
                margin="0px",
                padding="0px",
            ),
        )
        self.long_press_popup = Popup(
            location=self.popup_anchor_location(position, x_pixels=self.long_press_popup_anchor_x_pixels),
            child=content,
            close_button=False,  # We provide our own close button
            auto_close=False,
            close_on_escape_key=True,
            auto_pan=False,
            min_width=160,
            max_width=175,
        )
        self.add(self.long_press_popup)

    def close_long_press_popup(self):
        if self.long_press_popup is not None:
            self.remove(self.long_press_popup)
            self.long_press_popup = None

    def close_short_press_popup(self):
        if self.short_press_popup is not None:
            self.remove(self.short_press_popup)
            self.short_press_popup = None

    def close_popups(self):
        """Close any visible long-press or short-press popup.

        Ensures that at most one of each popup type is visible at any
        time and that they remain mutually exclusive.
        """
        self.close_long_press_popup()
        self.close_short_press_popup()

    def set_short_press_interaction(self, short_press_options: dict | None = None):
        """Configure short-press (simple click) behavior.

        This is separate from long-press handling. A short press should
        only ever show a short_press_popup, and will close any existing
        long-press popup first.
        """
        short_press_options = short_press_options or {}

        def interact(**event):
            if event.get("type") != "click":
                return

            # A short press should not leave a long-press popup visible.
            self.close_long_press_popup()
            # Also close any previous short-press popup so only one exists.
            self.close_short_press_popup()

            # Implement your specific short-press popup creation here.
            # For now we only record the click location if provided.
            position = event.get("coordinates")
            if position is None:
                return

            close_btn = Button(description="Close", layout=Layout(width="32px"))

            def on_click_handler(btn: Button):
                self.close_short_press_popup()

            close_btn.on_click(on_click_handler)
            content = VBox([close_btn, HTML(value="Short press")])
            self.short_press_popup = Popup(
                location=self.popup_anchor_location(position),
                child=content,
                close_button=True,
                auto_close=True,
                close_on_escape_key=True,
                auto_pan=False,
            )
            self.add(self.short_press_popup)

        self.on_interaction(interact)

    def set_long_press_interaction(
        self,
        long_press_select_options: dict | None = None,
        long_press_checkbox_options: dict | None = None,
        *widgets: Widget,
    ):
        async def defer_map_position_task(position):
            try:
                await asyncio.sleep(self.long_press_threshold)
                # Ensure that this really is a long press by the time the
                # delay elapses; if the task has been cleared, skip.
                if self.long_press_task is not None:
                    self.long_press_handler(position, long_press_select_options, long_press_checkbox_options, *widgets)
            except asyncio.CancelledError:
                pass

        def interact(**event):
            if event["type"] == "mousedown":
                if self.long_press_task is not None and not self.long_press_task.done():
                    self.long_press_task.cancel()
                self.long_press_task = asyncio.create_task(defer_map_position_task(event["coordinates"]))
            elif event["type"] == "mouseup":
                # Mouse released before threshold -> this was a short press;
                # cancel the long-press task and let any click handler deal
                # with short-press behavior.
                if self.long_press_task is not None and not self.long_press_task.done():
                    self.long_press_task.cancel()
                    self.long_press_task = None

        self.on_interaction(interact)

    def build_close_btn(self):
        close_btn = Button(
            icon="times",
            layout=Layout(
                width="20px",
                height="20px",
                padding="0px",
                border="none",
                align_self="flex-end",
                margin="0px",
            ),
            style={"button_color": "transparent"},
        )

        def on_click_handler(btn: Button):
            self.close_long_press_popup()

        close_btn.on_click(on_click_handler)
        return close_btn

    def bind_position_handler(self, position_handler: Callable[[tuple[float, float]], None] | None = None):
        def observe(change: Bunch):
            # Any map movement closes the long-press popup so it does not
            # linger over a different map region.
            self.close_long_press_popup()
            # Optionally also close short-press popup to not  persist across pans/zooms.
            # self.close_short_press_popup()
            if not position_handler:
                return
            if change.name in "center":
                position_handler(change.new)
            elif change.name == "zoom":
                position_handler(self.center)

        self.observe(observe, ["center", "zoom"])
