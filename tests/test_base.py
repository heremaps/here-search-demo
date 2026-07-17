###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from here_search_demo.base import OneBoxCore, UserProfileMixin
from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.intent import ActionIntent
from here_search_demo.entity.place import PlaceTaxonomyExample
from here_search_demo.entity.request import RequestContext
from here_search_demo.entity.response import Response
from here_search_demo.event import (
    ActionSearchEvent,
    DetailsSearchEvent,
    EmptySearchEvent,
    FollowUpSearchEvent,
    PartialTextSearchEvent,
    PlaceTaxonomySearchEvent,
    TextSearchEvent,
)
from here_search_demo.user import DefaultUser


class _PersonalizedApp(UserProfileMixin, OneBoxCore):
    """Minimal test double: UserProfileMixin + OneBoxCore without any widgets."""


def test_oneboxcore_rejects_unknown_kwargs():
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        OneBoxCore(result_queue=asyncio.Queue())


def test_user_profile_mixin_rejects_unknown_kwargs():
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        _PersonalizedApp(result_queue=asyncio.Queue())


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
    "intent_fixture, expected_event_type, config_fixture",
    [
        ("transient_text_intent", PartialTextSearchEvent, "autosuggest_config"),
        ("formulated_text_intent", TextSearchEvent, "discover_config"),
        ("place_taxonomy_intent", PlaceTaxonomySearchEvent, "browse_config"),
        ("more_details_intent", DetailsSearchEvent, "lookup_config"),
        ("no_intent", EmptySearchEvent, None),
    ],
)
async def test_handle_search_event(app, intent_fixture, expected_event_type, config_fixture, session, request, context):
    """
    Test that handle_search_event routes intents through real triage,
    calls get_response, and invokes the response handler with the result.
    """
    intent = request.getfixturevalue(intent_fixture)

    # Put the intent on the queue so wait_for_search_event (real code) can consume it
    app.queue.put_nowait(intent)

    fake_response = MagicMock(spec=Response)

    with (
        patch.object(RequestContext, "__call__", return_value=context),
        patch.object(expected_event_type, "get_response", new_callable=AsyncMock, return_value=fake_response),
    ):
        returned_intent, returned_event, returned_resp = await app.handle_search_event(session)

    assert returned_intent is intent
    assert isinstance(returned_event, expected_event_type)
    assert returned_resp is fake_response


@pytest.mark.asyncio
async def test_run_and_stop(monkeypatch):
    app = OneBoxCore()
    fut = asyncio.get_running_loop().create_future()
    fut.set_result(None)
    monkeypatch.setattr(asyncio, "ensure_future", lambda coro: fut)
    app.run(lambda: fut)
    assert app.task is fut
    await app.stop()
    assert app.task.cancelled() or app.task.done()


def test_transient_coalescing_keeps_recent(monkeypatch):
    q = asyncio.Queue()
    app = OneBoxCore(queue=q, max_transient_keep=3)
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


@pytest.mark.asyncio
async def test_transient_stale_response_is_dropped():
    q = asyncio.Queue()
    app = OneBoxCore(queue=q, max_transient_keep=1)
    handled: list[str] = []

    class DelayedEvent:
        def __init__(self, query: str):
            self.query = query

        async def get_response(self, api, config, session):
            if self.query == "a":
                await asyncio.sleep(0.03)
            return MagicMock(spec=Response)

    def triage(intent, context):
        return DelayedEvent(intent.materialization), lambda i, r: None, None

    app.triage_intent = triage
    app._handle_search_response = lambda intent, handler, resp: handled.append(intent.materialization)
    app.run()
    q.put_nowait(SearchIntent(kind="transient_text", materialization="a", time=1.0))
    await asyncio.sleep(0.005)
    q.put_nowait(SearchIntent(kind="transient_text", materialization="ab", time=2.0))
    await asyncio.sleep(0.08)
    await app.stop()

    assert handled == ["ab"]


def test_get_preferred_language():
    user = DefaultUser()
    app = _PersonalizedApp(user_profile=user)
    # No country code
    assert app.get_preferred_language() == user.get_current_language()
    # With country code
    cc = "DE"
    assert app.get_preferred_language(cc) == user.get_preferred_country_language(cc)


def test_extract_country_code_single():
    resp = MagicMock()
    resp.data = {"items": [{"address": {"countryCode": "DE"}}, {"address": {"countryCode": "DE"}}]}
    assert UserProfileMixin._extract_country_code(resp) == "DE"


def test_extract_country_code_mixed():
    resp = MagicMock()
    resp.data = {"items": [{"address": {"countryCode": "DE"}}, {"address": {"countryCode": "FR"}}]}
    assert UserProfileMixin._extract_country_code(resp) is None


def test_extract_country_code_absent():
    resp = MagicMock()
    resp.data = {"items": [{"address": {}}, {"title": "no address key"}]}
    assert UserProfileMixin._extract_country_code(resp) is None


def test_extract_country_code_empty_items():
    resp = MagicMock()
    resp.data = {"items": []}
    assert UserProfileMixin._extract_country_code(resp) is None


@pytest.mark.asyncio
async def test_adapt_language_changes_preferred_language():
    user = DefaultUser(preferred_languages={"DE": "de", None: "en"})
    app = _PersonalizedApp(user_profile=user)
    assert app.preferred_language == "en"

    resp = MagicMock()
    resp.data = {"items": [{"address": {"countryCode": "DE"}}, {"address": {"countryCode": "DE"}}]}
    await app.adapt_language(resp)
    assert app.preferred_language == "de"


