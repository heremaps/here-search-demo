###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest

from here_search.demo.api import API

from here_search.demo.event import (
    PartialTextSearchEvent,
    TextSearchEvent,
    PlaceTaxonomySearchEvent,
    DetailsSearchEvent,
    EmptySearchEvent,
)
from here_search.demo.entity.intent import (
    FormulatedTextIntent,
    TransientTextIntent,
    PlaceTaxonomyIntent,
    MoreDetailsIntent,
    NoIntent,
)
from here_search.demo.entity.request import Request, RequestContext
from here_search.demo.entity.response import Response, ResponseItem, QuerySuggestionItem
from here_search.demo.entity.endpoint import Endpoint, AutosuggestConfig, DiscoverConfig, BrowseConfig, LookupConfig
from here_search.demo.entity.place import PlaceTaxonomyItem
from here_search.demo.widgets.input import PlaceTaxonomyButton
from here_search.demo.base import OneBoxSimple

from unittest.mock import Mock
from unittest.mock import AsyncMock
from os import environ


@pytest.fixture
def api_key():
    return "api_key"


@pytest.fixture
def api(api_key):
    return API(api_key=api_key)


@pytest.fixture
def x_headers():
    return {"X-Request-Id": "userid", "X-Correlation-ID": "correlationId"}


@pytest.fixture
def a_dummy_request(x_headers):
    return Request(
        endpoint=Endpoint.AUTOSUGGEST,
        url="url",
        params={"p1": "v1", "p2": "v2"},
        x_headers=x_headers,
    )


@pytest.fixture
def lat_lon():
    return 1.0, 2.0


@pytest.fixture
def instant_query_text() -> str:
    return "r"


@pytest.fixture
def query_text() -> str:
    return "restaurant"


@pytest.fixture
def location_id() -> str:
    return "location_id"


@pytest.fixture
def href(api_key) -> str:
    return f"{API.BASE_URL[Endpoint.DISCOVER]}?apiKey={api_key}&href_text"


@pytest.fixture
def place_taxonomy_item() -> PlaceTaxonomyItem:
    return PlaceTaxonomyItem("gas", ["cat1", "cat2", "cat3"], None, None)


@pytest.fixture
def context(lat_lon):
    language = "language"
    return RequestContext(latitude=lat_lon[0], longitude=lat_lon[1], language=language)


@pytest.fixture
def autosuggest_request(context, instant_query_text, x_headers):
    return Request(
        endpoint=Endpoint.AUTOSUGGEST,
        url=API.BASE_URL[Endpoint.AUTOSUGGEST],
        params={
            "q": instant_query_text,
            "at": f"{context.latitude},{context.longitude}",
        },
        x_headers=x_headers,
    )


@pytest.fixture
def autosuggest_href_request(context, x_headers):
    return Request(
        endpoint=Endpoint.AUTOSUGGEST_HREF,
        url=API.BASE_URL[Endpoint.DISCOVER],
        params={
            "foo": "bar",
        },
        x_headers=x_headers,
    )


@pytest.fixture
def autosuggest_response(autosuggest_request):
    data = [
        {"resultType": "place"},
        {"resultType": "chainQuery"},
        {"resultType": "categoryQuery"},
    ]
    return Response(req=autosuggest_request, data={"items": data})


@pytest.fixture
def location_response_item(autosuggest_response):
    rank = 0
    data = autosuggest_response.data["items"][rank]
    assert data["resultType"] == "place"
    return ResponseItem(resp=autosuggest_response, data=data, rank=rank)


@pytest.fixture
def chain_query_response_item(autosuggest_response):
    rank = 1
    data = autosuggest_response.data["items"][rank]
    assert data["resultType"] == "chainQuery"
    return QuerySuggestionItem(resp=autosuggest_response, data=data, rank=rank)


@pytest.fixture
def category_query_response_item(autosuggest_response):
    rank = 2
    data = autosuggest_response.data["items"][rank]
    assert data["resultType"] == "categoryQuery"
    return QuerySuggestionItem(resp=autosuggest_response, data=data, rank=rank)


