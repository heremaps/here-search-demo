import traceback

from aiohttp import ClientSession, client_exceptions
from ujson import loads

from here_search.widgets import OneBoxMap
from here_search.api import API, Response, base_url, Endpoint, ResponseItem, Request
from here_search.user import UserProfile
from .query import NearbySimpleParser

from typing import Tuple, Callable, ClassVar, Iterable, Optional
import asyncio
import os
from getpass import getpass
from collections import OrderedDict
from enum import IntEnum, auto


class LGEndpoint(IntEnum):
    HERE_PLACE = auto()
    SEARCH_PLACE = auto()
    PLACES_CAT_NEAR_CAT = auto()


lg_base_url = {LGEndpoint.HERE_PLACE: 'https://locationgraph.hereapi.com/v2/data/HEREPlace',
               LGEndpoint.PLACES_CAT_NEAR_CAT: 'https://locationgraph.hereapi.com/v2/placesCategorizedNearCategorized'}


class LGAPI:
    api_key: str
    cache: dict

    base_url = 'https://locationgraph.hereapi.com/v2'
    place_url = f'{base_url}/data/HEREPlace/{{place_id}}?apiKey={{self.api_key}}'

    default_radius = 10000
    default_pair_distance = 200
    default_result_limit = 20

    def __init__(self, api_key: str=None, cache: dict=None):
        self.api_key = api_key or os.environ.get('API_KEY') or getpass(prompt="api key: ")
        self.cache = cache or {}

    async def uncache_or_get(self, session: ClientSession, url: str, params: dict) -> Response:
        cache_key = tuple(params.items())
        if cache_key in self.cache:
            return self.cache[cache_key]

        async with session.get(url, params=params) as response:
            result = await response.json(loads=loads)
            self.cache[cache_key] = result
            return result

    @staticmethod
    def in_circle(latitude: float, longitude: float, radius: int=None) -> str:
        return f'circle:{latitude},{longitude};r={radius or LGAPI.default_radius}'

    async def category_near_category(self, session: ClientSession,
                                     find_categories: Iterable, near_categories: Iterable,
                                     in_: str, distance: int=None, limit: int=None, **kwargs):
        params = OrderedDict((('findCategories', ','.join(sorted(find_categories))),
                              ('nearCategories', ','.join(sorted(near_categories))),
                              ('distance', distance or LGAPI.default_pair_distance),
                              ('in', in_),
                              ('limit', limit or LGAPI.default_result_limit),
                              ('apiKey', self.api_key)))
        params.update(kwargs)
        return await self.uncache_or_get(session, lg_base_url[LGEndpoint.PLACES_CAT_NEAR_CAT], params)


