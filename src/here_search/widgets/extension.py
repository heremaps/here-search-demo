import traceback

from aiohttp import ClientSession, client_exceptions
from ujson import loads

from here_search.widgets.app import OneBoxMap
from here_search.api import API, base_url
from here_search.entities import Response, ResponseItem, Request

from here_search.user import Profile
from here_search.api import Endpoint
from .request import NearbySimpleParser
from here_search.util import logger

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
            logger.info(response.url)
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
                              ('t', 's'),
                              ('apiKey', self.api_key)))
        params.update(kwargs)
        return await self.uncache_or_get(session, lg_base_url[LGEndpoint.PLACES_CAT_NEAR_CAT], params)


class OneBoxCatNearCat(OneBoxMap):
    default_extra_api_params = {Endpoint.AUTOSUGGEST: {'show': 'ontologyDetails,expandedOntologies'}}
    default_lg_text_submission = True
    lg_children_details = False

    def __init__(self,
                 user_profile: Profile,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 extra_api_params: dict=None,
                 lg_radius: int=None,
                 lg_pair_distance: int=None,
                 lg_text_submission: bool=None,
                 lg_children_details: bool=None,
                 **kwargs):

        OneBoxMap.__init__(self,
                           user_profile,
                           results_limit=results_limit,
                           suggestions_limit=suggestions_limit,
                           extra_api_params=extra_api_params or OneBoxCatNearCat.default_extra_api_params,
                           **kwargs)

        self.lg_api = LGAPI(api_key=self.api.api_key)
        self.lg_radius = lg_radius or self.lg_api.default_radius
        self.lg_pair_distance = lg_pair_distance or self.lg_api.default_pair_distance
        self.lg_text_submission = lg_text_submission or OneBoxCatNearCat.default_lg_text_submission
        self.lg_children_details = lg_children_details or OneBoxCatNearCat.lg_children_details
        self.get_conjunction_mode = None

    async def handle_key_strokes(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=OneBoxMap.default_headers) as session:
            if not self.initial_query and self.language is None:
                language = self.language
                self.language = await self.get_preferred_location_language(session)
                if language != self.language:
                    self.get_conjunction_mode = NearbySimpleParser(self.language).conjunction_mode_function()
            find_ontology = None
            while True:
                query_text = await self.wait_for_new_key_stroke()
                if query_text is None:
                    break
                if query_text.strip() == '':
                    self.handle_empty_text_submission()
                    find_ontology = None
                    continue

                latitude, longitude = self.search_center
                conjunction_mode, conjunction, query_head, query_tail = self.get_conjunction_mode(query_text)
                autosuggest_resp, top_ontology = await self.get_first_category_ontology(session, query_text, latitude, longitude)
                if conjunction_mode == NearbySimpleParser.Mode.TOKENS or top_ontology:
                    find_ontology = top_ontology

                if conjunction_mode == NearbySimpleParser.Mode.TOKENS_INCOMPLETE_CONJUNCTION:
                    autosuggest_resp.data["queryTerms"] = ([{"term": conjunction}] + autosuggest_resp.data["queryTerms"])[:OneBoxMap.default_terms_limit]

                elif conjunction_mode == NearbySimpleParser.Mode.TOKENS_CONJUNCTION_TOKENS and find_ontology:
                    near_resp, near_ontology = await self.get_first_category_ontology(session, query_tail, latitude, longitude)
                    if near_ontology:
                        # Replace the query below with the calls to Location Graph
                        new_autosuggest_resp = self.add_cat_near_cat_suggestion(autosuggest_resp, conjunction, find_ontology,
                                                                                latitude, longitude, near_ontology, near_resp)
                        autosuggest_resp = new_autosuggest_resp

                self.handle_suggestion_list(autosuggest_resp)

    async def handle_text_submissions(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=self.headers) as session:
            x_headers = self.x_headers

            if self.initial_query:
                if self.language is None:
                    self.language = await self.get_preferred_location_language(session)
                    self.get_conjunction_mode = NearbySimpleParser(self.language).conjunction_mode_function()
                if self.lg_text_submission:
                    await self._do_lg_discover(session, self.initial_query, x_headers)
                else:
                    await self._do_discover(session, self.initial_query, x_headers)

            while True:
                query_text = await self.wait_for_submitted_value()

                if query_text is None:
                    self._do_profiler_stop()
                    break
                elif query_text.strip() == '':
                    self.handle_empty_text_submission()
                    continue

                if self.lg_text_submission:
                    country_codes = await self._do_lg_discover(session, query_text, x_headers)
                else:
                    country_codes = await self._do_discover(session, query_text, x_headers)

                preferred_languages = {self.user_profile.get_preferred_language(country_code) for country_code in country_codes}
                if len(preferred_languages) == 1:
                    language = preferred_languages.pop()
                    if language != self.language:
                        self.language = language
                        self.get_conjunction_mode = NearbySimpleParser(language).conjunction_mode_function()

        await self.__astop()

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

                if item.data["resultType"] in ("categoryQuery", "chainQuery"):
                    await self._do_autosuggest_expansion(session, item, self.user_profile.share_experience, x_headers)
                elif item.data["resultType"] == "categoryNearCategoryQuery":
                    follow_up = item.data["followUpDetails"]
                    response = await self.lg_to_search_response(session,
                                                                latitude=follow_up["searchLocus"]["latitude"],
                                                                longitude=follow_up["searchLocus"]["longitude"],
                                                                find_categories=follow_up["findCategories"],
                                                                near_categories=follow_up["nearCategories"],
                                                                conjunction=item.data["titleDetails"]["conjunction"])
                    self.handle_result_list(response)
                elif item.resp.req.endpoint == LGEndpoint.PLACES_CAT_NEAR_CAT:
                    response = Response(req=item.resp.req, data=item.data, x_headers=item.resp.req.x_headers)
                    self.handle_result_details(response)
                else:
                    await self._do_lookup(session, item, self.user_profile.share_experience, x_headers)

    def add_cat_near_cat_suggestion(self, autosuggest_resp, conjunction, find_ontology, latitude, longitude,
                                    near_ontology, near_resp) -> Response:
        find_categories = [cat["id"] for cat in find_ontology.get('categories', [])]
        near_categories = [cat["id"] for cat in near_ontology.get('categories', [])]
        ontology_near_ontology = {"clientSideAddition": True,
                                  "title": f"{find_ontology['title']} {conjunction} {near_ontology['title']}",
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
        data = {"items": [ontology_near_ontology], "queryTerms": []}
        data["items"].extend(autosuggest_resp.data["items"].copy())
        data["items"] = data["items"][:OneBoxMap.default_suggestions_limit]
        new_autosugest_resp = Response(data=data, x_headers=autosuggest_resp.x_headers, req=autosuggest_resp.req)
        if near_resp.data["queryTerms"]:
            new_autosugest_resp.data["queryTerms"].append({"term": near_resp.data["queryTerms"][0]["term"]})
        new_autosugest_resp.data["queryTerms"].extend(autosuggest_resp.data["queryTerms"])
        new_autosugest_resp.data["queryTerms"] = new_autosugest_resp.data["queryTerms"][:OneBoxMap.default_terms_limit]
        return new_autosugest_resp

    async def _do_lg_discover(self, session, query_text, x_headers):
        response = Response(req=Request())
        latitude, longitude = self.search_center()
        country_codes = set()
        conjunction_mode, conjunction, query_head, query_tail = self.get_conjunction_mode(query_text)
        if conjunction_mode == NearbySimpleParser.Mode.TOKENS_CONJUNCTION_TOKENS:
            find_resp, find_ontology = await self.get_first_category_ontology(session, query_head, latitude, longitude)
            if find_ontology:
                near_resp, near_ontology = await self.get_first_category_ontology(session, query_tail, latitude,
                                                                                  longitude)
                if near_ontology:
                    find_categories = [cat["id"] for cat in find_ontology['categories']]
                    near_categories = [cat["id"] for cat in near_ontology['categories']]
                    response = await self.lg_to_search_response(session,
                                                                latitude=latitude,
                                                                longitude=longitude,
                                                                find_categories=find_categories,
                                                                near_categories=near_categories,
                                                                conjunction=conjunction)
                    country_codes.update({item["address"]["countryCode"] for item in response.data["items"]})
        if response.data is None:
            country_codes = await self._do_discover(session, query_text, x_headers)
        else:
            self.handle_result_list(response)
        return country_codes

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
            find_id = item['findPlace']['properties']['SearchPlace']['placeId']
            near_id = item['nearPlace']['properties']['SearchPlace']['placeId']
            try:
                find_lookup_resp = await asyncio.ensure_future(
                    self.api.lookup(f'here:pds:place:{find_id}',
                                    x_headers=self.x_headers,
                                    session=session,
                                    lang=self.language,
                                    **self.lookup_query_params))
                data = {"clientSideAddition": True}
                data.update(find_lookup_resp.data.copy())
                find_lookup_resp_copy = Response(req=find_lookup_resp.req, data=data, x_headers=find_lookup_resp.x_headers)
                find_lookup_resp_copy.data['children'] = [{'association': 'nearby', 'id': f'here:pds:place:{near_id}'}]
                if self.lg_children_details:
                    title = find_lookup_resp_copy.data["title"]
                    near_lookup_resp = await asyncio.ensure_future(
                        self.api.lookup(f'here:pds:place:{near_id}',
                                        x_headers=self.x_headers,
                                        session=session,
                                        lang=self.language,
                                        **self.lookup_query_params))
                    find_lookup_resp_copy.data["titleDetails"] = {
                        "findTitle": title,
                        "conjunction": conjunction,
                        "nearTitle": near_lookup_resp.data['title']
                    }
                    find_lookup_resp_copy.data["title"] = f'{title} ({conjunction} {near_lookup_resp.data["title"]})'

                    find_lookup_resp_copy.data['children'][0].update(near_lookup_resp.data)
            except:
                continue
            else:
                search_items.append(find_lookup_resp_copy.data)

        if search_items:
            data = {"clientSideAddition": True, 'items': search_items}
            response = Response(data=data, req=Request(endpoint=LGEndpoint.PLACES_CAT_NEAR_CAT))
        else:
            response = Response()

        return response

    async def get_first_category_ontology(self, session: ClientSession,
                                          query: str, latitude: float, longitude: float) -> Tuple[Response, Optional[dict]]:
        autosuggest_resp = await asyncio.ensure_future(
            self.api.autosuggest(query, latitude, longitude,
                                 x_headers=None,
                                 session=session,
                                 lang=self.language,
                                 limit=self.suggestions_limit,
                                 termsLimit=self.terms_limit,
                                 **self.autosuggest_query_params))
        for item in autosuggest_resp.data["items"]:
            if item["resultType"] == "categoryQuery" and "relationship" not in item:
                return autosuggest_resp, item
        else:
            return autosuggest_resp, None

    def run(self):
        OneBoxMap.run(self, handle_key_strokes=self.handle_key_strokes)
