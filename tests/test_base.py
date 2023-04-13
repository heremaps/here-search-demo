###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest

from here_search.demo.event import (
    SearchEvent,
    PartialTextSearchEvent,
    TextSearchEvent,
    PlaceTaxonomySearchEvent,
    FollowUpSearchEvent,
    DetailsSearchEvent,
    EmptySearchEvent,
)
from here_search.demo.entity.intent import (
    FormulatedTextIntent,
    TransientTextIntent,
    PlaceTaxonomyIntent,
    MoreDetailsIntent,
    NoIntent,
)
from here_search.demo.entity.request import RequestContext
from here_search.demo.entity.place import PlaceTaxonomyExample

from unittest.mock import patch


@pytest.mark.asyncio
@pytest.mark.parametrize("query_text", ["r", "re", "res", "rest"])
async def test_wait_for_search_event_1(app, query_text, context):
    """
    Tests the reception of a formulated text
    """
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = TransientTextIntent(materialization=query_text)
        app.queue.put_nowait(intent)
        event: SearchEvent = await app.wait_for_search_event()
        assert (
            isinstance(event, PartialTextSearchEvent) and event.query_text == query_text
        )


@pytest.mark.asyncio
async def test_wait_for_search_event_2(app, context):
    """
    Tests the reception of a submitted text
    """
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = FormulatedTextIntent(materialization="restaurant")
        app.queue.put_nowait(intent)
        event: SearchEvent = await app.wait_for_search_event()
        assert isinstance(event, TextSearchEvent) and event.query_text == "restaurant"


@pytest.mark.asyncio
@pytest.mark.parametrize("item", PlaceTaxonomyExample.taxonomy.items.values())
async def test_wait_for_search_event_3(app, item, context):
    """
    Tests the reception of a taxonomy item
    """
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = PlaceTaxonomyIntent(materialization=item)
        app.queue.put_nowait(intent)
        event: SearchEvent = await app.wait_for_search_event()
        assert isinstance(event, PlaceTaxonomySearchEvent) and event.item == item


@pytest.mark.asyncio
async def test_wait_for_search_event_4(app, location_response_item, context):
    """
    Tests the reception of a location response item text
    """
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = MoreDetailsIntent(materialization=location_response_item)
        app.queue.put_nowait(intent)
        event: SearchEvent = await app.wait_for_search_event()
        assert (
            isinstance(event, DetailsSearchEvent)
            and event.item == location_response_item
        )


@pytest.mark.asyncio
async def test_wait_for_search_event_5(app, chain_query_response_item, context):
    """
    Tests the reception of a chain query response item
    """
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = MoreDetailsIntent(materialization=chain_query_response_item)
        app.queue.put_nowait(intent)
        event: SearchEvent = await app.wait_for_search_event()
        assert (
            isinstance(event, FollowUpSearchEvent)
            and event.item == chain_query_response_item
        )


@pytest.mark.asyncio
async def test_wait_for_search_event_6(app, category_query_response_item, context):
    """
    Tests the reception of a category query response item
    """
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = MoreDetailsIntent(materialization=category_query_response_item)
        app.queue.put_nowait(intent)
        event: SearchEvent = await app.wait_for_search_event()
        assert (
            isinstance(event, FollowUpSearchEvent)
            and event.item == category_query_response_item
        )


@pytest.mark.asyncio
async def test_wait_for_search_event_7(app, context):
    """
    Tests the reception of an empty text
    """
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = NoIntent()
        app.queue.put_nowait(intent)
        event: SearchEvent = await app.wait_for_search_event()
        assert isinstance(event, EmptySearchEvent)


@pytest.mark.asyncio
async def test_wait_for_search_event_8(app):
    """
    Tests the reception of an unknown intent
    """
    with patch.object(RequestContext, "__call__", return_value=None):
        intent = None
        app.queue.put_nowait(intent)
        with pytest.raises(KeyError):
            await app.wait_for_search_event()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event, config",
    [
        (
            pytest.lazy_fixture("partial_text_search_event"),
            pytest.lazy_fixture("autosuggest_config"),
        ),
        (
            pytest.lazy_fixture("text_search_event"),
            pytest.lazy_fixture("discover_config"),
        ),
        (
            pytest.lazy_fixture("taxonomy_search_event"),
            pytest.lazy_fixture("browse_config"),
        ),
        (
            pytest.lazy_fixture("details_search_event"),
            pytest.lazy_fixture("lookup_config"),
        ),
        (pytest.lazy_fixture("empty_search_event"), None),
    ],
)


async def test_handle_search_event(app, event, config, autosuggest_response, session):
    """
    Test that
    - SearchEvent get_response() is called with the right config
    - _handle_search_response() is called with the SearchEvent, Response and Session instances
    """
    response_handlers = {type(event): (lambda r: r, config)}
    with patch.object(
        app, "wait_for_search_event", return_value=event
    ) as wfse, patch.object(
        app, "_handle_search_response", return_value=None
    ) as hsr, patch.object(
        event, "get_response", return_value=autosuggest_response
    ) as gr, patch.object (
        app, "response_handlers", response_handlers
    ):
        await app.handle_search_event(session)
        wfse.assert_called_once()
        gr.assert_called_once_with(api=app.api, config=config, session=session)
        hsr.assert_called_once_with(response_handlers[type(event)][0], autosuggest_response)

