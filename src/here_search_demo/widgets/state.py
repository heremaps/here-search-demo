from collections import defaultdict
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
    def __init__(self) -> None:
        self.items_by_rank: dict[int, ResponseItem] = {}
        self.items_data_by_rank: dict[int, dict] = {}
        self.last_endpoint: Endpoint | None = None
        self.expanded_ranks: set[int] = set()
        self.current_query: str = ""
        self.selected_taxonomy: PlaceTaxonomyItem | None = None
        self.term_suggestions: list[str] = []

    def hydrate(self, resp: Response) -> None:
        self.items_by_rank.clear()
        self.items_data_by_rank.clear()
        self.expanded_ranks.clear()
        self.last_endpoint = resp.req.endpoint

        for rank, item_data in self._iter_response_items(resp):
            self.items_by_rank[rank] = self._build_item(resp, item_data, rank)
            self.items_data_by_rank[rank] = item_data

    def update_item(self, rank: int, data: dict, resp: Response) -> None:
        if self.last_endpoint is None:
            self.last_endpoint = resp.req.endpoint
        self.items_by_rank[rank] = self._build_item(resp, data, rank)
        self.items_data_by_rank[rank] = data

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
        return data.get("title", "") if data else ""

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
        if resp.req.endpoint == Endpoint.LOOKUP:
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
