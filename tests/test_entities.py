###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest

from here_search.demo.entity.request import Request
from here_search.demo.entity.response import Response
from here_search.demo.entity.endpoint import Endpoint

expected_response_data = {"a": "b"}
expected_x_headers = {"X-Request-Id": "userid", "X-Correlation-ID": "correlationId"}

request = Request(
    endpoint=Endpoint.AUTOSUGGEST,
    url="url",
    x_headers={"X-a": 1, "Y-b": 2},
    params={"p1": "v1", "p2": "v2"},
)


def test_request_key():
    request = Request(
        endpoint=Endpoint.AUTOSUGGEST,
        url="url",
        x_headers={"X-a": 1, "Y-b": 2},
        params={"p1": "v1", "p2": "v2"},
    )
    assert request.key == "urlp1v1p2v2"


def test_request_full():
    request = Request(
        endpoint=Endpoint.AUTOSUGGEST,
        url="url",
        x_headers={"X-a": 1, "Y-b": 2},
        params={"p1": "v1", "p2": "v2"},
    )
    assert request.full == "url?p1=v1&p2=v2"


def test_response_titles():
    assert Response(req=Request(endpoint=Endpoint.AUTOSUGGEST), data={"items": []}).titles == []
    assert Response(
        req=Request(endpoint=Endpoint.AUTOSUGGEST),
        data={"items": [{"title": "title1"}]},
    ).titles == ["title1"]
    assert Response(
        req=Request(endpoint=Endpoint.AUTOSUGGEST),
        data={"items": [{"title": "title1"}, {"title": "title2"}]},
    ).titles == ["title1", "title2"]
    assert Response(req=Request(endpoint=Endpoint.LOOKUP), data={"title": "title1"}).titles == ["title1"]
    with pytest.raises(KeyError):
        titles = Response(req=Request(endpoint=Endpoint.AUTOSUGGEST), data={"items": [{}]}).titles
    with pytest.raises(KeyError):
        titles = Response(req=Request(endpoint=Endpoint.LOOKUP), data={}).titles
        assert titles == []


def test_response_terms():
    assert Response(req=Request(endpoint=Endpoint.AUTOSUGGEST), data={}).terms == []
    assert Response(req=Request(endpoint=Endpoint.AUTOSUGGEST), data={"queryTerms": []}).terms == []
    assert Response(
        req=Request(endpoint=Endpoint.AUTOSUGGEST),
        data={"queryTerms": [{"term": "term1"}]},
    ).terms == ["term1"]
    assert Response(
        req=Request(endpoint=Endpoint.AUTOSUGGEST),
        data={"queryTerms": [{"term": "term1"}, {"term": "term2"}]},
    ).terms == ["term1", "term2"]
    with pytest.raises(KeyError):
        titles = Response(req=Request(endpoint=Endpoint.AUTOSUGGEST), data={"queryTerms": [{}]}).terms
        assert titles == []
