import pytest

from here_search.api import (
    SearchEvent,
    PartialTextSearchEvent,
    TextSearchEvent,
    TaxonomySearchEvent,
    FollowUpSearchEvent,
    DetailsSearchEvent,
    EmptySearchEvent,
)
from here_search.entities import (
    SearchIntent,
    FormulatedIntent,
    TransientIntent,
    NoIntent,
    UnsupportedIntentMaterialization,
    SearchContext,
    PlaceTaxonomyExample,
)

from unittest.mock import patch


@pytest.mark.asyncio
@pytest.mark.parametrize("query_text", ["r", "re", "res", "rest"])
async def test_wait_for_search_event_1(app, query_text, context):
    """
    Tests the reception of a formulated text
    """
    with patch.object(SearchContext, "__call__", return_value=context):
        intent = TransientIntent(materialization=query_text)
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
    with patch.object(SearchContext, "__call__", return_value=context):
        intent = FormulatedIntent(materialization="restaurant")
        app.queue.put_nowait(intent)
        event: SearchEvent = await app.wait_for_search_event()
        assert isinstance(event, TextSearchEvent) and event.query_text == "restaurant"


@pytest.mark.asyncio
@pytest.mark.parametrize("item", PlaceTaxonomyExample.taxonomy.items.values())
async def test_wait_for_search_event_3(app, item, context):
    """
    Tests the reception of a taxonomy item
    """
    with patch.object(SearchContext, "__call__", return_value=context):
        intent = FormulatedIntent(materialization=item)
        app.queue.put_nowait(intent)
        event: SearchEvent = await app.wait_for_search_event()
        assert isinstance(event, TaxonomySearchEvent) and event.item == item


@pytest.mark.asyncio
async def test_wait_for_search_event_4(app, location_response_item, context):
    """
    Tests the reception of a location response item text
    """
    with patch.object(SearchContext, "__call__", return_value=context):
        intent = FormulatedIntent(materialization=location_response_item)
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
    with patch.object(SearchContext, "__call__", return_value=context):
        intent = FormulatedIntent(materialization=chain_query_response_item)
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
    with patch.object(SearchContext, "__call__", return_value=context):
        intent = FormulatedIntent(materialization=category_query_response_item)
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
    with patch.object(SearchContext, "__call__", return_value=context):
        intent = NoIntent()
        app.queue.put_nowait(intent)
        event: SearchEvent = await app.wait_for_search_event()
        assert isinstance(event, EmptySearchEvent)


@pytest.mark.asyncio
async def test_wait_for_search_event_8(app, context):
    """
    Tests the reception of an unknown intent materialization
    """
    with patch.object(SearchContext, "__call__", return_value=context):
        intent = SearchIntent(materialization=None)
        app.queue.put_nowait(intent)
        with pytest.raises(UnsupportedIntentMaterialization):
            await app.wait_for_search_event()


@pytest.mark.asyncio
async def test_wait_for_search_event_9(app):
    """
    Tests the reception of an unknown intent
    """
    with patch.object(SearchContext, "__call__", return_value=None):
        intent = None
        app.queue.put_nowait(intent)
        with pytest.raises(AttributeError):
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
async def test_handle_search_event(app, event, config, response, session):
    """
    Test that
    - SearchEvent get_response() is called with the right config
    - handle_search_response() is called with the SearchEvent, Response and Session instances
    """
    with patch.object(
        app, "wait_for_search_event", return_value=event
    ) as wfse, patch.object(
        app, "handle_search_response", return_value=None
    ) as hsr, patch.object(
        event, "get_response", return_value=response
    ) as gr:
        await app.handle_search_event(session)
        wfse.assert_called_once()
        gr.assert_called_once_with(api=app.api, config=config, session=session)
        hsr.assert_called_once_with(event, response, session)


@pytest.mark.asyncio
@pytest.mark.parametrize("query_text", ["r", "re", "res"])
async def test_handle_search_response_1(app, query_text, context, response, session):
    with patch.object(
        app, "handle_suggestion_list", return_value=None
    ) as hsl, patch.object(
        app, "handle_result_list", return_value=None
    ) as hrl, patch.object(
        app, "handle_empty_text_submission", return_value=None
    ) as hets:
        event = PartialTextSearchEvent(query_text=query_text, context=context)
        await app.handle_search_response(event, response, session)
        hsl.assert_called_once_with(response, session)
        hrl.assert_not_called()
        hets.assert_not_called()


@pytest.mark.asyncio
async def test_handle_search_response_2(app, context, response, session):
    with patch.object(
        app, "handle_suggestion_list", return_value=None
    ) as hsl, patch.object(
        app, "handle_result_list", return_value=None
    ) as hrl, patch.object(
        app, "handle_empty_text_submission", return_value=None
    ) as hets:
        event = TextSearchEvent(query_text="restaurant", context=context)
        await app.handle_search_response(event, response, session)
        hrl.assert_called_once_with(response, session)
        hsl.assert_not_called()
        hets.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("item", list(PlaceTaxonomyExample.taxonomy.items.values())[:1])
async def test_handle_search_response_3(app, item, context, response, session):
    with patch.object(
        app, "handle_suggestion_list", return_value=None
    ) as hsl, patch.object(
        app, "handle_result_list", return_value=None
    ) as hrl, patch.object(
        app, "handle_empty_text_submission", return_value=None
    ) as hets:
        event = TaxonomySearchEvent(item=item, context=context)
        await app.handle_search_response(event, response, session)
        hrl.assert_called_once_with(response, session)
        hsl.assert_not_called()
        hets.assert_not_called()
