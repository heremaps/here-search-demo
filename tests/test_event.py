###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Tests for the corridor-search delegation in here_search_demo.event."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from here_search_demo.entity.endpoint import BrowseConfig, DiscoverConfig
from here_search_demo.entity.place import PlaceTaxonomyItem
from here_search_demo.entity.request import RequestContext
from here_search_demo.entity.response import Response
from here_search_demo.event import PlaceTaxonomySearchEvent, TextSearchEvent

_SENTINEL_RESP = Response(req=None, data={"items": []})


# ---------------------------------------------------------------------------
# TextSearchEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_text_search_event_delegates_to_corridor_search():
    context = RequestContext(latitude=1.0, longitude=2.0, polyline="poly", width=100, all_along=True, language="en")
    event = TextSearchEvent(context=context, query_text="restaurant")
    config = DiscoverConfig(limit=20)
    api = MagicMock()
    session = MagicMock()

    with patch("here_search_demo.event.corridor_search", new=AsyncMock(return_value=_SENTINEL_RESP)) as mocked:
        result = await event.get_response(api, config, session)

    assert result is _SENTINEL_RESP
    kwargs = mocked.await_args.kwargs
    assert kwargs["context"] is context
    assert kwargs["limit"] == 20
    assert kwargs["session"] is session

    # The single_call closure forwards correctly into api.discover.
    api.discover = AsyncMock(return_value=_SENTINEL_RESP)
    await kwargs["single_call"](session, "slice-poly", 10.0, 20.0, 3)
    api.discover.assert_awaited_once_with(
        session=session,
        q="restaurant",
        latitude=10.0,
        longitude=20.0,
        polyline="slice-poly",
        width=100,
        all_along=True,
        x_headers=None,
        lang="en",
        limit=3,
    )


@pytest.mark.asyncio
async def test_text_search_event_short_route_calls_discover_once():
    context = RequestContext(latitude=1.0, longitude=2.0, language="en")  # no route -> no stratification
    event = TextSearchEvent(context=context, query_text="restaurant")
    config = DiscoverConfig(limit=20)
    api = MagicMock()
    api.discover = AsyncMock(return_value=_SENTINEL_RESP)
    session = MagicMock()

    result = await event.get_response(api, config, session)

    assert result is _SENTINEL_RESP
    api.discover.assert_awaited_once_with(
        session=session,
        q="restaurant",
        latitude=1.0,
        longitude=2.0,
        polyline=None,
        width=None,
        all_along=None,
        x_headers=None,
        lang="en",
        limit=20,
    )


# ---------------------------------------------------------------------------
# PlaceTaxonomySearchEvent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_taxonomy_search_event_delegates_to_corridor_search():
    context = RequestContext(latitude=1.0, longitude=2.0, polyline="poly", width=100, all_along=True, language="en")
    item = PlaceTaxonomyItem("gas", ["cat1"], None, None)
    event = PlaceTaxonomySearchEvent(context=context, item=item)
    config = BrowseConfig(limit=20)
    api = MagicMock()
    session = MagicMock()

    with patch("here_search_demo.event.corridor_search", new=AsyncMock(return_value=_SENTINEL_RESP)) as mocked:
        result = await event.get_response(api, config, session)

    assert result is _SENTINEL_RESP
    kwargs = mocked.await_args.kwargs
    assert kwargs["limit"] == 20

    api.browse = AsyncMock(return_value=_SENTINEL_RESP)
    await kwargs["single_call"](session, "slice-poly", 10.0, 20.0, 3)
    api.browse.assert_awaited_once_with(
        session=session,
        latitude=10.0,
        longitude=20.0,
        polyline="slice-poly",
        width=100,
        all_along=True,
        x_headers=None,
        lang="en",
        limit=3,
        categories=["cat1"],
        food_types=None,
        chains=None,
    )


@pytest.mark.asyncio
async def test_taxonomy_search_event_short_route_calls_browse_once():
    context = RequestContext(latitude=1.0, longitude=2.0, language="en")
    item = PlaceTaxonomyItem("gas", ["cat1"], None, None)
    event = PlaceTaxonomySearchEvent(context=context, item=item)
    config = BrowseConfig(limit=20)
    api = MagicMock()
    api.browse = AsyncMock(return_value=_SENTINEL_RESP)
    session = MagicMock()

    result = await event.get_response(api, config, session)

    assert result is _SENTINEL_RESP
    api.browse.assert_awaited_once_with(
        session=session,
        latitude=1.0,
        longitude=2.0,
        polyline=None,
        width=None,
        all_along=None,
        x_headers=None,
        lang="en",
        limit=20,
        categories=["cat1"],
        food_types=None,
        chains=None,
    )
