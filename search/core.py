from ujson import loads
from aiohttp import ClientSession
import nest_asyncio
from pyinstrument import Profiler

from . import __version__
from .user import UserProfile
from .api import API, Response, Endpoint

from getpass import getpass
from typing import Tuple, Awaitable, Callable, Mapping
import os
import asyncio
from collections import OrderedDict
from dataclasses import dataclass
import uuid


class OneBoxBase:

    default_results_limit = 20
    default_suggestions_limit = 5
    default_terms_limit = 0
    default_autosuggest_query_params = {}
    default_discover_query_params = {}
    default_lookup_query_params = {}
    default_profile_language = 'en'
    default_headers = {'User-Agent': f'here-search-notebook-{__version__}'}

    def __init__(self,
                 user_profile: UserProfile,
                 api: API=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 autosuggest_query_params: dict=None,
                 discover_query_params: dict=None,
                 lookup_query_params: dict=None,
                 result_queue: asyncio.Queue=None,
                 **kwargs):

        profiling = kwargs.pop("profiling", None)
        if profiling:
            self.profiler = Profiler(async_mode="enabled")
            self.profiler.start()
        else:
            self.profiler = False
        self.api = api or API()
        self.user_profile = user_profile or UserProfile(api=self.api)
        self.latitude = self.user_profile.current_latitude
        self.longitude = self.user_profile.current_longitude
        self.language = self.user_profile.get_current_language()

        self.results_limit = results_limit or self.__class__.default_results_limit
        self.suggestions_limit = suggestions_limit or self.__class__.default_suggestions_limit
        self.terms_limit = terms_limit or self.__class__.default_terms_limit
        self.autosuggest_query_params = autosuggest_query_params or self.__class__.default_autosuggest_query_params
        self.discover_query_params = discover_query_params or self.__class__.default_discover_query_params
        self.lookup_query_params = lookup_query_params or self.__class__.default_lookup_query_params

        self.result_queue: asyncio.Queue = result_queue or asyncio.Queue()

        self.x_headers =  None
        self.headers = OneBoxBase.default_headers
        if self.user_profile.store_my_activity:
            self.x_headers = {'X-User-ID': self.user_profile.id,
                              'X-AS-Session-ID': str(uuid.uuid4())}
            self.headers.update(self.x_headers)


    async def handle_key_strokes(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=self.headers) as session:
            x_headers = self.x_headers
            while True:
                query_text = await self.wait_for_new_key_stroke()
                if query_text is None:
                    self.result_queue.put_nowait(None)
                    break
                if query_text:
                    latitude, longitude = self.get_search_center()
                    autosuggest_resp = await asyncio.ensure_future(
                        self.api.autosuggest(session,
                                             query_text,
                                             latitude,
                                             longitude,
                                             lang=self.get_language(),
                                             limit=self.results_limit,
                                             termsLimit=self.terms_limit,
                                             x_headers=x_headers,
                                             **self.autosuggest_query_params))
                    self.handle_suggestion_list(autosuggest_resp)
                else:
                    self.handle_empty_text_submission()

    async def handle_text_submissions(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=self.headers) as session:
            x_headers = self.x_headers
            while True:
                query_text = await self.wait_for_submitted_value()
                if query_text is None:
                    if self.profiler:
                        self.profiler.stop()
                        #self.profiler.print(show_all=True)
                        self.profiler.open_in_browser()
                    break
                if query_text:

                    latitude, longitude = self.get_search_center()
                    discover_task = asyncio.ensure_future(
                        self.api.discover(session, 
                                          query_text, 
                                          latitude, 
                                          longitude, 
                                          lang=self.get_language(),
                                          limit=self.results_limit,
                                          x_headers=x_headers,
                                          **self.discover_query_params))
                    discover_resp = await discover_task
                    self.handle_result_list(discover_resp)

    async def handle_result_selections(self):
        """
        This method is called for each search result selected.
        """
        async with ClientSession(raise_for_status=True, headers=self.headers) as session:
            x_headers = self.x_headers
            while True:
                item: ResponseItem = await self.wait_for_selected_result()
                if item is None:
                    break
                if not item:
                    continue

                # TO be used for signals
                signal = {'id': item.data['id'],
                          'rank': item.rank,
                          'correlation_id': item.resp.x_headers['X-Correlation-ID'],
                          'action': 'tap'}

                if item.data["resultType"] in ("categoryQuery", "chainQuery"):
                    if self.user_profile.store_my_activity:
                        signal['asSessionID'] = x_headers['X-AS-Session-ID']
                        print(f"send signal {signal}")
                    discover_resp = await asyncio.ensure_future(
                        self.api.autosuggest_href(session,
                                                  item.data["href"],
                                                  limit=self.results_limit,
                                                  x_headers=x_headers))
                    self.handle_result_list(discover_resp)
                else:
                    if item.resp.req.endpoint == Endpoint.AUTOSUGGEST:
                        if self.user_profile.store_my_activity:
                            signal['asSessionID'] = x_headers['X-AS-Session-ID']
                            print(f"send signal {signal}")
                        lookup_resp = await asyncio.ensure_future(
                            self.api.lookup(session,
                                            item.data["id"],
                                            lang=self.get_language(),
                                            x_headers=x_headers,
                                            **self.lookup_query_params))
                    else:
                        print(f"send signal {signal}")
                        lookup_resp = await asyncio.ensure_future(
                            self.api.lookup(session,
                                            item.data["id"],
                                            lang=self.get_language(),
                                            x_headers=None,
                                            **self.lookup_query_params))
                    self.handle_result_details(lookup_resp)

    def get_language(self):
        return self.language

    def get_search_center(self) -> Tuple[float, float]:
        return self.latitude, self.longitude

    def renew_session_id(self):
        if self.user_profile.store_my_activity:
            self.x_headers['X-AS-Session-ID'] = str(uuid.uuid4())
            print(f"new as session id: {self.x_headers['X-AS-Session-ID']}\n")

    def wait_for_new_key_stroke(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_submitted_value(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_selected_result(self) -> Awaitable:
        return self.result_queue.get()

    def handle_suggestion_list(self, response: Response) -> None:
        raise NotImplementedError()

    def handle_empty_text_submission(self, **kwargs) -> None:
        raise NotImplementedError()

    def handle_result_list(self, response: Response) -> None:
        raise NotImplementedError()

    def handle_result_details(self, response: Response) -> None:
        raise NotImplementedError()
    
    def run(self,
            handle_user_profile_setup: Callable=None,
            handle_key_strokes: Callable=None, 
            handle_text_submissions: Callable=None, 
            handle_result_selections: Callable=None):

        asyncio.ensure_future((handle_key_strokes or self.handle_key_strokes)())
        asyncio.ensure_future((handle_text_submissions or self.handle_text_submissions)())
        asyncio.ensure_future((handle_result_selections or self.handle_result_selections)())
