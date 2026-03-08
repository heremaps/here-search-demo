###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
import logging

from ipyleaflet import WidgetControl
from IPython.display import display
from ipywidgets import HBox, Label, VBox

from here_search_demo.api import API
from here_search_demo.api_options import APIOptions, details, evDetails, recommendPlaces, tripadvisorDetails
from here_search_demo.base import OneBoxBase
from here_search_demo.entity.endpoint import Endpoint
from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.place import PlaceTaxonomyExample
from here_search_demo.entity.request import RequestContext
from here_search_demo.entity.response import Response
from here_search_demo.user import UserProfile
from here_search_demo.widgets.state import SearchState

from .input import PlaceTaxonomyButtons, SubmittableTextBox, TermsButtons
from .output import ResponseMap, SearchResultButtons, SearchResultJson, SearchResultList
from .util import TableLogWidget

style_refactor = True


def _build_api_options(config, include_recommend_places: bool) -> APIOptions:
    options = {}
    for endpoint, base_options in config.items():
        endpoint_options = list(base_options)
        if (
            include_recommend_places
            and endpoint in recommendPlaces.endpoints
            and recommendPlaces not in endpoint_options
        ):
            endpoint_options.append(recommendPlaces)
        options[endpoint] = endpoint_options
    return APIOptions(options)


