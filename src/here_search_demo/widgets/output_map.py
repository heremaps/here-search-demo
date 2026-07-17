###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
import time
from collections.abc import Callable

from ipyleaflet import GeoJSON, Popup
from ipywidgets import HTML

from ..entity.intent import ActionIntent, SearchIntent
from ..entity.response import Response
from .state import MapState, SearchState
from .input_map import PositionMap
from .output_details import DetailsMixin
from .output_labels import LabelsMixin
from . import output_helpers as fr


class ResponseMap(PositionMap, DetailsMixin, LabelsMixin):
    """Map widget used to render search responses and selection actions.

    The map displays results as GeoJSON markers, optionally adds extra labels
    (fuel prices / TripAdvisor), and can fit bounds to returned items.
    It is also interactive: marker clicks push ``ActionIntent`` instances to
    ``queue`` so upper layers can retrieve details or trigger detour logic.

    :param queue: Queue used for emitted intents from map interactions.
    :param state: Shared state containing ranked response items.
    :param search_center_handler: Callback invoked when the map center changes.
    :param tile_opacity: Base map tile opacity.
    :param kwargs: Forwarded to :class:`~here_search_demo.widgets.input_map.PositionMap`.
    """

    maximum_zoom_level = 18
    default_point_style = {
        "strokeColor": "white",
        "lineWidth": 1,
        "fillOpacity": 0.7,
        "radius": 7,
    }

    def __init__(
        self,
        queue: asyncio.Queue | None = None,
        state: SearchState | None = None,
        search_center_handler: Callable[[tuple[float, float]], None] = None,
        tile_opacity: float = PositionMap.default_tile_opacity,
        **kwargs,
    ):
        self.queue = queue
        self.state = state or SearchState()
        self.collection = None
        self.map_state = MapState()
        self._last_intent: SearchIntent | None = None
        self._fit_task: asyncio.Task | None = None
        super().__init__(position_handler=search_center_handler, tile_opacity=tile_opacity, **kwargs)
        self._init_labels()

    def clear_results(self) -> None:
        self.route.clear_detour_routes()
        if self.collection:
            self.remove(self.collection)
            self.collection = None

        self._clear_labels()
        self._last_geojson_data = None
        self.close_popups()

    def display(self, resp: Response, intent: SearchIntent | None = None, fit: bool = False):

        self.clear_results()

        self._last_resp = resp
        self._last_intent = intent
        bbox = resp.bbox()
        if bbox:
            geojson_data = resp.geojson()
            self._last_geojson_data = geojson_data

            self.collection = GeoJSON(
                data=geojson_data,
                show_bubble=True,
                point_style=ResponseMap.default_point_style,
                style_callback=fr.style_callback,
            )
            self.add(self.collection)

            self._redraw_labels(geojson_data)

            if fit and bbox[0] != bbox[1] and bbox[2] != bbox[3]:
                south, north, east, west = bbox
                height = north - south
                width = east - west
                bounds = ((south - height / 8, west - width / 8), (north + height / 8, east + width / 8))
                if None in (south, north, east, west):
                    return
                self._fit_task = asyncio.create_task(self.fit_bounds(bounds))
            elif fit:
                # Single-point result: just recenter, keep zoom.
                south, north, east, west = bbox
                if None not in (south, west):
                    self._fit_task = asyncio.create_task(self.recenter(south, west))

            self.collection.on_click(self._on_feature_click)
        else:
            self._last_geojson_data = None

    def _on_feature_click(self, event, feature, **kwargs) -> None:
        """Handle a click on a GeoJSON feature: emit an action intent and show the popup."""
        if self.long_press_popup is not None:
            return
        item = feature["properties"]
        rank = item.get("_rank")
        self._emit_action_intent(rank)
        self._show_item_popup(item, rank=rank)
        if self.route.has_route and self.route.ranking_mode.travel_time:
            self._show_detour_route(item)

    def _emit_action_intent(self, rank: int | None) -> None:
        if rank is None:
            return
        response_item = self.state.get_item(rank)
        if response_item is None:
            return
        self.queue.put_nowait(ActionIntent(materialization=response_item, time=time.perf_counter_ns()))

    def _show_detour_route(self, item_data: dict) -> None:
        position = item_data.get("position", {})
        start_position = self.route.search_at_position or self.route.current_position
        if start_position is None:
            return
        start_lat, start_lon = start_position
        via_lat = position.get("lat")
        via_lon = position.get("lng")
        stop_lat, stop_lon = self.route.stop_position
        if via_lat is None or via_lon is None or stop_lat is None or stop_lon is None:
            return
        cache_key = "via", start_lat, start_lon, via_lat, via_lon, stop_lat, stop_lon
        cached = self.route._route_cache.get(cache_key)
        if isinstance(cached, tuple):
            _, _, poly_to, _, _, poly_from = cached
            self.route.draw_detour_routes(poly_from, poly_to)

    def _show_item_popup(self, item_data: dict, rank: int | None = None) -> None:
        if self.long_press_popup is not None:
            return
        position = item_data.get("position", {})
        lat = position.get("lat")
        lng = position.get("lng")
        if lat is None or lng is None:
            return
        self.close_short_press_popup()
        effective_rank = item_data.get("_rank", rank)
        display_rank = f"{effective_rank + 1}: " if isinstance(effective_rank, int) else ""
        title = item_data.get("title", "")
        html = HTML(value=f"<div>{display_rank}{title}</div>" + self.html(item_data, image_variant="original"))
        self.short_press_popup = Popup(
            location=(lat, lng),
            child=html,
            close_button=True,
            auto_close=False,
            close_on_escape_key=True,
            auto_pan=True,
            keep_in_view=False,
            min_width=260,
        )
        self.add(self.short_press_popup)

    def click_result(
        self,
        rank: int,
        *,
        emit_action: bool = True,
        recenter: bool = True,
        show_details: bool = True,
    ) -> None:
        """Programmatically simulate a map click on the result at *rank*.

        This pushes an ``ActionIntent`` to the queue and, when travel-time
        mode is active, draws the detour route for the clicked result.

        Example::

            app.map_w.click_result(6)
        """
        item_data = self.state.get_item_data(rank)
        if item_data is None:
            raise IndexError(f"No result at rank {rank}. Available ranks: {list(self.state.items_data_by_rank)}")
        self.map_state.select_rank(rank)
        if emit_action:
            self._emit_action_intent(rank)
        if self.route.has_route and self.route.ranking_mode.travel_time:
            self._show_detour_route(item_data)
        if recenter:
            position = item_data.get("position", {})
            lat = position.get("lat")
            lng = position.get("lng")
            if lat is not None and lng is not None:
                self._fit_task = asyncio.create_task(self.recenter(lat, lng))
        if show_details:
            self._show_item_popup(item_data, rank=rank)
