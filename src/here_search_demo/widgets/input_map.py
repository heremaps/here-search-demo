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
from typing import Callable, Tuple

from ipyleaflet import (
    FullScreenControl,
    Map,
    Popup,
    ScaleControl,
    TileLayer,
    WidgetControl,
    ZoomControl,
)
from ipywidgets import HTML, Button, Checkbox, HBox, Layout, Select, ToggleButtons, VBox, Widget
from traitlets.utils.bunch import Bunch

from ..auth import Credentials
from .input_map_layers import BaseLayerMixin
from .input_map_viewport import ViewportMixin
from .route import RouteController
from .util import style_html


class PositionMap(ViewportMixin, BaseLayerMixin, Map):
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
        self._credentials = credentials
        self._preferred_language = lang
        self._base_layer_style = "lite.day"

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
            url=self._base_layer_url(self._base_layer_style),
            attribution=self._base_layer_attribution(),
            opacity=tile_opacity if tile_opacity != PositionMap.max_tile_opacity else 1.0,
        )
        self.add(self.base_layer)

        # Create toggle widget for switching between Lite and Satellite
        layer_toggle = ToggleButtons(
            options=[("L", "lite.day"), ("S", "satellite.day")],
            value=self._base_layer_style,
            layout=Layout(width="fit-content"),
            style={"button_width": "30px"},
        )

        # Update layer URL when toggle changes
        def update_layer_style(change):
            if change["name"] == "value":
                self.set_base_layer_style(change["new"])

        layer_toggle.observe(update_layer_style)

        # Wrap in HBox with transparent background and no padding
        toggle_container = HBox(
            [layer_toggle], layout=Layout(width="fit-content", padding="0px", margin="0px", border="none")
        )

        # Add toggle as a widget control. Track the bottom-right controls so
        # their stacking order can be restored after the attribution control is
        # recreated (see :meth:`_replace_base_layer`).
        self._bottom_right_controls = [
            ScaleControl(position="bottomright"),
            WidgetControl(widget=toggle_container, position="bottomright"),
            FullScreenControl(position="bottomright"),
            ZoomControl(position="bottomright"),
        ]
        for control in self._bottom_right_controls:
            self.add(control)
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

    # Minimum expected map container width in pixels.  Used by
    # :meth:`fit_bounds` to detect unreliable viewport bounds during
    # container relayout (see *Unreliable-bounds detection* below).
    _MIN_EXPECTED_CONTAINER_PX = 400

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
