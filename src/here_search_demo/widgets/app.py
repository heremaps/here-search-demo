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
from collections.abc import Callable
from ipyleaflet import WidgetControl
from IPython.display import display
from ipywidgets import HBox, Label, VBox

from ..api import API
from ..auth import Credentials
from ..api_options import (
    APIOptions,
    recommendPlaces,
    tripadvisorDetails,
    fuelDetails,
    fuelPriceDetails,
    default_options_config,
    build_api_options,
)
from ..base import OneBoxCore, UserProfileMixin
from ..detour import DetourRanker
from ..entity.endpoint import Endpoint
from ..entity.intent import SearchIntent
from ..entity.place import PlaceTaxonomyExample
from ..entity.request import RequestContext
from ..entity.response import QuerySuggestionItem, Response
from .state import SearchState
from ..user import UserProfile
from .credentials import CredentialsLoader
from .input_text import PlaceTaxonomyButtons, SubmittableTextBox, TermsButtons
from .output_map import ResponseMap
from .output_buttons import SearchResultButtons
from .output_json import SearchResultJson, SearchResultList
from .util import TableLogWidget

style_refactor = True


class OneBoxMap(UserProfileMixin, OneBoxCore):
    """Interactive one-box search application with map and result panels.

    ``OneBoxMap`` wires text input, taxonomy shortcuts, map rendering and
    result/details handling into a ready-to-use demo widget.

    :param credentials: Optional credentials provider.
    :param user_profile: Optional user profile controlling language/signals.
    :param results_limit: Max displayed results.
    :param suggestions_limit: Max displayed suggestions.
    :param terms_limit: Max displayed term buttons.
    :param place_taxonomy_buttons: Optional custom taxonomy buttons widget.
    :param extra_api_params: Extra params forwarded to API requests.
    :param on_map: Whether to display controls on map.
    :param fuel: Enable fuel details.
    :param tripadvisor: Enable TripAdvisor details.
    :param recommendations: Enable recommendation reranking flow.
    :param map_only: Hide JSON/log panels and keep map-centric layout.
    :param options: Optional prebuilt API options.
    :param testing_header: Include NLP testing header for API calls.
    :param kwargs: Forwarded widget/layout options.
    """

    default_search_box_layout = {"width": "240px"}
    default_placeholder = "free text"
    default_output_format = "text"
    default_taxonomy, default_icons = (
        PlaceTaxonomyExample.taxonomy,
        PlaceTaxonomyExample.icons,
    )

    default_options = build_api_options(default_options_config)

    # Set to True once the HERE Search API explicitly allows the X-User-ID
    # header in its CORS Access-Control-Allow-Headers policy.
    # When True and share_experience is enabled, X-User-ID will be included
    # in every outgoing request header (browse, lookup, autosuggest, …).
    # Until then keep this False: the user id is passed only to api.signals()
    # via RequestContext.user_id, leaving regular API calls free of the header.
    cors_allow_user_id_header: bool = False

    logger: logging.Logger
    result_queue: asyncio.Queue
    state: SearchState
    credentials: Credentials
    log_handler: TableLogWidget | None
    map_w: ResponseMap
    result_json_w: SearchResultJson | None
    query_box_w: SubmittableTextBox
    query_terms_w: TermsButtons
    buttons_box_w: PlaceTaxonomyButtons
    result_buttons_w: SearchResultButtons
    search_center_label_w: Label
    credentials_properties: CredentialsLoader
    search_api_calls: int
    routing_api_calls: int
    _root: VBox
    map_only: bool
    _recommendations: bool
    _base_autosuggest_limit: int
    _base_discover_limit: int
    _last_result_resp: Response | None
    _last_result_intent: SearchIntent | None
    _rerank_task: asyncio.Task | None
    _orig_set_minimal_detour: Callable[[bool], None]
    _display_id: str | None

    def __init__(
        self,
        credentials: Credentials | None = None,
        user_profile: UserProfile | None = None,
        results_limit: int | None = None,
        suggestions_limit: int | None = None,
        terms_limit: int | None = None,
        place_taxonomy_buttons: PlaceTaxonomyButtons | None = None,
        extra_api_params: dict | None = None,
        on_map: bool = False,
        fuel: bool = False,
        tripadvisor: bool = False,
        recommendations: bool = False,
        map_only: bool = False,
        options: APIOptions | None = None,
        testing_header: bool = False,
        **kwargs,
    ):
        self.logger = logging.getLogger("here_search")
        self.result_queue: asyncio.Queue = asyncio.Queue()
        self.state = SearchState()
        self._recommendations = recommendations
        self.map_only = map_only
        self.search_api_calls = 0
        self.routing_api_calls = 0

        self.credentials = credentials or Credentials()

        self.log_handler = None if self.map_only else TableLogWidget()

        if options is None:
            extra = []
            if tripadvisor:
                extra.append(tripadvisorDetails)
            if fuel:
                extra.extend([fuelDetails, fuelPriceDetails])
            if recommendations:
                extra.append(recommendPlaces)
            options = build_api_options(default_options_config, extra_options=extra)

        api = API(
            credentials=self.credentials,
            options=options,
            log_fn=self.log_handler.log if self.log_handler is not None else None,
            on_request_sent=self._on_search_api_call,
            testing_header=testing_header,
        )

        super().__init__(
            api=api,
            user_profile=user_profile,
            results_limit=results_limit or OneBoxMap.default_results_limit,
            suggestions_limit=suggestions_limit or OneBoxMap.default_suggestions_limit,
            terms_limit=terms_limit or OneBoxMap.default_terms_limit,
        )

        self.extra_api_params = extra_api_params or {}

        # X-User-ID must NOT be added to self.x_headers until the HERE Search
        # API explicitly allows it via CORS (Access-Control-Allow-Headers).
        # Flip `OneBoxMap.cors_allow_user_id_header = True` (or override at
        # instance level) to re-enable once the API is ready.
        if self.user_profile.share_experience and type(self).cors_allow_user_id_header:
            self.x_headers = {"X-User-ID": self.user_profile.id}

        self._base_autosuggest_limit = self.autosuggest_backend_limit
        self._base_discover_limit = self.discover_backend_limit
        if self._recommendations:
            self.autosuggest_backend_limit = max(self.autosuggest_backend_limit, 100)
            self.discover_backend_limit = max(self.discover_backend_limit, 100)

        self.map_w = ResponseMap(
            credentials=self.credentials,
            center=self.search_center,
            search_center_handler=self.set_search_center,
            queue=self.queue,
            state=self.state,
            more_details_for_suggestion=self.more_details_for_suggestion,
            routing_api_call_handler=self._increment_routing_api_calls,
        )

        # Storage for the last result list so we can re-display it when the
        # "travel time" checkbox is toggled off (to drop _detour_label annotations).
        self._last_result_resp: Response | None = None
        self._last_result_intent: SearchIntent | None = None
        self._rerank_task: asyncio.Task | None = None
        self._results_event: asyncio.Event | None = None
        self._results_postprocess_cb = None

        # Wrap set_minimal_detour_option so that turning it OFF immediately
        # refreshes the result list with the un-annotated original response.
        _route = self.map_w.route
        self._orig_set_minimal_detour = _route.set_travel_time_option
        self._orig_set_mins_from_pos = _route.set_mins_from_pos
        _route.set_travel_time_option = self._set_minimal_detour_with_refresh
        _route.set_mins_from_pos = self._set_mins_from_pos_with_clear_results

        _route.on_drawn(self._clear_results_on_route_change)
        _route.on_removed(self._clear_results_on_route_change)

        # The JSON output (omitted in map-only mode).
        self.result_json_w = None
        if not self.map_only:
            self.result_json_w = SearchResultJson(
                state=self.state,
                queue=self.queue,
                max_results_number=max(self.results_limit, self.suggestions_limit),
                layout={"width": "400px", "max_height": "600px"},
            )

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
            on_result_click=self._focus_result_on_map,
        )
        self.search_center_label_w = Label()
        self._update_search_center_label()

        def update_label(change: dict):
            if change["name"] not in ("center", "zoom"):
                return
            self._update_search_center_label()

        self.map_w.observe(update_label, names=["center", "zoom"])

        search_box = VBox(
            ([self.buttons_box_w] if self.buttons_box_w else [])
            + [self.query_box_w, self.query_terms_w, self.result_buttons_w, self.search_center_label_w],
        )
        self.search_box = search_box
        # Keep the search widgets hidden until valid credentials (an api_key and a
        # retrievable OAuth token) have been confirmed.
        self.search_box.layout.display = "none"

        # App widgets composition
        widget_control_left = WidgetControl(widget=search_box, position="topleft", transparent_bg=False)
        self.map_w.add(widget_control_left)

        self.credentials_properties = CredentialsLoader()
        initial_active_config = self.credentials.active_config
        if initial_active_config:
            self.credentials_properties.active_config = initial_active_config
        self.credentials_properties.observe(self._on_credentials_properties_change, names="active_config")
        self._apply_credentials_properties(self.credentials_properties.active_config)
        # Cover the case where credentials were already loaded (env/file) so that
        # _apply_credentials_properties short-circuited on an empty config.
        self._schedule_search_box_visibility()
        self.map_w.add(WidgetControl(widget=self.credentials_properties, position="topright", transparent_bg=False))

        if on_map or self.map_only:
            if self.result_json_w is not None:
                self.map_w.add(WidgetControl(widget=self.result_json_w, position="topright", transparent_bg=False))
            if self.log_handler is not None:
                self.map_w.add(WidgetControl(widget=self.log_handler.out, position="bottomleft", transparent_bg=False))
            root = VBox([self.map_w])
        else:
            if self.log_handler is None:
                raise RuntimeError("log_handler must be initialized when map_only is disabled")
            if self.result_json_w is None:
                raise RuntimeError("result_json_w must be initialized when map_only is disabled")
            root = VBox([HBox([self.map_w, self.result_json_w]), self.log_handler.out])

        self._root = root
        # Track whether we've been displayed, so we can optionally clean up.
        self._display_id = None

    def _update_search_center_label(self) -> None:
        center = self.map_w.center
        self.search_center_label_w.value = (
            f"lat/lon/zoom: {round(center[0], 5)}/{round(center[1], 5)}/{int(self.map_w.zoom)}"
            f" | api: {self.search_api_calls}/{self.routing_api_calls}"
        )

    def _on_search_api_call(self, request) -> None:
        if request.endpoint != Endpoint.SIGNALS:
            self.search_api_calls += 1
            self._update_search_center_label()

    def _increment_routing_api_calls(self, calls: int = 1) -> None:
        self.routing_api_calls += max(0, calls)
        self._update_search_center_label()

    def _on_credentials_properties_change(self, change: dict) -> None:
        if change.get("name") != "active_config":
            return
        self._apply_credentials_properties(change.get("new") or {})

    def _apply_credentials_properties(self, properties: dict) -> None:
        if not properties:
            return
        self.credentials.apply_active_config(properties)
        self.map_w.refresh_base_layer()
        self._schedule_search_box_visibility()

    def _set_search_box_visible(self, visible: bool) -> None:
        self.search_box.layout.display = "" if visible else "none"

    async def _credentials_are_valid(self) -> bool:
        """Return True when an api_key is set and an OAuth token can be retrieved."""
        if not self.credentials.api_key:
            return False
        try:
            return bool(await self.credentials.atoken)
        except Exception:
            self.logger.debug("Token retrieval failed; hiding search box", exc_info=True)
            return False

    async def _update_search_box_visibility(self) -> None:
        self._set_search_box_visible(await self._credentials_are_valid())

    def _schedule_search_box_visibility(self) -> None:
        """Re-evaluate search box visibility on the running event loop.

        The token check is a network call that is async in the browser runtime,
        so it is scheduled as a task. When no event loop is running (e.g. plain
        construction in tests), the check is skipped and the box keeps its
        current (hidden) state to avoid blocking network calls.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._update_search_box_visibility())

    def triage_intent(self, intent, context):
        if self._recommendations:
            if context.polyline:
                self.autosuggest_backend_limit = self._base_autosuggest_limit
                self.discover_backend_limit = self._base_discover_limit
            else:
                self.autosuggest_backend_limit = max(self._base_autosuggest_limit, 100)
                self.discover_backend_limit = max(self._base_discover_limit, 100)
        return super().triage_intent(intent, context)

    def _get_context(self) -> RequestContext:

        route = self.map_w.route

        lat, lon = route.search_at_position or self.search_center

        return RequestContext(
            latitude=lat,
            longitude=lon,
            polyline=route.search_flexpolyline,
            width=route.width,
            all_along=route.all_along,
            language=self.preferred_language,
            x_headers=self.x_headers,
            share_experience=self.user_profile.share_experience,
            user_id=self.user_profile.id if self.user_profile.share_experience else None,
        )

    def _set_minimal_detour_with_refresh(self, value: bool):
        """Toggle minimal-detour and refresh the result list accordingly."""
        self._orig_set_minimal_detour(value)
        if self._last_result_resp is None or self._last_result_intent is None:
            return
        if not value:
            # Turning off: restore original labels without reranking.
            self._display_result_list(self._last_result_intent, self._last_result_resp, fit=False, clear_query=False)
        else:
            # Turning on: re-apply detour ranking when route data is available.
            route = self.map_w.route
            if (
                (
                    self._last_result_intent.kind in ("submitted_text", "taxonomy")
                    or (
                        self._last_result_intent.kind == "details"
                        and isinstance(self._last_result_intent.materialization, QuerySuggestionItem)
                    )
                )
                and route.ranking_mode.needs_client_rerank
                and route.start_position is not None
                and route.stop_position is not None
                and route.current_position is not None
                and route.route_summary_length is not None
            ):
                self._rerank_task = asyncio.create_task(
                    self._handle_result_list_with_detour(self._last_result_intent, self._last_result_resp)
                )
                route.detour_task = self._rerank_task

    def _set_mins_from_pos_with_clear_results(self, mins: int | None):
        """Update min-from-pos and clear displayed results so they match the new center."""
        self._orig_set_mins_from_pos(mins)
        self._clear_results_on_route_change()

    def _clear_results_on_route_change(self, route=None):
        self.map_w.clear_results()
        self.result_buttons_w._inner_box.children = ()
        self._last_result_resp = None
        self._last_result_intent = None

    def add_result_postprocess(self) -> None:
        """Register a built-in postprocess that signals when a result list arrives.

        The callback removes itself automatically after firing once, so calling
        ``remove_result_postprocess()`` is optional.

        After calling this, ``await app.post_process_tasks`` will block until:
        - a ``submitted_text`` or ``taxonomy`` response has been fully processed,
        - any travel-time reranking task has completed, and
        - the map fit-bounds animation has finished.
        """
        self._results_event = asyncio.Event()

        async def _cb(intent, event, resp, session):
            if intent.kind in ("submitted_text", "taxonomy"):
                self._results_event.set()
                self.remove_postprocess(_cb)  # one-shot: deregister after firing
                self._results_postprocess_cb = None

        self._results_postprocess_cb = _cb
        self.add_postprocess(_cb)

    def remove_result_postprocess(self) -> None:
        """Deregister the callback registered by ``add_result_postprocess``."""
        if self._results_postprocess_cb is not None:
            self.remove_postprocess(self._results_postprocess_cb)
            self._results_postprocess_cb = None
        self._results_event = None

    @property
    def post_process_tasks(self):
        """Awaitable that resolves once results are displayed, reranked, and the map fitted.

        Example usage::

            app.add_result_postprocess()
            app.buttons_box_w.buttons[0].click()
            await app.post_process_tasks
            app.remove_result_postprocess()
        """
        return self._await_post_process_tasks()

    async def _await_post_process_tasks(self):
        if self._results_event is not None:
            await self._results_event.wait()
        if self._rerank_task is not None:
            await self._rerank_task
        if self.map_w._fit_task is not None:
            await self.map_w._fit_task

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
        # Hydrate state first so result_json_w can reuse pre-computed _vicinity.
        self.result_buttons_w.display(limited_resp, intent=intent)
        if self.result_json_w is not None:
            self.result_json_w.display(limited_resp)
        # self.display_result_map(autosuggest_resp, update_search_center=False)

    def _display_terms(self, autosuggest_resp: Response, intent: SearchIntent):
        # Used by handle_suggestion_list
        terms = {term["term"]: None for term in autosuggest_resp.data.get("queryTerms", [])}
        self.query_terms_w.set(list(terms.keys()))

    def _display_result_map(self, resp: Response, intent: SearchIntent, fit: bool = False):
        # Used by handle_suggestion_list
        self.map_w.display(resp, intent=intent, fit=fit)

    def _focus_result_on_map(self, rank: int) -> None:
        self.map_w.click_result(rank, emit_action=False, recenter=True, show_details=True)

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
        route = self.map_w.route

        # Always keep the original (non-reranked) response so we can restore
        # it when the "travel time" checkbox is turned off.
        self._last_result_resp = limited_resp
        self._last_result_intent = intent

        if (
            (
                intent.kind in ("submitted_text", "taxonomy")
                or (intent.kind == "details" and isinstance(intent.materialization, QuerySuggestionItem))
            )
            and getattr(route, "minimal_detour", False)
            and route.start_position is not None
            and route.stop_position is not None
            and route.current_position is not None
            and route.route_summary_length is not None
        ):
            # Kick off async reranking; display immediately once done.
            self._rerank_task = asyncio.create_task(self._handle_result_list_with_detour(intent, limited_resp))
            route.detour_task = self._rerank_task
        else:
            self._display_result_list(intent, limited_resp)

    async def _handle_result_list_with_detour(self, intent: SearchIntent, resp: Response):
        """Rerank *resp* items by minimal excursion distance, then display."""
        route = self.map_w.route
        ranker = DetourRanker(
            credentials=self.credentials,
            at_pos=route.search_at_position or route.current_position,
            stop_pos=route.stop_position,
            on_routing_request=self._increment_routing_api_calls,
            route_cache=self.map_w.route._route_cache,
        )
        try:
            reranked_resp = await ranker.rerank(
                resp,
                all_along=route.all_along,
                # max_excursion=route.width * 3
            )
        except Exception:
            self.logger.exception("Minimal-detour reranking failed; falling back to original order")
            reranked_resp = resp
        self._display_result_list(intent, reranked_resp)

    def _display_result_list(self, intent: SearchIntent, resp: Response, fit: bool = True, clear_query: bool = True):
        """Perform the actual UI update for a result list response."""
        # Hydrate state (result_buttons_w) first so result_json_w can reuse _vicinity.
        self.result_buttons_w.display(resp, intent=intent)
        if self.result_json_w is not None:
            self.result_json_w.display(resp)
        self._display_result_map(resp, intent, fit=fit)
        if clear_query:
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
        if self.result_json_w is not None:
            self.result_json_w.display(lookup_resp)
        self.result_buttons_w.modify(lookup_resp, intent=intent)
        self._display_result_map(lookup_resp, intent, fit=True)

    def clear_query_text(self):
        self.query_box_w.text_w.value = ""
        self.query_terms_w.set([])

    def clear_logs(self):
        if self.log_handler is None:
            return
        self.log_handler.clear_logs()
        self.log_handler.close()

    async def search_events_preprocess(self, session) -> None:
        """Send a 'start' signal when the app begins processing events."""
        if self.user_profile.share_experience and self.user_profile.id:
            try:
                await self.api.signals(
                    session=session,
                    resource_id="application",
                    rank=0,
                    correlation_id="noCorrelationID",
                    action="start",
                    userId=self.user_profile.id,
                )
            except Exception:
                pass

    async def stop(self):
        """Send an 'end' signal then stop the event loop."""
        await super().stop()
        if self.user_profile.share_experience and self.user_profile.id:
            from here_search_demo.http import HTTPSession as _HTTPSession

            try:
                async with _HTTPSession() as session:
                    await self.api.signals(
                        session=session,
                        resource_id="application",
                        rank=0,
                        correlation_id="noCorrelationID",
                        action="end",
                        userId=self.user_profile.id,
                    )
            except Exception:
                pass

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
