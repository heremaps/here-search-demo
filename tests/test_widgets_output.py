###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
from unittest.mock import MagicMock

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.request import Request
from here_search_demo.entity.response import LocationResponseItem, Response
from here_search_demo.widgets.output_buttons import SearchResultButtons
from here_search_demo.widgets.output_map import ResponseMap
from here_search_demo.widgets.route import RouteController
from here_search_demo.widgets.state import MapState, SearchState


class _FakeGeoJSON:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._click = None
        self._hover = None
        self._mouseout = None

    def on_click(self, handler):
        self._click = handler

    def on_hover(self, handler):
        self._hover = handler

    def on_mouseout(self, handler):
        self._mouseout = handler


class _GeoFactory:
    def __init__(self):
        self.instances = []

    def __call__(self, **kwargs):
        inst = _FakeGeoJSON(**kwargs)
        self.instances.append(inst)
        return inst


class _FakePopup:
    def __init__(
        self,
        location=None,
        child=None,
        close_button=True,
        auto_close=False,
        close_on_escape_key=True,
        auto_pan=False,
        keep_in_view=False,
        min_width=0,
    ):
        # Mirror the Popup signature used in ResponseMap.display sufficiently
        # for tests. Only auto_pan is asserted in tests; others are kept for
        # compatibility.
        self.auto_pan = auto_pan
        self.child = child
        self.close_button = close_button
        self.opened = False
        self.location = location
        self.keep_in_view = keep_in_view
        self.min_width = min_width

    def open_popup(self, location):
        self.opened = True
        self.location = location

    def close_popup(self):
        self.opened = False


class _DummyQueue:
    def __init__(self):
        self.items = []

    def put_nowait(self, item):
        self.items.append(item)


class _StubResponseMap(ResponseMap):
    """Lightweight test double that captures objects added to the map.

    We do *not* add any attributes that do not exist on the real
    implementation; instead we only surface calls to the public
    Map.add/remove methods so tests can assert on what ResponseMap
    actually adds to the map.
    """

    def __init__(self, queue, state):
        # Match ResponseMap's public constructor surface as far as tests
        # care: a queue and a SearchState instance.
        self.queue = queue
        self.state = state
        self.collection = None
        self.fuel_text_markers = []
        self._label_render_cache = {}
        self._last_geojson_data = None
        self.map_state = MapState()
        self.added = []
        self.removed = []
        self.long_press_popup = None
        self.short_press_popup = None
        self.route = RouteController(self, MagicMock())

    def add(self, obj):  # type: ignore[override]
        # Record every object added (GeoJSON first, then Popup on click).
        self.added.append(obj)

    def remove(self, obj):  # type: ignore[override]
        self.removed.append(obj)


def _sample_response():
    return Response(
        req=Request(endpoint=Endpoint.DISCOVER),
        data={
            "items": [
                {
                    "title": "Foo",
                    "resultType": "place",
                    "position": {"lat": 1, "lng": 2},
                    "categories": [{"primary": True, "id": "123", "name": "Test"}],
                    "address": {"label": "Foo, Somewhere"},
                    "openingHours": [],
                }
            ]
        },
        x_headers={},
    )


async def test_response_map_display_emits_more_details(monkeypatch):
    """ResponseMap.display wires a click handler for feature popups.

    The current implementation only creates and adds a Popup on click;
    it does not emit a "details" intent from map clicks, so this test
    asserts the actual observable behavior instead of a non-wired
    get_more_details handler.
    """
    geo_factory = _GeoFactory()
    monkeypatch.setattr("here_search_demo.widgets.output_map.GeoJSON", geo_factory)
    monkeypatch.setattr("here_search_demo.widgets.output_map.Popup", _FakePopup)

    queue = _DummyQueue()
    state = SearchState()
    resp = _sample_response()
    state.hydrate(resp)

    fmap = _StubResponseMap(queue=queue, state=state)
    fmap.display(resp, fit=False)

    # GeoJSON should be created once with the response
    assert len(geo_factory.instances) == 1
    fake_geo = geo_factory.instances[0]
    feature = fake_geo.kwargs["data"]["features"][0]

    # Simulate a click; this should create and add a Popup.
    assert fake_geo._click is not None
    fake_geo._click(None, feature)
    await asyncio.sleep(0)

    # First object added is the GeoJSON layer; second is the Popup for the click.
    assert len(fmap.added) >= 2
    popup = fmap.added[-1]
    assert isinstance(popup, _FakePopup)
    assert popup.location == tuple(feature["geometry"]["coordinates"][::-1])
    assert popup.close_button is True


