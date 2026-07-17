###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################
"""
Test hydrate() call deduplication in SearchResultButtons.

Verifies that display() only calls state.hydrate() when the response signature
changes, skipping redundant re-hydration for identical responses.
"""

from unittest.mock import Mock, patch

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.response import Response
from here_search_demo.widgets.output_buttons import SearchResultButtons
from here_search_demo.widgets.state import SearchState


def make_response(endpoint: Endpoint, query: str, num_items: int = 5) -> Response:
    """Create a mock Response for testing."""
    items = [
        {
            "id": f"item-{i}",
            "resultType": "place",
            "title": f"Result {i} for '{query}'",
            "position": {"lat": 48.0 + i * 0.1, "lng": 2.0 + i * 0.1},
            "address": {"label": f"Address {i}, {query}, France"},
        }
        for i in range(num_items)
    ]

    resp = Mock(spec=Response)
    resp.req = Mock()
    resp.req.endpoint = endpoint
    resp.data = {"items": items}
    return resp


def test_hydrate_redundancy_constant_results():
    """
    Identical responses should trigger hydrate() only on the first display() call.
    (Simulates typing one query while search keeps returning same results.)
    """
    buttons = SearchResultButtons(state=SearchState())
    response = make_response(Endpoint.DISCOVER, "pizza", num_items=5)

    with patch.object(buttons.state, "hydrate", wraps=buttons.state.hydrate) as spy:
        for _ in range(5):
            buttons.display(response, SearchIntent(kind="transient_text", materialization="pizza", time=0))

    assert spy.call_count == 1, "Only the first call should hydrate; the rest are identical"


def test_hydrate_redundancy_changing_results():
    """
    Each distinct response signature must trigger hydrate().
    Simulates: "p" → "pi" → "piz" → "pizz" → "pizza"
    """
    buttons = SearchResultButtons(state=SearchState())
    queries = ["p", "pi", "piz", "pizz", "pizza"]

    with patch.object(buttons.state, "hydrate", wraps=buttons.state.hydrate) as spy:
        for query in queries:
            buttons.display(
                make_response(Endpoint.DISCOVER, query, num_items=5),
                SearchIntent(kind="transient_text", materialization=query, time=0),
            )

    assert spy.call_count == 5, "Each unique response should trigger hydrate()"


def test_hydrate_redundancy_mixed_scenario():
    """
    Realistic mixed scenario: repeated results are skipped, new signatures trigger hydrate().
    Sequence: 3× same pizza → 1× pizza at new location → 2× same new location
    Expected: 2 hydrate() calls out of 6 display() calls.
    """
    buttons = SearchResultButtons(state=SearchState())

    with patch.object(buttons.state, "hydrate", wraps=buttons.state.hydrate) as spy:
        for _ in range(3):
            buttons.display(
                make_response(Endpoint.DISCOVER, "pizza", num_items=5),
                SearchIntent(kind="transient_text", materialization="pizza", time=0),
            )

        response_new_location = make_response(Endpoint.DISCOVER, "pizza", num_items=5)
        response_new_location.data["items"][0]["position"]["lat"] = 50.0
        buttons.display(response_new_location, SearchIntent(kind="transient_text", materialization="pizza", time=0))

        for _ in range(2):
            response_repeat = make_response(Endpoint.DISCOVER, "pizza", num_items=5)
            response_repeat.data["items"][0]["position"]["lat"] = 50.0
            buttons.display(response_repeat, SearchIntent(kind="transient_text", materialization="pizza", time=0))

    assert spy.call_count == 2, "Only the first pizza and the location change should hydrate()"
