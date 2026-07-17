###############################################################################
#
# Copyright (c) 2022-2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from abc import ABCMeta
from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.request import Request
from here_search_demo.entity.response_data import ResponseData

ResponseDataView = Mapping[str, Any]


@dataclass(frozen=True)
class Response:
    """Immutable HERE Search response wrapper.

    :ivar req: originating request
    :ivar data: parsed JSON payload view
    :ivar x_headers: captured response ``X-*`` headers
    :ivar raw: optional raw response body
    """

    req: Request | None
    data: ResponseDataView | None
    x_headers: dict = field(default_factory=dict)
    raw: str | None = None

    @property
    def titles(self):
        """Return response item titles in display order.

        :return: list of item titles
        """
        if self.req.endpoint == Endpoint.LOOKUP:
            return [self.data["title"]]
        else:
            return [i["title"] for i in self.data.get("items", [])]

    @property
    def terms(self):
        """Return unique autosuggest query terms in first-seen order.

        :return: list of autosuggest query terms
        """
        return list({term["term"]: None for term in self.data.get("queryTerms", [])}.keys())

    def bbox(self) -> Tuple[float, float, float, float] | None:
        """
        Return response bounding rectangle.

        :return: tuple ``(south_lat, north_lat, east_lng, west_lng)`` when
                 positioned items exist, else ``None``
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
        Return a GeoJSON FeatureCollection for items that include ``position``.

        :return: GeoJSON mapping containing only items with coordinates
        """
        collection = {"type": "FeatureCollection", "features": []}
        items: list[ResponseData] = [self.data] if self.req.endpoint == Endpoint.LOOKUP else self.data.get("items", [])
        for rank, item in enumerate(items):
            if "position" not in item:
                continue
            collection["features"].append(self.item_geojson(item, rank))

        return collection

    def item_geojson(self, item: ResponseData, rank: int):
        """Convert a single HERE item to a GeoJSON ``Feature``.

        :param item: HERE item payload
        :param rank: rank to store as ``_rank`` in feature properties
        :return: GeoJSON feature mapping
        """
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
    rank: int | None = None


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