def test_response_map_on_feature_click_calls_show_popup_and_emits_action(monkeypatch):
    """_on_feature_click is callable directly without display() wiring."""
    queue = _DummyQueue()
    state = SearchState()
    resp = _sample_response()
    state.hydrate(resp)
    fmap = _StubResponseMap(queue=queue, state=state)

    show_calls = []
    emit_calls = []
    monkeypatch.setattr(fmap, "_show_item_popup", lambda item, rank=None: show_calls.append(rank))
    monkeypatch.setattr(fmap, "_emit_action_intent", lambda rank: emit_calls.append(rank))

    feature = {"properties": {"_rank": 0, "title": "Foo", "position": {"lat": 1, "lng": 2}}}
    fmap._on_feature_click(None, feature)

    assert emit_calls == [0]
    assert show_calls == [0]


def test_response_map_on_feature_click_blocked_by_long_press(monkeypatch):
    """_on_feature_click is a no-op when a long-press popup is open."""
    queue = _DummyQueue()
    state = SearchState()
    fmap = _StubResponseMap(queue=queue, state=state)
    fmap.long_press_popup = _FakePopup()  # simulate open long-press

    emit_calls = []
    monkeypatch.setattr(fmap, "_emit_action_intent", lambda rank: emit_calls.append(rank))

    feature = {"properties": {"_rank": 0}}
    fmap._on_feature_click(None, feature)

    assert emit_calls == []


def _search_response(*titles):
    return Response(
        req=Request(endpoint=Endpoint.DISCOVER),
        data={
            "items": [
                {
                    "title": title,
                    "resultType": "place",
                    "position": {"lat": idx + 1, "lng": idx + 2},
                }
                for idx, title in enumerate(titles)
            ]
        },
        x_headers={},
    )


def test_search_result_buttons_display_sets_button_titles():
    resp = _search_response("Foo", "Bar")
    buttons = SearchResultButtons(queue=_DummyQueue(), max_results_number=3)
    buttons.display(resp)

    assert buttons.buttons[0].button.description == "Foo"
    assert buttons.buttons[1].button.description == "Bar"
    assert buttons.state.ranks() == [0, 1]


def test_search_result_buttons_modify_replaces_row_with_details():
    discover_resp = _search_response("Foo")
    buttons = SearchResultButtons(queue=_DummyQueue(), max_results_number=2)
    buttons.display(discover_resp)

    lookup_resp = Response(
        req=Request(endpoint=Endpoint.LOOKUP),
        data={
            "title": "Foo+",
            "resultType": "place",
            "position": {"lat": 10, "lng": 20},
            "address": {"label": "Foo, Bar"},
            "categories": [{"primary": True, "id": "abc", "name": "Updated"}],
            "openingHours": [],
        },
        x_headers={},
    )
    previous_item = LocationResponseItem(
        data={"_rank": 0, "title": "Foo", "resultType": "place", "position": {"lat": 1, "lng": 2}},
        rank=0,
        resp=discover_resp,
    )
    intent = type("_Intent", (), {"materialization": previous_item})

    buttons.state.expanded_ranks.add(0)

    buttons.modify(lookup_resp, intent)

    assert buttons.buttons[0].button.description == "Foo+"
    children = buttons.buttons[0].button_box.children
    assert len(children) == 2  # expanded rank shows details


def test_search_result_buttons_click_invokes_map_focus_callback():
    resp = _search_response("Foo")
    clicked_ranks = []
    buttons = SearchResultButtons(queue=_DummyQueue(), max_results_number=2, on_result_click=clicked_ranks.append)
    buttons.display(resp)

    button_row = buttons.buttons[0]
    button_row.handle_click(button_row.button)

    assert 0 in buttons.state.expanded_ranks
    assert clicked_ranks == [0]
    assert len(button_row.button_box.children) == 2


def test_search_result_buttons_display_preserves_expansion_on_transient_text():
    """Verify expansion is preserved when typing (transient_text intent)."""
    resp = _search_response("Foo")
    buttons = SearchResultButtons(queue=_DummyQueue(), max_results_number=2)
    buttons.display(resp)

    button_row = buttons.buttons[0]
    button_row.handle_click(button_row.button)
    assert len(button_row.button_box.children) == 2  # button + details
    assert 0 in buttons.state.expanded_ranks

    # Display with transient_text intent (typing)
    intent = SearchIntent(kind="transient_text", materialization="f", time=0)
    buttons.display(resp, intent=intent)

    # Expansion should be PRESERVED during typing (not cleared)
    assert len(button_row.button_box.children) == 2  # Still expanded
    assert 0 in buttons.state.expanded_ranks


