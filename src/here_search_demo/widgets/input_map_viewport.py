###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Viewport centering, zoom and bounds fitting for the position map."""

import asyncio
import math

from ipyleaflet import (
    wait_for_change,
)


class ViewportMixin:
    """Viewport centering, zoom and bounds fitting for the position map."""

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
        lat_target_m = max(abs(self._mercator_y(north) - self._mercator_y(south)), 1e-9)
        world_lat_m = self._mercator_y(mercator_limit) - self._mercator_y(-mercator_limit)

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
        zoom = int(self.zoom) if self.zoom is not None else self.default_zoom_level
        lng += self._lng_delta_for_pixels(x_pixels if x_pixels is not None else self.popup_anchor_x_pixels, zoom)
        return lat, lng

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
        if not self._bounds_ready(self.bounds):
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

        lat_visible_m = self._mercator_y(north) - self._mercator_y(south)
        lat_target_m = self._mercator_y(b_north) - self._mercator_y(b_south)

        zoom_for_lng = current_zoom + math.log2(lng_visible / lng_target) if lng_target > 0 else current_zoom
        zoom_for_lat = current_zoom + math.log2(lat_visible_m / lat_target_m) if lat_target_m > 0 else current_zoom

        new_zoom = max(1, min(self.maximum_zoom_level, int(min(zoom_for_lng, zoom_for_lat))))

        if new_zoom != current_zoom:
            self.zoom = new_zoom
            await wait_for_change(self, "bounds")
