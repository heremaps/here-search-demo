###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
import traceback
from dataclasses import dataclass
from time import perf_counter_ns
from typing import Callable, Mapping, Tuple

from here_search_demo import __version__
from here_search_demo.api import API
from here_search_demo.entity.endpoint import (
    AutosuggestConfig,
    BrowseConfig,
    DiscoverConfig,
    EndpointConfig,
    LookupConfig,
    NoConfig,
)
from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.request import RequestContext
from here_search_demo.entity.response import LocationSuggestionItem, QuerySuggestionItem, Response
from here_search_demo.event import (
    DetailsSearchEvent,
    DetailsSuggestionEvent,
    EmptySearchEvent,
    FollowUpSearchEvent,
    PartialTextSearchEvent,
    PlaceTaxonomySearchEvent,
    SearchEvent,
    TextSearchEvent,
)
from here_search_demo.http import HTTPSession
from here_search_demo.user import DefaultUser, UserProfile


@dataclass(frozen=True)
class Route:
    event_type: type[SearchEvent]
    config_factory: Callable[["OneBoxSimple"], EndpointConfig | LookupConfig | NoConfig | None]
    handler_factory: Callable[["OneBoxSimple"], Callable[[SearchIntent, Response], None]]


ROUTES: Mapping[str, Route] = {
    "transient_text": Route(
        event_type=PartialTextSearchEvent,
        config_factory=lambda ob: AutosuggestConfig(limit=ob.autosuggest_backend_limit, terms_limit=ob.terms_limit),
        handler_factory=lambda ob: ob.handle_suggestion_list,
    ),
    "submitted_text": Route(
        event_type=TextSearchEvent,
        config_factory=lambda ob: DiscoverConfig(limit=ob.discover_backend_limit),
        handler_factory=lambda ob: ob.handle_result_list,
    ),
    "taxonomy": Route(
        event_type=PlaceTaxonomySearchEvent,
        config_factory=lambda ob: BrowseConfig(limit=ob.browse_backend_limit),
        handler_factory=lambda ob: ob.handle_result_list,
    ),
    "empty": Route(
        event_type=EmptySearchEvent,
        config_factory=lambda ob: None,
        handler_factory=lambda ob: ob.handle_empty_text_submission,
    ),
}


