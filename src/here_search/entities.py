from typing import Tuple, Dict, Sequence, Optional
from dataclasses import dataclass
from enum import IntEnum, auto


class Endpoint(IntEnum):
    AUTOSUGGEST = auto()
    AUTOSUGGEST_HREF = auto()
    DISCOVER = auto()
    LOOKUP = auto()
    BROWSE = auto()
    REVGEOCODE = auto()
    SIGNALS = auto()


@dataclass
class Request:
    endpoint: Endpoint = None
    url: str = None
    params: Dict[str, str] = None
    x_headers: dict = None

    def key(self) -> Tuple[str, str]:
        return self.url, str(self.params)


@dataclass
class Response:
    req: Request = None
    data: dict = None
    x_headers: dict = None


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
