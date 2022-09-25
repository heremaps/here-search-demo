import pytest

from here_search.api import (
    API,
    base_url,
)
from here_search.event import (
    PartialTextSearchEvent,
    TextSearchEvent,
    PlaceTaxonomySearchEvent,
    DetailsSearchEvent,
    EmptySearchEvent,
)
from here_search.entity.request import (
    Request,
    RequestContext,
    Response,
    ResponseItem,
)
from here_search.entity.endpoint import Endpoint, AutosuggestConfig, DiscoverConfig, BrowseConfig, LookupConfig
from here_search.entity.place import PlaceTaxonomyItem
from here_search.base import OneBoxSimple

from unittest.mock import Mock
from unittest.mock import AsyncMock
from os import environ


@pytest.fixture
def api():
    return API(api_key="api_key")


@pytest.fixture
def x_headers():
    return {"X-Request-Id": "userid", "X-Correlation-ID": "correlationId"}


@pytest.fixture
def a_request(x_headers):
    return Request(
        endpoint=Endpoint.AUTOSUGGEST,
        url="url",
        params={"p1": "v1", "p2": "v2"},
        x_headers=x_headers,
    )


@pytest.fixture
def instant_query_text() -> str:
    return "r"


@pytest.fixture
def query_text() -> str:
    return "restaurant"


@pytest.fixture
def place_taxonomy_item() -> PlaceTaxonomyItem:
    return PlaceTaxonomyItem("gas", ["cat1", "cat2", "cat3"], None, None)


@pytest.fixture
def context():
    language, latitude, longitude = "language", 1.0, 2.0
    return RequestContext(latitude=latitude, longitude=longitude, language=language)


@pytest.fixture
def autosuggest_request(context, instant_query_text, x_headers):
    return Request(
        endpoint=Endpoint.AUTOSUGGEST,
        url=base_url[Endpoint.AUTOSUGGEST],
        params={
            "q": instant_query_text,
            "at": f"{context.latitude},{context.longitude}",
        },
        x_headers=x_headers,
    )


@pytest.fixture
def response(a_request):
    data = [
        {"resultType": "place"},
        {"resultType": "chainQuery"},
        {"resultType": "categoryQuery"},
    ]
    return Response(req=a_request, data={"items": data})


@pytest.fixture
def location_response_item(response):
    rank = 0
    data = response.data["items"][rank]
    assert data["resultType"] == "place"
    return ResponseItem(resp=response, data=data, rank=rank)


@pytest.fixture
def chain_query_response_item(response):
    rank = 1
    data = response.data["items"][rank]
    assert data["resultType"] == "chainQuery"
    return ResponseItem(resp=response, data=data, rank=rank)


@pytest.fixture
def category_query_response_item(response):
    rank = 2
    data = response.data["items"][rank]
    assert data["resultType"] == "categoryQuery"
    return ResponseItem(resp=response, data=data, rank=rank)


@pytest.fixture
def partial_text_search_event(instant_query_text, context) -> PartialTextSearchEvent:
    return PartialTextSearchEvent(query_text=instant_query_text, context=context)


@pytest.fixture
def text_search_event(query_text, context) -> TextSearchEvent:
    return TextSearchEvent(query_text=query_text, context=context)


@pytest.fixture
def taxonomy_search_event(place_taxonomy_item, context) -> PlaceTaxonomySearchEvent:
    return PlaceTaxonomySearchEvent(item=place_taxonomy_item, context=context)


@pytest.fixture
def details_search_event(location_response_item, context) -> DetailsSearchEvent:
    return DetailsSearchEvent(item=location_response_item, context=context)


@pytest.fixture
def empty_search_event() -> EmptySearchEvent:
    return EmptySearchEvent()


@pytest.fixture
def session_response(response, x_headers):
    return AsyncMock(
        **{
            "url": Mock(**{"human_repr.return_value": "human_url"}),
            "json.return_value": response.data,
            "headers": x_headers,
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


@pytest.fixture
def autosuggest_config(app):
    return AutosuggestConfig(limit=app.suggestions_limit, terms_limit=app.terms_limit)


@pytest.fixture
def discover_config(app):
    return DiscoverConfig(limit=app.results_limit)


@pytest.fixture
def browse_config(app):
    return BrowseConfig(limit=app.results_limit)


@pytest.fixture
def lookup_config(app):
    return LookupConfig()
