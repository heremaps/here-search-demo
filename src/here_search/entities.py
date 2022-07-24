from typing import Tuple, Dict
from dataclasses import dataclass
from enum import IntEnum, auto
import uuid


class Endpoint(IntEnum):
    AUTOSUGGEST = auto()
    AUTOSUGGEST_HREF = auto()
    DISCOVER = auto()
    LOOKUP = auto()
    REVGEOCODE = auto()
    SIGNALS = auto()


@dataclass
class Request:
    endpoint: Endpoint=None
    url: str=None
    params: Dict[str, str]=None
    x_headers: dict=None
    post: bool=False

    def key(self) -> Tuple[Endpoint, Tuple[str]]:
        return self.endpoint, tuple(self.params.items())


@dataclass
class Response:
    req: Request=None
    data: dict=None
    x_headers: dict=None


@dataclass
class ResponseItem:
    resp: Response=None
    data: dict=None
    rank: int=None


class UserProfile:
    preferred_languages: dict
    current_latitude: float
    current_longitude: float
    current_country_code: str

    default_name = "default"
    default_current_latitude = 52.518333
    default_current_longitude = 13.408333
    default_country_code = "DEU"
    default_profile_languages = {default_name: "en"}

    def __init__(self,
                 use_positioning: bool,
                 share_experience: bool,
                 languages: dict=None,
                 name: str=None):
        """
        :param use_position: Mandatory opt-in/out about position usage
        :param share_experience: Mandatory opt-in/out about activity usage
        :param api: Optional API instance
        :param languages: Optional user language preferences
        :param name: Optional user name
        """
        self.name = name or UserProfile.default_name
        self.id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f'{self.name}{uuid.getnode()}'))

        self.__use_positioning = use_positioning
        self.__share_experience = share_experience

        self.preferred_languages = languages or {}
        self.has_country_preferences = not (self.preferred_languages == {} or list(self.preferred_languages.keys()) == [UserProfile.default_name])
