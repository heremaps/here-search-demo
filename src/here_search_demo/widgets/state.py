import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.place import PlaceTaxonomyItem
from here_search_demo.entity.response import (
    LocationResponseItem,
    LocationSuggestionItem,
    QuerySuggestionItem,
    Response,
    ResponseItem,
)


_QUERY_RESULT_TYPES = {"chainQuery", "categoryQuery"}

# Matches any parenthetical expression anywhere in a title, e.g.
# "Post Office (Main Branch)" or "Rue de la Paix (1st arrondissement)".
_BRACKETED_RE = re.compile(r"\(.*?\)")


def _get_vicinity(items_data_by_rank: dict[int, dict]) -> dict[int, str]:
    """Compute the shortest differentiating label for every result item.

    Items of type ``chainQuery`` or ``categoryQuery`` are left untouched
    (their ``item["title"]`` is used as-is).  For all other result types the
    label is built from ``address["label"]`` parts as follows:

    * ``part[0]``  – place name (always shown)

    * **Bracketed-title exception**: if ``item["title"]`` already contains a
      parenthetical expression (e.g. ``"Post Office (Main Branch)"``), the
      title is used as-is as the display label and as the sole ``_vicinity``
      entry.  The item is excluded from the progressive-suffix loop entirely.

    * If the result set spans **multiple countries**:
      country (``part[-1]``) is pre-included for *all* items immediately,
      so e.g. "Statue of Liberty, USA" is shown alongside
      "Statue of Liberty, …, Paris, France".

    * Remaining ambiguity is resolved by progressively adding parts
      state-first (right-to-left, skipping country unless single-country):
      ``part[-2]``, ``part[-3]``, … ``part[1]``.

    Parts are always displayed in their original left-to-right order.
    ``_vicinity`` is set on every disambiguated item.
    """
    candidate_ranks = [r for r, d in items_data_by_rank.items() if d.get("resultType") not in _QUERY_RESULT_TYPES]
    result: dict[int, str] = {r: d.get("title", "") for r, d in items_data_by_rank.items()}

    if len(candidate_ranks) <= 1:
        if len(candidate_ranks) == 1:
            rank = candidate_ranks[0]
            item = items_data_by_rank[rank]
            parts = item.get("address", {}).get("label", "").split(", ")
            if parts and parts[0]:
                item["_vicinity"] = [parts[0]]
        return result

    items = [items_data_by_rank[r] for r in candidate_ranks]
    parts_list = [item.get("address", {}).get("label", "").split(", ") for item in items]

    # Determine whether the result set spans multiple countries.
    countries = {parts[-1] for parts in parts_list if len(parts) > 1}
    is_multi_country = len(countries) > 1

    # active_indices[j] is the set of part indices (>0) currently included
    # in the label for item j.  Parts are rendered in ascending index order
    # (i.e. their original address order).
    active_indices: list[set[int]] = [set() for _ in items]

    if is_multi_country:
        # Pre-include country for every item so that items in different
        # countries are immediately distinguished.
        for j, parts in enumerate(parts_list):
            if len(parts) > 1:
                active_indices[j].add(len(parts) - 1)

    # For each item: order in which additional indices are tried.
    # Go right-to-left through intermediate parts, then add
    # country as a last resort only in single-country results.
    def _try_order(n: int) -> list[int]:
        order = [i for i in range(n - 2, 0, -1)]  # n-2, n-3, …, 1
        if not is_multi_country and n >= 2:
            order.append(n - 1)  # country as final tie-breaker
        return order

    orders = [_try_order(len(p)) for p in parts_list]
    order_ptrs = [0] * len(items)

    # Cache the name part so build_label() doesn't recompute it each call.
    base_names = [
        (parts[0] if parts and parts[0] else None) or item.get("title", "") for parts, item in zip(parts_list, items)
    ]

    # Items whose *title* field already contains a parenthetical qualifier are
    # self-disambiguating: item["title"] is used as-is as the display label
    # and as the sole _vicinity entry.  They are excluded from the
    # suffix-addition loop entirely.
    bracketed = [bool(_BRACKETED_RE.search(item.get("title", ""))) for item in items]

    def label_for(j: int) -> str:
        if not active_indices[j]:
            return base_names[j]
        suffix = ", ".join(parts_list[j][i] for i in sorted(active_indices[j]))
        return f"{base_names[j]}, {suffix}" if suffix else base_names[j]

    labels = [label_for(j) for j in range(len(items))]

    # Iteratively resolve ambiguity: each pass finds labels shared by more than
    # one item and extends each of them by the next candidate address part
    # (following the pre-built per-item order).  Stops as soon as all labels
    # are unique, no more parts are available to add, or the safety-cap on
    # iterations (one more than the longest part order) is reached.
    max_iters = max((len(o) for o in orders), default=0) + 1
    for _ in range(max_iters):
        # Only non-bracketed items participate in duplicate resolution.
        duplicate_labels = {
            label
            for label, count in Counter(labels[j] for j in range(len(items)) if not bracketed[j]).items()
            if count > 1
        }
        if not duplicate_labels:
            break
        changed = False
        for j in range(len(items)):
            if not bracketed[j] and labels[j] in duplicate_labels and order_ptrs[j] < len(orders[j]):
                active_indices[j].add(orders[j][order_ptrs[j]])
                order_ptrs[j] += 1
                labels[j] = label_for(j)
                changed = True
        if not changed:
            break

    for j, rank in enumerate(candidate_ranks):
        label = labels[j]
        parts = parts_list[j]
        # Exception: if item["title"] contains a bracketed qualifier, use the
        # title as-is as the display label and as the sole _vicinity entry.
        if bracketed[j]:
            title = items[j].get("title", label)
            result[rank] = title
            items_data_by_rank[rank]["_vicinity"] = [title]
        else:
            result[rank] = label if label else result[rank]
            # Expose the parts that compose the display label as _vicinity so they
            # are visible in the JSON output widget.  Always includes part[0] (the
            # place name) followed by any active suffix parts in address order.
            used_indices = [0] + sorted(active_indices[j])
            items_data_by_rank[rank]["_vicinity"] = [parts[i] for i in used_indices if i < len(parts)]

    return result


