###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.place import PlaceTaxonomy, PlaceTaxonomyItem
from here_search_demo.entity.request import Request
from here_search_demo.entity.response import Response

expected_response_data = {"a": "b"}
expected_x_headers = {"X-Request-Id": "userid", "X-Correlation-ID": "correlationId"}

request = Request(
    endpoint=Endpoint.AUTOSUGGEST,
    base_url="url",
    x_headers={"X-a": 1, "Y-b": 2},
    params={"p1": "v1", "p2": "v2"},
)


def test_request_key():
    request = Request(
        endpoint=Endpoint.AUTOSUGGEST,
        base_url="url",
        x_headers={"X-a": 1, "Y-b": 2},
        params={"p1": "v1", "p2": "v2"},
    )
    assert request.key == "urlp1v1p2v2"


def test_request_key_includes_data():
    # The route polyline and corridor width are carried in the POST body ``data``.
    # Two requests differing only by width must yield different cache keys so a
    # width change triggers a fresh search instead of returning the stale result.
    common = dict(endpoint=Endpoint.DISCOVER, base_url="url", params={"q": "cafe"})
    narrow = Request(data="route=poly;w=100", **common)
    wide = Request(data="route=poly;w=500", **common)

    assert narrow.key != wide.key
    assert narrow.key == "urlqcaferoute=poly;w=100"


def test_request_full():
    request = Request(
        endpoint=Endpoint.AUTOSUGGEST,
        base_url="url",
        x_headers={"X-a": 1, "Y-b": 2},
        params={"p1": "v1", "p2": "v2"},
    )
    assert request.full == "url?p1=v1&p2=v2"


def test_response_titles():
    assert Response(req=Request(endpoint=Endpoint.AUTOSUGGEST), data={"items": []}, x_headers={}).titles == []
    assert Response(
        req=Request(endpoint=Endpoint.AUTOSUGGEST),
        data={"items": [{"title": "title1"}]},
        x_headers={},
    ).titles == ["title1"]
    assert Response(
        req=Request(endpoint=Endpoint.AUTOSUGGEST),
        data={"items": [{"title": "title1"}, {"title": "title2"}]},
        x_headers={},
    ).titles == ["title1", "title2"]
    assert Response(req=Request(endpoint=Endpoint.LOOKUP), data={"title": "title1"}, x_headers={}).titles == ["title1"]
    with pytest.raises(KeyError):
        titles = Response(req=Request(endpoint=Endpoint.AUTOSUGGEST), data={"items": [{}]}, x_headers={}).titles
    with pytest.raises(KeyError):
        titles = Response(req=Request(endpoint=Endpoint.LOOKUP), data={}, x_headers={}).titles
        assert titles == []


def test_response_terms():
    assert Response(req=Request(endpoint=Endpoint.AUTOSUGGEST), data={}, x_headers={}).terms == []
    assert Response(req=Request(endpoint=Endpoint.AUTOSUGGEST), data={"queryTerms": []}, x_headers={}).terms == []
    assert Response(
        req=Request(endpoint=Endpoint.AUTOSUGGEST),
        data={"queryTerms": [{"term": "term1"}]},
        x_headers={},
    ).terms == ["term1"]
    assert Response(
        req=Request(endpoint=Endpoint.AUTOSUGGEST),
        data={"queryTerms": [{"term": "term1"}, {"term": "term2"}]},
        x_headers={},
    ).terms == ["term1", "term2"]
    with pytest.raises(KeyError):
        titles = Response(req=Request(endpoint=Endpoint.AUTOSUGGEST), data={"queryTerms": [{}]}, x_headers={}).terms
        assert titles == []


def test_place_taxonomy_getattr_returns_known_item():
    item = PlaceTaxonomyItem("gas", ["700-7600-0116"])
    taxonomy = PlaceTaxonomy("example", [item])
    assert taxonomy.gas is item


def test_place_taxonomy_getattr_raises_attribute_error_for_unknown_name():
    taxonomy = PlaceTaxonomy("example", [PlaceTaxonomyItem("gas", ["700-7600-0116"])])
    with pytest.raises(AttributeError):
        _ = taxonomy.not_existing


def test_place_taxonomy_getattr_raises_attribute_error_for_objclass_introspection():
    taxonomy = PlaceTaxonomy("example", [PlaceTaxonomyItem("gas", ["700-7600-0116"])])
    with pytest.raises(AttributeError):
        _ = taxonomy.__objclass__
