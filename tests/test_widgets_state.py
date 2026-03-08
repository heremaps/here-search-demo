import pytest

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.request import Request
from here_search_demo.entity.response import Response
from here_search_demo.widgets.state import MapState, SearchState


@pytest.fixture
def lookup_response():
    return Response(
        req=Request(endpoint=Endpoint.LOOKUP),
        data={"title": "Lookup", "resultType": "place", "position": {"lat": 1, "lng": 2}},
    )


@pytest.fixture
def autosuggest_response():
    return Response(
        req=Request(endpoint=Endpoint.AUTOSUGGEST),
        data={
            "items": [
                {"title": "Foo", "resultType": "place", "position": {"lat": 1, "lng": 2}},
                {"title": "Bar", "resultType": "categoryQuery", "position": {"lat": 3, "lng": 4}},
            ]
        },
    )


def test_search_state_hydrate_lookup(lookup_response):
    state = SearchState()
    state.hydrate(lookup_response)
    assert state.ranks() == [0]
    assert state.icon_for(0) == ""
    assert state.title_for(0) == "Lookup"


def test_search_state_hydrate_autosuggest(autosuggest_response):
    state = SearchState()
    state.hydrate(autosuggest_response)
    assert state.ranks() == [0, 1]
    assert state.icon_for(1) == "search"
    assert state.title_for(1) == "Bar"


def test_search_state_update_item(autosuggest_response):
    state = SearchState()
    state.hydrate(autosuggest_response)
    state.update_item(
        1, {"title": "Baz", "resultType": "place", "position": {"lat": 5, "lng": 6}}, autosuggest_response
    )
    assert state.get_item(1).data["title"] == "Baz"


def test_search_state_query_and_terms():
    state = SearchState()
    state.set_query_text("hello")
    state.select_taxonomy_item(None)
    state.set_term_suggestions(["foo", "bar"])
    assert state.current_query == "hello"
    assert state.term_suggestions == ["foo", "bar"]


def test_map_state_updates():
    state = MapState()
    state.update_center((1.0, 2.0))
    state.update_zoom(5)
    state.select_rank(3)
    assert state.center == (1.0, 2.0)
    assert state.zoom == 5
    assert state.selected_rank == 3
