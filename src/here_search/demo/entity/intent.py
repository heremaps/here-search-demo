###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from here_search.demo.entity.response import ResponseItem, LocationSuggestionItem, QuerySuggestionItem
from here_search.demo.entity.place import PlaceTaxonomyItem

from typing import Optional, Union
from abc import ABCMeta
from dataclasses import dataclass


@dataclass
class SearchIntent(metaclass=ABCMeta):
    """
    A search intent materialized/realized through a response item.

    Intents are at the very start of a search query workflow.
    """
    materialization: Union[None, str, PlaceTaxonomyItem, ResponseItem, LocationSuggestionItem, QuerySuggestionItem]


@dataclass
class FormulatedTextIntent(SearchIntent):
    """
    A search intent formulated with a finalized text
    """
    pass


@dataclass
class TransientTextIntent(SearchIntent):
    """
    A search intent formulated with a text but not yet finalized
    """
    pass


@dataclass
class PlaceTaxonomyIntent(SearchIntent):
    """
    A search intent formulated with a place taxonomy instance
    """
    pass


@dataclass
class MoreDetailsIntent(SearchIntent):
    """
    An intent to get more details about a search item
    """
    pass


@dataclass
class NoIntent(SearchIntent):
    materialization: Optional[None] = None


class UnsupportedIntentMaterialization(Exception):
    pass
