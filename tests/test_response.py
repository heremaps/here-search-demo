###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest
from here_search.demo.entity.response import Response
from here_search.demo.entity.endpoint import Endpoint


@pytest.fixture
def lookup_request():
    class DummyRequest:
        endpoint = Endpoint.LOOKUP

    return DummyRequest()


@pytest.fixture
def items_request():
    class DummyRequest:
        endpoint = Endpoint.AUTOSUGGEST

    return DummyRequest()


def test_titles_lookup(lookup_request):
    data = {"title": "Test Title"}
    resp = Response(req=lookup_request, data=data)
    assert resp.titles == ["Test Title"]


def test_titles_items(items_request):
    data = {"items": [{"title": "A"}, {"title": "B"}]}
    resp = Response(req=items_request, data=data)
    assert resp.titles == ["A", "B"]


def test_terms(items_request):
    data = {"queryTerms": [{"term": "foo"}, {"term": "bar"}, {"term": "foo"}]}
    resp = Response(req=items_request, data=data)
    assert set(resp.terms) == {"foo", "bar"}


def test_bbox_lookup(lookup_request):
    data = {"position": {"lat": 1.0, "lng": 2.0}}
    resp = Response(req=lookup_request, data=data)
    assert resp.bbox() == (1.0, 1.0, 2.0, 2.0)


def test_bbox_items(items_request):
    data = {
        "items": [
            {"position": {"lat": 1.0, "lng": 2.0}},
            {"position": {"lat": 3.0, "lng": 4.0}, "mapView": {"north": 5.0, "south": 0.0, "west": 1.0, "east": 6.0}},
        ]
    }
    resp = Response(req=items_request, data=data)
    assert resp.bbox() == (0.0, 5.0, 6.0, 1.0)


def test_bbox_none(items_request):
    data = {"items": [{}]}
    resp = Response(req=items_request, data=data)
    assert resp.bbox() is None


def test_geojson_lookup(lookup_request):
    data = {"position": {"lat": 1.0, "lng": 2.0}}
    resp = Response(req=lookup_request, data=data)
    geojson = resp.geojson()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 1
    assert geojson["features"][0]["geometry"]["coordinates"] == [2.0, 1.0]


def test_geojson_items(items_request):
    data = {
        "items": [
            {"position": {"lat": 1.0, "lng": 2.0}},
            {"position": {"lat": 3.0, "lng": 4.0}},
        ]
    }
    resp = Response(req=items_request, data=data)
    geojson = resp.geojson()
    assert len(geojson["features"]) == 2
    assert geojson["features"][0]["geometry"]["coordinates"] == [2.0, 1.0]
    assert geojson["features"][1]["geometry"]["coordinates"] == [4.0, 3.0]
