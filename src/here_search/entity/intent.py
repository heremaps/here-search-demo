from here_search.entity.request import ResponseItem, LocationSuggestionItem, QuerySuggestionItem
from here_search.entity.place import PlaceTaxonomyItem

from typing import Optional, Union
from abc import ABCMeta
from dataclasses import dataclass


@dataclass
class SearchIntent(metaclass=ABCMeta):
    materialization: Union[None, str, PlaceTaxonomyItem, ResponseItem, LocationSuggestionItem, QuerySuggestionItem]


@dataclass
class FormulatedTextIntent(SearchIntent):
    pass


@dataclass
class TransientTextIntent(SearchIntent):
    pass


@dataclass
class PlaceTaxonomyIntent(SearchIntent):
    pass


@dataclass
class MoreDetailsIntent(SearchIntent):
    pass


@dataclass
class NoIntent(SearchIntent):
    materialization: Optional[None] = None


class UnsupportedIntentMaterialization(Exception):
    pass
