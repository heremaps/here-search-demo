"""Map drawing and bounds methods of the route controller."""

from typing import Any, cast

from flexpolyline import decode
from ipyleaflet import AwesomeIcon, GeoJSON, Marker, Polyline
from ipywidgets import HTML
from shapely import Polygon as ShapelyPolygon
from shapely.geometry import mapping

from .route_geometry import build_corridor


class RouteDrawMixin:
    """Map drawing and bounds methods of the route controller."""

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
