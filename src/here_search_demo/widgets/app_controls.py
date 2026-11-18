###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Credentials and search-box visibility, route-change handling and post-process hooks for the one-box map app."""

import asyncio

from ..entity.response import QuerySuggestionItem


class OneBoxControlsMixin:
    """Credentials and search-box visibility, route-change handling and post-process hooks for the one-box map app."""

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
