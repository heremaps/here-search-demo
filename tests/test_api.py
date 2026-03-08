###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from unittest.mock import patch

import orjson
import pytest

import here_search_demo as demo
from here_search_demo.api import API
from here_search_demo.entity.request import Request
from here_search_demo.entity.endpoint import Endpoint


@pytest.fixture
def api():
    return API(api_key="api_key")


@pytest.fixture
def session():
    # Configure a response object with the expected interface.
    class _Response:
        def __init__(self, payload):
            self.headers = {"X-Request-Id": "userid", "X-Correlation-ID": "correlationId"}
            self._text = orjson.dumps(payload).decode("utf-8")
            self.url = "url"

        async def text(self) -> str:
            return self._text

        async def bytes(self) -> bytes:
            return self._text.encode("utf-8")

        def raise_for_status(self) -> None:
            # Synchronous no-op for tests
            return None

    payload = {"items": []}
    response = _Response(payload)

    class _CM:
        async def __aenter__(self):
            return response

        async def __aexit__(self, exc_type, exc, tb):
            return False

    # Create a simple object with a request() method that returns an async
    # context manager instance; this mimics the aiohttp/HTTPSession API that
    # api.do_send expects.
    class _Session:
        def __init__(self, cm):
            self._cm = cm

        def request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return self._cm

    return _Session(_CM())


@pytest.fixture
def a_dummy_request():
    return Request(
        endpoint=Endpoint.AUTOSUGGEST,
        url="url",
        params={"p1": "v1", "p2": "v2"},
        data=None,
        x_headers={"X-Request-Id": "userid", "X-Correlation-ID": "correlationId"},
    )


@pytest.mark.asyncio
async def test_get(api, a_dummy_request, session):
    response = await api.send(session, "GET", a_dummy_request)

    assert response.data == {"items": []}
    assert response.req is a_dummy_request
    assert response.x_headers["X-Request-Id"] == "userid"


@pytest.mark.asyncio
async def test_get_uncache(api, a_dummy_request, session):
    # First call populates the cache
    first = await api.send(session, "GET", a_dummy_request)
    # Second call should return a cached Response with the same data
    second = await api.send(session, "GET", a_dummy_request)

    assert second.data == first.data == {"items": []}
    assert second.req is first.req is a_dummy_request


@pytest.mark.asyncio
async def test_uncache(api, a_dummy_request, session):
    # Populate cache
    _ = await api.send(session, "GET", a_dummy_request)
    # Directly uncache and ensure we still get a Response with same data
    cached = api._API__uncache(a_dummy_request.key)
    assert cached.data == {"items": []}
    assert cached.req == a_dummy_request


@pytest.mark.asyncio
async def test_autosuggest(api, autosuggest_request, session):
    with patch.object(demo.api.API, "send") as send:
        latitude, longitude = map(float, autosuggest_request.params["at"].split(","))
        await api.autosuggest(
            session=session,
            q=autosuggest_request.params["q"],
            latitude=latitude,
            longitude=longitude,
            x_headers=autosuggest_request.x_headers,
        )
    send.assert_called_once_with(session, "GET", autosuggest_request)


@pytest.mark.asyncio
async def test_autosuggest_href(api, autosuggest_href_request, session):
    with patch.object(demo.api.API, "send") as send:
        await api.autosuggest_href(
            session=session, href=autosuggest_href_request.full, x_headers=autosuggest_href_request.x_headers
        )
    send.assert_called_once_with(session, "GET", autosuggest_href_request)


@pytest.mark.asyncio
async def test_discover(api, discover_request, session):
    with patch.object(demo.api.API, "send") as send:
        latitude, longitude = map(float, discover_request.params["at"].split(","))
        await api.discover(
            session=session,
            q=discover_request.params["q"],
            latitude=latitude,
            longitude=longitude,
            x_headers=discover_request.x_headers,
        )
    send.assert_called_once_with(session, "GET", discover_request)


@pytest.mark.asyncio
async def test_browse(api, browse_request, session):
    with patch.object(demo.api.API, "send") as send:
        latitude, longitude = map(float, browse_request.params["at"].split(","))
        await api.browse(session=session, latitude=latitude, longitude=longitude, x_headers=browse_request.x_headers)
    send.assert_called_once_with(session, "GET", browse_request)


@pytest.mark.asyncio
async def test_browse_with_categories(api, browse_categories_request, session):
    with patch.object(demo.api.API, "send") as send:
        latitude, longitude = map(float, browse_categories_request.params["at"].split(","))
        await api.browse(
            session=session,
            latitude=latitude,
            longitude=longitude,
            categories=browse_categories_request.params["categories"].split(","),
            x_headers=browse_categories_request.x_headers,
        )
    send.assert_called_once_with(session, "GET", browse_categories_request)


@pytest.mark.asyncio
async def test_browse_with_foodtypes(api, browse_cuisines_request, session):
    with patch.object(demo.api.API, "send") as send:
        latitude, longitude = map(float, browse_cuisines_request.params["at"].split(","))
        await api.browse(
            session=session,
            latitude=latitude,
            longitude=longitude,
            food_types=sorted(browse_cuisines_request.params["foodTypes"].split(",")),
            x_headers=browse_cuisines_request.x_headers,
        )
    send.assert_called_once_with(session, "GET", browse_cuisines_request)


@pytest.mark.asyncio
async def test_browse_with_chains(api, browse_chains_request, session):
    with patch.object(demo.api.API, "send") as send:
        latitude, longitude = map(float, browse_chains_request.params["at"].split(","))
        await api.browse(
            session=session,
            latitude=latitude,
            longitude=longitude,
            chains=browse_chains_request.params["chains"].split(","),
            x_headers=browse_chains_request.x_headers,
        )
    send.assert_called_once_with(session, "GET", browse_chains_request)


@pytest.mark.asyncio
async def test_lookup(api, lookup_request, session):
    with patch.object(demo.api.API, "send") as send:
        await api.lookup(session=session, id=lookup_request.params["id"], x_headers=lookup_request.x_headers)
    send.assert_called_once_with(session, "GET", lookup_request)


@pytest.mark.asyncio
async def test_revgeocode(api, revgeocode_request, session):
    with patch.object(demo.api.API, "send") as send:
        latitude, longitude = map(float, revgeocode_request.params["at"].split(","))
        await api.reverse_geocode(
            session=session, latitude=latitude, longitude=longitude, x_headers=revgeocode_request.x_headers
        )
    send.assert_called_once_with(session, "GET", revgeocode_request)
