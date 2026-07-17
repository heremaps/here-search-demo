###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from unittest.mock import MagicMock

from ipywidgets import Label

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.request import Request
from here_search_demo.entity.response import Response
from here_search_demo.widgets.app import OneBoxMap


def _widget_controls(app: OneBoxMap) -> list:
    return [control for control in app.map_w.controls if hasattr(control, "widget")]


def test_oneboxmap_map_only_hides_json_and_log():
    app = OneBoxMap(map_only=True, on_map=True)

    assert app.log_handler is None
    assert app.result_json_w is None
    assert tuple(app._root.children) == (app.map_w,)

    controls = _widget_controls(app)
    assert any(app.result_buttons_w in getattr(control.widget, "children", ()) for control in controls)
    assert all(type(control.widget).__name__ != "Output" for control in controls)


def test_oneboxmap_non_basic_keeps_default_layout():
    app = OneBoxMap(on_map=False)

    assert app.result_json_w is not None
    assert len(app._root.children) == 2

    controls = _widget_controls(app)
    assert any(app.result_buttons_w in getattr(control.widget, "children", ()) for control in controls)
    assert all(control.widget is not app.result_json_w for control in controls)


def test_oneboxmap_on_map_keeps_json_and_log_controls():
    app = OneBoxMap(on_map=True)

    assert app.log_handler is not None
    assert tuple(app._root.children) == (app.map_w,)

    controls = _widget_controls(app)
    assert any(app.result_buttons_w in getattr(control.widget, "children", ()) for control in controls)
    assert any(control.widget is app.result_json_w for control in controls)
    assert any(control.widget is app.log_handler.out for control in controls)


def test_oneboxmap_status_label_includes_api_counters():
    app = OneBoxMap(map_only=True, on_map=True)

    assert "api: 0/0" in app.search_center_label_w.value

    app._increment_routing_api_calls()
    assert "api: 0/1" in app.search_center_label_w.value


def test_oneboxmap_get_context_uses_route_state():
    app = OneBoxMap(map_only=True, on_map=True)
    route = app.map_w.route
    route.engine.current_position = (48.0, 9.0)
    route.engine.future_position = (49.0, 10.0)
    route.engine.search_flexpolyline = "abc_poly"
    route.set_route_width(321)
    route.all_along = True

    ctx = app._get_context()

    assert (ctx.latitude, ctx.longitude) == (49.0, 10.0)
    assert ctx.polyline == "abc_poly"
    assert ctx.width == 321
    assert ctx.all_along is True


def test_oneboxmap_get_context_falls_back_to_search_center_without_route_position():
    app = OneBoxMap(map_only=True, on_map=True)
    route = app.map_w.route
    route.engine.current_position = None
    route.engine.future_position = None

    ctx = app._get_context()

    assert (ctx.latitude, ctx.longitude) == app.search_center


def test_oneboxmap_handle_result_list_without_detour_displays_directly():
    app = OneBoxMap(map_only=True, on_map=True)
    route = app.map_w.route
    route.minimal_detour = False
    route.start_position = (48.8, 2.3)
    route.stop_position = (48.9, 2.4)
    route.current_position = (48.8, 2.3)
    route.route_summary_length = 1000

    intent = SearchIntent(kind="submitted_text", materialization="coffee", time=0.0)
    resp = Response(req=Request(endpoint=Endpoint.DISCOVER, params={}), data={"items": []})

    called = {"display": 0}

    def _display_result_list(_intent, _resp, fit=True, clear_query=True):
        called["display"] += 1

    app._display_result_list = _display_result_list

    app.handle_result_list(intent, resp)

    assert called["display"] == 1
    assert app._rerank_task is None


def test_oneboxmap_remove_route_clears_results():
    app = OneBoxMap(map_only=True, on_map=True)
    app.map_w.clear_results = MagicMock()
    app.result_buttons_w._inner_box.children = (Label(value="x"),)
    app._last_result_resp = MagicMock()
    app._last_result_intent = MagicMock()

    app.map_w.route.remove_route_attributes()

    app.map_w.clear_results.assert_called_once()
    assert app.result_buttons_w._inner_box.children == ()
    assert app._last_result_resp is None
    assert app._last_result_intent is None


def test_oneboxmap_change_mins_from_pos_clears_results():
    app = OneBoxMap(map_only=True, on_map=True)
    app.map_w.clear_results = MagicMock()
    app.result_buttons_w._inner_box.children = (Label(value="x"),)
    app._last_result_resp = MagicMock()
    app._last_result_intent = MagicMock()

    app.map_w.route.set_mins_from_pos(5)

    app.map_w.clear_results.assert_called_once()
    assert app.result_buttons_w._inner_box.children == ()
    assert app._last_result_resp is None
    assert app._last_result_intent is None
