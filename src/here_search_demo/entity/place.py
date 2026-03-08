###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from collections.abc import Sequence


class PlaceTaxonomyItem:
    def __init__(
        self,
        name: str,
        categories: Sequence[str] | None = None,
        food_types: Sequence[str] | None = None,
        chains: Sequence[str] | None = None,
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
    name: str
    items: dict[str, PlaceTaxonomyItem]

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
            (PlaceTaxonomyItem("ev", ["700-7600-0322"], None, None), "fa-charging-station"),
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
