import here_search.api
from src.here_search.entities import Request, Response, Endpoint
from unittest.mock import Mock, AsyncMock, patch
import pytest

expected_response_data = {"a": "b"}
expected_x_headers = {"X-Request-Id": 'userid',
                      "X-Correlation-ID": "correlationId"}

request = Request(endpoint=Endpoint.AUTOSUGGEST,
                  url='url',
                  x_headers={'X-a': 1, 'Y-b': 2},
                  params={'p1': 'v1', 'p2': 'v2'})

aiohttp_response = AsyncMock(**{'url': Mock(**{'human_repr.return_value': "human_url"}),
                                'json.return_value': expected_response_data,
                                'headers': expected_x_headers})
aiohttp_session = AsyncMock(get=Mock(**{'return_value.__aenter__': AsyncMock(return_value=aiohttp_response),
                                        'return_value.__aexit__': AsyncMock(return_value=None)}))


async def response() -> Response:
    api = here_search.api.API(api_key="api_key")

    aiohttp_response = AsyncMock(**{'json.return_value': expected_response_data, 'headers': expected_x_headers})
    aiohttp_session = AsyncMock(get=Mock(**{'return_value.__aenter__': AsyncMock(return_value=aiohttp_response),
                                            'return_value.__aexit__': AsyncMock(return_value=None)}))

    response = await api.get(request, aiohttp_session)

    return response

@pytest.mark.asyncio
async def test_retrieve_response():
    api = here_search.api.API(api_key="api_key")

    request = Request(endpoint=Endpoint.AUTOSUGGEST,
                      url="url",
                      x_headers={'X-a': 1, 'Y-b': 2},
                      params={'p1': 'v1', 'p2': 'v2'})

    expected_response_data = {"a": "b"}
    expected_x_headers = {"X-Request-Id": 'userid',
                          "X-Correlation-ID": "correlationId"}

    aiohttp_response = AsyncMock(**{'url': Mock(**{'human_repr.return_value': "human_url"}),
                                    'json.return_value': expected_response_data,
                                    'headers': expected_x_headers})

    cache_key = "cache_key"

    response = await api.restrieve_response(aiohttp_response, request, cache_key=cache_key)

    assert expected_response_data == response.data
    assert expected_x_headers == response.x_headers
    assert request == response.req
    assert api.cache[cache_key] == (aiohttp_response.url.human_repr(), response)


def test_request_key():
    request = Request(endpoint=Endpoint.AUTOSUGGEST,
                      url="url",
                      x_headers={'X-a': 1, 'Y-b': 2},
                      params={'p1': 'v1', 'p2': 'v2'})
    assert request.key() == "urlp1v1p2v2"


@pytest.mark.asyncio
@patch('here_search.api.ClientSession.get')
async def test_get_without_session(mock_get):
    expected_response_data = {"a": "b"}
    expected_x_headers = {"X-Request-Id": 'userid',
                          "X-Correlation-ID": "correlationId"}
    aiohttp_response = AsyncMock(**{'url': Mock(**{'human_repr.return_value': "human_url"}),
                                    'json.return_value': expected_response_data,
                                    'headers': expected_x_headers})
    mock_get.return_value = AsyncMock(__aenter__=AsyncMock(return_value=aiohttp_response),
                                      __aexit__=AsyncMock(return_value=None))
    api = here_search.api.API(api_key="api_key")

    request = Request(endpoint=Endpoint.AUTOSUGGEST,
                      url="url",
                      x_headers={'X-a': 1, 'Y-b': 2},
                      params={'p1': 'v1', 'p2': 'v2'})

    response = await api.get(request)

    assert expected_response_data == response.data
    assert expected_x_headers == response.x_headers
    assert request == response.req


@pytest.mark.asyncio
async def test_get_with_session():
    expected_response_data = {"a": "b"}
    expected_x_headers = {"X-Request-Id": 'userid',
                          "X-Correlation-ID": "correlationId"}
    aiohttp_response = AsyncMock(**{'url': Mock(**{'human_repr.return_value': "human_url"}),
                                    'json.return_value': expected_response_data,
                                    'headers': expected_x_headers})
    aiohttp_session = AsyncMock(get=Mock(**{'return_value.__aenter__': AsyncMock(return_value=aiohttp_response),
                                            'return_value.__aexit__': AsyncMock(return_value=None)}))
    api = here_search.api.API(api_key="api_key")

    request = Request(endpoint=Endpoint.AUTOSUGGEST,
                      url="url",
                      x_headers={'X-a': 1, 'Y-b': 2},
                      params={'p1': 'v1', 'p2': 'v2'})

    response = await api.get(request, aiohttp_session)

    assert expected_response_data == response.data
    assert expected_x_headers == response.x_headers
    assert request == response.req



