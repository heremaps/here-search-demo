###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from here_search.demo.entity.endpoint import Endpoint

from typing import Tuple, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urlencode
from abc import ABCMeta


@dataclass
class Request:
    endpoint: Endpoint = None
    url: str = None
    params: Dict[str, str] = None
    x_headers: dict = None

    @property
    def key(self) -> str:
        return self.url + "".join(f"{k}{v}" for k, v in self.params.items())

    @property
    def full(self):
        return f"{self.url}?{urlencode(self.params)}"


@dataclass
class Response:
    req: Request = None
    data: dict = None
    x_headers: dict = None

    @property
    def titles(self):
        if self.req.endpoint == Endpoint.LOOKUP:
            return [self.data["title"]]
        else:
            return [i["title"] for i in self.data.get("items", [])]

    @property
    def terms(self):
        return list(
            {term["term"]: None for term in self.data.get("queryTerms", [])}.keys()
        )

    def bbox(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Returns response bounding rectangle (south latitude, north latitude, east longitude, west longitude)
        """
        latitudes, longitudes = [], []
        items = (
            [self.data]
            if self.req.endpoint == Endpoint.LOOKUP
            else self.data.get("items", [])
        )
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
        collection = {"type": "FeatureCollection", "features": []}
        items = (
            [self.data]
            if self.req.endpoint == Endpoint.LOOKUP
            else self.data.get("items", [])
        )
        for item in items:
            if "position" not in item:
                continue
            longitude, latitude = item["position"]["lng"], item["position"]["lat"]
            categories = (
                [c["name"] for c in item["categories"] if c.get("primary")][0]
                if "categories" in item
                else None
            )
            collection["features"].append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
                    "properties": {"title": item["title"], "categories": categories},
                }
            )
            if False and "mapView" in item:
                west, south, east, north = (
                    item["mapView"]["west"],
                    item["mapView"]["south"],
                    item["mapView"]["east"],
                    item["mapView"]["north"],
                )
                collection["features"].append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [west, south],
                                [east, south],
                                [east, north],
                                [west, north],
                                [west, south],
                            ],
                        },
                    }
                )
        return collection


@dataclass
class ResponseItem(metaclass=ABCMeta):
    resp: Response = None
    data: dict = None
    rank: int = None


@dataclass
class LocationResponseItem(ResponseItem):
    pass


@dataclass
class SuggestionItem(ResponseItem, metaclass=ABCMeta):
    pass


@dataclass
class LocationSuggestionItem(ResponseItem):
    pass


@dataclass
class QuerySuggestionItem(ResponseItem):
    pass


@dataclass
class RequestContext:
    latitude: float
    longitude: float
    language: Optional[str] = None
    x_headers: Optional[dict] = None
