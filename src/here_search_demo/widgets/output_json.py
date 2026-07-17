###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio

from IPython.display import HTML, Code as ICode, JSON as IJSON, display as Idisplay
from ipywidgets import Output, VBox, Widget
import orjson

from here_search_demo.http import IS_BROWSER_RUNTIME
from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.response import Response
from here_search_demo.widgets.state import SearchState, _get_vicinity


class SearchResultList(VBox):
    default_layout = {
        "display": "flex",
        "width": "276px",
        "height": "400px",
        "justify_content": "flex-start",
        "overflow": "scroll",
    }
    default_max_results_count = 20

    def __init__(
        self,
        widget: Widget | None = None,
        max_results_number: int | None = None,
        queue: asyncio.Queue | None = None,
        layout: dict | None = None,
        **kwargs,
    ):
        self.widget = widget or Output()
        self.max_results_number = max_results_number or self.default_max_results_count
        self.queue = queue or asyncio.Queue()
        self.layout = layout or self.default_layout
        self.futures = []
        super().__init__([self.widget], **kwargs)

    def _display(self, resp: Response, intent: SearchIntent | None = None) -> Widget:
        raise NotImplementedError()

    def _modify(self, resp: Response, intent: SearchIntent | None = None) -> Widget:
        raise NotImplementedError()

    def _clear(self):
        return Output(layout=self.layout)

    def display(self, resp: Response, intent: SearchIntent | None = None) -> None:
        # https://github.com/jupyterlab/jupyterlab/issues/3151#issuecomment-339476572
        old_out = self.children[0]
        out = self._display(resp, intent=intent)
        self.children = [out]
        old_out.close()

    def modify(self, resp: Response, intent: SearchIntent | None = None) -> None:
        self._modify(resp, intent=intent)

    def clear(self):
        old_out = self.children[0]
        out = self._clear()
        self.children = [out]
        old_out.close()


class SearchResultJson(SearchResultList):
    _pool_size = 20
    _style_injected = False

    def __init__(self, state: "SearchState | None" = None, **kwargs):
        super().__init__(**kwargs)
        self.add_class("search-json-pane")
        if not SearchResultJson._style_injected:
            Idisplay(
                HTML(
                    "<style>"
                    ".search-json-pane pre, "
                    ".search-json-pane code, "
                    ".search-json-pane .jp-OutputArea-output {"
                    " font-size: 11px !important;"
                    " line-height: 1.2;"
                    "}"
                    "</style>"
                ),
                display_id=True,
            )
            SearchResultJson._style_injected = True
        self._state = state
        self._pool: list[Output] = [Output(layout=self.layout) for _ in range(self._pool_size)]
        self._pool_index = 0

    def _display(self, resp: Response, intent: SearchIntent | None = None) -> Widget:
        out: Output = self._next_output()
        data = orjson.loads(resp.raw) if resp.raw is not None else resp.data
        # Inject _vicinity into the fresh JSON copy.  When a state reference is
        # available and has already been hydrated for this response (caller
        # guarantees result_buttons_w.display runs first), copy the pre-computed
        # _vicinity values rather than re-running _compute_disambiguated_titles.
        if isinstance(data, dict):
            items_by_rank = {rank: item for rank, item in enumerate(data.get("items", [])) if isinstance(item, dict)}
            if items_by_rank:
                state_data = self._state.items_data_by_rank if self._state is not None else {}
                if state_data and all(rank in state_data for rank in items_by_rank):
                    for rank, item in items_by_rank.items():
                        state_item = state_data[rank]
                        if "_vicinity" in state_item:
                            item["_vicinity"] = state_item["_vicinity"]
                else:
                    _get_vicinity(items_by_rank)
        if IS_BROWSER_RUNTIME:
            data_display_obj = ICode(orjson.dumps(data, option=orjson.OPT_INDENT_2).decode(), language="json")
            headers_display_object = ICode(
                orjson.dumps(resp.x_headers, option=orjson.OPT_INDENT_2).decode(), language="json"
            )
        else:
            data_display_obj = IJSON(data, expanded=True)
            headers_display_object = IJSON(resp.x_headers, expanded=True, root="headers")
        out.append_display_data(data_display_obj)
        out.append_display_data(headers_display_object)
        return out

    def _clear(self) -> Output:
        return self._next_output()

    def _next_output(self) -> Output:
        out = self._pool[self._pool_index]
        self._pool_index += 1
        if self._pool_index >= self._pool_size:
            # Pool exhausted — recycle: close all old widgets and create fresh ones
            for w in self._pool:
                w.close()
            self._pool = [Output(layout=self.layout) for _ in range(self._pool_size)]
            self._pool_index = 0
            out = self._pool[self._pool_index]
            self._pool_index += 1
        return out
