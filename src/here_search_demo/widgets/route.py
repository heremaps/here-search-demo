###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
from typing import Callable, TYPE_CHECKING, cast, Any
from traitlets.utils.bunch import Bunch

from ..auth import Credentials
from ..route_engine import RouteEngine
from .route_geometry import build_corridor, haversine_m  # noqa: F401 – available to callers

if TYPE_CHECKING:
    from .input_map import PositionMap

from flexpolyline import decode
from ipyleaflet import GeoJSON, Marker, Polyline, AwesomeIcon
from ipywidgets import Text, Layout, HTML
from shapely import Polygon as ShapelyPolygon
from shapely.geometry import mapping


def _engine_property(name: str) -> property:
    """Build a read/write property that delegates to ``self.engine.<name>``.

    Keeps :class:`RouteEngine` the single source of truth for route state while
    letting callers read and write these fields directly on the controller.
    """

    def getter(self: "RouteController") -> Any:
        return getattr(self.engine, name)

    def setter(self: "RouteController", value: Any) -> None:
        setattr(self.engine, name, value)

    return property(getter, setter)


class RouteController:
    """Route acquisition and rendering controller for map widgets.

    The controller fetches route geometry, renders route overlays/markers,
    and exposes helpers used by notebooks and UI callbacks to update route
    start/stop/at positions and corridor width.

    :param map_instance: Map widget receiving route layers.
    :param credentials: HERE credentials used for routing requests.
    """

    map_instance: "PositionMap"
    # Widgets
    geojson_w: GeoJSON | None
    at_w: Marker | None
    future_position_w: Marker | None  # semi-transparent car at the future position
    start_w: Marker | None
    stop_w: Marker | None

    # Orchestration
    credentials: Credentials
    acquisition_task: asyncio.Task | None
    route_pl: Polyline | None
    _to_detour_pl: Polyline | None
    _from_detour_pl: Polyline | None

    # State delegated to the head-agnostic RouteEngine (single source of truth).
    has_route = _engine_property("has_route")
    start_position = _engine_property("start_position")
    stop_position = _engine_property("stop_position")
    current_position = _engine_property("current_position")
    future_position = _engine_property("future_position")
    width = _engine_property("width")
    mins_from_pos = _engine_property("mins_from_pos")
    ranking_mode = _engine_property("ranking_mode")
    route_flexpolyline = _engine_property("route_flexpolyline")
    search_flexpolyline = _engine_property("search_flexpolyline")
    waypoints_count = _engine_property("waypoints_count")
    route_summary_length = _engine_property("route_summary_length")
    _current_waypoints = _engine_property("_current_waypoints")
    _cached_spans = _engine_property("_cached_spans")
    _route_cache = _engine_property("_route_cache")

    def __init__(
        self,
        map_instance: "PositionMap",
        credentials: Credentials,
        routing_api_call_handler: Callable[[], None] | None = None,
    ):
        self.map_instance = map_instance
        self.credentials = credentials
        self.routing_api_call_handler = routing_api_call_handler
        self.engine = RouteEngine(
            credentials=credentials,
            on_routing_request=routing_api_call_handler,
        )
        self.geojson_w = None
        self.at_w = None
        self.future_position_w = None
        self.start_w = None
        self.stop_w = None
        self.acquisition_task = None
        self._on_drawn_callbacks: list[Callable[["RouteController"], None]] = []
        self._on_removed_callbacks: list[Callable[["RouteController"], None]] = []
        self._init_route_attributes()

    def _init_route_attributes(self):
        self.engine._init_route_attributes()
        self.future_position_w = None
        self.route_pl = None
        self._to_detour_pl = None
        self._from_detour_pl = None

    @property
    def all_along(self) -> bool:
        """Convenience property — reads ``ranking_mode.all_along``."""
        return self.ranking_mode.all_along

    @all_along.setter
    def all_along(self, value: bool):
        self.engine.all_along = value

    @property
    def minimal_detour(self) -> bool:
        """Convenience property — reads ``ranking_mode.travel_time``."""
        return self.ranking_mode.travel_time

    @minimal_detour.setter
    def minimal_detour(self, value: bool):
        self.engine.minimal_detour = value

    @property
    def search_at_position(self) -> tuple[float, float] | None:
        """Position sent as `at=` to the Search API.

        When *mins_from_pos* > 0 this is the point that many minutes ahead
        of the origin along the route; otherwise it is the same as
        ``current_position`` (the car marker location).
        """
        return self.future_position or self.current_position

    def set_route_start(self, latlon: tuple[float, float]):
        """Set the route origin marker and trigger route acquisition when complete.

        :param latlon: ``(lat, lon)`` origin position.
        """
        self.engine.set_route_start(latlon)
        if self.has_all_route_properties():
            self.acquisition_task = asyncio.create_task(self.draw_corridor())

    def set_route_stop(self, latlon: tuple[float, float]):
        """Set the route destination marker and trigger route acquisition when complete.

        :param latlon: ``(lat, lon)`` destination position.
        """
        self.engine.set_route_stop(latlon)
        if self.has_all_route_properties():
            self.acquisition_task = asyncio.create_task(self.draw_corridor())

    def set_current_position(self, latlon: tuple[float, float] | None = None):
        """Set the current car position on the route.

        :param latlon: ``(lat, lon)`` current position.
        """
        self.engine.set_current_position(latlon or self.map_instance.center)
        self.clear_detour_routes()
        self._apply_mins_from_pos()

    def set_mins_from_pos(self, mins: int | None):
        """Set X minutes ahead of the origin position as the new search centre."""
        self.engine.set_mins_from_pos(mins)
        self._apply_mins_from_pos()

    def _apply_mins_from_pos(self, draw: bool = True):
        """Update ``future_position`` from ``current_position`` + ``mins_from_pos``.

        The API search centre (``search_at_position``) is shifted ahead.
        When *draw* is False the marker is not redrawn (used during initial
        route rendering).
        """
        self.clear_detour_routes()
        if draw and (self.geojson_w is not None or self.route_pl is not None):
            self.draw_current_position()
            self.draw_future_position()

    def set_route_width(self, width: int | None):
        """Set corridor width (meters) used for route geometry and rerender it.

        :param width: Corridor width in meters; ``None`` keeps/defaults width.
        """
        self.engine.set_route_width(width)
        if not self.has_all_route_properties():
            return
        if self._current_waypoints is not None:
            self.modify_corridor_width()
        else:
            self.acquisition_task = asyncio.create_task(self.draw_corridor())

    def modify_corridor_width(self):
        # Change the width of an already drawn route
        cache_key = (
            "route",
            self.start_position[0],
            self.start_position[1],
            self.stop_position[0],
            self.stop_position[1],
        )
        if cache_key in self._route_cache:
            self.build_flexpolyline(self._route_cache[cache_key]["flexpolyline_raw"], self._current_waypoints)
        self.acquisition_task = asyncio.create_task(self._render_route_widgets(self._current_waypoints))

    def set_travel_time_option(self, value: bool):
        self.minimal_detour = value
        if self._current_waypoints is not None:
            self.acquisition_task = asyncio.create_task(self._render_route_widgets(self._current_waypoints))
        elif self.has_all_route_properties() and self.route_flexpolyline is not None:
            self.acquisition_task = asyncio.create_task(self.draw_corridor())

    def remove_route_widgets(self, *_):
        if self.geojson_w:
            self.map_instance.remove(self.geojson_w)
            self.geojson_w = None
        if self.route_pl:
            self.map_instance.remove(self.route_pl)
            self.route_pl = None
        self.clear_detour_routes()
        if self.start_w:
            self.map_instance.remove(self.start_w)
            self.start_w = None
        if self.stop_w:
            self.map_instance.remove(self.stop_w)
            self.stop_w = None
        if self.at_w:
            self.map_instance.remove(self.at_w)
            self.at_w = None
        if self.future_position_w:
            self.map_instance.remove(self.future_position_w)
            self.future_position_w = None

    def clear_detour_routes(self):
        """Remove any rendered detour overlays without touching the route."""
        if self._to_detour_pl:
            self.map_instance.remove(self._to_detour_pl)
            self._to_detour_pl = None
        if self._from_detour_pl:
            self.map_instance.remove(self._from_detour_pl)
            self._from_detour_pl = None

    def remove_route_attributes(self, *_):
        self.remove_route_widgets(())
        self._init_route_attributes()
        for cb in self._on_removed_callbacks:
            cb(self)

    def get_route_select_options(self) -> dict[str, Callable[[tuple[float, float]], None]]:
        return {
            "route start": self.set_route_start,
            "route stop": self.set_route_stop,
            "pos on route": self.set_current_position,
            "remove route": self.remove_route_attributes,
        }

    def get_route_checkbox_options(self) -> dict[str, tuple[Callable[[], bool], Callable[[bool], None]]]:
        return {
            "all along": (lambda: self.all_along, lambda v: setattr(self, "all_along", v)),
            "travel time": (lambda: self.minimal_detour, lambda v: self.set_travel_time_option(v)),
        }

    def build_mins_from_pos_text_w(self):
        mins_w = Text(
            description="min from pos:",
            placeholder="minutes",
            value=str(self.mins_from_pos) if self.mins_from_pos is not None else "",
            continuous_update=False,
            layout=Layout(width="155px"),
            style={"description_width": "85px"},
        )

        def on_mins_change(change: Bunch):
            try:
                mins = int(change["new"]) if change["new"].strip() else None
            except ValueError:
                mins = None
            self.set_mins_from_pos(mins)

        mins_w.observe(on_mins_change, names="value")
        return mins_w

    def build_width_text_w(self):
        width_w = Text(
            description="width:",
            placeholder="meters",
            value=str(self.width) if self.width is not None else "",
            continuous_update=False,
            layout=Layout(width="155px"),
            style={"description_width": "85px"},
        )

        def on_width_change(change: Bunch):
            try:
                width = int(change["new"]) if change["new"].strip() else None
            except ValueError:
                width = None
            self.set_route_width(width)

        width_w.observe(on_width_change, names="value")
        return width_w

    def get_text_widgets(self):
        return [self.build_width_text_w(), self.build_mins_from_pos_text_w()]

    def on_drawn(self, callback: Callable[["RouteController"], None]) -> None:
        """Register *callback* to be called each time a route is fully drawn.

        The callback receives this ``RouteController`` instance so it can
        inspect ``flexpolyline``, ``waypoints_count``, ``start_position``, etc.
        Multiple callbacks may be registered; they are called in registration order.

        Example::

            def my_handler(route):
                print(f"Route ready: {route.waypoints_count} waypoints")

            controller.on_drawn(my_handler)
        """
        self._on_drawn_callbacks.append(callback)

    def on_removed(self, callback: Callable[["RouteController"], None]) -> None:
        """Register *callback* to be called when a route is removed."""
        self._on_removed_callbacks.append(callback)

    async def draw_corridor(self):
        try:
            cached = await self.update_route_attributes()

            # Recompute current_position (may shift by mins_from_pos) before the map widgets
            # are rendered so draw_current_position() places the marker at the correct spot.

            if self.current_position is None:
                self.engine.set_current_position(self.start_position)
            else:
                self.engine.set_current_position(self.current_position)
            self._apply_mins_from_pos(draw=False)

            await self._render_route_widgets(cached["waypoints"])

            for cb in self._on_drawn_callbacks:
                cb(self)

        except Exception:
            import traceback

            traceback.print_exc()
        finally:
            self.has_route = True

    async def update_route_attributes(self) -> dict:
        cached = await self.engine.update_route_attributes()
        return cached

    async def _render_route_widgets(self, waypoints: list):
        """Rebuild map widgets from *waypoints* using the current options.

        No API call is made — this is purely a visual update.  It is safe to
        call any time ``minimal_detour`` or ``width`` changes.
        """
        self.remove_route_widgets()
        self.start_w = Marker(
            location=waypoints[0],
            popup=HTML("<b>Start</b>"),
            icon=AwesomeIcon(name="play"),
            draggable=False,
        )
        self.start_w.icon.color = "green"
        self.stop_w = Marker(
            location=waypoints[-1],
            popup=HTML("<b>Arrival</b>"),
            icon=AwesomeIcon(name="flag"),
            draggable=False,
        )
        self.stop_w.icon.color = "blue"
        self.map_instance.add(self.start_w)
        self.map_instance.add(self.stop_w)

        # Move the origin of the car to the start
        self.set_current_position(waypoints[0])
        self.draw_current_position()
        self.draw_future_position()
        # Yield to the event loop so the pending comm messages are flushed
        # to the front-end before the caller continues.
        await asyncio.sleep(0)
        bounds = await self.get_route_bounds(waypoints)

        bbox = await self.get_visible_bounds(*bounds)
        asyncio.create_task(self.map_instance.fit_bounds(bbox))

    async def get_route_bounds(self, waypoints: list) -> tuple[float, float, float, float]:
        if self.ranking_mode.travel_time:
            # Render the raw route polyline (no corridor buffer).
            self.route_pl = Polyline(locations=waypoints, color="blue", weight=3, fill=False)
            self.map_instance.add(self.route_pl)
            lats = [p[0] for p in waypoints]
            lons = [p[1] for p in waypoints]
            c_south, c_north = min(lats), max(lats)
            c_west, c_east = min(lons), max(lons)
        else:
            corridor = await build_corridor(waypoints, self.width)
            route_geojson = mapping(cast(ShapelyPolygon, corridor))
            self.geojson_w = GeoJSON(data=route_geojson, style={"color": "blue", "fillOpacity": 0.25})
            self.map_instance.add(self.geojson_w)
            c_west, c_south, c_east, c_north = corridor.bounds
        return c_east, c_north, c_south, c_west

    async def get_visible_bounds(
        self,
        c_east: Any,
        c_north: Any,
        c_south: Any,
        c_west: Any,
    ) -> tuple[tuple[float | Any, float | Any], tuple[float | Any, float | Any]]:
        # Fit the map to the union of the route and any already-displayed
        # search results so that the full context remains visible.
        collection = getattr(self.map_instance, "collection", None)
        if collection is not None:
            lats_r, lngs_r = [], []
            for feature in collection.data.get("features", []):
                coords = feature.get("geometry", {}).get("coordinates")
                if coords and len(coords) >= 2:
                    lngs_r.append(coords[0])
                    lats_r.append(coords[1])
            if lats_r:
                c_south = min(c_south, min(lats_r))
                c_north = max(c_north, max(lats_r))
                c_west = min(c_west, min(lngs_r))
                c_east = max(c_east, max(lngs_r))
        h = c_north - c_south
        w = c_east - c_west
        bbox = ((c_south - h / 8, c_west - w / 8), (c_north + h / 8, c_east + w / 8))
        return bbox

    def draw_detour_routes(self, route_from: str, route_to: str):
        """Render a green polyline from ``current_position`` → result and a purple
        one from result → ``stop_position``, replacing any previously shown
        detour routes.
        """

        self.clear_detour_routes()

        waypoints_to = decode(route_to)
        waypoints_from = decode(route_from)
        self._to_detour_pl = Polyline(locations=waypoints_to, color="green", weight=2, fill=False)
        self._from_detour_pl = Polyline(locations=waypoints_from, color="purple", weight=2, fill=False)
        self.map_instance.add(self._to_detour_pl)
        self.map_instance.add(self._from_detour_pl)

    def build_flexpolyline(self, flexpolyline: str, waypoints: list[tuple[float, float]]):
        self.engine.build_flexpolyline(flexpolyline, waypoints)

    def draw_current_position(self):
        if self.at_w is not None:
            self.map_instance.remove(self.at_w)

        self.at_w = Marker(
            location=self.current_position,
            popup=HTML("<b>at</b>"),
            icon=AwesomeIcon(name="car", marker_color="blue", icon_color="white"),
            draggable=False,
        )
        self.at_w.icon.extra_classes = "fa-2x"
        self.map_instance.add(self.at_w)

    def draw_future_position(self):
        """Place (or remove) a semi-transparent car marker at the future position.

        The marker is shown when ``future_position`` is set (i.e. *mins_from_pos* > 0)
        and removed otherwise.
        """
        if self.future_position_w is not None:
            try:
                self.map_instance.remove(self.future_position_w)
            except Exception:
                pass
            self.future_position_w = None

        if self.future_position is None:
            return

        self.future_position_w = Marker(
            location=self.future_position,
            popup=HTML(f"<b>in {self.mins_from_pos} min</b>"),
            icon=AwesomeIcon(name="car", marker_color="blue", icon_color="white"),
            opacity=0.4,
            draggable=False,
        )
        self.future_position_w.icon.extra_classes = "fa-2x"
        self.map_instance.add(self.future_position_w)

    def has_any_route_property(self) -> bool:
        return self.start_position is not None or self.stop_position is not None or self.width is not None

    def has_all_route_properties(self) -> bool:
        return self.start_position is not None and self.stop_position is not None and self.width is not None
