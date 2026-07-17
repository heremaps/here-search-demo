###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.request import Request
from here_search_demo.entity.response import Response
from here_search_demo.widgets.state import MapState, SearchState, _get_vicinity


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


# ---------------------------------------------------------------------------
# _get_vicinity – bracketed-title exception
# ---------------------------------------------------------------------------


def _item(title: str, address_label: str, result_type: str = "place") -> dict:
    return {"title": title, "resultType": result_type, "address": {"label": address_label}}


def test_bracketed_title_used_as_is_single_item():
    """A single item whose title contains brackets keeps the title verbatim."""
    items = {0: _item("Post Office (Main Branch)", "Post Office (Main Branch), London, UK")}
    result = _get_vicinity(items)
    assert result[0] == "Post Office (Main Branch)"
    assert items[0]["_vicinity"] == ["Post Office (Main Branch)"]


def test_bracketed_title_not_expanded_among_duplicates():
    """A bracketed item is not expanded even when another item has the same bare name."""
    items = {
        0: _item("Starbucks (Airport)", "Starbucks (Airport), Amsterdam, Netherlands"),
        1: _item("Starbucks", "Starbucks, Centrum, Amsterdam, Netherlands"),
        2: _item("Starbucks", "Starbucks, Zuid, Amsterdam, Netherlands"),
    }
    result = _get_vicinity(items)
    # bracketed item kept verbatim
    assert result[0] == "Starbucks (Airport)"
    assert items[0]["_vicinity"] == ["Starbucks (Airport)"]
    # non-bracketed duplicates are still disambiguated by address parts
    assert result[1] != result[2]


def test_bracketed_title_excluded_from_disambiguation_loop():
    """Two bracketed items with different titles stay independent; no suffix added."""
    items = {
        0: _item("The George (Pub)", "The George (Pub), Fleet Street, London, UK"),
        1: _item("The George (Hotel)", "The George (Hotel), Strand, London, UK"),
    }
    result = _get_vicinity(items)
    assert result[0] == "The George (Pub)"
    assert result[1] == "The George (Hotel)"
    assert items[0]["_vicinity"] == ["The George (Pub)"]
    assert items[1]["_vicinity"] == ["The George (Hotel)"]


def test_non_bracketed_title_still_disambiguated():
    """Items without brackets continue to be disambiguated normally."""
    items = {
        0: _item("Café", "Café, Rue de Rivoli, Paris, France"),
        1: _item("Café", "Café, Boulevard Haussmann, Paris, France"),
    }
    result = _get_vicinity(items)
    assert result[0] != result[1]
