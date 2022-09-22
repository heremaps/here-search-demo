from typing import Tuple, Dict, Sequence, Optional, Union
from dataclasses import dataclass
from collections import namedtuple
from enum import IntEnum, auto
from urllib.parse import urlencode
from abc import ABCMeta, abstractmethod


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
class QueryResponseItem(ResponseItem):
    pass


class PlaceTaxonomyItem:
    def __init__(
        self,
        name: str,
        categories: Optional[Sequence[str]] = None,
        food_types: Optional[Sequence[str]] = None,
        chains: Optional[Sequence[str]] = None,
    ):
        self.name = name
        self.categories = categories
        self.food_types = food_types
        self.chains = chains

    @property
    def mapping(self):
        return {
            "categories": self.categories,
            "food_types": self.food_types,
            "chains": self.chains,
        }

    def __repr__(self):
        return f"{self.name}({self.categories}, {self.food_types}, {self.chains})"


class PlaceTaxonomy:
    def __init__(self, name: str, items: Sequence[PlaceTaxonomyItem]):
        self.name = name
        self.items = {i.name: i for i in items or []}

    def __getattr__(self, item_name: str):
        return self.items[item_name]

    def __repr__(self):
        items = ", ".join(map(str, self.items.values()))
        return f"{self.name}({items})"


# fmt: off
class PlaceTaxonomyExample:
    items, icons = zip(
        *[
            #                --------------------------------------------------------------------
            #                | item name | categories     | food types | chains  | icon         |
            #                --------------------------------------------------------------------
            (PlaceTaxonomyItem("gas", ["700-7600-0000", "700-7600-0116", "700-7600-0444"], None, None), "fa-gas-pump"),
            (PlaceTaxonomyItem("eat", ["100"], None, None), "fa-utensils"),
            (PlaceTaxonomyItem("sleep", ["500-5000"], None, None), "fa-bed"),
            (PlaceTaxonomyItem("park", ["400-4300", "800-8500"], None, None), "fa-parking"),
            (PlaceTaxonomyItem("ATM", ["700-7010-0108"], None, None), "fa-euro-sign"),
            (PlaceTaxonomyItem("pizza", None, ["800-057"], None), "fa-pizza-slice"),
            (PlaceTaxonomyItem("fastfood", None, None, ["1566", "1498"]), "fa-hamburger"),
        ]
    )
    taxonomy = PlaceTaxonomy("example", items)
# fmt: on


@dataclass
class SearchContext:
    latitude: float
    longitude: float
    language: Optional[str] = None


@dataclass
class EndpointConfig:
    DEFAULT_LIMIT = 20
    limit: Optional[int] = DEFAULT_LIMIT


@dataclass
class AutosuggestConfig(EndpointConfig):
    DEFAULT_TERMS_LIMIT = 20
    terms_limit: Optional[int] = DEFAULT_TERMS_LIMIT


@dataclass
class DiscoverConfig(EndpointConfig):
    pass


@dataclass
class BrowseConfig(EndpointConfig):
    pass


@dataclass
class LookupConfig:
    pass


@dataclass
class NoConfig:
    pass


class MetaFactory:
    klass = None
    primitive = (int, float, str, bool, type)

    def __new__(cls, name, bases, namespaces):
        klass = namespaces["klass"]
        if klass in MetaFactory.primitive:
            return klass
        namespaces["__new__"] = cls.__new
        return type(name, bases, namespaces)

    def __new(cls, *args, **kwargs):
        obj = object.__new__(cls.klass)
        obj.__init__(*args[1:], **kwargs)
        return obj


class AutosuggestConfigFactory(metaclass=MetaFactory):
    klass = AutosuggestConfig


class DiscoverConfigFactory(metaclass=MetaFactory):
    klass = DiscoverConfig


class BrowseConfigFactory(metaclass=MetaFactory):
    klass = BrowseConfig
