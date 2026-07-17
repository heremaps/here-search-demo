###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.response import Response


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


def test_bbox_skips_items_without_position(items_request):
    """Items lacking a position are ignored; positioned items still define the bbox."""
    data = {"items": [{"title": "no position"}, {"position": {"lat": 1.0, "lng": 2.0}}]}
    resp = Response(req=items_request, data=data)
    assert resp.bbox() == (1.0, 1.0, 2.0, 2.0)


def test_bbox_widens_to_include_mapview(items_request):
    """mapView extents widen the bbox beyond the point position."""
    data = {
        "items": [
            {
                "position": {"lat": 10.0, "lng": 10.0},
                "mapView": {"north": 12.0, "south": 8.0, "west": 9.0, "east": 11.0},
            }
        ]
    }
    resp = Response(req=items_request, data=data)
    # (south_lat, north_lat, east_lng, west_lng)
    assert resp.bbox() == (8.0, 12.0, 11.0, 9.0)


def test_item_geojson_sets_and_mutates_rank(items_request):
    """item_geojson stamps _rank into the feature properties and mutates the item."""
    item = {"position": {"lat": 1.0, "lng": 2.0}, "title": "X"}
    resp = Response(req=items_request, data={"items": [item]})
    feature = resp.item_geojson(item, 7)
    assert feature["geometry"]["coordinates"] == [2.0, 1.0]
    assert feature["properties"]["_rank"] == 7
    assert item["_rank"] == 7


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