class OneBoxSimple:
    default_results_limit = 20
    default_suggestions_limit = 20
    default_terms_limit = 3
    default_search_center = 52.51604, 13.37691
    default_max_transient_keep = 1
    default_language = "en"
    default_headers = {"User-Agent": f"here-search-notebook-{__version__}"}

    def __init__(
        self,
        api: API = None,
        queue: asyncio.Queue = None,
        search_center: Tuple[float, float] = None,
        language: str = None,
        results_limit: int = None,
        suggestions_limit: int = None,
        terms_limit: int = None,
        max_transient_keep: int | None = None,
        **kwargs,
    ):
        self.task = None
        self.api = api or API()
        klass = type(self)
        self.search_center = search_center or klass.default_search_center
        self.preferred_language = language or klass.default_language
        self.results_limit = results_limit or klass.default_results_limit
        self.backend_results_limit = self.results_limit
        self.discover_backend_limit = self.results_limit
        self.browse_backend_limit = self.results_limit
        self.suggestions_limit = suggestions_limit or klass.default_suggestions_limit
        self.autosuggest_backend_limit = self.suggestions_limit
        self.terms_limit = terms_limit or klass.default_terms_limit
        self.queue = queue or asyncio.Queue()
        self.max_transient_keep = max_transient_keep or self.default_max_transient_keep
        self.more_details_for_suggestion = self.api.lookup_has_more_details
        self.latencies = []
        self.headers = OneBoxSimple.default_headers
        self.x_headers = None
        self._running: bool = False

    def build_event_and_route(
        self, intent: SearchIntent, context: RequestContext
    ) -> tuple[
        SearchEvent,
        Callable[[SearchIntent, Response], None],
        EndpointConfig | LookupConfig | NoConfig | None,
    ]:
        """Resolve an intent into a SearchEvent, handler and config.

        Keeps routing declarative via ROUTES for most kinds; only the
        inherently irregular "details" case is handled specially.
        """

        if intent.kind == "details":
            materialization_type = type(intent.materialization)
            if materialization_type is QuerySuggestionItem:
                event = FollowUpSearchEvent.from_intent(context=context, intent=intent)
                config: EndpointConfig | LookupConfig | NoConfig | None = NoConfig()
                handler = self.handle_result_list
                return event, handler, config
            if materialization_type is LocationSuggestionItem:
                event = DetailsSuggestionEvent.from_intent(context=context, intent=intent)
                config = LookupConfig()
                handler = self.handle_result_details
                return event, handler, config
            event = DetailsSearchEvent.from_intent(context=context, intent=intent)
            config = LookupConfig()
            handler = self.handle_result_details
            return event, handler, config

        try:
            route = ROUTES[intent.kind]
        except KeyError as exc:
            raise KeyError(f"Unsupported intent kind: {intent.kind}") from exc

        event = route.event_type.from_intent(context=context, intent=intent)
        config = route.config_factory(self)
        handler = route.handler_factory(self)
        return event, handler, config

    async def handle_search_event(self, session: HTTPSession) -> tuple[SearchIntent, SearchEvent, Response]:
        """Handle a single search event and return (intent, event, response).

        This helper is used by tests and subclasses; it processes one
        intent using the same routing as handle_search_events.
        """
        intent, event, handler, config = await self.wait_for_search_event()
        # In normal operation wait_for_search_event never returns (None,...)
        # because the sentinel is only used by the long-running loop.
        assert intent is not None and event is not None and handler is not None
        resp = await event.get_response(api=self.api, config=config, session=session)
        self._handle_search_response(intent, handler, resp)
        return intent, event, resp

    async def handle_search_events(self):
        """This method repeatedly waits for search events."""
        async with HTTPSession() as session:
            await self.search_events_preprocess(session)
            try:
                while self._running or not self.queue.empty():  # pragma: no cover
                    try:
                        intent, event, handler, config = await self.wait_for_search_event()
                    except asyncio.CancelledError:
                        break

                    # Sentinel received: exit loop.
                    if intent is None:
                        break

                    t0 = perf_counter_ns()
                    resp = await event.get_response(api=self.api, config=config, session=session)
                    t1 = perf_counter_ns()
                    self._handle_search_response(intent, handler, resp)
                    t2 = perf_counter_ns()

                    self.latencies.append((intent.kind, t0 - intent.time, t1 - t0, t2 - t1, intent.materialization))
                    # Run any post-processing hooks before marking the task as done,
                    # so await app.stop() only completes after UI handlers finish.
                    await self.search_event_postprocess(intent, event, resp, session)
                    self.queue.task_done()
            finally:
                # Drain any remaining items without processing if we are stopping abruptly.
                while not self.queue.empty():
                    try:
                        _ = self.queue.get_nowait()
                        self.queue.task_done()
                    except asyncio.QueueEmpty:
                        break

    def _handle_search_response(
        self, intent: SearchIntent, handler: Callable[[SearchIntent, Response], None], resp: Response
    ) -> None:
        handler(intent, resp)  # pragma: no cover

    async def wait_for_search_event(
        self,
    ) -> tuple[
        SearchIntent,
        SearchEvent,
        Callable[[SearchIntent, Response], None],
        EndpointConfig | LookupConfig | NoConfig | None,
    ]:
        """Wait for the next intent, and resolve it via build_event_and_route."""
        intent: SearchIntent = await self.queue.get()

        if intent.kind == "__stop__":
            # Mark this item as done; caller will handle the sentinel.
            self.queue.task_done()
            return None, None, None, None

        elif intent.kind == "transient_text":
            transients = [intent]
            others: list[SearchIntent] = []
            extra_gets = 0  # how many extra get_nowait() calls we did
            while True:
                try:
                    nxt: SearchIntent = self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                extra_gets += 1
                if nxt.kind == "transient_text":
                    transients.append(nxt)
                else:
                    others.append(nxt)
            keep = transients if not self.max_transient_keep else transients[-self.max_transient_keep :]
            intent = keep[-1]
            for other in others:
                self.queue.put_nowait(other)
            # For every extra item taken out with get_nowait(), mark it done
            # so queue.join() can terminate.
            for _ in range(extra_gets):
                self.queue.task_done()

        context = self._get_context()
        event, handler, config = self.build_event_and_route(intent=intent, context=context)
        return intent, event, handler, config

    def _get_context(self) -> RequestContext:
        return RequestContext(
            latitude=self.search_center[0],
            longitude=self.search_center[1],
            language=self.preferred_language,
            x_headers=self.x_headers,
        )

    @staticmethod
    def _done_handler(task: asyncio.Task) -> None:
        try:
            exc = task.exception()
            if exc:
                print("Task exception:", exc)
                traceback.print_exception(type(exc), exc, exc.__traceback__)
            task.result()
        except asyncio.CancelledError:
            pass

    async def search_events_preprocess(self, session: HTTPSession) -> None:
        pass  # pragma: no cover

    async def search_event_postprocess(
        self, intent: SearchIntent, event: SearchEvent, resp: Response, session: HTTPSession
    ) -> None:
        pass  # pragma: no cover

    def run(self, handle_search_events: Callable = None) -> "OneBoxSimple":
        self._running = True
        coro = (handle_search_events or self.handle_search_events)()
        self.task = asyncio.ensure_future(coro)
        self.task.add_done_callback(OneBoxSimple._done_handler)

    async def stop(self):
        """Wait until queue is empty and background task has finished.

        In Jupyter, `await app.stop()` will keep the cell busy until:
          * all queued intents are processed, and
          * the consumer task has exited.
        """
        self._running = False

        # Wake up handle_search_events if it is blocked on queue.get\(\).
        try:
            from here_search_demo.entity.intent import SearchIntent

            # A minimal sentinel intent; kind value should not match any real route.
            sentinel = SearchIntent(kind="__stop__", materialization=None, time=0)
            self.queue.put_nowait(sentinel)
        except Exception:
            # If constructing or putting a sentinel fails, just rely on timeout / cancellation below.
            pass

        if self.task:
            try:
                await self.task
            except asyncio.CancelledError:
                # Background task was cancelled externally; ignore in stop\(\).
                pass

    def __del__(self):
        return

    def handle_suggestion_list(self, intent: SearchIntent, response: Response) -> None:
        """
        Typically
          - called in OneBoxSimple.handle_search_event()
          - associated with OneBoxSimple.PartialTextSearchEvent via self.intent_routes
        :param intent: Response intent
        :param response: Response instance
        :return: None
        """
        pass

    def handle_result_list(self, intent: SearchIntent, response: Response) -> None:
        """
        Typically
          - called in OneBoxSimple.handle_search_event()
          - associated with OneBoxSimple.TextSearchEvent and OneBoxSimple.PlaceTaxonomySearchEvent via self.intent_routes
        :param intent: Response intent
        :param response: Response instance
        :return: None
        """
        pass

    def handle_result_details(self, intent: SearchIntent, response: Response) -> None:
        """
        Typically
          - called in OneBoxSimple.handle_search_event()
          - associated with OneBoxSimple.DetailsSearchEvent via self.intent_routes
        :param intent: Response intent
        :param response: Response instance
        :return: None
        """
        pass

    def handle_empty_text_submission(self, intent: SearchIntent, response: Response) -> None:
        """
        Typically
          - called in OneBoxSimple.handle_search_event()
          - associated with OneBoxSimple.EmptySearchEvent via self.intent_routes
        :param intent: Response intent
        :param response: Response instance
        :return: None
        """
        pass


