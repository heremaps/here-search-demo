import traceback

from IPython.display import display as Idisplay
from ipywidgets import Output
from aiohttp import ClientSession
import nest_asyncio

from search.core import OneBoxBase
from search.user import UserProfile
from search.api import API, Response, base_url, Endpoint
from .query import SubmittableTextBox, TermsButtons, NearbySimpleParser
from .response import SearchFeatureCollection, SearchResultButtons, PositionMap, SearchResultJson, SearchResultRadioButtons
from .design import Design


from typing import Callable, ClassVar, Tuple, Awaitable
import asyncio


class OneBoxMap(OneBoxBase):

    default_results_limit = 10
    default_suggestions_limit = 5
    default_terms_limit = 3
    minimum_zoom_level = 11
    default_search_box_layout = {'width': '240px'}
    default_placeholder = "free text"
    default_output_format = 'text'
    default_resultlist_class = SearchResultButtons
    default_design = Design.three
    default_debounce_time = 0

    def __init__(self,
                 user_profile: UserProfile,
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
                 **kwargs):

        self.result_queue: asyncio.Queue = asyncio.Queue()
        OneBoxBase.__init__(self,
                            user_profile,
                            api=api,
                            results_limit=results_limit or OneBoxMap.default_results_limit,
                            suggestions_limit=suggestions_limit or OneBoxMap.default_suggestions_limit,
                            terms_limit=terms_limit or OneBoxMap.default_terms_limit,
                            result_queue=self.result_queue, **kwargs)

        self.query_box_w = SubmittableTextBox(OneBoxMap.default_debounce_time if debounce_time is None else debounce_time,
                                              layout=kwargs.pop('layout', self.__class__.default_search_box_layout),
                                              placeholder=kwargs.pop('placeholder', self.__class__.default_placeholder),
                                              **kwargs)
        self.query_terms_w = TermsButtons(self.query_box_w, buttons_count=self.__class__.default_terms_limit)
        self.result_points_w: SearchFeatureCollection = None
        self.design = design
        self.map_w = None
        self.app_design_w = None

        self.result_list_w = (resultlist_class or self.__class__.default_resultlist_class)(widget=Output(), result_queue=self.result_queue)

    def get_search_center(self):
        return self.map_w.center

    def wait_for_new_key_stroke(self) -> Awaitable:
        return self.query_box_w.get_key_stroke_future()

    def wait_for_submitted_value(self) -> Awaitable:
        return self.query_box_w.get_submitted_value_future()

    def handle_suggestion_list(self, autosuggest_resp: Response):
        """
        Typically called by OneBoxBase.handle_key_strokes()
        :param autosuggest_resp:
        :return: None
        """
        self.display_suggestions(autosuggest_resp)
        self.display_terms(autosuggest_resp)

    def handle_empty_text_submission(self) -> None:
        """
        Typically called by OneBoxBase.handle_key_strokes()
        :param autosuggest_resp:
        :return: None
        """
        self.query_terms_w.set([])

    def handle_result_list(self, discover_resp: Response):
        """
        Typically called by OneBoxBase.handle_text_submissions()
        :param autosuggest_resp:
        :return: None
        """
        self.result_list_w.display(discover_resp)
        self.display_result_map(discover_resp, update_search_center=True)
        self.clear_query_text()
        self.renew_session_id()

    def handle_result_details(self, lookup_resp: Response):
        """
        Typically called by OneBoxBase.handle_result_selections()
        :param autosuggest_resp:
        :return: None
        """
        lookup_resp.data = {"items": [lookup_resp.data]}
        self.display_result_map(lookup_resp, update_search_center=True)

    def display_terms(self, autosuggest_resp: Response):
        terms = [term['term'] for term in autosuggest_resp.data.get('queryTerms', [])]
        self.query_terms_w.set(terms)

    def display_suggestions(self, autosuggest_resp: Response) -> None:
        self.result_list_w.display(autosuggest_resp)

        search_feature = SearchFeatureCollection(autosuggest_resp)
        if search_feature.bbox:
            if self.result_points_w:
                self.map_w.remove_layer(self.result_points_w)
            self.result_points_w = search_feature
            self.map_w.add_layer(self.result_points_w)
        #self.display_result_map(autosuggest_resp, update_search_center=False)

    def __get_terms_buttons_handler(self, query_terms_w: TermsButtons):
        def on_terms_click_handler(button):
            # replace the last token with the clicked button description and a whitespace
            if self.text.value.endswith(' '):
                self.text.value = f"{self.text.value}{button.description.strip()} "
            else:
                tokens = self.text.value.strip().split(' ')
                if tokens:
                    head = tokens[:-1]
                    head.extend([button.description.strip(), ''])
                    self.text.value = ' '.join(head)
            query_terms_w.set([])
        return on_terms_click_handler

    def clear_query_text(self):
        self.query_box_w.text.value = ''
        self.query_terms_w.set([])

    def display_result_map(self, resp: Response, update_search_center: bool=False):
        if self.result_points_w:
            self.map_w.remove_layer(self.result_points_w)
        self.result_points_w = SearchFeatureCollection(resp)
        self.map_w.add_layer(self.result_points_w)
        if self.result_points_w.bbox:
            self.map_w.bounds = self.result_points_w.bbox
            if len(resp.data["items"]) == 1:
                self.map_w.zoom = OneBoxMap.minimum_zoom_level

    async def __init_map(self):
        self.map_w = PositionMap(api_key=self.api.api_key, center=[self.latitude, self.longitude])
        self.app_design_w = (self.design or self.__class__.default_design)(self.query_box_w, self.map_w, self.query_terms_w, self.result_list_w)


    def run(self,
            handle_user_profile_setup: Callable=None,
            handle_key_strokes: Callable=None,
            handle_text_submissions: Callable=None,
            handle_result_selections: Callable=None):

        nest_asyncio.apply()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        loop.run_until_complete(self.__init_map())
        Idisplay(self.app_design_w)

        OneBoxBase.run(self,
                       handle_user_profile_setup,
                       handle_key_strokes or self.handle_key_strokes,
                       handle_text_submissions or self.handle_text_submissions,
                       handle_result_selections or self.handle_result_selections)