class OneBoxMap(OneBoxBase):
    default_search_box_layout = {"width": "240px"}
    default_placeholder = "free text"
    default_output_format = "text"
    default_taxonomy, default_icons = (
        PlaceTaxonomyExample.taxonomy,
        PlaceTaxonomyExample.icons,
    )
    default_options_config = {
        Endpoint.AUTOSUGGEST: (details,),
        Endpoint.AUTOSUGGEST_HREF: (evDetails,),
        Endpoint.DISCOVER: (evDetails,),
        Endpoint.BROWSE: (evDetails,),
        Endpoint.LOOKUP: (evDetails,),
    }
    default_options = _build_api_options(default_options_config, include_recommend_places=True)
    premium_ta_options_config = {
        Endpoint.AUTOSUGGEST: (details,),
        Endpoint.AUTOSUGGEST_HREF: (tripadvisorDetails, evDetails),
        Endpoint.DISCOVER: (tripadvisorDetails, evDetails),
        Endpoint.BROWSE: (tripadvisorDetails, evDetails),
        Endpoint.LOOKUP: (tripadvisorDetails, evDetails),
    }
    premium_ta_options = _build_api_options(premium_ta_options_config, include_recommend_places=False)

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
        tripadvisor: bool = False,
        recommendations: bool = False,
        route_post: bool = False,
        options: APIOptions = None,
        **kwargs,
    ):
        self.logger = logging.getLogger("here_search")
        self.result_queue: asyncio.Queue = asyncio.Queue()
        self.state = SearchState()
        self._recommendations = recommendations
        self._route_post = route_post

        self.log_handler = TableLogWidget()

        if not api:
            if (opts := options) is None:
                config = self.premium_ta_options_config if tripadvisor else self.default_options_config
                opts = _build_api_options(config, include_recommend_places=recommendations)
            api = API(
                api_key=api_key,
                options=opts,
                log_fn=self.log_handler.log,
                url_format_fn=self.log_handler.url_to_md_link,
            )

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

        if self._recommendations:
            self.autosuggest_backend_limit = max(self.autosuggest_backend_limit, 100)
            self.discover_backend_limit = max(self.discover_backend_limit, 100)

        self.map_w = ResponseMap(
            api_key=self.api.api_key,
            center=self.search_center,
            search_center_handler=self.set_search_center,
            queue=self.queue,
            state=self.state,
            more_details_for_suggestion=self.more_details_for_suggestion,
            route_post=route_post,
        )

        # The JSON output
        self.result_json_w = SearchResultJson(
            result_queue=self.queue,
            max_results_number=max(self.results_limit, self.suggestions_limit),
            layout={"width": "400px", "max_height": "600px"},
        )
        # Do not pre-render an empty response; it caused a lingering empty JSON block
        # self.result_json_w.display(
        #     Response(data={}), intent=SearchIntent(kind="empty", materialization=None, time=perf_counter_ns())
        # )

        # The Search input box
        self.query_box_w = SubmittableTextBox(
            queue=self.queue,
            state=self.state,
            layout=kwargs.pop("layout", self.__class__.default_search_box_layout),
            placeholder=kwargs.pop("placeholder", self.__class__.default_placeholder),
            **kwargs,
        )
        self.query_terms_w = TermsButtons(
            self.query_box_w, state=self.state, buttons_count=self.__class__.default_terms_limit
        )
        self.buttons_box_w = place_taxonomy_buttons or PlaceTaxonomyButtons(
            queue=self.queue,
            taxonomy=OneBoxMap.default_taxonomy,
            icons=OneBoxMap.default_icons,
            state=self.state,
        )
        self.result_buttons_w = SearchResultButtons(
            queue=self.queue,
            state=self.state,
            max_results_number=max(self.results_limit, self.suggestions_limit),
        )
        self.search_center_label_w = Label()
        self.search_center_label_w.value = (
            f"lat/lon/zoom: {round(self.map_w.center[0], 5)}{round(self.map_w.center[1], 5)}/{int(self.map_w.zoom)}"
        )

        def update_label(change: dict):
            if change["name"] not in ("center", "zoom"):
                return
            center = self.map_w.center
            self.search_center_label_w.value = (
                f"lat/lon/zoom: {round(center[0], 5)}/{round(center[1], 5)}/{int(self.map_w.zoom)}"
            )

        self.map_w.observe(update_label, names=["center", "zoom"])

        search_box = VBox(
            ([self.buttons_box_w] if self.buttons_box_w else [])
            + [self.query_box_w, self.query_terms_w, self.result_buttons_w, self.search_center_label_w],
        )

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
            root = VBox([self.map_w])
        else:
            root = VBox([HBox([self.map_w, self.result_json_w]), self.log_handler.out])

        # Store the root widget rather than subclassing VBox ourselves.
        self._root = root
        # Track whether we've been displayed, so we can optionally clean up.
        self._display_id = None

    def _get_context(self) -> RequestContext:
        return RequestContext(
            latitude=self.search_center[0],
            longitude=self.search_center[1],
            route=self.map_w.route.flexpolyline,
            all_along=self.map_w.route.all_along,
            language=self.preferred_language,
            x_headers=self.x_headers,
        )

    def show(self) -> None:
        """Display the application UI in the current notebook.

        This displays the internal root widget without exposing or
        returning the underlying display handle.
        """
        handle = display(self._root, display_id=True)
        if style_refactor:
            self.query_terms_w.apply_style()
            # Apply CSS styling for result buttons as well.
            self.result_buttons_w.apply_style()
            # Some IPython versions return a DisplayHandle, others None; store
        # the display_id if available so we can update it on deletion.
        try:
            self._display_id = getattr(handle, "display_id", None)
        except Exception:
            self._display_id = None

    def _limit_ui_response(self, resp: Response) -> Response:
        if not self._recommendations:
            return resp
        endpoint = getattr(getattr(resp, "req", None), "endpoint", None)
        if endpoint not in {Endpoint.AUTOSUGGEST, Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER}:
            return resp
        limit = SearchResultList.default_max_results_count
        items = resp.data.get("items")
        if not isinstance(items, list) or len(items) <= limit:
            return resp
        data = {**resp.data, "items": items[:limit]}
        return Response(req=resp.req, data=data, x_headers=resp.x_headers)

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
        limited_resp = self._limit_ui_response(autosuggest_resp)
        self._display_suggestions(limited_resp, intent)
        self._display_result_map(limited_resp, intent, fit=False)
        self._display_terms(limited_resp, intent)

    def _display_suggestions(self, autosuggest_resp: Response, intent: SearchIntent) -> None:
        # Used by handle_suggestion_list
        limited_resp = self._limit_ui_response(autosuggest_resp)
        self.result_json_w.display(limited_resp)
        self.result_buttons_w.display(limited_resp, intent=intent)
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
        limited_resp = self._limit_ui_response(resp)
        self.result_json_w.display(limited_resp)
        self.result_buttons_w.display(limited_resp, intent=intent)
        self._display_result_map(limited_resp, intent, fit=True)
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
        self.log_handler.clear_logs()
        self.log_handler.close()

    def __del__(self):
        # Best-effort UI cleanup: if we know the display_id, update it to
        # an empty box so the app disappears from the notebook output.
        try:
            if self._display_id is not None:
                try:
                    from IPython.display import DisplayHandle

                    dh = DisplayHandle(display_id=self._display_id)
                    dh.update(VBox([]))
                except Exception:
                    try:
                        self._root.close()
                    except Exception:
                        pass
            else:
                # We may still have a live widget; closing it will remove
                # leaf controls from subsequent renders.
                try:
                    self._root.close()
                except Exception:
                    pass
        except Exception:
            pass
        super().__del__()