@pytest.mark.asyncio
async def test_adapt_language_no_change_on_mixed_countries():
    user = DefaultUser(preferred_languages={"DE": "de", None: "en"})
    app = _PersonalizedApp(user_profile=user)
    initial = app.preferred_language

    resp = MagicMock()
    resp.data = {"items": [{"address": {"countryCode": "DE"}}, {"address": {"countryCode": "FR"}}]}
    await app.adapt_language(resp)
    assert app.preferred_language == initial


def test_set_search_center():
    app = _PersonalizedApp()
    app.set_search_center((10.0, 20.0))
    assert app.search_center == (10.0, 20.0)


# ---------------------------------------------------------------------------
# ActionIntent routing and signal tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_action_intent_routes_to_action_search_event(app, location_response_item, context):
    """ActionIntent must be routed to ActionSearchEvent (not DetailsSearchEvent)."""
    intent = ActionIntent(materialization=location_response_item, time=0.0)
    app.queue.put_nowait(intent)
    _, event, handler, config = await app.wait_for_search_event()
    assert isinstance(event, ActionSearchEvent)
    assert event.item is location_response_item


@pytest.mark.asyncio
async def test_action_search_event_sends_signal_when_opted_in(action_search_event):
    """ActionSearchEvent.get_response calls api.signals when share_experience=True."""
    mock_api = AsyncMock()
    mock_session = AsyncMock()
    from here_search_demo.entity.endpoint import NoConfig

    resp = await action_search_event.get_response(mock_api, NoConfig(), mock_session)

    assert resp is None
    mock_api.signals.assert_awaited_once()
    call_kwargs = mock_api.signals.call_args.kwargs
    assert call_kwargs["userId"] == "test-user-id"
    assert call_kwargs["action"] == "here:gs:action:view"


@pytest.mark.asyncio
async def test_action_search_event_skips_signal_when_opted_out(location_response_item, context):
    """ActionSearchEvent.get_response must NOT call api.signals when share_experience=False."""
    mock_api = AsyncMock()
    mock_session = AsyncMock()
    from here_search_demo.entity.endpoint import NoConfig

    event = ActionSearchEvent(item=location_response_item, context=context)
    await event.get_response(mock_api, NoConfig(), mock_session)

    mock_api.signals.assert_not_awaited()


# ---------------------------------------------------------------------------
# Architecture: OneBoxCore, UserProfileMixin, SearchHead Protocol
# ---------------------------------------------------------------------------


def test_onebox_core_is_importable():
    """OneBoxCore must be importable directly from here_search_demo.base."""
    from here_search_demo.base import OneBoxCore  # noqa: F401


def test_search_head_protocol_is_importable():
    """SearchHead Protocol must be importable from here_search_demo.base."""
    from here_search_demo.base import SearchHead  # noqa: F401


def test_user_profile_mixin_is_importable():
    """UserProfileMixin must be importable from here_search_demo.base."""
    from here_search_demo.base import UserProfileMixin  # noqa: F401


def test_onebox_core_satisfies_search_head_protocol():
    """OneBoxCore must structurally satisfy the SearchHead Protocol."""
    from typing import runtime_checkable
    from here_search_demo.base import OneBoxCore, SearchHead

    assert runtime_checkable  # SearchHead must be @runtime_checkable
    app = OneBoxCore()
    assert isinstance(app, SearchHead)


def test_user_profile_mixin_works_standalone_with_core():
    """UserProfileMixin can be mixed with OneBoxCore without widgets or credentials."""
    from here_search_demo.base import OneBoxCore, UserProfileMixin
    from here_search_demo.user import DefaultUser

    class MinimalApp(UserProfileMixin, OneBoxCore):
        pass

    user = DefaultUser()
    app = MinimalApp(user_profile=user)
    assert app.user_profile is user
    assert app.search_center == (user.current_latitude, user.current_longitude)


def test_user_profile_mixin_get_context_includes_user_fields():
    """_get_context() from UserProfileMixin enriches RequestContext with share_experience and user_id."""
    from here_search_demo.base import OneBoxCore, UserProfileMixin
    from here_search_demo.user import UserProfile

    class MinimalApp(UserProfileMixin, OneBoxCore):
        pass

    user = UserProfile(use_positioning=True, share_experience=True)
    app = MinimalApp(user_profile=user)
    ctx = app._get_context()
    assert ctx.share_experience is True
    assert ctx.user_id == user.id


def test_user_profile_mixin_set_search_center():
    """set_search_center() on a UserProfileMixin+OneBoxCore instance updates search_center."""
    from here_search_demo.base import OneBoxCore, UserProfileMixin

    class MinimalApp(UserProfileMixin, OneBoxCore):
        pass

    app = MinimalApp()
    app.set_search_center((48.85, 2.35))
    assert app.search_center == (48.85, 2.35)


def test_onebox_map_mro_includes_user_profile_mixin_before_core():
    """OneBoxMap MRO must place UserProfileMixin before OneBoxCore."""
    from here_search_demo.base import OneBoxCore, UserProfileMixin
    from here_search_demo.widgets.app import OneBoxMap

    mro = OneBoxMap.__mro__
    assert UserProfileMixin in mro
    assert OneBoxCore in mro
    assert mro.index(UserProfileMixin) < mro.index(OneBoxCore)