@dataclass
class ItemIcon:
    klass: type[ResponseItem]
    icon: str = ""


ITEM_ICON_FACTORY = defaultdict(
    lambda: defaultdict(lambda: ItemIcon(LocationResponseItem)),
    {
        Endpoint.AUTOSUGGEST: defaultdict(
            lambda: ItemIcon(LocationSuggestionItem),
            {
                "categoryQuery": ItemIcon(QuerySuggestionItem, "search"),
                "chainQuery": ItemIcon(QuerySuggestionItem, "search"),
            },
        )
    },
)


class SearchState:
    """Widget-local search view state.

    This object keeps presentation-oriented data that helps widgets render the
    current response and preserve UI interactions between updates.
    """

    def __init__(self) -> None:
        self.items_by_rank: dict[int, ResponseItem] = {}
        self.items_data_by_rank: dict[int, dict] = {}
        self.display_titles_by_rank: dict[int, str] = {}
        self.last_endpoint: Endpoint | None = None
        self.expanded_ranks: set[int] = set()
        self.current_query: str = ""
        self.selected_taxonomy: PlaceTaxonomyItem | None = None
        self.term_suggestions: list[str] = []

    def hydrate(self, resp: Response) -> None:
        self.items_by_rank.clear()
        self.items_data_by_rank.clear()
        self.expanded_ranks.clear()
        self.last_endpoint = resp.req.endpoint if resp.req is not None else None

        for rank, item_data in self._iter_response_items(resp):
            self.items_by_rank[rank] = self._build_item(resp, item_data, rank)
            self.items_data_by_rank[rank] = item_data

        self.display_titles_by_rank = _get_vicinity(self.items_data_by_rank)

    def update_item(self, rank: int, data: dict, resp: Response) -> None:
        if self.last_endpoint is None and resp.req is not None:
            self.last_endpoint = resp.req.endpoint
        self.items_by_rank[rank] = self._build_item(resp, data, rank)
        self.items_data_by_rank[rank] = data
        self.display_titles_by_rank = _get_vicinity(self.items_data_by_rank)

    def get_item(self, rank: int) -> ResponseItem | None:
        return self.items_by_rank.get(rank)

    def get_item_data(self, rank: int) -> dict | None:
        return self.items_data_by_rank.get(rank)

    def icon_for(self, rank: int) -> str:
        if self.last_endpoint is None:
            return ""
        data = self.get_item_data(rank)
        if not data:
            return ""
        return ITEM_ICON_FACTORY[self.last_endpoint][data.get("resultType", "")].icon

    def title_for(self, rank: int) -> str:
        data = self.get_item_data(rank)
        if not data:
            return ""
        try:
            return data["_detour"]["label"]
        except (KeyError, TypeError):
            pass
        return self.display_titles_by_rank.get(rank, data.get("title", ""))

    def ranks(self) -> list[int]:
        return sorted(self.items_by_rank.keys())

    def set_query_text(self, text: str) -> None:
        self.current_query = text

    def select_taxonomy_item(self, item: PlaceTaxonomyItem | None) -> None:
        self.selected_taxonomy = item

    def set_term_suggestions(self, terms: list[str]) -> None:
        self.term_suggestions = terms

    @staticmethod
    def _iter_response_items(resp: Response):
        if resp.req is not None and resp.req.endpoint == Endpoint.LOOKUP:
            yield 0, resp.data
        else:
            for rank, item in enumerate(resp.data.get("items", [])):
                yield rank, item

    @staticmethod
    def _build_item(resp: Response, data: dict, rank: int) -> ResponseItem:
        icon = ITEM_ICON_FACTORY[resp.req.endpoint][data.get("resultType", "")]
        return icon.klass(data=data, rank=rank, resp=resp)


@dataclass
class MapState:
    center: tuple[float, float] | None = None
    zoom: int | None = None
    selected_rank: int | None = None

    def update_center(self, center: tuple[float, float]) -> None:
        self.center = center

    def update_zoom(self, zoom: int) -> None:
        self.zoom = zoom

    def select_rank(self, rank: int | None) -> None:
        self.selected_rank = rank
