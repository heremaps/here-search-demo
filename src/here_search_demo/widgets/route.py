###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
import math
from typing import Callable, Any, cast, TYPE_CHECKING

from here_search_demo.http import HTTPSession

if TYPE_CHECKING:
    from here_search_demo.widgets.input import PositionMap

from flexpolyline import decode, encode
from ipyleaflet import GeoJSON, Marker, Popup, Polygon, AwesomeIcon
from ipywidgets import Text, Layout, HTML
from pyproj import CRS, Transformer
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info
from shapely import LineString, Polygon as ShapelyPolygon
from shapely.geometry import mapping
from shapely.ops import transform


class RouteController:
    routing_api_tpl = (
        "https://router.hereapi.com/v8/routes?apikey={api_key}"
        "&origin={start_lat},{start_lon}"
        "&destination={stop_lat},{stop_lon}"
        "&return=polyline,summary&spans=duration,dynamicSpeedInfo,length"
        "&transportMode=car"
    )
    max_waypoints_count = 2000

    def __init__(self, map_instance: "PositionMap"):
        self.map_instance = map_instance
        self.geojson_w: GeoJSON | None = None
        self.at_w: Marker | None = None
        self.start_w: Marker | None = None
        self.stop_w: Marker | None = None
        self.acquisition_task: asyncio.Task | None = None
        self.popup: Popup | None = None
        self.ui_cleanup: Callable[[], None] | None = None
        self._init_route_attributes()

    def _init_route_attributes(self):
        self.start_position: tuple[float, float] | None = None
        self.stop_position: tuple[float, float] | None = None
        self.at_position: tuple[float, float] | None = None
        self.width: int | None = 100
        self.all_along: bool = False
        self.flexpolyline: str | None = None
        self.waypoints_count: int | None = None

    def set_route_start(self, latlon: tuple[float, float]):
        self.start_position = latlon
        if self.has_all_route_properties():
            self.acquisition_task = asyncio.create_task(self.draw_route())

    def set_route_stop(self, latlon: tuple[float, float]):
        self.stop_position = latlon
        if self.has_all_route_properties():
            self.acquisition_task = asyncio.create_task(self.draw_route())

    def set_route_at(self, latlon: tuple[float, float]):
        self.at_position = latlon
        if self.geojson_w is not None:
            self.draw_at()

    def set_route_width(self, width: int | None):
        self.width = width
        if self.has_all_route_properties():
            self.acquisition_task = asyncio.create_task(self.draw_route())

    def set_all_along_option(self, value: bool):
        self.all_along = value

    def get_all_along_option(self) -> bool:
        return self.all_along

    def remove_route_widgets(self, *_):
        if self.geojson_w:
            self.map_instance.remove(self.geojson_w)
            self.geojson_w = None
        if self.start_w:
            self.map_instance.remove(self.start_w)
            self.start_w = None
        if self.stop_w:
            self.map_instance.remove(self.stop_w)
            self.stop_w = None
        if self.at_w:
            self.map_instance.remove(self.at_w)
            self.at_w = None

    def remove_route_attributes(self, *_):
        self.remove_route_widgets(())
        self._init_route_attributes()

    def get_route_select_options(self) -> dict[str, Callable[[tuple[float, float]], None]]:
        return {
            "route start": self.set_route_start,
            "route stop": self.set_route_stop,
            "pos on route": self.set_route_at,
            "remove route": self.remove_route_attributes,
        }

    def get_route_checkbox_options(self) -> dict[str, tuple[Callable[[], bool], Callable[[bool], None]]]:
        return {
            "all along": (self.get_all_along_option, self.set_all_along_option),
        }

    @staticmethod
    async def build_corridor(
        points: list[tuple[float | Any, float | Any, float | Any] | tuple[float | Any, float | Any]], width: int
    ) -> Polygon:
        line = LineString([(lon, lat) for lat, lon in points])

        aoi = AreaOfInterest(
            west_lon_degree=line.centroid.x,
            south_lat_degree=line.centroid.y,
            east_lon_degree=line.centroid.x,
            north_lat_degree=line.centroid.y,
        )

        infos = query_utm_crs_info(
            datum_name="WGS 84",
            area_of_interest=aoi,
        )

        if not infos:
            raise RuntimeError("No UTM CRS found for this location")

        utm_crs = CRS.from_epsg(infos[0].code)
        to_utm = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True).transform
        to_wgs84 = Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True).transform
        line_utm = transform(to_utm, line)
        buffer_utm = line_utm.buffer(width)
        buffer_wgs84 = transform(to_wgs84, buffer_utm)
        return buffer_wgs84

    def build_width_text_w(self, on_change: Callable[[], None] | None = None):
        width_w = Text(
            description="width:",
            placeholder="(meters)",
            value=str(self.width) if self.width is not None else None,
            continuous_update=False,
            layout=Layout(
                width="100px",  # applies to the input field
                # align_self="flex-start",
                # border="1px solid red",
            ),
            style={"description_width": "initial"},
        )

        def on_width_change(_):
            try:
                width = int(width_w.value) if width_w.value else None
            except ValueError:
                width = None
            self.set_route_width(width)
            if on_change:
                on_change()

        width_w.observe(on_width_change, names="value")
        return width_w

    def get_widgets(self, on_change: Callable[[], None] | None = None):
        return [self.build_width_text_w(on_change)]

    async def draw_route(self):
        routing_url = self.routing_api_tpl.format(
            api_key=self.map_instance.api_key,
            start_lat=self.start_position[0],
            start_lon=self.start_position[1],
            stop_lat=self.stop_position[0],
            stop_lon=self.stop_position[1],
        )

        async with HTTPSession() as session:
            async with session.get(routing_url) as get_response:
                get_response.raise_for_status()
                route = await get_response.json()

        route_flexpolyline = route["routes"][0]["sections"][0]["polyline"]
        waypoints = decode(route_flexpolyline)
        self.build_flexpolyline(route_flexpolyline, waypoints)
        self.waypoints_count = len(waypoints)
        corridor = await RouteController.build_corridor(waypoints, self.width)
        route_geojson = mapping(cast(ShapelyPolygon, corridor))

        self.remove_route_widgets()
        self.geojson_w = GeoJSON(data=route_geojson, style={"color": "blue", "fillOpacity": 0.25})
        self.start_w = Marker(
            location=waypoints[0],
            popup=HTML("<b>Start</b>"),
            icon=AwesomeIcon(color="green", name="play"),
            draggable=False,
        )
        self.stop_w = Marker(
            location=waypoints[-1],
            popup=HTML("<b>Arrival</b>"),
            icon=AwesomeIcon(color="blue", name="flag"),
            draggable=False,
        )

        self.map_instance.add(self.start_w)
        self.map_instance.add(self.stop_w)
        self.map_instance.add(self.geojson_w)
        self.draw_at()

    @staticmethod
    def _perpendicular_distance(
        point: tuple[float, float], segment: tuple[tuple[float, float], tuple[float, float]]
    ) -> float:
        # https://en.wikipedia.org/wiki/Distance_from_a_point_to_a_line
        p1, p2 = segment
        if p1 == p2:
            return math.dist(point, p1)

        num = abs((p2[1] - p1[1]) * point[0] - (p2[0] - p1[0]) * point[1] + p2[0] * p1[1] - p2[1] * p1[0])
        den = math.hypot(p2[1] - p1[1], p2[0] - p1[0])
        return num / den

    @staticmethod
    def douglas_peucker(points, epsilon):
        # https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm
        if len(points) <= 2:
            return points

        start, end = points[0], points[-1]

        # Find the point with the maximum perpendicular distance to the line
        max_dist = 0.0
        index = 0
        for i, point in enumerate(points[1:-1], start=1):
            dist = RouteController._perpendicular_distance(point, (start, end))
            if dist > max_dist:
                index = i
                max_dist = dist

        # If the max distance is greater than epsilon, recursively simplify
        if max_dist > epsilon:
            left = RouteController.douglas_peucker(points[: index + 1], epsilon)
            right = RouteController.douglas_peucker(points[index:], epsilon)
            return left[:-1] + right
        else:
            return [start, end]

    @staticmethod
    def simplify(points: list[tuple[float, float]], max_points: int, iterations: int = 25):
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        bbox_scale = max(max(xs) - min(xs), max(ys) - min(ys))

        eps_low, eps_high = 0.0, bbox_scale
        best = points

        # binary search for the best epsilon that gives us a simplified route with at most max_points
        for _ in range(iterations):
            eps = (eps_low + eps_high) / 2
            simplified = RouteController.douglas_peucker(points, eps)

            if len(simplified) <= max_points:
                best = simplified
                eps_high = eps
            else:
                eps_low = eps

        return best

    def build_flexpolyline(self, flexpolyline: str, waypoints: list[tuple[float, float]]):
        if len(waypoints) > RouteController.max_waypoints_count:
            simplified_waypoints = RouteController.simplify(waypoints, RouteController.max_waypoints_count)
            flexpolyline = encode(simplified_waypoints)
        self.flexpolyline = f"{flexpolyline};w={self.width}"

    def draw_at(self):
        if self.at_position is None:
            self.at_position = self.map_instance.center
        if self.at_w is not None:
            self.map_instance.remove(self.at_w)
        # html = "<img = src='https://raw.githubusercontent.com/heremaps/here-icons/master/icons/travel-transport-tracking/SVG/driving_solid_24px.svg'/>"

        self.at_w = Marker(
            location=self.at_position,
            popup=HTML("<b>at</b>"),
            # icon=AwesomeIcon(color="red", name="car"),
            # icon=DivIcon(
            #    html='<i class="fa fa-car fa-3x" style="color: red;"></i>',
            #    icon_size=[30, 30], # Adjust the bounding box
            #    icon_anchor=[15, 30] # Anchor the bottom tip to the coordinates
            # ),
            icon=AwesomeIcon(name="car", marker_color="blue", icon_color="white", extra_classes="fa-2x"),
            # icon=DivIcon(html=html),
            draggable=False,
        )
        self.map_instance.add(self.at_w)

    def has_any_route_property(self) -> bool:
        return self.start_position is not None or self.stop_position is not None or self.width is not None

    def has_all_route_properties(self) -> bool:
        return self.start_position is not None and self.stop_position is not None and self.width is not None