@pytest.fixture
def discover_request(context, query_text, x_headers):
    return Request(
        endpoint=Endpoint.DISCOVER,
        url=API.BASE_URL[Endpoint.DISCOVER],
        params={
            "q": query_text,
            "at": f"{context.latitude},{context.longitude}",
        },
        x_headers=x_headers,
    )


@pytest.fixture
def discover_browse_response(discover_request):
    data = [
        {"resultType": "place"},
        {"resultType": "street"},
        {"resultType": "location"},
    ]
    return Response(req=discover_request, data={"items": data})


@pytest.fixture
def browse_request(context, query_text, x_headers):
    return Request(
        endpoint=Endpoint.BROWSE,
        url=API.BASE_URL[Endpoint.BROWSE],
        params={
            "at": f"{context.latitude},{context.longitude}",
        },
        x_headers=x_headers,
    )


@pytest.fixture
def browse_categories_request(context, query_text, x_headers):
    return Request(
        endpoint=Endpoint.BROWSE,
        url=API.BASE_URL[Endpoint.BROWSE],
        params={
            "categories": "foo",
            "at": f"{context.latitude},{context.longitude}",
        },
        x_headers=x_headers,
    )


@pytest.fixture
def browse_cuisines_request(context, query_text, x_headers):
    return Request(
        endpoint=Endpoint.BROWSE,
        url=API.BASE_URL[Endpoint.BROWSE],
        params={
            "foodTypes": "bar,foo",
            "at": f"{context.latitude},{context.longitude}",
        },
        x_headers=x_headers,
    )


@pytest.fixture
def browse_chains_request(context, query_text, x_headers):
    return Request(
        endpoint=Endpoint.BROWSE,
        url=API.BASE_URL[Endpoint.BROWSE],
        params={
            "chains": "1,2,3",
            "at": f"{context.latitude},{context.longitude}",
        },
        x_headers=x_headers,
    )


@pytest.fixture
def lookup_request(context, location_id, x_headers):
    return Request(
        endpoint=Endpoint.LOOKUP,
        url=API.BASE_URL[Endpoint.LOOKUP],
        params={
            "id": location_id,
        },
        x_headers=x_headers,
    )


@pytest.fixture
def revgeocode_request(lat_lon, x_headers):
    return Request(
        endpoint=Endpoint.REVGEOCODE,
        url=API.BASE_URL[Endpoint.REVGEOCODE],
        params={
            "at": f"{lat_lon[0]},{lat_lon[1]}",
        },
        x_headers=x_headers,
    )


#########################################################
# SearchIntent fixtures


@pytest.fixture
def place_taxonomy_item2():
    return PlaceTaxonomyItem("gas", ["cat1", "cat2"], ["food1", "food2"], ["chain1", "chain2"])


@pytest.fixture
def place_taxonomy_button(place_taxonomy_item2):
    return PlaceTaxonomyButton(place_taxonomy_item2, "some_icon")


@pytest.fixture
def formulated_text_intent():
    return FormulatedTextIntent("formulated intent")


@pytest.fixture
def transient_text_intent():
    return TransientTextIntent("formulated i")


@pytest.fixture
def place_taxonomy_intent(place_taxonomy_button):
    return PlaceTaxonomyIntent(place_taxonomy_button.item)


@pytest.fixture
def more_details_intent(location_response_item):
    return MoreDetailsIntent(location_response_item)


@pytest.fixture
def no_intent():
    return NoIntent()


#########################################################
# SearchEvent fixtures


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
def session_response(autosuggest_response, x_headers):
    return AsyncMock(
        **{
            "url": Mock(**{"human_repr.return_value": "human_url"}),
            "json.return_value": autosuggest_response.data,
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


@pytest.fixture(scope="session")
def app():
    environ["API_KEY"] = "api_key"
    return OneBoxSimple()


#########################################################
# EndpointConfig fixtures


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