class OneBoxBase(OneBoxSimple):
    def __init__(
        self,
        user_profile: UserProfile = None,
        api: API = None,
        results_limit: int = None,
        suggestions_limit: int = None,
        terms_limit: int = None,
        extra_api_params: dict = None,
        initial_query: str = None,
        **kwargs,
    ):
        self.user_profile = user_profile or DefaultUser()
        super().__init__(
            api=api,
            search_center=(
                self.user_profile.current_latitude,
                self.user_profile.current_longitude,
            ),
            language=self.user_profile.preferred_language,
            results_limit=results_limit,
            suggestions_limit=suggestions_limit,
            terms_limit=terms_limit,
            **kwargs,
        )

        self.extra_api_params = extra_api_params or {}
        self.initial_query = initial_query

        self.preferred_language = self.get_preferred_language()

    async def handle_search_event(self, session: HTTPSession) -> Tuple[SearchIntent, SearchEvent, Response]:
        """Process a single search event and adapt language if needed.

        This overrides :meth:`OneBoxSimple.handle_search_event` to add
        language adaptation based on the response. The event is first
        resolved and handled by the base implementation; if the event
        represents a full text or taxonomy search, :meth:`adapt_language`
        is then called to update ``preferred_language`` using the
        response content.

        Parameters
        ----------
        session:
            An :class:`HTTPSession` used to perform the backend request.

        Returns
        -------
        (intent, event, response):
            The intent dequeued from the queue, the corresponding
            :class:`SearchEvent` instance, and the :class:`Response`
            returned by the API.
        """
        intent, event, resp = await super().handle_search_event(session)
        if isinstance(event, TextSearchEvent) or isinstance(event, PlaceTaxonomySearchEvent):
            await self.adapt_language(resp)
        return intent, event, resp

    def get_preferred_language(self, country_code: str = None):
        if country_code:
            return self.user_profile.get_preferred_country_language(country_code)
        else:
            return self.user_profile.get_current_language()

    async def adapt_language(self, resp):
        country_codes = {item["address"]["countryCode"] for item in resp.data["items"]}
        preferred_languages = {self.get_preferred_language(country_code) for country_code in country_codes}
        if len(preferred_languages) == 1 and preferred_languages != {None}:
            language = preferred_languages.pop()
            if language != self.preferred_language:
                self.preferred_language = language

    def set_search_center(self, latlon: tuple[float, float]) -> None:
        self.search_center = latlon
