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

@dataclass
class ResponseItem:
    resp: Response = None
    data: dict = None
    rank: int = None

@dataclass
class Ontology:
    name: str
    categories: Optional[Sequence[str]] = None
    food_types: Optional[Sequence[str]] = None
    chains: Optional[Sequence[str]] = None


class OntologyItem:
    def __init__(self, name: str,
                 categories: Optional[Sequence[str]] = None,
                 food_types: Optional[Sequence[str]] = None,
                 chains: Optional[Sequence[str]] = None):
        self._tuple = namedtuple(name, ("categories", "foodTypes", "chains"))(
            categories=categories, foodTypes=food_types, chains=chains)

    @property
    def name(self):
        return type(self._tuple).__name__

    @property
    def mapping(self):
        return {k: v for k, v in self._tuple._asdict().items() if v}

    def __repr__(self):
        return repr(self._tuple)


def Ontology(items: Sequence[OntologyItem]):
    return namedtuple("Ontology", [i.name for i in items])(*items)