class OneBoxCatNearCat(OneBoxMap):
    default_autosuggest_query_params = {'show': 'ontologyDetails,expandedOntologies'}
    default_lg_text_submission = True
    lg_children_details = False

    def __init__(self,
                 user_profile: UserProfile,
                 api_key: str=None,
                 api: API=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 autosuggest_query_params: dict=None,
                 discover_query_params: dict=None,
                 lookup_query_params: dict=None,
                 design: Callable=None,
                 resultlist_class: ClassVar=None,
                 autosuggest_automatic_recenter: bool=False,
                 debounce_time: int=None,
                 lg_radius: int=None,
                 lg_pair_distance: int=None,
                 lg_text_submission: bool=None,
                 lg_children_details: bool=None,
                 **kwargs):

        OneBoxMap.__init__(self,
                           user_profile,
                           api_key=api_key,
                           api=api,
                           results_limit=results_limit,
                           suggestions_limit=suggestions_limit,
                           terms_limit=terms_limit,
                           autosuggest_query_params=autosuggest_query_params or OneBoxCatNearCat.default_autosuggest_query_params,
                           discover_query_params=discover_query_params,
                           lookup_query_params=lookup_query_params,
                           design=design,
                           resultlist_class=resultlist_class,
                           autosuggest_automatic_recenter=autosuggest_automatic_recenter,
                           debounce_time=debounce_time,
                           **kwargs)

        self.lg_api = LGAPI(api_key=self.api.api_key)
        self.lg_radius = lg_radius or self.lg_api.default_radius
        self.lg_pair_distance = lg_pair_distance or self.lg_api.default_pair_distance
        self.lg_text_submission = lg_text_submission or OneBoxCatNearCat.default_lg_text_submission
        self.lg_children_details = lg_children_details or OneBoxCatNearCat.lg_children_details
        self.get_conjunction_mode = NearbySimpleParser(self.language).conjunction_mode_function()

    async def handle_key_strokes(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=OneBoxMap.default_headers) as session:

            find_ontology = None
            while True:
                query_text = await self.wait_for_new_key_stroke()
                if query_text is None:
                    break
                if query_text.strip() == '':
                    self.handle_empty_text_submission()
                    find_ontology = None
                    continue

                latitude, longitude = self.get_search_center()
                conjunction_mode, conjunction, query_head, query_tail = self.get_conjunction_mode(query_text)
                autosuggest_resp, top_ontology = await self.get_first_category_ontology(session, query_text, latitude, longitude)
                if conjunction_mode == NearbySimpleParser.Mode.TOKENS:
                    find_ontology = top_ontology
                elif conjunction_mode in (NearbySimpleParser.Mode.TOKENS_SPACES,
                                          NearbySimpleParser.Mode.TOKENS_CONJUNCTION,
                                          NearbySimpleParser.Mode.TOKENS_CONJUNCTION_SPACES):
                    if top_ontology:
                        find_ontology = top_ontology
                elif conjunction_mode == NearbySimpleParser.Mode.TOKENS_INCOMPLETE_CONJUNCTION:
                    if top_ontology:
                        find_ontology = top_ontology
                    autosuggest_resp.data["queryTerms"] = ([{"term": conjunction}] + autosuggest_resp.data["queryTerms"])[:OneBoxMap.default_terms_limit]

                elif conjunction_mode == NearbySimpleParser.Mode.TOKENS_CONJUNCTION_TOKENS:
                    if top_ontology:
                        find_ontology = top_ontology

                    if find_ontology:
                        near_resp, near_ontology = await self.get_first_category_ontology(session, query_tail, latitude, longitude)
                        if near_ontology:
                            # Replace the query below with the calls to Location Graph
                            self.add_cat_near_cat_suggestion(autosuggest_resp, conjunction, find_ontology,
                                                                   latitude, longitude, near_ontology, near_resp)

                self.handle_suggestion_list(autosuggest_resp)

    def add_cat_near_cat_suggestion(self, autosuggest_resp, conjunction, find_ontology, latitude, longitude,
                                          near_ontology, near_resp):
        find_categories = [cat["id"] for cat in find_ontology['categories']]
        near_categories = [cat["id"] for cat in near_ontology['categories']]
        ontology_near_ontology = {"title": f"{find_ontology['title']} {conjunction} {near_ontology['title']}",
                                  "id": f"{find_ontology['id']}:near:{near_ontology['id']}",
                                  "resultType": "categoryNearCategoryQuery",
                                  "relationship": "nearby",
                                  "titleDetails": {
                                      "findTitle": find_ontology['title'],
                                      "conjunction": conjunction,
                                      "nearTitle": near_ontology['title']
                                  },
                                  "followUpDetails": {"findCategories": find_categories,
                                                      "nearCategories": near_categories,
                                                      "searchLocus": {"latitude": latitude,
                                                                      "longitude": longitude,
                                                                      "radius": self.lg_radius},
                                                      "distance": self.lg_pair_distance,
                                                      "limit": OneBoxCatNearCat.default_results_limit}}
        autosuggest_resp.data["items"] = ([ontology_near_ontology] + autosuggest_resp.data["items"])[
                                         :OneBoxMap.default_suggestions_limit]
        if near_resp.data["queryTerms"]:
            autosuggest_resp.data["queryTerms"] = ([{"term": near_resp.data["queryTerms"][0]["term"]}] +
                                                   autosuggest_resp.data["queryTerms"])[:OneBoxMap.default_terms_limit]

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
                        try:
                            self.profiler.stop()
                            self.profiler.open_in_browser()
                        except RuntimeError:
                            pass
                    break
                if query_text.strip() == '':
                    self.handle_empty_text_submission()
                    continue

                latitude, longitude = self.get_search_center()
                response = Response()
                if self.lg_text_submission:
                    conjunction_mode, conjunction, query_head, query_tail = self.get_conjunction_mode(query_text)
                    if conjunction_mode == NearbySimpleParser.Mode.TOKENS_CONJUNCTION_TOKENS:
                        find_resp, find_ontology = await self.get_first_category_ontology(session, query_head, latitude, longitude)
                        if find_ontology:
                            near_resp, near_ontology = await self.get_first_category_ontology(session, query_tail, latitude, longitude)
                            if near_ontology:
                                find_categories = [cat["id"] for cat in find_ontology['categories']]
                                near_categories = [cat["id"] for cat in near_ontology['categories']]
                                response = await self.lg_to_search_response(session,
                                                                            latitude=latitude,
                                                                            longitude=longitude,
                                                                            find_categories=find_categories,
                                                                            near_categories=near_categories,
                                                                            conjunction=conjunction)
                if not response.data:
                    response = await asyncio.ensure_future(
                        self.api.discover(session,
                                          query_text, latitude, longitude,
                                          lang=self.get_language(),
                                          limit=self.results_limit,
                                          x_headers=x_headers,
                                          **self.discover_query_params))

                self.handle_result_list(response)

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
                    if self.user_profile.share_experience:
                        signal['asSessionID'] = x_headers['X-AS-Session-ID']
                        print(f"send signal {signal}")
                    discover_resp = await asyncio.ensure_future(
                        self.api.autosuggest_href(session, item.data["href"],
                                                  limit=self.results_limit,
                                                  x_headers=x_headers))
                    self.handle_result_list(discover_resp)
                elif item.data["resultType"] == "categoryNearCategoryQuery":
                    follow_up = item.data["followUpDetails"]
                    response = await self.lg_to_search_response(session,
                                                                latitude=follow_up["searchLocus"]["latitude"],
                                                                longitude=follow_up["searchLocus"]["longitude"],
                                                                find_categories=follow_up["findCategories"],
                                                                near_categories=follow_up["nearCategories"],
                                                                conjunction=item.data["titleDetails"]["conjunction"])
                    self.handle_result_list(response)
                else:
                    if item.resp.req.endpoint == Endpoint.AUTOSUGGEST:
                        if self.user_profile.share_experience:
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

    async def lg_to_search_response(self, session: ClientSession,
                                    latitude: float, longitude: float,
                                    find_categories: list, near_categories: list,
                                    conjunction: str) -> Response:
        lg_resp = await self.lg_api.category_near_category(session,
                                                           find_categories=find_categories,
                                                           near_categories=near_categories,
                                                           in_=self.lg_api.in_circle(latitude, longitude,
                                                                                     self.lg_radius),
                                                           distance=self.lg_pair_distance,
                                                           limit=OneBoxCatNearCat.default_results_limit)
        search_items = []
        for item in lg_resp.get('items', []):
            find_id = item['findPlace']['properties']['HEREPlace']['placeId']
            near_id = item['nearPlace']['properties']['HEREPlace']['placeId']
            try:
                find_lookup_resp = await asyncio.ensure_future(
                    self.api.lookup(session, f'here:pds:place:{find_id}',
                                    lang=self.get_language(),
                                    x_headers=self.x_headers,
                                    **self.lookup_query_params))
                find_lookup_resp.data['children'] = [{'association': 'nearby', 'id': f'here:pds:place:{near_id}'}]
                if self.lg_children_details:
                    near_lookup_resp = await asyncio.ensure_future(
                        self.api.lookup(session, f'here:pds:place:{near_id}',
                                        lang=self.get_language(),
                                        x_headers=self.x_headers,
                                        **self.lookup_query_params))
                    find_lookup_resp.data["title"] = f'{find_lookup_resp.data["title"]} ({conjunction} {near_lookup_resp.data["title"]})'
                    find_lookup_resp.data['children'][0].update(near_lookup_resp.data)
            except:
                continue

            search_items.append(find_lookup_resp.data)
        return Response(data={'items': search_items}, req=Request())

    async def get_first_category_ontology(self, session: ClientSession,
                                          query: str, latitude: float, longitude: float) -> Tuple[Response, Optional[dict]]:
        autosuggest_resp = await asyncio.ensure_future(
            self.api.autosuggest(session,
                                 query,
                                 latitude,
                                 longitude,
                                 lang=self.get_language(),
                                 limit=self.suggestions_limit,
                                 termsLimit=self.terms_limit,
                                 x_headers=None,
                                 **self.autosuggest_query_params))
        for item in autosuggest_resp.data["items"]:
            if item["resultType"] == "categoryQuery" and "relationship" not in item:
                return autosuggest_resp, item
        else:
            return autosuggest_resp, None

    def run(self):
        OneBoxMap.run(self, handle_key_strokes=self.handle_key_strokes)
