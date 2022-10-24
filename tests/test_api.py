import pytest

import here_search.api

from unittest.mock import patch


@pytest.mark.asyncio
async def test_get(api, a_request, session):
    response = await api.get(a_request, session)

    assert response.data == await (await session.get().__aenter__()).json()
    assert response.x_headers == (await session.get().__aenter__()).headers
    assert response.req == a_request


@pytest.mark.asyncio
async def test_autosuggest(api, autosuggest_request, session):
    with patch.object(here_search.api.API, "get") as get:
        latitude, longitude = map(float, autosuggest_request.params["at"].split(","))
        await api.autosuggest(
            q=autosuggest_request.params["q"],
            latitude=latitude,
            longitude=longitude,
            session=session,
            x_headers=autosuggest_request.x_headers,
        )
    get.assert_called_once_with(autosuggest_request, session)
