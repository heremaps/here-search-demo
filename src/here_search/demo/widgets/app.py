###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
import logging

from ipyleaflet import WidgetControl
from ipywidgets import HBox, Label, VBox

from here_search.demo.api import API
from here_search.demo.api_options import APIOptions, details, evDetails, recommendPlaces, tripadvisorDetails
from here_search.demo.base import OneBoxBase
from here_search.demo.entity.endpoint import Endpoint
from here_search.demo.entity.intent import NoIntent, SearchIntent
from here_search.demo.entity.place import PlaceTaxonomyExample
from here_search.demo.entity.response import Response
from here_search.demo.user import UserProfile

from .input import PlaceTaxonomyButtons, SubmittableTextBox, TermsButtons
from .output import ResponseMap, SearchResultButtons, SearchResultJson
from .util import TableLogWidgetHandler


class OneBoxMap(OneBoxBase, VBox):
    default_search_box_layout = {"width": "240px"}
    default_placeholder = "free text"
    default_output_format = "text"
    default_taxonomy, default_icons = (
        PlaceTaxonomyExample.taxonomy,
        PlaceTaxonomyExample.icons,
    )
    default_options = APIOptions(
        {
            Endpoint.AUTOSUGGEST: [details, recommendPlaces],
            Endpoint.AUTOSUGGEST_HREF: [evDetails, recommendPlaces],
            Endpoint.DISCOVER: [evDetails, recommendPlaces],
            Endpoint.BROWSE: [evDetails],
            Endpoint.LOOKUP: [evDetails],
        }
    )
    premium_ta_options = APIOptions(
        {
            Endpoint.AUTOSUGGEST: [details],
            Endpoint.AUTOSUGGEST_HREF: [tripadvisorDetails, evDetails],
            Endpoint.DISCOVER: [tripadvisorDetails, evDetails],
            Endpoint.BROWSE: [tripadvisorDetails, evDetails],
            Endpoint.LOOKUP: [tripadvisorDetails, evDetails],
        }
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
        with_tripadvisor: bool = False,
        options: APIOptions = None,
        **kwargs,
    ):
        self.logger = logging.getLogger("here_search")
        self.result_queue: asyncio.Queue = asyncio.Queue()

        if not api:
            if (opts := options) is None:
                opts = self.premium_ta_options if with_tripadvisor else self.default_options
            api = API(api_key=api_key, url_format_fn=TableLogWidgetHandler.format_url, options=opts)

        OneBoxBase.__init__(
            self,
            api=api,
            user_profile=user_profile,
            results_limit=results_limit or OneBoxMap.default_results_limit,
            suggestions_limit=suggestions_limit or OneBoxMap.default_suggestions_limit,
            terms_limit=terms_limit or OneBoxMap.default_terms_limit,
            extra_api_params=extra_api_params,
            result_queue=self.result_queue,
            **kwargs,
        )

        self.map_w = ResponseMap(
            api_key=self.api.api_key,
            center=self.search_center,
            position_handler=self.set_search_center,
            queue=self.queue,
            more_details_for_suggestion=self.more_details_for_suggestion,
        )

        # The JSON output
        self.result_json_w = SearchResultJson(
            result_queue=self.queue,
            max_results_number=max(self.results_limit, self.suggestions_limit),
            layout={"width": "400px", "max_height": "600px"},
        )
        self.result_json_w.display(Response(data={}), intent=NoIntent())

        # The Search input box
        self.query_box_w = SubmittableTextBox(
            queue=self.queue,
            layout=kwargs.pop("layout", self.__class__.default_search_box_layout),
            placeholder=kwargs.pop("placeholder", self.__class__.default_placeholder),
            **kwargs,
        )
        self.query_terms_w = TermsButtons(self.query_box_w, buttons_count=self.__class__.default_terms_limit)
        self.buttons_box_w = place_taxonomy_buttons or PlaceTaxonomyButtons(
            queue=self.queue,
            taxonomy=OneBoxMap.default_taxonomy,
            icons=OneBoxMap.default_icons,
        )
        self.result_buttons_w = SearchResultButtons(
            queue=self.queue,
            max_results_number=max(self.results_limit, self.suggestions_limit),
            more_details_for_suggestion=self.more_details_for_suggestion,
        )
        self.search_center_label_w = Label()
        self.search_center_label_w.value = (
            f"lat/lon/zoom: {round(self.map_w.center[0], 5)}{round(self.map_w.center[1], 5)}/{int(self.map_w.zoom)}"
        )

        def update_label(change):
            self.search_center_label_w.value = f"lat/lon/zoom: {round(change['owner'].center[0], 5)}/{round(change['owner'].center[1], 5)}/{int(change['owner'].zoom)}"

        self.map_w.observe(update_label, names=["center", "zoom"])

        search_box = VBox(
            ([self.buttons_box_w] if self.buttons_box_w else [])
            + [self.query_box_w, self.query_terms_w, self.result_buttons_w, self.search_center_label_w],
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
            self.map_w.add(
                WidgetControl(widget=self.result_json_w, position="topright", name="search_out", transparent_bg=False)
            )
            self.map_w.add(
                WidgetControl(
                    widget=self.log_handler.out, position="bottomleft", name="search_log", transparent_bg=False
                )
            )
            VBox.__init__(self, [self.map_w])
        else:
            VBox.__init__(self, [HBox([self.map_w, self.result_json_w]), self.log_handler.out])

    def handle_suggestion_list(self, intent: SearchIntent, autosuggest_resp: Response):
        """
        Display autosuggest_resp in a JSON widget
        Display autosuggest_resp with intent in SearchResultButtons widget
        Display results on responseMap
        Display terms suggestions in TermsButtons widget
        :param intent: the intent behind the Response instance
        :param autosuggest_resp: the Response instance to handle
        :return: None
        """
        self._display_suggestions(autosuggest_resp, intent)
        self._display_result_map(autosuggest_resp, intent, fit=False)
        self._display_terms(autosuggest_resp, intent)

    def _display_suggestions(self, autosuggest_resp: Response, intent: SearchIntent) -> None:
        # Used by handle_suggestion_list
        self.result_json_w.display(autosuggest_resp)
        self.result_buttons_w.display(autosuggest_resp, intent=intent)
        # self.display_result_map(autosuggest_resp, update_search_center=False)

    def _display_terms(self, autosuggest_resp: Response, intent: SearchIntent):
        # Used by handle_suggestion_list
        terms = {term["term"]: None for term in autosuggest_resp.data.get("queryTerms", [])}
        self.query_terms_w.set(list(terms.keys()))

    def _display_result_map(self, resp: Response, intent: SearchIntent, fit: bool = False):
        # Used by handle_suggestion_list
        self.map_w.display(resp, intent=intent, fit=fit)

    def handle_result_list(self, intent: SearchIntent, resp: Response):
        """
        Display resp in a JSON widget
        Display resp with intent in SearchResultButtons widget
        Display results on responseMap
        :param intent: the intent behind the Response instance
        :param resp: the Response instance to handle
        :return: None
        """
        self.result_json_w.display(resp)
        self.result_buttons_w.display(resp, intent=intent)
        self._display_result_map(resp, intent, fit=True)
        self.clear_query_text()

    def handle_result_details(self, intent: SearchIntent, lookup_resp: Response):
        """
        Display single lookup Response details in a JSON widget
        Display result on responseMap
        Do not touch the SearchResultButtons widget
        :param intent: the intent behind the Response instance
        :param lookup_resp: the lookup Response instance to handle
        :return: None
        """
        self.result_json_w.display(lookup_resp)
        self.result_buttons_w.modify(lookup_resp, intent=intent)
        self._display_result_map(lookup_resp, intent, fit=True)

    def clear_query_text(self):
        self.query_box_w.text_w.value = ""
        self.query_terms_w.set([])

    def clear_logs(self):
        self.logger.removeHandler(self.log_handler)
        self.log_handler.clear_logs()
        self.log_handler.close()

    def __del__(self):
        super().__del__()
