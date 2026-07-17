###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Tests for LabelsMixin."""

from unittest.mock import MagicMock

from here_search_demo.widgets.output_labels import LabelsMixin
from here_search_demo.widgets.state import SearchState


# ---------------------------------------------------------------------------
# Minimal stub host that satisfies LabelsMixin's protocol requirements
# ---------------------------------------------------------------------------


class _StubHost(LabelsMixin):
    """Minimal host combining LabelsMixin with a fake Map API."""

    def __init__(self, zoom=13, state=None):
        self.zoom = zoom
        self.state = state or SearchState()
        self._observers: list = []
        self.added: list = []
        self.removed: list = []
        self._init_labels()

    def observe(self, callback, names=None):
        self._observers.append((callback, names))

    def add(self, obj):
        self.added.append(obj)

    def remove(self, obj):
        self.removed.append(obj)


# ---------------------------------------------------------------------------
# _init_labels
# ---------------------------------------------------------------------------


def test_init_labels_sets_fuel_text_markers():
    host = _StubHost()
    assert host.fuel_text_markers == []


def test_init_labels_sets_label_render_cache():
    host = _StubHost()
    assert host._label_render_cache == {}


def test_init_labels_sets_last_geojson_data_none():
    host = _StubHost()
    assert host._last_geojson_data is None


def test_init_labels_registers_zoom_observer():
    host = _StubHost()
    observer_names = [names for _, names in host._observers]
    assert ["zoom"] in observer_names


# ---------------------------------------------------------------------------
# _clear_labels
# ---------------------------------------------------------------------------


def test_clear_labels_removes_all_markers_from_map():
    host = _StubHost()
    m1, m2 = MagicMock(), MagicMock()
    host.fuel_text_markers = [m1, m2]
    host._clear_labels()
    assert m1 in host.removed
    assert m2 in host.removed


def test_clear_labels_empties_list():
    host = _StubHost()
    host.fuel_text_markers = [MagicMock(), MagicMock()]
    host._clear_labels()
    assert host.fuel_text_markers == []


# ---------------------------------------------------------------------------
# _redraw_labels — basic integration
# ---------------------------------------------------------------------------


def _make_geojson(*titles):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [2.3 + i * 0.5, 48.8]},
                "properties": {"title": title, "_rank": i, "resultType": "place"},
            }
            for i, title in enumerate(titles)
        ],
    }


def test_redraw_labels_clears_previous_markers():
    host = _StubHost()
    old_marker = MagicMock()
    host.fuel_text_markers = [old_marker]
    host._redraw_labels(_make_geojson("Place A"))
    assert old_marker in host.removed


def test_redraw_labels_adds_markers_to_map():
    host = _StubHost()
    host._redraw_labels(_make_geojson("Place A"))
    assert len(host.added) == 1


def test_redraw_labels_empty_collection_clears_only():
    host = _StubHost()
    old = MagicMock()
    host.fuel_text_markers = [old]
    host._redraw_labels({"type": "FeatureCollection", "features": []})
    assert old in host.removed
    assert host.fuel_text_markers == []


# ---------------------------------------------------------------------------
# Zoom-observer bug regression
# ---------------------------------------------------------------------------


def test_zoom_observer_triggers_redraw_when_geojson_present():
    """Regression: zoom observer must use _last_geojson_data (not the defunct
    _last_response_geojson) so label redraw actually fires on zoom changes."""
    host = _StubHost()
    geojson = _make_geojson("Place A")
    host._last_geojson_data = geojson

    redraw_calls = []
    host._redraw_labels = lambda data: redraw_calls.append(data)  # type: ignore[method-assign]

    # Simulate the zoom observer firing (it was registered in _init_labels)
    zoom_observer = next(cb for cb, names in host._observers if names == ["zoom"])
    zoom_observer({"name": "zoom", "new": 14})

    assert len(redraw_calls) == 1
    assert redraw_calls[0] is geojson


def test_zoom_observer_does_not_redraw_when_no_geojson():
    host = _StubHost()
    assert host._last_geojson_data is None

    redraw_calls = []
    host._redraw_labels = lambda data: redraw_calls.append(data)  # type: ignore[method-assign]

    zoom_observer = next(cb for cb, names in host._observers if names == ["zoom"])
    zoom_observer({"name": "zoom", "new": 14})

    assert redraw_calls == []
