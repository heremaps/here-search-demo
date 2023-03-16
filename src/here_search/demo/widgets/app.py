###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from ipywidgets import HBox, VBox
from ipyleaflet import WidgetControl

from here_search.demo.api import API
from here_search.demo.base import OneBoxBase
from here_search.demo.user import UserProfile
from here_search.demo.entity.request import Response
from here_search.demo.entity.place import PlaceTaxonomyExample

from .util import TableLogWidgetHandler
from .input import SubmittableTextBox, TermsButtons, PlaceTaxonomyButtons
from .output import ResponseMap, SearchResultButtons, SearchResultJson

import asyncio
import logging


class OneBoxMap(OneBoxBase, VBox):
    default_search_box_layout = {"width": "240px"}
    default_placeholder = "free text"
    default_output_format = "text"
    default_taxonomy, default_icons = (
        PlaceTaxonomyExample.taxonomy,
        PlaceTaxonomyExample.icons,
    )

    def __init__(
            self,
            api_key: str = None,
            api: API = None,
            user_profile: UserProfile = None,
            results_limit: int = None,
            suggestions_limit: int = None,
            terms_limit: int = None,
            place_taxonomy_buttons: PlaceTaxonomyButtons = None,
            extra_api_params: dict = None,
            on_map: bool = False,
            **kwargs
    ):

        self.logger = logging.getLogger("here_search")
        self.result_queue: asyncio.Queue = asyncio.Queue()
        if not api and api_key:
            api = API(api_key=api_key,
                      url_format_fn=TableLogWidgetHandler.format_url)
        OneBoxBase.__init__(
            self,
            api=api,
            user_profile=user_profile,
            results_limit=results_limit or OneBoxMap.default_results_limit,
            suggestions_limit=suggestions_limit or OneBoxMap.default_suggestions_limit,
            terms_limit=terms_limit or OneBoxMap.default_terms_limit,
            extra_api_params=extra_api_params,
            result_queue=self.result_queue,
            **kwargs
        )

        self.map_w = ResponseMap(
            api_key=self.api.api_key,
            center=self.search_center,
            position_handler=self.set_search_center,
        )

        # The JSON output
        self.result_json_w = SearchResultJson(
            result_queue=self.queue,
            max_results_number=max(self.results_limit, self.suggestions_limit),
            layout={"width": "400px", "max_height": "600px"},
        )
        self.result_json_w.display(Response(data={}))

        # The Search input box
        self.query_box_w = SubmittableTextBox(
            queue=self.queue,
            layout=kwargs.pop("layout", self.__class__.default_search_box_layout),
            placeholder=kwargs.pop("placeholder", self.__class__.default_placeholder),
            **kwargs
        )
        self.query_terms_w = TermsButtons(
            self.query_box_w, buttons_count=self.__class__.default_terms_limit
        )
        self.buttons_box_w = place_taxonomy_buttons or PlaceTaxonomyButtons(
            queue=self.queue,
            taxonomy=OneBoxMap.default_taxonomy,
            icons=OneBoxMap.default_icons,
        )
        self.result_buttons_w = SearchResultButtons(
            queue=self.queue,
            max_results_number=max(self.results_limit, self.suggestions_limit),
        )
        search_box = VBox(
            ([self.buttons_box_w] if self.buttons_box_w else [])
            + [self.query_box_w, self.query_terms_w, self.result_buttons_w],
            layout={"width": "280px"},
        )

        # The search query log
        self.log_handler = TableLogWidgetHandler()
        self.logger.addHandler(self.log_handler)
        self.logger.setLevel(logging.INFO)

        # App widgets composition
        widget_control_left = WidgetControl(
            widget=search_box, position="topleft", name="search_in", transparent_bg=False
        )
        self.map_w.add(widget_control_left)

        if on_map:
            self.map_w.add(WidgetControl(
                widget=self.result_json_w, position="topright", name="search_out", transparent_bg=False
            ))
            self.map_w.add(WidgetControl(
                widget=self.log_handler.out, position="bottomleft", name="search_log", transparent_bg=False
            ))
            VBox.__init__(self, [self.map_w])
        else:
            VBox.__init__(
                self, [HBox([self.map_w, self.result_json_w]), self.log_handler.out]
            )

    def handle_suggestion_list(self, autosuggest_resp: Response):
        self.display_suggestions(autosuggest_resp)
        self.display_result_map(autosuggest_resp, fit=False)
        self.display_terms(autosuggest_resp)

    def handle_result_list(self, resp: Response):
        self.result_buttons_w.display(resp)
        self.result_json_w.display(resp)
        self.display_result_map(resp, fit=True)
        self.clear_query_text()

    def handle_result_details(self, lookup_resp: Response):
        self.result_json_w.display(lookup_resp)
        self.display_result_map(lookup_resp, fit=True)

    def display_terms(self, autosuggest_resp: Response):
        terms = {
            term["term"]: None for term in autosuggest_resp.data.get("queryTerms", [])
        }
        self.query_terms_w.set(list(terms.keys()))

    def display_suggestions(self, autosuggest_resp: Response) -> None:
        self.result_buttons_w.display(autosuggest_resp)
        self.result_json_w.display(autosuggest_resp)
        #self.display_result_map(autosuggest_resp, update_search_center=False)

    def clear_query_text(self):
        self.query_box_w.text_w.value = ""
        self.query_terms_w.set([])

    def display_result_map(self, resp: Response, fit: bool = False):
        self.map_w.display(resp, fit)

    def clear_logs(self):
        self.logger.removeHandler(self.log_handler)
        self.log_handler.clear_logs()
        self.log_handler.close()

    def __del__(self):
        super().__del__()

