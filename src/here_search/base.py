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
    default_headers = {'User-Agent': f'here-search-notebook-{__version__}'}

    def __init__(self,
                 api: API=None,
                 search_center: Tuple[float, float]=None,
                 language: str=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 **kwargs):

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
            while True:
                query_text = await self.wait_for_text_extension()
                if query_text:
                    await self._do_autosuggest(session, query_text)
                else:
                    self.handle_empty_text_submission()

    async def handle_text_submissions(self):
        """
        This method repeatedly waits for texts submitted in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:
                query_text = await self.wait_for_text_submission()
                if query_text:
                    await self._do_discover(session, query_text)

    async def handle_taxonomy_selections(self):
        """
        This method is called for each shortcut button selected.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:
                taxonomy_item: PlaceTaxonomyItem = await self.wait_for_taxonomy_selection()
                if taxonomy_item:
                    await self._do_browse(session, taxonomy_item)

    async def _do_autosuggest(self, session, query_text, x_headers: dict=None, **kwargs) -> None:
        latitude, longitude = self.search_center
        autosuggest_resp = await asyncio.ensure_future(
            self.api.autosuggest(query_text, latitude, longitude, x_headers=x_headers, session=session,
                                 lang=self.language, limit=self.suggestions_limit, termsLimit=self.terms_limit, **kwargs))
        self.handle_suggestion_list(autosuggest_resp)

    async def _do_discover(self, session, query_text, x_headers: dict=None, **kwargs) -> set:
        latitude, longitude = self.search_center
        discover_task = asyncio.ensure_future(
            self.api.discover(query_text, latitude, longitude, x_headers=x_headers, session=session, lang=self.language,
                              limit=self.results_limit, **kwargs))
        discover_resp = await discover_task
        self.handle_result_list(discover_resp)
        return {item["address"]["countryCode"] for item in discover_resp.data["items"]}

    async def _do_browse(self, session, taxonomy_item, x_headers: dict=None, **kwargs) -> set:
        latitude, longitude = self.search_center
        browse_task = asyncio.ensure_future(
            self.api.browse(latitude, longitude,
                            x_headers=x_headers,
                            session=session,
                            lang=self.language,
                            limit=self.results_limit,
                            **taxonomy_item.mapping,
                            **kwargs))
        browse_resp = await browse_task
        self.handle_result_list(browse_resp)
        return {item["address"]["countryCode"] for item in browse_resp.data["items"]}

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

    def run(self,
            handle_key_strokes: Callable=None,
            handle_text_submissions: Callable=None,
            handle_taxonomy_selections: Callable=None) -> "OneBoxSimple":
        self.tasks.extend([asyncio.ensure_future(self.handle_key_strokes()),
                           asyncio.ensure_future(self.handle_text_submissions()),
                           asyncio.ensure_future(self.handle_taxonomy_selections())])
        return self

    async def stop(self):
        for task in self.tasks:
            task.cancel()

    def __del__(self):
        loop = asyncio.get_running_loop()
        loop.run_until_complete(self.stop())


class OneBoxBase(OneBoxSimple):

    def __init__(self,
                 user_profile: Profile=None,
                 api: API=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 extra_api_params: dict=None,
                 initial_query: str=None,
                 **kwargs):

        self.user_profile = user_profile or Default()
        super().__init__(api=api,
                         search_center=(self.user_profile.current_latitude, self.user_profile.current_longitude),
                         language = self.user_profile.language,
                         results_limit=results_limit,
                         suggestions_limit=suggestions_limit,
                         terms_limit=terms_limit)

        self.extra_api_params = extra_api_params or {}
        self.initial_query = initial_query

    async def handle_text_submissions(self):
        """
        This method repeatedly waits for texts submitted in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=self.headers) as session:
            if self.initial_query:
                await self._do_discover(self.initial_query, session)
            while True:
                query_text = await self.wait_for_text_submission()
                if query_text.strip() == '':
                    self.handle_empty_text_submission()
                    continue

                country_codes = await self._do_discover(session, query_text)
                preferred_languages = {self.user_profile.get_preferred_language(country_code) for country_code in country_codes}
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
            while True:
                item: ResponseItem = await self.wait_for_selected_result()
                if item is None:  break
                if not item: continue

                if item.data["resultType"] in ("categoryQuery", "chainQuery"):
                    await self._do_autosuggest_expansion(session, item)
                else:
                    await self._do_lookup(session, item)

    async def _do_discover(self, session, query_text, x_headers: dict=None, **kwargs) -> set:
        return await super()._do_discover(session, query_text, x_headers, **self.get_extra_params(Endpoint.DISCOVER))

    async def _do_autosuggest(self, session, query_text, x_headers: dict=None, **kwargs):
        return await super()._do_autosuggest(session, query_text, x_headers, **self.get_extra_params(Endpoint.AUTOSUGGEST))

    async def _do_browse(self, session, taxonomy_item, x_headers: dict=None, **kwargs) -> set:
        return await super()._do_browse(session, taxonomy_item, x_headers, **self.get_extra_params(Endpoint.DISCOVER))

    async def _do_autosuggest_expansion(self, session, item, x_headers: dict=None):
        # patch against OSQ-32323
        orig_show = item.resp.req.params.get("show")
        params = {"show": orig_show} if orig_show else {}
        discover_resp = await asyncio.ensure_future(
            self.api.autosuggest_href(item.data["href"],
                                      x_headers=x_headers,
                                      limit=self.results_limit,
                                      session=session,
                                      **params))
        self.handle_result_list(discover_resp)

    async def _do_lookup(self, session, item, x_headers: dict=None):
        """
        Perfooms a location id lookup
        :param session:
        :param item:
        :param x_headers:
        :return:
        """
        if item.resp.req.endpoint == Endpoint.AUTOSUGGEST:
            lookup_resp = await asyncio.ensure_future(
                self.api.lookup(item.data["id"],
                                x_headers=x_headers,
                                lang=self.language,
                                session=session))
        else:
            lookup_resp = await asyncio.ensure_future(
                self.api.lookup(item.data["id"],
                                x_headers=None,
                                session=session,
                                lang=self.language,
                                **self.get_extra_params(Endpoint.LOOKUP)))
        self.handle_result_details(lookup_resp)

    async def _do_revgeocode(self, session, latitude, longitude, x_headers: dict=None) -> Response:
        extra_params = self.get_extra_params(Endpoint.REVGEOCODE)
        if self.language:
            extra_params["lang"] = self.language
        revgeocode_resp = await asyncio.ensure_future(
            self.api.reverse_geocode(latitude, longitude,
                                     x_headers=x_headers,
                                     session=session,
                                     limit=self.results_limit,
                                     **extra_params))
        return revgeocode_resp

    def get_extra_params(self, endpoint) -> dict:
        extra_params = self.api.options.get(endpoint, {})
        extra_params.update(self.extra_api_params.get(endpoint, {}))
        extra_params.update(self.user_profile.api_options.get(endpoint, {}))
        return extra_params

    def set_search_center(self, latitude: float, longitude: float):
        self.search_center = latitude, longitude

    def wait_for_selected_result(self) -> Awaitable:
        return self.result_queue.get()

    def handle_result_details(self, response: Response) -> None:
        raise NotImplementedError()

    def run(self,
            handle_key_strokes: Callable=None,
            handle_text_submissions: Callable=None,
            handle_taxonomy_selections: Callable=None,
            handle_result_selections: Callable=None):
        super().run(handle_key_strokes, handle_text_submissions, handle_taxonomy_selections)
        self.tasks.append(asyncio.ensure_future((handle_result_selections or self.handle_result_selections)()))
        return self
