###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
from typing import Callable, Mapping, Tuple

from here_search.demo import __version__
from here_search.demo.api import API
from here_search.demo.entity.endpoint import (
    AutosuggestConfig,
    BrowseConfig,
    DiscoverConfig,
    EndpointConfig,
    LookupConfig,
    NoConfig,
)
from here_search.demo.entity.intent import (
    FormulatedTextIntent,
    MoreDetailsIntent,
    NoIntent,
    PlaceTaxonomyIntent,
    SearchIntent,
    TransientTextIntent,
)
from here_search.demo.entity.request import RequestContext
from here_search.demo.entity.response import LocationSuggestionItem, QuerySuggestionItem, Response
from here_search.demo.event import (
    DetailsSearchEvent,
    DetailsSuggestionEvent,
    EmptySearchEvent,
    FollowUpSearchEvent,
    PartialTextSearchEvent,
    PlaceTaxonomySearchEvent,
    SearchEvent,
    TextSearchEvent,
)
from here_search.demo.http import HTTPSession
from here_search.demo.user import DefaultUser, UserProfile


class OneBoxSimple:
    default_results_limit = 20
    default_suggestions_limit = 20
    default_terms_limit = 3
    default_search_center = 52.51604, 13.37691
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
        **kwargs,
    ):
        self.task = None
        self.api = api or API()
        klass = type(self)
        self.search_center = search_center or klass.default_search_center
        self.preferred_language = language or klass.default_language
        self.results_limit = results_limit or klass.default_results_limit
        self.suggestions_limit = suggestions_limit or klass.default_suggestions_limit
        self.terms_limit = terms_limit or klass.default_terms_limit
        self.queue = queue or asyncio.Queue()
        self.more_details_for_suggestion = self.api.lookup_has_more_details

        self.event_classes: Mapping[type(SearchIntent), Callable[[SearchIntent], type(SearchEvent)]] = {
            TransientTextIntent: lambda intent: PartialTextSearchEvent,
            FormulatedTextIntent: lambda intent: TextSearchEvent,
            PlaceTaxonomyIntent: lambda intent: PlaceTaxonomySearchEvent,
            MoreDetailsIntent: lambda intent: {
                QuerySuggestionItem: FollowUpSearchEvent,
                LocationSuggestionItem: DetailsSuggestionEvent,
            }.get(type(intent.materialization), DetailsSearchEvent),
            NoIntent: lambda intent: EmptySearchEvent,
        }
        self.response_handlers: Mapping[type, Tuple[Callable[[SearchIntent, Response], None], EndpointConfig]] = {
            PartialTextSearchEvent: (
                self.handle_suggestion_list,
                AutosuggestConfig(limit=self.suggestions_limit, terms_limit=self.terms_limit),
            ),
            TextSearchEvent: (self.handle_result_list, DiscoverConfig(limit=self.results_limit)),
            PlaceTaxonomySearchEvent: (self.handle_result_list, BrowseConfig(limit=self.results_limit)),
            DetailsSearchEvent: (self.handle_result_details, LookupConfig()),
            DetailsSuggestionEvent: (self.handle_result_details, LookupConfig()),
            FollowUpSearchEvent: (self.handle_result_list, NoConfig()),
            EmptySearchEvent: (self.handle_empty_text_submission, None),
        }

        self.headers = OneBoxSimple.default_headers
        self.x_headers = None

    async def handle_search_events(self):
        """
        This method repeatedly waits for search events.
        """
        async with HTTPSession() as session:
            await self.search_events_preprocess(session)
            while True:  # pragma: no cover
                intent, event, resp = await self.handle_search_event(session)  # type: SearchIntent, SearchEvent, Response
                await self.search_event_postprocess(intent, event, resp, session)

    async def handle_search_event(self, session: HTTPSession) -> Tuple[SearchIntent, SearchEvent, Response]:
        intent, event = await self.wait_for_search_event()  # type: SearchIntent, SearchEvent
        handler, config = self.response_handlers[type(event)]
        resp = await event.get_response(api=self.api, config=config, session=session)
        self._handle_search_response(intent, handler, resp)
        return intent, event, resp

    @staticmethod
    def _handle_search_response(
        intent: SearchIntent, handler: Callable[[SearchIntent, Response], None], resp: Response
    ) -> None:
        handler(intent, resp)  # pragma: no cover

    async def wait_for_search_event(self) -> tuple[SearchIntent, SearchEvent]:
        """
        Wait for the next intent in self.queue
        Retrieve associated event from GS7
        Return both intent and search event
        """
        intent: SearchIntent = await self.queue.get()
        context = self._get_context()
        event_class: type(SearchEvent) = self.event_classes[type(intent)](intent)
        event: SearchEvent = event_class.from_intent(context=context, intent=intent)
        return intent, event

    def _get_context(self) -> RequestContext:
        return RequestContext(
            latitude=self.search_center[0],
            longitude=self.search_center[1],
            language=self.preferred_language,
            x_headers=self.x_headers,
        )

    async def search_events_preprocess(self, session: HTTPSession) -> None:
        pass  # pragma: no cover

    async def search_event_postprocess(
        self, intent: SearchIntent, event: SearchEvent, resp: Response, session: HTTPSession
    ) -> None:
        pass  # pragma: no cover

    def run(self, handle_search_events: Callable = None) -> "OneBoxSimple":
        self.task = asyncio.ensure_future((handle_search_events or self.handle_search_events)())

        def _done_handler(task: asyncio.Task) -> None:
            try:
                task.result()
            except asyncio.CancelledError:
                pass

        self.task.add_done_callback(_done_handler)
        return self

    async def stop(self):
        if self.task:
            self.task.cancel()

    def __del__(self):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(self.stop()).add_done_callback(lambda t: t.exception())
            return

        try:
            asyncio.run(self.stop())
        except RuntimeError:
            pass

    def handle_suggestion_list(self, intent: SearchIntent, response: Response) -> None:
        """
        Typically
          - called in OneBoxSimple.handle_search_event()
          - associated with OneBoxSimple.PartialTextSearchEvent in self.response_handlers
        :param intent: Response intent
        :param response: Response instance
        :return: None
        """
        pass

    def handle_result_list(self, intent: SearchIntent, response: Response) -> None:
        """
        Typically
          - called in OneBoxSimple.handle_search_event()
          - associated with OneBoxSimple.TextSearchEvent in self.response_handlers
        :param intent: Response intent
        :param response: Response instance
        :return: None
        """
        pass

    def handle_result_details(self, intent: SearchIntent, response: Response) -> None:
        """
        Typically
          - called in OneBoxSimple.handle_search_event()
          - associated with OneBoxSimple.DetailsSearchEvent in self.response_handlers
        :param intent: Response intent
        :param response: Response instance
        :return: None
        """
        pass

    def handle_empty_text_submission(self, intent: SearchIntent, response: Response) -> None:
        """
        Typically
          - called in OneBoxSimple.handle_search_event()
          - associated with OneBoxSimple.EmptySearchEvent in self.response_handlers
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
        )

        self.extra_api_params = extra_api_params or {}
        self.initial_query = initial_query

        self.preferred_language = self.get_preferred_language()

    async def handle_search_event(self, session: HTTPSession) -> Tuple[SearchIntent, SearchEvent, Response]:
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

    def set_search_center(self, latitude: float, longitude: float):
        self.search_center = latitude, longitude
