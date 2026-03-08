###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from dataclasses import dataclass
from typing import Literal

from here_search_demo.entity.place import PlaceTaxonomyItem
from here_search_demo.entity.response import LocationSuggestionItem, QuerySuggestionItem, ResponseItem


@dataclass
class SearchIntent:
    """High-level intention to perform a search-related action.

    This is a single, flat intent type with:
    - ``kind``: what sort of action the user is taking
    - ``materialization``: the payload associated with that action
    - ``time``: timestamp when the intent was created
    """

    kind: Literal["transient_text", "submitted_text", "taxonomy", "details", "empty"]
    materialization: None | str | PlaceTaxonomyItem | ResponseItem | LocationSuggestionItem | QuerySuggestionItem
    time: float


class UnsupportedIntentMaterialization(Exception):
    pass
