###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Suggestion, result list and result details display for the one-box map app."""

import asyncio

from ..detour import DetourRanker
from ..entity.endpoint import Endpoint
from ..entity.intent import SearchIntent
from ..entity.response import QuerySuggestionItem, Response
from .output_json import SearchResultList


class OneBoxResultsMixin:
    """Suggestion, result list and result details display for the one-box map app."""

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
