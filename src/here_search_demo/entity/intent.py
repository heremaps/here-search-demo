###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from dataclasses import dataclass, field
from typing import Literal

from here_search_demo.entity.place import PlaceTaxonomyItem
from here_search_demo.entity.response import (
    LocationResponseItem,
    LocationSuggestionItem,
    QuerySuggestionItem,
    ResponseItem,
)


@dataclass
class SearchIntent:
    """High-level intention to perform a search-related action.

    This is a single, flat intent type with:
    - ``kind``: what sort of action the user is taking
    - ``materialization``: the payload associated with that action
    - ``time``: timestamp when the intent was created
    """

    kind: Literal["transient_text", "submitted_text", "taxonomy", "details", "action", "empty"]
    materialization: None | str | PlaceTaxonomyItem | ResponseItem | LocationSuggestionItem | QuerySuggestionItem
    time: float


@dataclass
class ActionIntent:
    """Intent emitted when the user clicks a result button for a LocationResponseItem.

    Unlike ``SearchIntent(kind="details")``, this intent only triggers a
    signals call — no lookup is performed.
    """

    materialization: LocationResponseItem
    time: float
    kind: str = field(default="action", init=False)


class UnsupportedIntentMaterialization(Exception):
    pass