#class OneBoxMapCI(OneBoxMap):
#    as_url = 'http://ci.opensearch.dev.api.here.com/v1/autosuggest'
#    ds_url = 'http://ci.opensearch.dev.api.here.com/v1/discover'
#    default_autosuggest_query_params = {'show': 'details,expandedOntologies'}
#    default_discover_query_params = {'show': 'ta,ev'}


class OneBoxCatNearCat(OneBoxMap):
    default_autosuggest_query_params = {'show': 'ontologyDetails,expandedOntologies'}

    async def handle_key_strokes(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=OneBoxMap.default_headers) as session:

            find_ontology = None
            get_conjunction_mode = NearbySimpleParser(self.language).conjunction_mode_function()

            while True:
                query_text = await self.wait_for_new_key_stroke()
                if query_text is None:
                    break
                if query_text.strip() == '':
                    self.handle_empty_text_submission()
                    find_ontology = None
                    continue

                latitude, longitude = self.get_search_center()
                conjunction_mode, conjunction, query_tail = get_conjunction_mode(query_text)
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
                            print(f"LG call: {find_ontology['categories']} near {near_ontology['categories']}")
                            autosuggest_resp = await asyncio.ensure_future(self.api.autosuggest(
                                session,
                                query_text,
                                latitude,
                                longitude,
                                lang=self.get_language(),
                                limit=self.suggestions_limit,
                                termsLimit=self.terms_limit,
                                **self.autosuggest_query_params))
                            ontology_near_ontology = {"title": f"{find_ontology['title']} {conjunction} {near_ontology['title']}",
                                                      "id": f"{find_ontology['id']}:near:{near_ontology['id']}",
                                                      "resultType": "categoryQuery",
                                                      "href": f"{base_url[Endpoint.DISCOVER]}?at={latitude},{longitude}&lang={self.get_language()}&q={query_text}",
                                                      "highlights": {}}
                            autosuggest_resp.data["items"] = ([ontology_near_ontology] + autosuggest_resp.data["items"])[:OneBoxMap.default_results_limit]
                            if near_resp.data["queryTerms"]:
                                autosuggest_resp.data["queryTerms"] = ([{"term": near_resp.data["queryTerms"][0]["term"]}] + autosuggest_resp.data["queryTerms"])[:OneBoxMap.default_terms_limit]

                self.handle_suggestion_list(autosuggest_resp)

    async def get_first_category_ontology(self, session: ClientSession,
                                          query: str, latitude: float, longitude: float) -> Tuple[Response, dict]:
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
        