def test_search_result_buttons_display_collapses_details_on_submitted_search():
    """Verify expansion is cleared when user submits a new search."""
    resp = _search_response("Foo")
    buttons = SearchResultButtons(queue=_DummyQueue(), max_results_number=2)
    buttons.display(resp)

    button_row = buttons.buttons[0]
    button_row.handle_click(button_row.button)
    assert len(button_row.button_box.children) == 2
    assert 0 in buttons.state.expanded_ranks

    # Display with submitted_text intent (explicit search)
    intent = SearchIntent(kind="submitted_text", materialization="foo", time=0)
    buttons.display(resp, intent=intent)

    # Expansion should be CLEARED on submitted searches
    assert len(button_row.button_box.children) == 1
    assert 0 not in buttons.state.expanded_ranks


def test_response_map_click_result_recenters_and_shows_popup(monkeypatch):
    monkeypatch.setattr("here_search_demo.widgets.output_map.Popup", _FakePopup)
    created_tasks = []

    class _DummyTask:
        def done(self):
            return False

    def _fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()
        return _DummyTask()

    monkeypatch.setattr("here_search_demo.widgets.output_map.asyncio.create_task", _fake_create_task)

    queue = _DummyQueue()
    state = SearchState()
    resp = _sample_response()
    state.hydrate(resp)
    fmap = _StubResponseMap(queue=queue, state=state)

    fmap.click_result(0)

    assert len(queue.items) == 1
    assert len(created_tasks) == 1
    assert fmap.map_state.selected_rank == 0
    popup = fmap.added[-1]
    assert isinstance(popup, _FakePopup)
    assert popup.location == (1, 2)


def test_response_map_click_result_uses_future_position_for_detour_lookup(monkeypatch):
    queue = _DummyQueue()
    state = SearchState()
    resp = _search_response("Foo")
    state.hydrate(resp)
    fmap = _StubResponseMap(queue=queue, state=state)

    fmap.route.has_route = True
    fmap.route.ranking_mode.travel_time = True
    fmap.route.current_position = (48.8, 2.3)
    fmap.route.future_position = (48.81, 2.31)
    fmap.route.stop_position = (48.9, 2.4)

    drawn = []
    monkeypatch.setattr(
        fmap.route, "draw_detour_routes", lambda route_from, route_to: drawn.append((route_from, route_to))
    )

    fmap.route._route_cache[("via", 48.81, 2.31, 1, 2, 48.9, 2.4)] = (10, 100, "poly_to", 20, 200, "poly_from")

    fmap.click_result(0, emit_action=False, recenter=False, show_details=False)

    assert drawn == [("poly_from", "poly_to")]


def test_response_map_clear_results_removes_detour_routes(monkeypatch):
    queue = _DummyQueue()
    state = SearchState()
    fmap = _StubResponseMap(queue=queue, state=state)

    removed = []
    monkeypatch.setattr(fmap.route, "clear_detour_routes", lambda: removed.append("cleared"))

    fmap.clear_results()

    assert removed == ["cleared"]


def test_response_map_click_result_draws_detour_from_item_annotation(monkeypatch):
    """The reranked item carries its own legs, so no cache lookup is needed."""
    queue = _DummyQueue()
    state = SearchState()
    resp = _search_response("Foo")
    resp.data["items"][0]["_detour"] = {
        "label": "Foo (1min, 2min, +3km)",
        "polyline_to": "annotated_to",
        "polyline_from": "annotated_from",
    }
    state.hydrate(resp)
    fmap = _StubResponseMap(queue=queue, state=state)

    fmap.route.has_route = True
    fmap.route.ranking_mode.travel_time = True
    fmap.route.current_position = (48.8, 2.3)
    # A stale anchor makes the derived cache key unusable; the annotation must still win.
    fmap.route.future_position = (48.99, 2.99)
    fmap.route.stop_position = (48.9, 2.4)

    drawn = []
    monkeypatch.setattr(
        fmap.route, "draw_detour_routes", lambda route_from, route_to: drawn.append((route_from, route_to))
    )

    fmap.click_result(0, emit_action=False, recenter=False, show_details=False)

    assert drawn == [("annotated_from", "annotated_to")]
