from ujson import loads
from aiohttp import ClientSession

from getpass import getpass
from typing import Tuple, Awaitable
import os
import asyncio

from . import __version__


class Timer:
    def __init__(self, milliseconds, callback):
        self._timeout = milliseconds
        self._callback = callback

    async def _job(self):
        await asyncio.sleep(self._timeout/1000.0)
        self._callback()

    def start(self):
        self._task = asyncio.ensure_future(self._job())

    def cancel(self):
        self._task.cancel()

def debounce(milliseconds):
    def decorator(fn):
        timer = None
        def debounced(*args, **kwargs):
            nonlocal timer
            def call_it():
                fn(*args, **kwargs)
            if timer is not None:
                timer.cancel()
            timer = Timer(milliseconds, call_it)
            timer.start()
        return debounced
    return decorator


class OneBoxBase:
    as_url = 'https://autosuggest.search.hereapi.com/v1/autosuggest'
    ds_url = 'https://discover.search.hereapi.com/v1/discover'
    l_url = 'https://lookup.search.hereapi.com/v1/lookup'
    default_results_limit = 20
    default_suggestions_limit = 5
    default_terms_limit = 0
    default_autosuggest_query_params = {}
    default_discover_query_params = {}
    default_lookup_query_params = {}
    default_headers = {'User-Agent': f'here-search-notebook-{__version__}'}

    def __init__(self,
                 api_key: str=None,
                 language: str=None,
                 suggestions_limit: int=None,
                 results_limit: int=None,
                 terms_limit: int=None,
                 autosuggest_query_params: dict=None,
                 discover_query_params: dict=None,
                 lookup_query_params: dict=None):
        self.api_key = api_key or os.environ.get('API_KEY')
        self.language = language
        self.results_limit = results_limit or self.__class__.default_results_limit
        self.suggestions_limit = suggestions_limit or self.__class__.default_suggestions_limit
        self.terms_limit = terms_limit or self.__class__.default_terms_limit
        self.autosuggest_query_params = autosuggest_query_params or self.__class__.default_autosuggest_query_params
        self.discover_query_params = discover_query_params or self.__class__.default_discover_query_params
        self.lookup_query_params = lookup_query_params or self.__class__.default_lookup_query_params

        self.result_queue: asyncio.Queue = asyncio.Queue()


    async def autosuggest(self, session: ClientSession,
                          q: str, latitude: float, longitude: float,
                          **params) -> dict:
        """
        Calls HERE Search Autosuggest endpoint
        https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :return: a tuple made of the input query text and the response dictionary
        """
        _params = {'q': q,
                  'at': f'{latitude},{longitude}',
                  'limit': self.suggestions_limit,
                  'termsLimit': self.terms_limit}
        _params.update(params)
        language = self.get_language()
        if language:
            _params['lang'] = language
        if self.api_key:
            _params['apiKey'] = self.api_key

        async with session.get(self.__class__.as_url, params=_params) as response:
            return await response.json(loads=loads)

    async def autosuggest_href(self, session: ClientSession, href: str, **params) -> dict:
        """
        Blindly calls Autosuggest href
        :param session:
        :param href:
        :param params:
        :return:
        """
        _params = {'limit': self.results_limit}
        if self.api_key:
            _params['apiKey'] = self.api_key

        async with session.get(href, params=_params) as response:
            result = await response.json(loads=loads)
            result["_url"] = href
            result["_params"] =_params
            return result

    async def discover(self, session: ClientSession,
                       q: str, latitude: float, longitude: float,
                       **params) -> dict:
        """
        Calls HERE Search Discover endpoint
        https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :return: a response dictionary
        """
        _params = {'q': q,
                  'at': f'{latitude},{longitude}',
                  'limit': self.results_limit}
        _params.update(params)
        language = self.get_language()
        if language:
            _params['lang'] = language
        if self.api_key:
            _params['apiKey'] = self.api_key

        async with session.get(self.__class__.ds_url, params=_params) as response:
            result = await response.json(loads=loads)
            result["_url"] = self.__class__.ds_url
            result["_params"] =_params
            return result

    async def lookup(self, session: ClientSession, id: str, **params) -> dict:
        """
        Calls HERE Search Lookup for a specific id
        :param session:
        :param id:
        :param params:
        :return:
        """
        _params = {'id': id}
        _params.update(params)
        language = self.get_language()
        if language:
            _params['lang'] = language
        if self.api_key:
            _params['apiKey'] = self.api_key

        async with session.get(self.__class__.l_url, params=_params) as response:
            result = await response.json(loads=loads)
            result["_url"] = self.__class__.l_url
            result["_params"] =_params
            return result

    async def handle_key_strokes(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=OneBoxBase.default_headers) as session:
            while True:
                q = await self.wait_for_new_key_stroke()
                if q is None:
                    break
                if not q:
                    continue

                latitude, longitude = self.get_search_center()
                autosuggest_resp = await asyncio.ensure_future(self.autosuggest(session, q, latitude, longitude, **self.autosuggest_query_params))

                self.handle_suggestion_list(autosuggest_resp)

    async def handle_text_submissions(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=OneBoxBase.default_headers) as session:
            while True:
                q = await self.wait_for_submitted_value()
                if q is None:
                    break
                if not q:
                    continue

                latitude, longitude = self.get_search_center()
                discover_resp = await asyncio.ensure_future(self.discover(session, q, latitude, longitude, **self.discover_query_params))

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
                    discover_resp = await asyncio.ensure_future(self.autosuggest_href(session, item["href"]))
                    self.handle_result_list(discover_resp)
                else:
                    lookup_resp = await asyncio.ensure_future(self.lookup(session, item["id"], **self.lookup_query_params))
                    self.handle_result_details(lookup_resp)

    def get_language(self):
        return self.language

    def get_search_center(self) -> Tuple[float, float]:
        raise NotImplementedError()

    def wait_for_new_key_stroke(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_submitted_value(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_selected_result(self) -> Awaitable:
        return self.result_queue.get()

    def handle_suggestion_list(self, response: dict) -> None:
        raise NotImplementedError()

    def handle_result_list(self, response: dict) -> None:
        raise NotImplementedError()

    def handle_result_details(self, response: dict) -> None:
        raise NotImplementedError()

    async def main(self):
        self.result_queue = asyncio.Queue()
        t1 = asyncio.create_task(self.handle_key_strokes())
        t2 = asyncio.create_task(self.handle_text_submissions())
        t3 = asyncio.create_task(self.handle_result_selections())
        await asyncio.gather(t1, t2, t3)

    def run(self):
        #asyncio.run(self.main())
        asyncio.ensure_future(self.handle_key_strokes())
        asyncio.ensure_future(self.handle_text_submissions())
        asyncio.ensure_future(self.handle_result_selections())