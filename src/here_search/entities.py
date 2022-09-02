from typing import Tuple, Dict, Sequence, Optional
from dataclasses import dataclass
from collections import namedtuple
from enum import IntEnum, auto
from urllib.parse import urlencode


class Endpoint(IntEnum):
    AUTOSUGGEST = auto()
    AUTOSUGGEST_HREF = auto()
    DISCOVER = auto()
    LOOKUP = auto()
    BROWSE = auto()
    REVGEOCODE = auto()


@dataclass
class Request:
    endpoint: Endpoint = None
    url: str = None
    params: Dict[str, str] = None
    x_headers: dict = None

    def key(self) -> str:
        return self.url+"".join(f"{k}{v}"for k, v in self.params.items())

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
            return [self.data.get("title")]
        else:
            return [i["title"] for i in self.data["items"]]

    def bbox(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Returns response bounding rectangle (south latitude, north latitude, east longitude, west longitude)
        """
        latitudes, longitudes = [], []
        for item in self.data.get("items", []):
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
            return min(latitudes), min(longitudes), max(latitudes), max(longitudes)
        else:
            return None

    def geojson(self) -> dict:
        collection = {"type": "FeatureCollection", "features": []}
        for item in self.data["items"]:
            if "position" not in item:
                continue
            longitude, latitude = item["position"]["lng"], item["position"]["lat"]
            categories = [c["name"] for c in item["categories"]
                          if c.get("primary")][0] if "categories" in item else None
            collection["features"].append({"type": "Feature",
                                           "geometry": {
                                               "type": "Point",
                                               "coordinates": [longitude, latitude]},
                                           "properties": {"title": item["title"],
                                                          "categories": categories}})
            if False and "mapView" in item:
                west, south, east, north = item["mapView"]["west"], item["mapView"]["south"], item["mapView"]["east"], item["mapView"]["north"]
                collection["features"].append({"type": "Feature",
                                               "geometry": {
                                                   "type": "Polygon",
                                                   "coordinates":    [[west, south], [east, south], [east, north],
                                                                      [west, north], [west, south]]
                                               }})
        return collection

@dataclass
class ResponseItem:
    resp: Response = None
    data: dict = None
    rank: int = None


class PlaceTaxonomyItem:
    def __init__(self, name: str,
                 categories: Optional[Sequence[str]] = None,
                 food_types: Optional[Sequence[str]] = None,
                 chains: Optional[Sequence[str]] = None):
        self.name = name
        self.categories = categories
        self.food_types = food_types
        self.chains = chains

    @property
    def mapping(self):
        return {"categories": self.categories, "food_types": self.food_types, "chains": self.chains}

    def __repr__(self):
        return f"{self.name}({self.categories}, {self.food_types}, {self.chains})"


def PlaceTaxonomy(items: Sequence[PlaceTaxonomyItem]=None):
    items = items or []
    return namedtuple("PlaceTaxonomy", [i.name for i in items])(*items)


taxonomy_items, taxonomy_icons = zip(*[
    (PlaceTaxonomyItem("gas",     ["700-7600-0000",
                                   "700-7600-0116",
                                   "700-7600-0444"], None,       None),    "fa-gas-pump"),
    (PlaceTaxonomyItem("eat",     ["100"],           None,       None),    "fa-utensils"),
    (PlaceTaxonomyItem("sleep",   ["500-5000"],      None,       None),    "fa-bed"),
    (PlaceTaxonomyItem("park",    ["400-4300",
                                   "800-8500"],      None,       None),    "fa-parking"),
    (PlaceTaxonomyItem("ATM",     ["700-7010-0108"], None,       None),    "fa-euro-sign"),
    (PlaceTaxonomyItem("pizza",    None,            ["800-057"], None),    "fa-pizza-slice"),
    (PlaceTaxonomyItem("fastfood", None,             None,      ["1566",
                                                                 "1498"]), "fa-hamburger")])
taxonomy = PlaceTaxonomy(taxonomy_items)