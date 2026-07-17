###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################
"""Pure-geometry helpers for route operations.

``build_corridor`` computes a metre-accurate buffer polygon around a route
polyline using a local tangent-plane projection implemented with the Python
standard library, avoiding heavy ``numpy``/``pyproj`` runtime dependencies.
``simplify_polyline`` reduces a polyline to a maximum number of points using a
GEOS Douglas–Peucker simplification.
"""

import math
from array import array
from typing import Any, Sequence

from shapely import LineString
from shapely import get_coordinates, get_num_coordinates
from shapely import simplify as _shapely_simplify
from shapely.geometry import mapping  # noqa: F401 – re-exported for callers
from shapely.ops import transform

_Point = tuple[float | Any, float | Any] | tuple[float | Any, float | Any, float | Any]
_LatLon = tuple[float, float]
_EARTH_RADIUS_M = 6_371_000.0


def _build_flat_coord_array(points: Sequence[_LatLon]) -> array:
    """Pack ``[(x1, y1), ...]`` into a compact ``array('d')`` container."""

    flat = array(
        "d",
        (value for x, y in points for value in (float(x), float(y))),
    )
    return flat


def _pairs_from_flat(flat: array) -> list[_LatLon]:
    """Materialize ``array('d')`` coordinates back into ``[(x, y), ...]``."""
    return [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]


def _bbox_scale_from_flat(flat: array) -> float:
    """Return max(width, height) of the coordinate bounding box."""
    if len(flat) < 4:
        return 0.0

    min_x = max_x = flat[0]
    min_y = max_y = flat[1]
    for i in range(2, len(flat), 2):
        x = flat[i]
        y = flat[i + 1]
        if x < min_x:
            min_x = x
        elif x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        elif y > max_y:
            max_y = y
    return max(max_x - min_x, max_y - min_y)


def _local_metric_projectors(ref_lat: float, ref_lon: float):
    """Return forward/inverse local tangent-plane projectors.

    The forward projector maps ``(lon, lat)`` to local metres around a fixed
    reference point. The inverse projector maps local metres back to WGS84-like
    lon/lat coordinates.
    """
    cos_lat0 = math.cos(math.radians(ref_lat))
    cos_lat0 = max(cos_lat0, 1e-12)  # protect inverse projection near poles

    def to_local(lon: float, lat: float) -> tuple[float, float]:
        x = _EARTH_RADIUS_M * math.radians(lon - ref_lon) * cos_lat0
        y = _EARTH_RADIUS_M * math.radians(lat - ref_lat)
        return x, y

    def to_wgs84(x: float, y: float) -> tuple[float, float]:
        lon = ref_lon + math.degrees(x / (_EARTH_RADIUS_M * cos_lat0))
        lat = ref_lat + math.degrees(y / _EARTH_RADIUS_M)
        return lon, lat

    return to_local, to_wgs84


async def build_corridor(
    points: list[_Point],
    width: int,
):
    """Return a Shapely polygon that is a ``width``-metre buffer around the polyline.

    Parameters
    ----------
    points:
        Route points in ``(lat, lon)`` or ``(lat, lon, z)`` order.
    width:
        Buffer width in metres.
    """
    if not points:
        raise ValueError("points must not be empty")

    line = LineString((float(p[1]), float(p[0])) for p in points)

    ref_lat = float(line.centroid.y)
    ref_lon = float(line.centroid.x)
    to_local, to_wgs84 = _local_metric_projectors(ref_lat, ref_lon)
    line_local = LineString([to_local(lon, lat) for lon, lat in line.coords])
    buffer_local = line_local.buffer(width)
    return transform(to_wgs84, buffer_local)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two ``(lat, lon)`` points."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return _EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def elapsed_sec_at_position(spans: list, waypoints: list, lat: float, lon: float) -> float:
    """Return the elapsed seconds from the route start to the waypoint closest to ``(lat, lon)``.

    Each span dict must contain ``offset`` (int) and ``duration`` (float, seconds).
    The span at index *i* covers waypoints from ``spans[i-1]['offset']`` (or 0) up to
    but excluding ``spans[i]['offset']``.
    """
    # Find the closest waypoint by squared Euclidean distance (fast proxy).
    min_dist2 = float("inf")
    closest_idx = 0
    for i, wp in enumerate(waypoints):
        d2 = (lat - wp[0]) ** 2 + (lon - wp[1]) ** 2
        if d2 < min_dist2:
            min_dist2 = d2
            closest_idx = i

    elapsed = 0.0
    prev_offset = 0
    for span in spans:
        span_end = span["offset"]
        if closest_idx <= span_end:
            span_width = span_end - prev_offset
            if span_width > 0:
                elapsed += span["duration"] * (closest_idx - prev_offset) / span_width
            return elapsed
        elapsed += span["duration"]
        prev_offset = span_end
    return elapsed


def position_at_x_sec_ahead(spans: list, waypoints: list, elapsed: float, x_sec: float) -> tuple[float, float]:
    """Return the ``(lat, lon)`` that is ``x_sec`` seconds ahead of ``elapsed`` along the route.

    If the target is beyond the end of the route the final waypoint is returned.
    """
    if not waypoints:
        raise ValueError("waypoints must not be empty")

    target = elapsed + x_sec
    acc = 0.0
    prev_offset = 0
    for span in spans:
        span_dur = span.get("duration", 0)
        span_len_m = span.get("length", 0)
        span_end = span["offset"]
        if acc + span_dur > target:
            fraction = (target - acc) / span_dur if span_dur > 0 else 0.0
            target_dist = span_len_m * fraction
            pts = waypoints[prev_offset : span_end + 1]
            if len(pts) < 2:
                return pts[0] if pts else waypoints[-1]
            cum = 0.0
            for j in range(len(pts) - 1):
                lat1, lon1 = pts[j]
                lat2, lon2 = pts[j + 1]
                seg = haversine_m(lat1, lon1, lat2, lon2)
                if cum + seg >= target_dist:
                    seg_frac = (target_dist - cum) / seg if seg > 1e-9 else 0.0
                    return lat1 + (lat2 - lat1) * seg_frac, lon1 + (lon2 - lon1) * seg_frac
                cum += seg
            return pts[-1]
        acc += span_dur
        prev_offset = span_end
    return waypoints[-1]


def _do_simplify_polyline(
    bbox_scale: float, iterations: int, line: LineString, max_points: int, points: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    eps_low, eps_high = 0.0, bbox_scale
    best_geo = None

    for _ in range(iterations):
        eps = (eps_low + eps_high) / 2
        simplified = _shapely_simplify(line, eps, preserve_topology=False)
        if get_num_coordinates(simplified) <= max_points:
            best_geo = simplified
            eps_high = eps
        else:
            eps_low = eps

    if best_geo is None:
        return points

    return [tuple(row) for row in get_coordinates(best_geo)]


def simplify_polyline(
    points: list[tuple[float, float]],
    max_points: int,
    iterations: int = 15,
) -> list[tuple[float, float]]:
    """Reduce ``points`` to at most ``max_points`` using GEOS Douglas–Peucker."""
    n = len(points)
    if n <= max_points:
        return points
    if max_points < 2:
        raise ValueError("max_points must be >= 2")

    flat = _build_flat_coord_array(points)
    line = LineString(_pairs_from_flat(flat))
    bbox_scale = _bbox_scale_from_flat(flat)

    return _do_simplify_polyline(bbox_scale, iterations, line, max_points, points)
