from aiohttp import ClientSession

from . import __version__
from .user import Profile, Default
from .api import API
from .entities import Response, Endpoint, ResponseItem, Ontology
from .util import Profiler

from typing import Tuple, Awaitable, Callable
import asyncio
import uuid


class OneBoxSimple:
    default_results_limit = 20
    default_suggestions_limit = 5
    default_terms_limit = 3
    default_search_center = 52.51604, 13.37691
    default_language = "en"

    def __init__(self):

        self.api = API()
        klass = type(self)
        self.search_center = klass.default_search_center
        self.language = klass.default_language
        self.results_limit = klass.default_results_limit
        self.suggestions_limit = klass.default_suggestions_limit
        self.terms_limit = klass.default_terms_limit
        self.result_queue = asyncio.Queue()
        self.tasks = []

    async def handle_key_strokes(self):
        """
        This method repeatedly waits on key strokes in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:
                query_text = await self.wait_for_new_key_stroke()
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
                query_text = await self.wait_for_submitted_value()
                if query_text:
                    await self._do_discover(session, query_text)

    async def handle_ontology_selections(self):
        """
        This method is called for each shortcut button selected.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:
                ontology: Ontology = await self.wait_for_selected_ontology()
                if ontology:
                    print(ontology)
                    await self._do_browse(session, ontology)

    async def _do_autosuggest(self, session, query_text, x_headers: dict=None) -> None:
        latitude, longitude = self.search_center
        autosuggest_resp = await asyncio.ensure_future(
            self.api.autosuggest(query_text, latitude, longitude, x_headers=x_headers, session=session,
                                 lang=self.language, limit=self.suggestions_limit, termsLimit=self.terms_limit))
        self.handle_suggestion_list(autosuggest_resp)

    async def _do_discover(self, session, query_text, x_headers: dict=None) -> None:
        latitude, longitude = self.search_center
        discover_task = asyncio.ensure_future(
            self.api.discover(query_text, latitude, longitude, x_headers=x_headers, session=session, lang=self.language,
                              limit=self.results_limit))
        discover_resp = await discover_task
        self.handle_result_list(discover_resp)

    async def _do_browse(self, session, ontology, x_headers: dict=None) -> None:
        latitude, longitude = self.search_center
        browse_task = asyncio.ensure_future(
            self.api.browse(latitude, longitude,
                            x_headers=x_headers,
                            session=session,
                            lang=self.language,
                            limit=self.results_limit,
                            **ontology.mapping))
        browse_resp = await browse_task
        self.handle_result_list(browse_resp)

    def run(self) -> "OneBoxSimple":
        self.tasks.extend([asyncio.ensure_future(self.handle_key_strokes()),
                      asyncio.ensure_future(self.handle_text_submissions()),
                      asyncio.ensure_future(self.handle_ontology_selections())])
        return self

    async def stop(self):
        for task in self.tasks:
            task.cancel()

    def __del__(self):
        loop = asyncio.get_running_loop()
        loop.run_until_complete(self.stop())

    def wait_for_new_key_stroke(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_submitted_value(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_selected_ontology(self) -> Awaitable:
        raise NotImplementedError()

    def handle_suggestion_list(self, response: Response) -> None:
        raise NotImplementedError()

    def handle_result_list(self, response: Response) -> None:
        raise NotImplementedError()

    def handle_empty_text_submission(self, **kwargs) -> None:
        raise NotImplementedError()


class OneBoxBase:

    default_results_limit = 20
    default_suggestions_limit = 5
    default_terms_limit = 3
    default_headers = {'User-Agent': f'here-search-notebook-{__version__}'}

    def __init__(self,
                 user_profile: Profile=None,
                 api: API=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 extra_api_params: dict=None,
                 initial_query: str=None,
                 result_queue: asyncio.Queue=None,
                 **kwargs):

        self._do_profiler_start(kwargs)

        self.user_profile = user_profile or Default()
        self.api = api or API()
        self.search_center = self._get_initial_search_center()
        self.language = None
        self.initial_query = initial_query
        self.results_limit = results_limit or self.__class__.default_results_limit
        self.suggestions_limit = suggestions_limit or self.__class__.default_suggestions_limit
        self.terms_limit = terms_limit or self.__class__.default_terms_limit
        self.extra_api_params = extra_api_params or {}
        self.result_queue: asyncio.Queue = result_queue or asyncio.Queue()

        self.x_headers = None
        self.headers = OneBoxBase.default_headers
        if self.user_profile.share_experience:
            self.x_headers = {'X-User-ID': self.user_profile.id,
                              'X-AS-Session-ID': str(uuid.uuid4())}
            self.headers.update(self.x_headers)

    def _get_initial_search_center(self) -> Tuple[float, float]:
        """
        Returns the initial search center used at application start
        :return: a (latitude, longitude) tuple of floats
        """
        return self.user_profile.current_latitude, self.user_profile.current_longitude

    async def handle_key_strokes(self):
        """
        This method repeatedly waits on key strokes in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=self.headers) as session:
            x_headers = self.x_headers
            if self.user_profile.share_experience:
                await self.signal_application_start()
            if not self.initial_query:
                if self.language is None:
                    self.language = await self.get_preferred_location_language(session)
            while True:
                query_text = await self.wait_for_new_key_stroke()
                if query_text is None:
                    self.result_queue.put_nowait(None)
                    break

                if query_text:
                    await self._do_autosuggest(session, query_text, x_headers)
                else:
                    self.handle_empty_text_submission()

    async def signal_application_start(self) -> None:
        pass

    async def handle_text_submissions(self):
        """
        This method repeatedly waits for texts submitted in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=self.headers) as session:
            x_headers = self.x_headers
            if self.initial_query:
                if self.language is None:
                    self.language = await self.get_preferred_location_language(session)
                await self._do_discover(self.initial_query, session, x_headers)

            while True:
                query_text = await self.wait_for_submitted_value()

                if query_text is None:
                    self._do_profiler_stop()
                    break
                elif query_text.strip() == '':
                    self.handle_empty_text_submission()
                    continue

                country_codes = await self._do_discover(session, query_text, x_headers)
                preferred_languages = {self.user_profile.get_preferred_language(country_code) for country_code in country_codes}
                if len(preferred_languages) == 1 and preferred_languages != {None}:
                    language = preferred_languages.pop()
                    if language != self.language:
                        self.language = language

        await self.__astop()

    async def get_preferred_location_language(self, session) -> str:
        if self.user_profile.preferred_languages is None:
            country_code, language = await self.get_position_locale(session)
        elif list(self.user_profile.preferred_languages.keys()) == [Profile.default_name]:
            language = self.user_profile.preferred_languages[Profile.default_name]
        else:
            country_code, country_language = await self.get_position_locale(session)
            preferred_language = self.user_profile.get_preferred_language(country_code)
            language = preferred_language or country_language
        return language

    async def get_position_locale(self, session):
        country_code, language = None, None
        latitude, longitude = self.search_center
        x_headers = self.x_headers.copy()
        x_headers.pop('X-AS-Session-ID', None)
        local_addresses = await self._do_revgeocode(session, latitude, longitude, x_headers)
        if local_addresses and "items" in local_addresses.data and len(local_addresses.data["items"]) > 0:
            country_code = local_addresses.data["items"][0]["address"]["countryCode"]
            address_details = await asyncio.ensure_future(
                self.api.lookup(id=local_addresses.data["items"][0]["id"], session=session))
            language = address_details.data["language"]
        return country_code, language

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
                    await self._do_autosuggest_expansion(session, item, self.user_profile.share_experience, self.x_headers)
                else:
                    await self._do_lookup(session, item, self.user_profile.share_experience, self.x_headers)

    async def handle_ontology_selections(self):
        """
        This method is called for each shortcut button selected.
        """
        async with ClientSession(raise_for_status=True, headers=self.headers) as session:
            while True:
                ontology: Ontology = await self.wait_for_selected_ontology()
                if ontology is None:
                    break
                if not ontology:
                    continue

                x_headers = self.x_headers.copy()
                x_headers.pop('X-AS-Session-ID', None)
                await self._do_browse(session, ontology, {})

    async def _do_discover(self, session, query_text, x_headers) -> set:
        latitude, longitude = self.search_center
        extra_params = self.api.options.get(Endpoint.DISCOVER, {})
        extra_params.update(self.extra_api_params.get(Endpoint.DISCOVER, {}))
        extra_params.update(self.user_profile.api_options.get(Endpoint.DISCOVER, {}))
        discover_task = asyncio.ensure_future(
            self.api.discover(query_text, latitude, longitude, x_headers=x_headers, session=session, lang=self.language,
                              limit=self.results_limit, **extra_params))
        discover_resp = await discover_task
        self.handle_result_list(discover_resp)
        return {item["address"]["countryCode"] for item in discover_resp.data["items"]}

    async def _do_autosuggest(self, session, query_text, x_headers):
        latitude, longitude = self.search_center
        extra_params = self.api.options.get(Endpoint.AUTOSUGGEST, {})
        extra_params.update(self.extra_api_params.get(Endpoint.AUTOSUGGEST, {}))
        extra_params.update(self.user_profile.api_options.get(Endpoint.AUTOSUGGEST, {}))
        autosuggest_resp = await asyncio.ensure_future(
            self.api.autosuggest(query_text, latitude, longitude, x_headers=x_headers, session=session,
                                 lang=self.language, limit=self.suggestions_limit, termsLimit=self.terms_limit,
                                 **extra_params))
        self.handle_suggestion_list(autosuggest_resp)

    async def _do_autosuggest_expansion(self, session, item, share_experience, x_headers):
        if share_experience:
            await self.share_autosuggest_result_selection(item, session, x_headers)

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

    async def share_autosuggest_result_selection(self, item, session, x_headers) -> None:
        pass

    async def _do_browse(self, session, ontology, x_headers) -> set:
        latitude, longitude = self.search_center
        extra_params = self.api.options.get(Endpoint.BROWSE, {}).copy()
        extra_params.update(self.extra_api_params.get(Endpoint.BROWSE, {}))
        extra_params.update(self.user_profile.api_options.get(Endpoint.BROWSE, {}))
        browse_resp = await asyncio.ensure_future(
            self.api.browse(latitude, longitude,
                            x_headers=x_headers,
                            session=session,
                            categories=ontology.categories,
                            food_types=ontology.food_types,
                            chains=ontology.chains,
                            lang=self.language,
                            limit=self.results_limit,
                            **extra_params))
        self.handle_result_list(browse_resp)
        return {item["address"]["countryCode"] for item in browse_resp.data["items"]}

    async def _do_lookup(self, session, item, share_experience, x_headers):
        """
        Perfooms a location id lookup
        :param session:
        :param item:
        :param share_experience:
        :param x_headers:
        :return:
        """
        if item.resp.req.endpoint == Endpoint.AUTOSUGGEST:
            if share_experience:
                await asyncio.ensure_future(
                    self.api.signals(session, resource_id=item.data['id'], rank=item.rank,
                                     correlation_id=item.resp.x_headers['X-Correlation-ID'],
                                     action="here:gs:action:view", userId=x_headers['X-User-ID'],
                                     asSessionId=x_headers['X-AS-Session-ID']))
            lookup_resp = await asyncio.ensure_future(
                self.api.lookup(item.data["id"],
                                x_headers=x_headers,
                                lang=self.language,
                                session=session))
        else:
            if share_experience and item.resp.x_headers:
                await asyncio.ensure_future(
                    self.api.signals(session, resource_id=item.data['id'], rank=item.rank,
                                     correlation_id=item.resp.x_headers['X-Correlation-ID'],
                                     action="here:gs:action:view", userId=x_headers['X-User-ID']))
            extra_params = self.api.options.get(Endpoint.LOOKUP, {})
            extra_params.update(self.extra_api_params.get(Endpoint.LOOKUP, {}))
            extra_params.update(self.user_profile.api_options.get(Endpoint.LOOKUP, {}))
            lookup_resp = await asyncio.ensure_future(
                self.api.lookup(item.data["id"],
                                x_headers=None,
                                session=session,
                                lang=self.language,
                                **extra_params))
        self.handle_result_details(lookup_resp)

    async def _do_revgeocode(self, session, latitude, longitude, x_headers) -> Response:
        extra_params = self.api.options.get(Endpoint.REVGEOCODE, {})
        extra_params.update(self.extra_api_params.get(Endpoint.REVGEOCODE, {}))
        extra_params.update(self.user_profile.api_options.get(Endpoint.REVGEOCODE, {}))
        if self.language:
            extra_params["lang"] = self.language
        revgeocode_resp = await asyncio.ensure_future(
            self.api.reverse_geocode(latitude, longitude,
                                     x_headers=x_headers,
                                     session=session,
                                     limit=self.results_limit,
                                     **extra_params))
        return revgeocode_resp

    def _do_profiler_start(self, kwargs):
        profiling = kwargs.pop("profiling", None)
        if profiling and Profiler:
            self.profiler = Profiler(async_mode="enabled")
            try:
                self.profiler.start()
            except RuntimeError:  # Previous self.profiler.stop() is not completely stopping the profiler....
                pass
        else:
            self.profiler = False

    def _do_profiler_stop(self):
        if self.profiler:
            try:
                self.profiler.stop()
                self.profiler.open_in_browser()
            except RuntimeError:
                pass

    def renew_session_id(self):
        if self.user_profile.share_experience:
            self.x_headers['X-AS-Session-ID'] = str(uuid.uuid4())

    def wait_for_selected_result(self) -> Awaitable:
        return self.result_queue.get()

    def run(self,
            handle_user_profile_setup: Callable=None,
            handle_key_strokes: Callable=None, 
            handle_text_submissions: Callable=None, 
            handle_result_selections: Callable=None,
            handle_ontology_selections: Callable=None):

        asyncio.ensure_future((handle_key_strokes or self.handle_key_strokes)())
        asyncio.ensure_future((handle_text_submissions or self.handle_text_submissions)())
        asyncio.ensure_future((handle_result_selections or self.handle_result_selections)())
        asyncio.ensure_future((handle_ontology_selections or self.handle_ontology_selections)())

    async def __astop(self):
        async with ClientSession(raise_for_status=True, headers=self.headers) as session:
            await asyncio.ensure_future(
                    self.api.signals(session, resource_id="application", rank=0, correlation_id="noCorrelationID",
                                     action="end", userId=self.x_headers['X-User-ID']))

    def wait_for_new_key_stroke(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_submitted_value(self) -> Awaitable:
        raise NotImplementedError()

    def handle_suggestion_list(self, response: Response) -> None:
        raise NotImplementedError()

    def handle_result_list(self, response: Response) -> None:
        raise NotImplementedError()

    def wait_for_selected_ontology(self) -> Awaitable:
        raise NotImplementedError()

    def handle_result_details(self, response: Response) -> None:
        raise NotImplementedError()

    def handle_empty_text_submission(self, **kwargs) -> None:
        raise NotImplementedError()

