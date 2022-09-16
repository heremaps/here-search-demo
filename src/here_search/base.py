from aiohttp import ClientSession

from . import __version__
from .user import Profile, Default
from .api import API
from .entities import Response, Endpoint, ResponseItem, PlaceTaxonomyItem

from typing import Tuple, Awaitable, Callable
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
        self.result_queue = asyncio.Queue()
        self.headers = OneBoxSimple.default_headers
        self.tasks = []

    async def handle_key_strokes(self):
        """
        This method repeatedly waits on key strokes in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:  # pragma: no cover
                await self.handle_key_stroke(session)

    async def handle_key_stroke(self, session: ClientSession):
        query_text = await self.wait_for_text_extension()
        if query_text:
            latitude, longitude = self.search_center
            resp = await asyncio.ensure_future(
                self.api.autosuggest(
                    query_text,
                    latitude,
                    longitude,
                    x_headers=None,
                    session=session,
                    lang=self.language,
                    limit=self.suggestions_limit,
                    termsLimit=self.terms_limit
                )
            )
            self.handle_suggestion_list(resp)
        else:
            self.handle_empty_text_submission()

    async def handle_text_submissions(self):
        """
        This method repeatedly waits for texts submitted in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:  # pragma: no cover
                await self.handle_text_submission(session)

    async def handle_text_submission(self, session):
        query_text = await self.wait_for_text_submission()
        if query_text:
            resp = await self._do_discover(session, query_text)
            self.handle_result_list(resp)

    async def handle_taxonomy_selections(self):
        """
        This method is called for each shortcut button selected.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:  # pragma: no cover
                await self.handle_taxonomy_selection(session)

    async def handle_taxonomy_selection(self, session):
        taxonomy_item: PlaceTaxonomyItem = await self.wait_for_taxonomy_selection()
        if taxonomy_item:
            resp = await self._do_browse(session, taxonomy_item)
            self.handle_result_list(resp)

    async def _do_discover(self, session, query_text, x_headers: dict = None, **kwargs) -> Response:
        latitude, longitude = self.search_center
        return await asyncio.ensure_future(
            self.api.discover(
                query_text,
                latitude,
                longitude,
                x_headers=x_headers,
                session=session,
                lang=self.language,
                limit=self.results_limit,
                **kwargs,
            )
        )

    async def _do_browse(self, session, taxonomy_item, x_headers: dict = None, **kwargs) -> Response:
        latitude, longitude = self.search_center
        return await asyncio.ensure_future(
            self.api.browse(
                latitude,
                longitude,
                x_headers=x_headers,
                session=session,
                lang=self.language,
                limit=self.results_limit,
                **taxonomy_item.mapping,
                **kwargs,
            )
        )

    def wait_for_text_extension(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_text_submission(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_taxonomy_selection(self) -> Awaitable:
        raise NotImplementedError()

    def handle_suggestion_list(self, response: Response) -> None:
        raise NotImplementedError()

    def handle_result_list(self, response: Response) -> None:
        raise NotImplementedError()

    def handle_empty_text_submission(self, **kwargs) -> None:
        raise NotImplementedError()

    def run(
        self,
        handle_key_strokes: Callable = None,
        handle_text_submissions: Callable = None,
        handle_taxonomy_selections: Callable = None,
    ) -> "OneBoxSimple":
        self.tasks.extend(
            [
                asyncio.ensure_future(self.handle_key_strokes()),
                asyncio.ensure_future(self.handle_text_submissions()),
                asyncio.ensure_future(self.handle_taxonomy_selections()),
            ]
        )
        return self

    async def stop(self):
        for task in self.tasks:
            task.cancel()

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
            search_center=(self.user_profile.current_latitude, self.user_profile.current_longitude),
            language=self.user_profile.language,
            results_limit=results_limit,
            suggestions_limit=suggestions_limit,
            terms_limit=terms_limit,
        )

        self.extra_api_params = extra_api_params or {}
        self.initial_query = initial_query

    async def handle_text_submission(self, session):
        query_text = await self.wait_for_text_submission()
        if query_text.strip() == "":
            self.handle_empty_text_submission()
        else:
            resp = await self._do_discover(session, query_text)
            await self.adapt_language(resp)
            self.handle_result_list(resp)

    async def adapt_language(self, resp):
        country_codes = {item["address"]["countryCode"] for item in resp.data["items"]}
        preferred_languages = {
            self.user_profile.get_preferred_language(country_code) for country_code in country_codes
        }
        if len(preferred_languages) == 1 and preferred_languages != {None}:
            language = preferred_languages.pop()
            if language != self.language:
                self.language = language

    async def handle_result_selections(self):
        """
        This method repeatedly waits for any result item to be selected.
        If the selected result type is categoryQuery or chainQuery, a follow-up category/chain expansion query is sent.
        If it is another type, a lookup call is sent.
        """
        async with ClientSession(raise_for_status=True, headers=self.headers) as session:
            while True:  # pragma: no cover
                await self.handle_result_selection(session)

    async def handle_result_selection(self, session):
        item: ResponseItem = await self.wait_for_selected_result()
        if item.data["resultType"] in ("categoryQuery", "chainQuery"):
            resp = await self._do_autosuggest_expansion(session, item)
            self.handle_result_list(resp)
        else:
            resp = await self._do_lookup(session, item)
            self.handle_result_details(resp)

    async def _do_autosuggest_expansion(self, session, item, x_headers: dict = None) -> Response:
        # patch against OSQ-32323
        orig_show = item.resp.req.params.get("show")
        params = {"show": orig_show} if orig_show else {}
        return await asyncio.ensure_future(
            self.api.autosuggest_href(
                item.data["href"], x_headers=x_headers, limit=self.results_limit, session=session, **params
            )
        )

    async def _do_lookup(self, session, item, x_headers: dict = None, **kwargs) -> Response:
        """
        Perfooms a location id lookup
        :param session:
        :param item:
        :param x_headers:
        :return:
        """
        if item.resp.req.endpoint == Endpoint.AUTOSUGGEST:
            return await asyncio.ensure_future(
                self.api.lookup(item.data["id"],
                                x_headers=x_headers,
                                lang=self.language,
                                session=session,
                                **kwargs)
            )
        else:
            return await asyncio.ensure_future(
                self.api.lookup(
                    item.data["id"],
                    x_headers=None,
                    lang=self.language,
                    session=session,
                    **kwargs
                )
            )

    async def _do_revgeocode(self, session, latitude, longitude, x_headers: dict = None, **kwargs) -> Response:
        extra_params = kwargs or {}
        if self.language:
            extra_params["lang"] = self.language
        return await asyncio.ensure_future(
            self.api.reverse_geocode(
                latitude, longitude,
                x_headers=x_headers,
                session=session,
                limit=self.results_limit,
                **kwargs
            )
        )

    def set_search_center(self, latitude: float, longitude: float):
        self.search_center = latitude, longitude

    def wait_for_selected_result(self) -> Awaitable:
        return self.result_queue.get()

    def handle_result_details(self, response: Response) -> None:
        raise NotImplementedError()

    def run(
        self,
        handle_key_strokes: Callable = None,
        handle_text_submissions: Callable = None,
        handle_taxonomy_selections: Callable = None,
        handle_result_selections: Callable = None,
    ):
        super().run(handle_key_strokes, handle_text_submissions, handle_taxonomy_selections)
        self.tasks.append(asyncio.ensure_future((handle_result_selections or self.handle_result_selections)()))
        return self
