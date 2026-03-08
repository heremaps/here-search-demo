###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from here_search_demo.base import OneBoxBase, OneBoxSimple
from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.place import PlaceTaxonomyExample
from here_search_demo.entity.request import RequestContext
from here_search_demo.entity.response import Response
from here_search_demo.event import (
    DetailsSearchEvent,
    EmptySearchEvent,
    FollowUpSearchEvent,
    PartialTextSearchEvent,
    PlaceTaxonomySearchEvent,
    TextSearchEvent,
)
from here_search_demo.user import DefaultUser


@pytest.mark.asyncio
@pytest.mark.parametrize("query_text", ["r", "re", "res", "rest"])
async def test_wait_for_search_event_1(app, query_text, context):
    """Tests the reception of a transient text"""
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = SearchIntent(kind="transient_text", materialization=query_text, time=0.0)
        app.queue.put_nowait(intent)
        intent_out, event, handler, config = await app.wait_for_search_event()
        assert isinstance(event, PartialTextSearchEvent) and event.query_text == query_text


@pytest.mark.asyncio
async def test_wait_for_search_event_2(app, context):
    """Tests the reception of a submitted text"""
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = SearchIntent(kind="submitted_text", materialization="restaurant", time=0.0)
        app.queue.put_nowait(intent)
        intent_out, event, handler, config = await app.wait_for_search_event()
        assert isinstance(event, TextSearchEvent) and event.query_text == "restaurant"


@pytest.mark.asyncio
@pytest.mark.parametrize("item", PlaceTaxonomyExample.taxonomy.items.values())
async def test_wait_for_search_event_3(app, item, context):
    """Tests the reception of a taxonomy item"""
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = SearchIntent(kind="taxonomy", materialization=item, time=0.0)
        app.queue.put_nowait(intent)
        intent_out, event, handler, config = await app.wait_for_search_event()
        assert isinstance(event, PlaceTaxonomySearchEvent) and event.item == item


@pytest.mark.asyncio
async def test_wait_for_search_event_4(app, location_response_item, context):
    """Tests the reception of a location response item text"""
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = SearchIntent(kind="details", materialization=location_response_item, time=0.0)
        app.queue.put_nowait(intent)
        intent_out, event, handler, config = await app.wait_for_search_event()
        assert isinstance(event, DetailsSearchEvent) and event.item == location_response_item


@pytest.mark.asyncio
async def test_wait_for_search_event_5(app, chain_query_response_item, context):
    """Tests the reception of a chain query response item"""
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = SearchIntent(kind="details", materialization=chain_query_response_item, time=0.0)
        app.queue.put_nowait(intent)
        intent_out, event, handler, config = await app.wait_for_search_event()
        assert isinstance(event, FollowUpSearchEvent) and event.item == chain_query_response_item


@pytest.mark.asyncio
async def test_wait_for_search_event_6(app, category_query_response_item, context):
    """Tests the reception of a category query response item"""
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = SearchIntent(kind="details", materialization=category_query_response_item, time=0.0)
        app.queue.put_nowait(intent)
        intent_out, event, handler, config = await app.wait_for_search_event()
        assert isinstance(event, FollowUpSearchEvent) and event.item == category_query_response_item


@pytest.mark.asyncio
async def test_wait_for_search_event_7(app, context):
    """Tests the reception of an empty text"""
    with patch.object(RequestContext, "__call__", return_value=context):
        intent = SearchIntent(kind="empty", materialization=None, time=0.0)
        app.queue.put_nowait(intent)
        intent_out, event, handler, config = await app.wait_for_search_event()
        assert isinstance(event, EmptySearchEvent)


