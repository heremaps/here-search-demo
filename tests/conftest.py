import pytest

import here_search.api
from here_search.entities import Request, Endpoint
from here_search.base import OneBoxSimple

from unittest.mock import Mock
from unittest.mock import AsyncMock
from os import environ


@pytest.fixture
def api():
    return here_search.api.API(api_key="api_key")


@pytest.fixture
def x_headers():
    return {"X-Request-Id": "userid", "X-Correlation-ID": "correlationId"}


@pytest.fixture
def a_request(x_headers):
    return Request(
        endpoint=Endpoint.AUTOSUGGEST, url="url", params={"p1": "v1", "p2": "v2"}, x_headers=x_headers
    )

@pytest.fixture
def autosuggest_request(x_headers):
    q, latitude, longitude = "q", 1.0, 2.0
    return Request(
        endpoint=Endpoint.AUTOSUGGEST, url=here_search.api.base_url[Endpoint.AUTOSUGGEST],
        params={"q": q, "at": f"{latitude},{longitude}"},
        x_headers=x_headers
    )


@pytest.fixture
def response_data():
    return {"a": "b"}


@pytest.fixture
def session_response(response_data, x_headers):
    return AsyncMock(
        **{
            "url": Mock(**{"human_repr.return_value": "human_url"}),
            "json.return_value": response_data,
            "headers": x_headers
        }
    )


@pytest.fixture
def session(session_response):
    return AsyncMock(
        get=Mock(
            **{
                "return_value.__aenter__": AsyncMock(return_value=session_response),
                "return_value.__aexit__": AsyncMock(return_value=None),
            }
        )
    )



@pytest.fixture
def app():
    environ["API_KEY"] = "api_key"
    return OneBoxSimple()
