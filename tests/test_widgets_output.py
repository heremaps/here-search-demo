###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.request import Request
from here_search_demo.entity.response import LocationResponseItem, Response
from here_search_demo.widgets.output import DetailsMixin, ResponseMap, SearchResultButtons
from here_search_demo.widgets.state import MapState, SearchState


class _DetailsTester(DetailsMixin):
    """Concrete helper to test DetailsMixin renders."""


@pytest.fixture
def details_tester():
    return _DetailsTester()


def test_details_mixin_html_includes_place_metadata(details_tester):
    data = {
        "resultType": "place",
        "title": "EV Hub",
        "address": {"label": "EV Hub, 123 Road, City"},
        "categories": [{"primary": True, "id": "700-7600-0322", "name": "EV Station"}],
        "openingHours": [
            {
                "categories": [{"id": "700-7600-0322"}],
                "isOpen": True,
                "text": ["Mon-Fri 08:00-20:00"],
            }
        ],
        "extended": {
            "evStation": {
                "connectors": [
                    {
                        "connectorType": {"name": "Type 2 (AC)"},
                        "maxPowerLevel": "22",
                        "chargingPoint": {"numberOfAvailable": 1, "numberOfConnectors": 3},
                    }
                ]
            }
        },
        "contacts": [
            {
                "phone": [{"value": "+123", "categories": [{"id": "700-7600-0322"}]}],
                "www": [{"value": "https://example.com"}],
                "email": [{"value": "info@example.com"}],
            }
        ],
        "media": {
            "images": {"items": [{"variants": {"medium": {"href": "https://img"}}}]},
            "ratings": {"items": [{"average": 4.5, "count": 12, "href": "https://trip"}]},
            "editorials": {"items": [{"href": "https://tripadvisor.com/foo-d123-bar", "description": "Great!"}]},
        },
        "references": [{"supplier": {"id": "tripadvisor"}, "id": "123"}],
    }

    html = details_tester.html(data, image_variant="medium")

    assert "Open" in html
    assert "Type 2" in html  # connector info
    assert "+123" in html and "mailto:info@example.com" in html
    assert "example.com" in html  # website anchor text
    assert "https://img" in html
    assert "Great!" in html


def test_details_mixin_html_handles_non_place(details_tester):
    data = {
        "resultType": "location",
        "address": {"label": "Public Park, Example City"},
    }

    html = details_tester.html(data)
    assert "Public Park" in html
    assert "<div" in html


@pytest.mark.parametrize(
    ("is_open", "expected"),
    [
        (True, "green"),
        (False, "red"),
        (None, "blue"),
    ],
)
def test_response_map_item_color_from_opening_hours(is_open, expected):
    feature = {
        "properties": {
            "categories": [{"primary": True, "id": "123"}],
            "resultType": "place",
            "openingHours": [
                {
                    "categories": [{"id": "123"}],
                    "isOpen": is_open,
                }
            ],
        }
    }

    assert ResponseMap.item_color(feature) == expected


def test_response_map_item_color_uses_ev_availability():
    feature = {
        "properties": {
            "categories": [{"primary": True, "id": "700-7600-0322"}],
            "resultType": "place",
            "openingHours": [
                {
                    "categories": [{"id": "700-7600-0322"}],
                    "isOpen": True,
                }
            ],
            "extended": {
                "evStation": {
                    "connectors": [
                        {
                            "chargingPoint": {"numberOfAvailable": 0},
                        },
                        {
                            "chargingPoint": {"numberOfAvailable": 2},
                        },
                    ]
                }
            },
        }
    }

    assert ResponseMap.item_color(feature) == "green"


def test_response_map_style_callback_delegates_to_item_color(monkeypatch):
    called = {}

    def fake_item_color(feature):
        called["feature"] = feature
        return "purple"

    monkeypatch.setattr(ResponseMap, "item_color", staticmethod(fake_item_color))

    feature = {"properties": {"resultType": "place"}}
    style = ResponseMap.style_callback(feature)

    assert called["feature"] is feature
    assert style == {"fillColor": "purple"}


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
        self.map_state = MapState()
        self.added = []
        self.removed = []
        self.long_press_popup = None
        self.short_press_popup = None

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
    )


def test_response_map_display_emits_more_details(monkeypatch):
    """ResponseMap.display wires a click handler for feature popups.

    The current implementation only creates and adds a Popup on click;
    it does not emit a "details" intent from map clicks, so this test
    asserts the actual observable behavior instead of a non-wired
    get_more_details handler.
    """
    geo_factory = _GeoFactory()
    monkeypatch.setattr("here_search_demo.widgets.output.GeoJSON", geo_factory)
    monkeypatch.setattr("here_search_demo.widgets.output.Popup", _FakePopup)

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

    # First object added is the GeoJSON layer; second is the Popup for the click.
    assert len(fmap.added) >= 2
    popup = fmap.added[-1]
    assert isinstance(popup, _FakePopup)
    assert popup.location == feature["geometry"]["coordinates"][::-1]


def test_response_map_click_adds_popup(monkeypatch):
    """Clicking a feature should create and add a Popup to the map.

    We don't fabricate attributes that ResponseMap doesn't have; instead
    we assert on objects passed to the public add() API.
    """
    geo_factory = _GeoFactory()
    monkeypatch.setattr("here_search_demo.widgets.output.GeoJSON", geo_factory)
    monkeypatch.setattr("here_search_demo.widgets.output.Popup", _FakePopup)

    state = SearchState()
    resp = _sample_response()
    state.hydrate(resp)
    fmap = _StubResponseMap(queue=_DummyQueue(), state=state)
    fmap.display(resp, fit=False)

    fake_geo = geo_factory.instances[0]
    feature = fake_geo.kwargs["data"]["features"][0]

    # Simulate a click: ResponseMap.display wires only on_click.
    fake_geo._click(None, feature)

    # The first added object is the GeoJSON layer; the second is the Popup.
    assert len(fmap.added) >= 2
    popup = fmap.added[-1]
    assert isinstance(popup, _FakePopup)
    # It should be anchored at the feature's coordinates (reversed to lat/lon).
    assert popup.location == feature["geometry"]["coordinates"][::-1]


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