@pytest.mark.asyncio
async def test_wait_for_search_event_8(app):
    """Tests the reception of an unknown intent kind"""
    with patch.object(RequestContext, "__call__", return_value=None):
        intent = SearchIntent(kind="unknown", materialization=None, time=0.0)
        app.queue.put_nowait(intent)
        with pytest.raises(KeyError):
            await app.wait_for_search_event()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "intent, event, config",
    [
        (
            "transient_text_intent",
            "partial_text_search_event",
            "autosuggest_config",
        ),
        (
            "formulated_text_intent",
            "text_search_event",
            "discover_config",
        ),
        (
            "place_taxonomy_intent",
            "taxonomy_search_event",
            "browse_config",
        ),
        (
            "more_details_intent",
            "details_search_event",
            "lookup_config",
        ),
        ("no_intent", "empty_search_event", None),
    ],
)
async def test_handle_search_event(app, intent, event, config, autosuggest_response, session, request):
    """
    Test that
    - SearchEvent get_response() is called with the right config
    - _handle_search_response() is called with the SearchEvent, Response and Session instances
    """
    intent = request.getfixturevalue(intent)
    event = request.getfixturevalue(event)
    config = request.getfixturevalue(config) if config else config

    def response_handler(intent, resp):
        return None

    with (
        patch.object(
            app,
            "wait_for_search_event",
            return_value=(intent, event, response_handler, config),
        ) as wfse,
        patch.object(app, "_handle_search_response", return_value=None) as hsr,
        patch.object(event, "get_response", return_value=autosuggest_response) as gr,
    ):
        await app.handle_search_event(session)
        wfse.assert_called_once()
        gr.assert_called_once_with(api=app.api, config=config, session=session)
        hsr.assert_called_once_with(intent, response_handler, autosuggest_response)


@pytest.mark.asyncio
async def test_search_events_preprocess_and_postprocess_are_noops():
    app = OneBoxSimple()
    session = MagicMock()
    assert await app.search_events_preprocess(session) is None
    assert await app.search_event_postprocess(None, None, None, session) is None


def test_run_and_stop(monkeypatch):
    app = OneBoxSimple()
    fut = asyncio.Future()
    fut.set_result(None)
    monkeypatch.setattr(asyncio, "ensure_future", lambda coro: fut)
    app.run(lambda: fut)
    assert app.task is fut
    asyncio.run(app.stop())
    assert app.task.cancelled() or app.task.done()


def test_transient_coalescing_keeps_recent(monkeypatch):
    q = asyncio.Queue()
    app = OneBoxSimple(queue=q, max_transient_keep=3)
    for val in ["a", "b", "c", "d"]:
        q.put_nowait(SearchIntent(kind="transient_text", materialization=val, time=0.0))
    # Add a non-transient to ensure it survives
    marker = SearchIntent(kind="submitted_text", materialization="final", time=0.0)
    q.put_nowait(marker)

    async def consume_once():
        return await app.wait_for_search_event()

    intent, event, handler, config = asyncio.run(consume_once())
    assert intent.materialization == "d"
    remaining = []
    while not q.empty():
        remaining.append(q.get_nowait())
    kinds = [i.kind for i in remaining]
    assert marker in remaining
    assert kinds.count("transient_text") == 0


def test_handle_suggestion_list_result_list_details_empty_submission():
    app = OneBoxSimple()
    # These methods are no-ops, just check they don't raise
    app.handle_suggestion_list(MagicMock(spec=SearchIntent), MagicMock(spec=Response))
    app.handle_result_list(MagicMock(spec=SearchIntent), MagicMock(spec=Response))
    app.handle_result_details(MagicMock(spec=SearchIntent), MagicMock(spec=Response))
    app.handle_empty_text_submission(MagicMock(spec=SearchIntent), MagicMock(spec=Response))


def test_get_preferred_language():
    user = DefaultUser()
    app = OneBoxBase(user_profile=user)
    # No country code
    assert app.get_preferred_language() == user.get_current_language()
    # With country code
    cc = "DE"
    assert app.get_preferred_language(cc) == user.get_preferred_country_language(cc)


@pytest.mark.asyncio
async def test_adapt_language_changes_preferred_language():
    user = DefaultUser()
    app = OneBoxBase(user_profile=user)
    resp = MagicMock()
    resp.data = {"items": [{"address": {"countryCode": "DE"}}]}
    with patch.object(app, "get_preferred_language", return_value="de"):
        await app.adapt_language(resp)
        assert app.preferred_language == "de"


def test_set_search_center():
    app = OneBoxBase()
    app.set_search_center((10.0, 20.0))
    assert app.search_center == (10.0, 20.0)


def test_del_runs_stop(monkeypatch):
    app = OneBoxSimple()
    app.task = MagicMock()
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: MagicMock(is_running=lambda: False))
    monkeypatch.setattr(asyncio, "run", lambda coro: None)
    app.__del__()  # Should not raise
