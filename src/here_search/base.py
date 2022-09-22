from aiohttp import ClientSession

from . import __version__
from .user import Profile, Default
from .api import (
    API,
    PartialTextSearchEvent,
    SearchEvent,
    TextSearchEvent,
    TaxonomySearchEvent,
    FollowUpSearchEvent,
    DetailsSearchEvent,
    EmptySearchEvent,
    UnsupportedSearchEvent,
)
from .entities import (
    Response,
    ResponseItem,
    PlaceTaxonomyItem,
    SearchContext,
    SearchIntent,
    FormulatedIntent,
    NoIntent,
    UnsupportedIntentMaterialization,
    AutosuggestConfig,
    DiscoverConfig,
    BrowseConfig,
    LookupConfig,
)

from typing import Tuple, Callable
import asyncio


class OneBoxSimple:
    default_results_limit = 20
    default_suggestions_limit = 5
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
        self.task = None

    async def handle_search_events(self):
        """
        This method repeatedly waits for search events.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:  # pragma: no cover
                await self.handle_search_event(session)

    async def handle_search_event(self, session: ClientSession) -> None:
        event: SearchEvent = await self.wait_for_search_event()
        if isinstance(event, PartialTextSearchEvent):
            config = AutosuggestConfig(
                limit=self.suggestions_limit, terms_limit=self.terms_limit
            )
        elif isinstance(event, TextSearchEvent):
            config = DiscoverConfig(limit=self.results_limit)
        elif isinstance(event, TaxonomySearchEvent):
            config = BrowseConfig(limit=self.results_limit)
        elif isinstance(event, DetailsSearchEvent):
            config = LookupConfig()
        elif isinstance(event, EmptySearchEvent):
            config = None
        else:
            raise UnsupportedSearchEvent(type(event).__name__)
        resp = await event.get_response(api=self.api, config=config, session=session)
        await self.handle_search_response(event, resp, session)

    async def handle_search_response(
        self, event: SearchEvent, resp: Response, session: ClientSession
    ) -> None:
        if isinstance(event, PartialTextSearchEvent):
            self.handle_suggestion_list(resp, session)
        elif isinstance(event, TextSearchEvent):
            self.handle_result_list(resp, session)
        elif isinstance(event, TaxonomySearchEvent):
            self.handle_result_list(resp, session)
        elif isinstance(event, DetailsSearchEvent):
            self.handle_result_details(resp, session)
        elif isinstance(event, FollowUpSearchEvent):
            self.handle_result_list(resp, session)
        elif isinstance(event, EmptySearchEvent):
            self.handle_empty_text_submission(session)
        else:
            raise UnsupportedSearchEvent(type(event).__name__)

    async def wait_for_search_event(self) -> SearchEvent:
        context = SearchContext(
            latitude=self.search_center[0],
            longitude=self.search_center[1],
            language=self.language,
        )
        intent: SearchIntent = await self.queue.get()
        if isinstance(intent.materialization, str):
            if isinstance(intent, FormulatedIntent):
                return TextSearchEvent(
                    context=context, query_text=intent.materialization
                )
            else:
                return PartialTextSearchEvent(
                    context=context, query_text=intent.materialization
                )
        elif isinstance(intent.materialization, PlaceTaxonomyItem):
            return TaxonomySearchEvent(context=context, item=intent.materialization)
        elif isinstance(intent.materialization, ResponseItem):
            if intent.materialization.data["resultType"] in (
                "categoryQuery",
                "chainQuery",
            ):
                return FollowUpSearchEvent(context=context, item=intent.materialization)
            else:
                return DetailsSearchEvent(context=context, item=intent.materialization)
        elif isinstance(intent, NoIntent):
            return EmptySearchEvent()
        else:
            raise UnsupportedIntentMaterialization()

    def handle_suggestion_list(
        self, response: Response, session: ClientSession
    ) -> None:
        raise NotImplementedError()

    def handle_result_list(self, response: Response, session: ClientSession) -> None:
        raise NotImplementedError()

    def handle_empty_text_submission(self, session: ClientSession) -> None:
        raise NotImplementedError()

    def handle_result_details(self, response: Response, session: ClientSession) -> None:
        raise NotImplementedError()

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
        asyncio.run(self.stop())


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

    async def handle_search_response(
        self, event: SearchEvent, resp: Response, session: ClientSession
    ) -> None:
        await super().handle_search_response(event, resp, session)
        if isinstance(event, TextSearchEvent) or isinstance(event, TaxonomySearchEvent):
            await self.adapt_language(resp)

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
