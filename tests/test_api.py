###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest

import here_search

from unittest.mock import patch


@pytest.mark.asyncio
async def test_get(api, a_dummy_request, session):
    with patch.object(here_search.demo.api.API, "_API__uncache") as uncache:
        response = await api.get(a_dummy_request, session)

        assert response.data == await (await session.get().__aenter__()).json()
        assert response.x_headers == (await session.get().__aenter__()).headers
        assert response.req == a_dummy_request
        uncache.assert_not_called()


@pytest.mark.asyncio
async def test_get_uncache(api, a_dummy_request, session):
    with patch.object(here_search.demo.api.API, "_API__uncache") as uncache:
        uncache.return_value = None
        response = await api.get(a_dummy_request, session)

        assert response.data == await (await session.get().__aenter__()).json()
        assert response.x_headers == (await session.get().__aenter__()).headers
        assert response.req == a_dummy_request
        uncache.assert_not_called()

        uncache.return_value = response
        response = await api.get(a_dummy_request, session)

        assert response.data == await (await session.get().__aenter__()).json()
        assert response.x_headers == (await session.get().__aenter__()).headers
        assert response.req == a_dummy_request
        uncache.assert_called_once()


@pytest.mark.asyncio
async def test_uncache(api, a_dummy_request, session):
    response = await api.get(a_dummy_request, session)
    cached_response = api._API__uncache(a_dummy_request.key)
    assert response.data == cached_response.data


@pytest.mark.asyncio
async def test_autosuggest(api, autosuggest_request, session):
    with patch.object(here_search.demo.api.API, "get") as get:
        latitude, longitude = map(float, autosuggest_request.params["at"].split(","))
        await api.autosuggest(
            q=autosuggest_request.params["q"],
            latitude=latitude,
            longitude=longitude,
            session=session,
            x_headers=autosuggest_request.x_headers,
        )
    get.assert_called_once_with(autosuggest_request, session)


@pytest.mark.asyncio
async def test_autosuggest_href(api, autosuggest_href_request, session):
    with patch.object(here_search.demo.api.API, "get") as get:
        await api.autosuggest_href(
            href=autosuggest_href_request.full,
            session=session,
            x_headers=autosuggest_href_request.x_headers,
        )
    get.assert_called_once_with(autosuggest_href_request, session)


@pytest.mark.asyncio
async def test_discover(api, discover_request, session):
    with patch.object(here_search.demo.api.API, "get") as get:
        latitude, longitude = map(float, discover_request.params["at"].split(","))
        await api.discover(
            q=discover_request.params["q"],
            latitude=latitude,
            longitude=longitude,
            session=session,
            x_headers=discover_request.x_headers,
        )
    get.assert_called_once_with(discover_request, session)


@pytest.mark.asyncio
async def test_browse(api, browse_request, session):
    with patch.object(here_search.demo.api.API, "get") as get:
        latitude, longitude = map(float, browse_request.params["at"].split(","))
        await api.browse(
            latitude=latitude,
            longitude=longitude,
            session=session,
            x_headers=browse_request.x_headers,
        )
    get.assert_called_once_with(browse_request, session)


@pytest.mark.asyncio
async def test_browse_with_categories(api, browse_categories_request, session):
    with patch.object(here_search.demo.api.API, "get") as get:
        latitude, longitude = map(float, browse_categories_request.params["at"].split(","))
        await api.browse(
            categories=browse_categories_request.params["categories"].split(","),
            latitude=latitude,
            longitude=longitude,
            session=session,
            x_headers=browse_categories_request.x_headers,
        )
    get.assert_called_once_with(browse_categories_request, session)


@pytest.mark.asyncio
async def test_browse_with_foodtypes(api, browse_cuisines_request, session):
    with patch.object(here_search.demo.api.API, "get") as get:
        latitude, longitude = map(float, browse_cuisines_request.params["at"].split(","))
        await api.browse(
            food_types=sorted(browse_cuisines_request.params["foodTypes"].split(",")),
            latitude=latitude,
            longitude=longitude,
            session=session,
            x_headers=browse_cuisines_request.x_headers,
        )
    get.assert_called_once_with(browse_cuisines_request, session)


@pytest.mark.asyncio
async def test_browse_with_chains(api, browse_chains_request, session):
    with patch.object(here_search.demo.api.API, "get") as get:
        latitude, longitude = map(float, browse_chains_request.params["at"].split(","))
        await api.browse(
            chains=browse_chains_request.params["chains"].split(","),
            latitude=latitude,
            longitude=longitude,
            session=session,
            x_headers=browse_chains_request.x_headers,
        )
    get.assert_called_once_with(browse_chains_request, session)


@pytest.mark.asyncio
async def test_lookup(api, lookup_request, session):
    with patch.object(here_search.demo.api.API, "get") as get:
        await api.lookup(
            id=lookup_request.params["id"],
            session=session,
            x_headers=lookup_request.x_headers,
        )
    get.assert_called_once_with(lookup_request, session)


@pytest.mark.asyncio
async def test_revgeocode(api, revgeocode_request, session):
    with patch.object(here_search.demo.api.API, "get") as get:
        latitude, longitude = map(float, revgeocode_request.params["at"].split(","))
        await api.reverse_geocode(
            latitude=latitude,
            longitude=longitude,
            session=session,
            x_headers=revgeocode_request.x_headers,
        )
    get.assert_called_once_with(revgeocode_request, session)
