###############################################################################
#
# Copyright (c) 2022-2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from abc import ABCMeta
from dataclasses import dataclass
from typing import Tuple

from here_search.demo.entity.endpoint import Endpoint
from here_search.demo.entity.request import Request
from here_search.demo.entity.response_data import ResponseData


@dataclass
class Response:
    req: Request = None
    data: ResponseData = None
    x_headers: dict = None

    @property
    def titles(self):
        if self.req.endpoint == Endpoint.LOOKUP:
            return [self.data["title"]]
        else:
            return [i["title"] for i in self.data.get("items", [])]

    @property
    def terms(self):
        return list({term["term"]: None for term in self.data.get("queryTerms", [])}.keys())

    def bbox(self) -> Tuple[float, float, float, float] | None:
        """
        Returns response bounding rectangle (south latitude, north latitude, east longitude, west longitude)
        """
        latitudes, longitudes = [], []
        items = [self.data] if self.req.endpoint == Endpoint.LOOKUP else self.data.get("items", [])
        for item in items:
            if "position" not in item:
                continue
            longitude, latitude = item["position"]["lng"], item["position"]["lat"]
            latitudes.append(latitude)
            longitudes.append(longitude)
            if "mapView" in item:
                latitudes.append(item["mapView"]["north"])
                latitudes.append(item["mapView"]["south"])
                longitudes.append(item["mapView"]["west"])
                longitudes.append(item["mapView"]["east"])
        if latitudes:
            return min(latitudes), max(latitudes), max(longitudes), min(longitudes)
        else:
            return None

    def geojson(self) -> dict:
        """
        Returns response geojson for items with a position
        :return: a GeoJSON dict
        """
        collection = {"type": "FeatureCollection", "features": []}
        items: list[ResponseData] = [self.data] if self.req.endpoint == Endpoint.LOOKUP else self.data.get("items", [])
        for rank, item in enumerate(items):
            if "position" not in item:
                continue
            collection["features"].append(self.item_geojson(item, rank))

        return collection

    def item_geojson(self, item: ResponseData, rank: int):
        longitude, latitude = item["position"]["lng"], item["position"]["lat"]
        item["_rank"] = rank
        item_feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            "properties": item,
        }
        return item_feature


@dataclass
class ResponseItemMixin(metaclass=ABCMeta):
    resp: Response = None
    rank: int = None


@dataclass
class ResponseItem(ResponseItemMixin, metaclass=ABCMeta):
    data: ResponseData = None


@dataclass
class LocationResponseItem(ResponseItem):
    pass


@dataclass
class LocationSuggestionItem(LocationResponseItem):
    pass


@dataclass
class QuerySuggestionItem(ResponseItem):
    pass
