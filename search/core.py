from ujson import loads
from aiohttp import ClientSession
import nest_asyncio

from . import __version__
from .user import UserProfile
from .api import API

from getpass import getpass
from typing import Tuple, Awaitable, Callable, Mapping
import os
import asyncio
from collections import OrderedDict
from dataclasses import dataclass



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
                 suggestions_limit: int=None,
                 results_limit: int=None,
                 terms_limit: int=None,
                 autosuggest_query_params: dict=None,
                 discover_query_params: dict=None,
                 lookup_query_params: dict=None,
                 result_queue: asyncio.Queue=None):

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

    async def handle_key_strokes(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=OneBoxBase.default_headers) as session:
            while True:
                query_text = await self.wait_for_new_key_stroke()
                if query_text is None:
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
                                             **self.autosuggest_query_params))
                    self.handle_suggestion_list(autosuggest_resp)
                else:
                    self.handle_empty_text_submission()

    async def handle_text_submissions(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=OneBoxBase.default_headers) as session:
            while True:
                query_text = await self.wait_for_submitted_value()
                print(query_text)
                if query_text is None:
                    break
                if query_text:

                    latitude, longitude = self.get_search_center()
                    discover_resp = await asyncio.ensure_future(
                        self.api.discover(session, 
                                          query_text, 
                                          latitude, 
                                          longitude, 
                                          lang=self.get_language(),
                                          limit=self.results_limit,
                                          **self.discover_query_params))

                    self.handle_result_list(discover_resp)

    async def handle_result_selections(self):
        """
        This method is called for each search result selected.
        """
        async with ClientSession(raise_for_status=True, headers=OneBoxBase.default_headers) as session:
            while True:
                item: dict = await self.wait_for_selected_result()
                if item is None:
                    break
                if not item:
                    continue

                if item["resultType"] in ("categoryQuery", "chainQuery"):
                    discover_resp = await asyncio.ensure_future(
                        self.api.autosuggest_href(session, 
                                                  item["href"],
                                                  limit=self.results_limit))
                    self.handle_result_list(discover_resp)
                else:
                    lookup_resp = await asyncio.ensure_future(
                        self.api.lookup(session, 
                                        item["id"], 
                                        lang=self.get_language(), 
                                        **self.lookup_query_params))
                    self.handle_result_details(lookup_resp)

    def get_language(self):
        return self.language

    def get_search_center(self) -> Tuple[float, float]:
        return self.latitude, self.longitude

    def wait_for_new_key_stroke(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_submitted_value(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_selected_result(self) -> Awaitable:
        return self.result_queue.get()

    def handle_suggestion_list(self, response: dict) -> None:
        raise NotImplementedError()

    def handle_empty_text_submission(self, **kwargs) -> None:
        raise NotImplementedError()

    def handle_result_list(self, response: dict) -> None:
        raise NotImplementedError()

    def handle_result_details(self, response: dict) -> None:
        raise NotImplementedError()
    
    def run(self,
            handle_user_profile_setup: Callable=None,
            handle_key_strokes: Callable=None, 
            handle_text_submissions: Callable=None, 
            handle_result_selections: Callable=None):

        asyncio.ensure_future((handle_key_strokes or self.handle_key_strokes)())
        asyncio.ensure_future((handle_text_submissions or self.handle_text_submissions)())
        asyncio.ensure_future((handle_result_selections or self.handle_result_selections)())

