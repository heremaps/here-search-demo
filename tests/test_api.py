import pytest

import here_search.api
from here_search.entities import Request, Response, Endpoint

from unittest.mock import Mock, patch
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_retrieve_response(api, a_request, session_response):

    cache_key = "cache_key"
    response = await api.restrieve_response(session_response, a_request, cache_key=cache_key)

    assert response.data == await session_response.json()
    assert response.x_headers == session_response.headers
    assert response.req == a_request
    assert api.cache[cache_key] == (session_response.url.human_repr(), response)


@pytest.mark.asyncio
@patch("here_search.api.ClientSession.get")
async def test_get_without_session(mock_get, api, a_request, session_response):
    mock_get.return_value = AsyncMock(
        __aenter__=AsyncMock(return_value=session_response), __aexit__=AsyncMock(return_value=None)
    )
    response = await api.get(a_request)

    assert response.data == await session_response.json()
    assert response.x_headers == session_response.headers
    assert a_request == response.req


@pytest.mark.asyncio
async def test_get_with_session(api, a_request, session):
    response = await api.get(a_request, session)

    assert response.data == await (await session.get().__aenter__()).json()
    assert response.x_headers == (await session.get().__aenter__()).headers
    assert response.req == a_request


@pytest.mark.asyncio
async def test_autosuggest(api, autosuggest_request):
    with patch.object(here_search.api.API, "get") as get:
        latitude, longitude = map(float, autosuggest_request.params["at"].split(","))
        await api.autosuggest(q=autosuggest_request.params["q"], latitude=latitude, longitude=longitude, x_headers=autosuggest_request.x_headers)
    get.assert_called_once_with(autosuggest_request, None)
