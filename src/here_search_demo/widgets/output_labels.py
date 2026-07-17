###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Mixin that adds DivIcon text-label rendering to an ipyleaflet Map subclass.

``LabelsMixin`` is designed to be combined with :class:`ipyleaflet.Map`-derived
classes.  It assumes the host provides:

* ``self.zoom`` — current map zoom level (ipyleaflet ``Map`` trait)
* ``self.add(layer)`` / ``self.remove(layer)`` — ipyleaflet layer management
* ``self.observe(callback, names)`` — traitlets observation
* ``self.state`` — a :class:`~here_search_demo.widgets.state.SearchState` instance
  exposing ``display_titles_by_rank``
"""

from __future__ import annotations

from html import escape

from ipyleaflet import DivIcon, Marker

from here_search_demo.widgets import output_helpers as fr
from here_search_demo.widgets.util import load_css

LABEL_ICON_WIDTH = 250
LABEL_LINE_HEIGHT = 20
LABEL_CSS = load_css("label.css")


class LabelsMixin:
    """Mixin for DivIcon text-label placement with overlap detection.

    Call :meth:`_init_labels` early in the host class ``__init__`` **after**
    ``super().__init__()`` so that ``self.observe`` is available.
    """

    def _init_labels(self) -> None:
        """Initialise label state and wire the zoom-change observer.

        Must be called after the Map widget has been initialised so that
        ``self.observe`` is available.
        """
        self.fuel_text_markers: list[Marker] = []
        self._label_render_cache: dict[tuple, tuple[tuple[float, float, float, float], str, int]] = {}
        self._last_geojson_data: dict | None = None

        def _on_zoom_change(change):
            if change.get("name") == "zoom" and self._last_geojson_data is not None:
                self._redraw_labels(self._last_geojson_data)

        self.observe(_on_zoom_change, names=["zoom"])

    def _clear_labels(self) -> None:
        """Remove all DivIcon text markers from the map and clear the list."""
        for marker in list(self.fuel_text_markers):
            self.remove(marker)
        self.fuel_text_markers.clear()

    def _redraw_labels(self, geojson_data: dict) -> None:
        """Remove and re-place all DivIcon text markers with overlap detection.

        Called from :meth:`display` after new results arrive and from the zoom
        observer so labels stay correctly sized and positioned.

        :param geojson_data: GeoJSON FeatureCollection to label
        """
        self._clear_labels()
        features = geojson_data.get("features", [])
        placed_label_bboxes: list[tuple[float, float, float, float]] = []
        for feature in features:
            self._redraw_label(feature, placed_label_bboxes)

    def _redraw_label(
        self,
        feature: dict,
        placed_label_bboxes: list[tuple[float, float, float, float]],
    ) -> None:
        """Compute and conditionally place a single DivIcon label.

        The label is skipped when its bounding box overlaps any already-placed
        label at the current zoom level.

        :param feature: GeoJSON Feature
        :param placed_label_bboxes: list of already-placed pixel bboxes, mutated in place
        """
        item = feature.get("properties", {})
        lng, lat = feature["geometry"]["coordinates"]
        rank = item.get("_rank")
        vicinity = item.get("_vicinity")
        display_title = self.state.display_titles_by_rank.get(rank, item.get("title", ""))
        if vicinity and len(vicinity) > 1:
            label_parts_list = vicinity
        else:
            label_parts_list = display_title.split(", ") or [display_title]
        label_first = escape(label_parts_list[0])
        vicinity_line = (
            f"<br><span class='here-search-demo-label-line'>{escape(', '.join(label_parts_list[1:]))}</span>"
            if len(label_parts_list) > 1
            else ""
        )
        extra_line = ""
        label_parts = fr.gas_station_label_parts(item)
        if label_parts:
            _, diesel_text = label_parts
            extra_line = (
                f"<br><span class='here-search-demo-label-line'>{escape(diesel_text)}</span>" if diesel_text else ""
            )
        if not extra_line:
            ta_html = fr.ta_label_html(item)
            if ta_html:
                extra_line = f"<br><span class='here-search-demo-label-line'>{ta_html}</span>"
        extra_lines = vicinity_line + extra_line
        icon_anchor_x = 0
        zoom = int(self.zoom) if self.zoom is not None else 13
        cache_key = (zoom, rank, lat, lng, label_first, extra_lines)
        cached = self._label_render_cache.get(cache_key)
        if cached is not None:
            candidate_bbox, label_html, icon_height = cached
        else:
            line_count = 1 + extra_lines.count("<br>")
            icon_height = line_count * LABEL_LINE_HEIGHT
            icon_anchor_y = icon_height // 2
            candidate_bbox = fr.label_pixel_bbox(
                lat, lng, zoom, LABEL_ICON_WIDTH, icon_height, icon_anchor_x, icon_anchor_y
            )
            label_html = (
                f"<style>{LABEL_CSS}</style>"
                "<div class='here-search-demo-label'>"
                f"<b class='here-search-demo-label-title'>{label_first}</b>"
                f"{extra_lines}"
                "</div>"
            )
            self._label_render_cache[cache_key] = (candidate_bbox, label_html, icon_height)
            if len(self._label_render_cache) > 2048:
                self._label_render_cache.clear()
        icon_anchor_y = icon_height // 2
        if not any(fr.pixel_bboxes_overlap(candidate_bbox, placed) for placed in placed_label_bboxes):
            placed_label_bboxes.append(candidate_bbox)
            marker = Marker(
                location=(lat, lng),
                draggable=False,
                icon=DivIcon(
                    html=label_html,
                    icon_size=[LABEL_ICON_WIDTH, icon_height],
                    icon_anchor=[icon_anchor_x, icon_anchor_y],
                ),
            )
            self.fuel_text_markers.append(marker)
            self.add(marker)
