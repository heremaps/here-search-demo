from aiohttp import ClientSession

from . import __version__
from .user import Profile, Default
from .api import API
from .entity.intent import (
    SearchIntent,
    FormulatedTextIntent,
    TransientTextIntent,
    PlaceTaxonomyIntent,
    MoreDetailsIntent,
    NoIntent,
)
from .entity.event import (
    PartialTextSearchEvent,
    SearchEvent,
    TextSearchEvent,
    PlaceTaxonomySearchEvent,
    FollowUpSearchEvent,
    DetailsSearchEvent,
    EmptySearchEvent,
)
from .entity.request import Response, RequestContext
from .entity.endpoint import EndpointConfig, AutosuggestConfig, DiscoverConfig, BrowseConfig, LookupConfig, NoConfig

from typing import Tuple, Callable, Mapping
import asyncio


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

        self.api = api or API()
        klass = type(self)
        self.search_center = search_center or klass.default_search_center
        self.language = language or klass.default_language
        self.results_limit = results_limit or klass.default_results_limit
        self.suggestions_limit = suggestions_limit or klass.default_suggestions_limit
        self.terms_limit = terms_limit or klass.default_terms_limit
        self.queue = queue or asyncio.Queue()
        self.headers = OneBoxSimple.default_headers
        self.event_classes: Mapping[type(SearchIntent), Callable[[SearchIntent], type(SearchEvent)]] = {
            TransientTextIntent: lambda intent: PartialTextSearchEvent,
            FormulatedTextIntent: lambda intent: TextSearchEvent,
            PlaceTaxonomyIntent: lambda intent: PlaceTaxonomySearchEvent,
            MoreDetailsIntent: lambda intent: (FollowUpSearchEvent
                                               if intent.materialization.data["resultType"] in ("categoryQuery",
                                                                                                "chainQuery")
                                               else DetailsSearchEvent),
            NoIntent: lambda intent: EmptySearchEvent
        }
        self.response_handlers: Mapping[
            type(SearchEvent), Tuple[Callable[[Response], None], EndpointConfig]] = {
            PartialTextSearchEvent: (self.handle_suggestion_list, AutosuggestConfig(
                limit=self.suggestions_limit, terms_limit=self.terms_limit
            )),
            TextSearchEvent: (self.handle_result_list, DiscoverConfig(limit=self.results_limit)),
            PlaceTaxonomySearchEvent: (self.handle_result_list, BrowseConfig(limit=self.results_limit)),
            DetailsSearchEvent: (self.handle_result_details, LookupConfig()),
            FollowUpSearchEvent: (self.handle_result_list, NoConfig()),
            EmptySearchEvent: (self.handle_empty_text_submission, None)
        }

        self.task = None

    async def handle_search_events(self):
        """
        This method repeatedly waits for search events.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:  # pragma: no cover
                event, resp = await self.handle_search_event(session)

    async def handle_search_event(self, session: ClientSession) -> Tuple[SearchEvent, Response]:
        event: SearchEvent = await self.wait_for_search_event()
        handler, config = self.response_handlers[type(event)]
        resp = await event.get_response(api=self.api, config=config, session=session)
        self._handle_search_response(handler, resp)
        return event, resp

    @staticmethod
    def _handle_search_response(handler: Callable[[Response], None], resp: Response) -> None:
        handler(resp)

    async def wait_for_search_event(self) -> SearchEvent:
        context = RequestContext(
            latitude=self.search_center[0],
            longitude=self.search_center[1],
            language=self.language,
        )
        intent: SearchIntent = await self.queue.get()
        event_class: SearchEvent = self.event_classes[type(intent)](intent)
        return event_class.from_intent(context=context, intent=intent)

    def run(self, handle_search_events: Callable = None) -> "OneBoxSimple":
        self.task = asyncio.ensure_future(
            (handle_search_events or self.handle_search_events)()
        )

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
            loop.create_task(self.stop()).add_done_callback(lambda t: t.result())
        else:
            asyncio.run(self.stop())

    def handle_suggestion_list(self, response: Response) -> None:
        pass

    def handle_result_list(self, response: Response) -> None:
        pass

    def handle_result_details(self, response: Response) -> None:
        pass

    def handle_empty_text_submission(self, *args, **kwargs) -> None:
        pass


class OneBoxBase(OneBoxSimple):
    def __init__(
            self,
            user_profile: Profile = None,
            api: API = None,
            results_limit: int = None,
            suggestions_limit: int = None,
            terms_limit: int = None,
            extra_api_params: dict = None,
            initial_query: str = None,
            **kwargs,
    ):

        self.user_profile = user_profile or Default()
        super().__init__(
            api=api,
            search_center=(
                self.user_profile.current_latitude,
                self.user_profile.current_longitude,
            ),
            language=self.user_profile.language,
            results_limit=results_limit,
            suggestions_limit=suggestions_limit,
            terms_limit=terms_limit,
        )

        self.extra_api_params = extra_api_params or {}
        self.initial_query = initial_query

    async def handle_search_event(self, session: ClientSession) -> Tuple[SearchEvent, Response]:
        event, resp = await super().handle_search_event(session)
        if isinstance(event, TextSearchEvent) or isinstance(event, PlaceTaxonomySearchEvent):
            await self.adapt_language(resp)
        return event, resp

    async def adapt_language(self, resp):
        country_codes = {item["address"]["countryCode"] for item in resp.data["items"]}
        preferred_languages = {
            self.user_profile.get_preferred_language(country_code)
            for country_code in country_codes
        }
        if len(preferred_languages) == 1 and preferred_languages != {None}:
            language = preferred_languages.pop()
            if language != self.language:
                self.language = language

    def set_search_center(self, latitude: float, longitude: float):
        self.search_center = latitude, longitude
