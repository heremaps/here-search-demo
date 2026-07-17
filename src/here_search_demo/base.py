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
from dataclasses import dataclass, replace
from typing import Callable, Mapping, Protocol, Tuple, runtime_checkable

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
from here_search_demo.entity.intent import ActionIntent, SearchIntent
from here_search_demo.entity.request import RequestContext
from here_search_demo.entity.response import LocationSuggestionItem, QuerySuggestionItem, Response
from here_search_demo.event import (
    ActionSearchEvent,
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
class Triage:
    event_type: type[SearchEvent]
    config_factory: Callable[["OneBoxCore"], EndpointConfig | LookupConfig | NoConfig | None]
    handler_factory: Callable[["OneBoxCore"], Callable[[SearchIntent, Response], None]]


TRIAGES: Mapping[str, Triage] = {
    "transient_text": Triage(
        event_type=PartialTextSearchEvent,
        config_factory=lambda ob: AutosuggestConfig(limit=ob.autosuggest_backend_limit, terms_limit=ob.terms_limit),
        handler_factory=lambda ob: ob.handle_suggestion_list,
    ),
    "submitted_text": Triage(
        event_type=TextSearchEvent,
        config_factory=lambda ob: DiscoverConfig(limit=ob.discover_backend_limit),
        handler_factory=lambda ob: ob.handle_result_list,
    ),
    "taxonomy": Triage(
        event_type=PlaceTaxonomySearchEvent,
        config_factory=lambda ob: BrowseConfig(limit=ob.browse_backend_limit),
        handler_factory=lambda ob: ob.handle_result_list,
    ),
    "action": Triage(
        event_type=ActionSearchEvent,
        config_factory=lambda ob: NoConfig(),
        handler_factory=lambda ob: ob.handle_action,
    ),
    "empty": Triage(
        event_type=EmptySearchEvent,
        config_factory=lambda ob: None,
        handler_factory=lambda ob: ob.handle_empty_text_submission,
    ),
}


class OneBoxCore:
    """Core async controller for one-box search workflows.

    ``OneBoxCore`` consumes :class:`~here_search_demo.entity.intent.SearchIntent`
    objects from ``queue``, maps them to typed search events, executes API calls,
    and dispatches responses to dedicated handlers.

    Subclasses typically override presentation hooks such as
    :meth:`handle_suggestion_list`, :meth:`handle_result_list`, and
    :meth:`handle_result_details` while reusing the routing/transport pipeline.

    :param api: API adapter. Defaults to :class:`here_search_demo.api.API`.
    :param queue: Intent queue consumed by ``run()``.
    :param search_center: Default ``(lat, lon)`` context used by requests.
    :param language: Preferred language code for requests.
    :param results_limit: Number of results to expose to UI handlers.
    :param suggestions_limit: Number of autosuggest items to expose.
    :param terms_limit: Number of term suggestions to expose.
    :param max_transient_keep: Maximum queued transient-text intents retained.
    """

    default_results_limit = 20
    default_suggestions_limit = 20
    default_terms_limit = 3
    default_search_center = 52.51604, 13.37691
    default_max_transient_keep = 1
    default_language = "en"
    default_headers = {"User-Agent": f"here-search-demo-{__version__}"}

    def __init__(
        self,
        api: API | None = None,
        queue: asyncio.Queue | None = None,
        search_center: Tuple[float, float] | None = None,
        language: str | None = None,
        results_limit: int | None = None,
        suggestions_limit: int | None = None,
        terms_limit: int | None = None,
        max_transient_keep: int | None = None,
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
        self.headers = OneBoxCore.default_headers
        self.x_headers = None
        self._running: bool = False
        self._postprocess_callbacks: list[Callable] = []

    def triage_intent(
        self, intent: SearchIntent, context: RequestContext
    ) -> tuple[
        SearchEvent,
        Callable[[SearchIntent, Response], None],
        EndpointConfig | LookupConfig | NoConfig | None,
    ]:
        """Resolve an intent into a SearchEvent, handler and config.

        Keeps routing declarative via TRIAGES for most kinds; only the
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
            triage = TRIAGES[intent.kind]
        except KeyError as exc:
            raise KeyError(f"Unsupported intent kind: {intent.kind}") from exc

        event = triage.event_type.from_intent(context=context, intent=intent)
        config = triage.config_factory(self)
        handler = triage.handler_factory(self)
        return event, handler, config

    async def handle_search_event(self, session: HTTPSession) -> tuple[SearchIntent, SearchEvent, Response]:
        """Handle a single search event and return (intent, event, response).

        This helper is used by tests and subclasses; it processes one
        intent using the same routing as handle_search_events.
        """
        intent, event, handler, config = await self.wait_for_search_event()
        # In normal operation wait_for_search_event never returns (None,...)
        # because the sentinel is only used by the long-running loop.
        if intent is None or event is None or handler is None:
            raise RuntimeError("wait_for_search_event returned sentinel values in handle_search_event")
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

                    is_transient = intent.kind == "transient_text"

                    try:
                        resp = await event.get_response(api=self.api, config=config, session=session)
                    except asyncio.CancelledError:
                        raise

                    if is_transient and self._has_pending_newer_transient(intent):
                        self.queue.task_done()
                        continue

                    self._handle_search_response(intent, handler, resp)

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

    def _has_pending_newer_transient(self, intent: SearchIntent) -> bool:
        pending = getattr(self.queue, "_queue", None)
        if pending is None:
            return False
        for queued_intent in pending:
            if getattr(queued_intent, "kind", None) != "transient_text":
                continue
            if getattr(queued_intent, "time", 0) > intent.time:
                return True
        return False

    async def wait_for_search_event(
        self,
    ) -> tuple[
        SearchIntent,
        SearchEvent,
        Callable[[SearchIntent, Response], None],
        EndpointConfig | LookupConfig | NoConfig | None,
    ]:
        """Wait for the next intent, and resolve it via triage_intent."""
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
        event, handler, config = self.triage_intent(intent=intent, context=context)
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
        """Run all registered postprocess callbacks in registration order."""
        for cb in list(self._postprocess_callbacks):
            await cb(intent, event, resp, session)

    def add_postprocess(
        self,
        callback: Callable,
    ) -> None:
        """Register an async *callback(intent, event, resp, session)* to be called
        after every processed search event.

        Multiple callbacks are called in registration order.  Use
        ``remove_postprocess`` to deregister.

        Example::

            results_ready = asyncio.Event()

            async def wait_for_results(intent, event, resp, session):
                if intent.kind in ("submitted_text", "taxonomy"):
                    results_ready.set()

            app.add_postprocess(wait_for_results)
            app.buttons_box_w.buttons[0].click()
            await results_ready.wait()
            app.remove_postprocess(wait_for_results)
        """
        self._postprocess_callbacks.append(callback)

    def remove_postprocess(self, callback: Callable) -> None:
        """Remove a previously registered postprocess *callback* (no-op if absent)."""
        try:
            self._postprocess_callbacks.remove(callback)
        except ValueError:
            pass

    def run(self, handle_search_events: Callable | None = None) -> "OneBoxCore":
        """Start the background consumer task and return ``self``.

        :param handle_search_events: Optional coroutine factory replacing the
            default event loop handler.
        :return: Running app instance.
        :rtype: OneBoxCore
        """
        self._running = True
        coro = (handle_search_events or self.handle_search_events)()
        self.task = asyncio.ensure_future(coro)
        self.task.add_done_callback(OneBoxCore._done_handler)
        return self

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
          - called in OneBoxCore.handle_search_event()
          - associated with OneBoxCore.PartialTextSearchEvent via self.intent_routes

        :param intent: Response intent
        :param response: Response instance
        :return: None
        """
        pass

    def handle_result_list(self, intent: SearchIntent, response: Response) -> None:
        """
        Typically
          - called in OneBoxCore.handle_search_event()
          - associated with OneBoxCore.TextSearchEvent and OneBoxCore.PlaceTaxonomySearchEvent via self.intent_routes

        :param intent: Response intent
        :param response: Response instance
        :return: None
        """
        pass

    def handle_result_details(self, intent: SearchIntent, response: Response) -> None:
        """
        Typically
          - called in OneBoxCore.handle_search_event()
          - associated with OneBoxCore.DetailsSearchEvent via self.intent_routes

        :param intent: Response intent
        :param response: Response instance
        :return: None
        """
        pass

    def handle_empty_text_submission(self, intent: SearchIntent, response: Response) -> None:
        """
        Typically
          - called in OneBoxCore.handle_search_event()
          - associated with OneBoxCore.EmptySearchEvent via self.intent_routes

        :param intent: Response intent
        :param response: Response instance
        :return: None
        """
        pass

    def handle_action(self, intent: ActionIntent, response: Response) -> None:
        """
        Called after an ActionSearchEvent has sent its signal for a
        LocationResponseItem click.  No lookup was performed; ``response``
        will be ``None``.
        """
        pass


@runtime_checkable
class SearchHead(Protocol):
    """Protocol documenting the response-rendering contract for a search head.

    Any class that overrides these methods can act as a rendering head on top of
    :class:`OneBoxCore`.  ``OneBoxCore`` itself satisfies this protocol via its
    built-in no-op stubs, so structural subtyping requires no explicit registration.

    Override these methods to send results to a different medium (map widgets,
    terminal, REST API response, …).
    """

    def handle_suggestion_list(self, intent: SearchIntent, response: Response) -> None: ...
    def handle_result_list(self, intent: SearchIntent, response: Response) -> None: ...
    def handle_result_details(self, intent: SearchIntent, response: Response) -> None: ...
    def handle_empty_text_submission(self, intent: SearchIntent, response: Response) -> None: ...
    def handle_action(self, intent: ActionIntent, response: Response) -> None: ...
    async def search_events_preprocess(self, session: HTTPSession) -> None: ...


class UserProfileMixin:
    """Composable mixin that binds a :class:`~here_search_demo.user.UserProfile` to any
    :class:`OneBoxCore` subclass.

    Adds personalization (language adaptation, user identity in context) as a side
    concern, independent of any rendering head.  Use cooperative multiple inheritance::

        class MyApp(UserProfileMixin, OneBoxCore):
            ...

    MRO: ``MyApp → UserProfileMixin → OneBoxCore``

    :param user_profile: Optional profile; defaults to :class:`~here_search_demo.user.DefaultUser`.
    :param kwargs: Forwarded to :class:`OneBoxCore`.
    """

    def __init__(
        self,
        user_profile: UserProfile | None = None,
        **kwargs,
    ):
        self.user_profile = user_profile or DefaultUser()
        super().__init__(
            search_center=(
                self.user_profile.current_latitude,
                self.user_profile.current_longitude,
            ),
            language=self.user_profile.preferred_language,
            **kwargs,
        )
        self.preferred_language = self.get_preferred_language()

    async def handle_search_event(self, session: HTTPSession) -> Tuple[SearchIntent, SearchEvent, Response]:
        """Process a single search event and adapt language if needed.

        Overrides :meth:`OneBoxCore.handle_search_event` to call :meth:`adapt_language`
        after full-text or taxonomy searches.
        """
        intent, event, resp = await super().handle_search_event(session)
        if isinstance(event, TextSearchEvent) or isinstance(event, PlaceTaxonomySearchEvent):
            await self.adapt_language(resp)
        return intent, event, resp

    def get_preferred_language(self, country_code: str | None = None) -> str | None:
        if country_code:
            return self.user_profile.get_preferred_country_language(country_code)
        else:
            return self.user_profile.get_current_language()

    @staticmethod
    def _extract_country_code(resp) -> str | None:
        """Return the single country code present across all response items, or None.

        Returns None when items have no countryCode, when countryCode values are
        mixed across items, or when the items list is empty.
        """
        codes = {item.get("address", {}).get("countryCode") for item in resp.data.get("items", [])} - {None}
        return codes.pop() if len(codes) == 1 else None

    async def adapt_language(self, resp) -> None:
        country_code = self._extract_country_code(resp)
        if country_code is None:
            return
        language = self.get_preferred_language(country_code)
        if language and language != self.preferred_language:
            self.preferred_language = language

    def set_search_center(self, latlon: tuple[float, float]) -> None:
        self.search_center = latlon

    def _get_context(self) -> RequestContext:
        ctx = super()._get_context()
        return replace(
            ctx,
            share_experience=self.user_profile.share_experience,
            user_id=self.user_profile.id if self.user_profile.share_experience else None,
        )
