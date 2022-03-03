from IPython.display import display as Idisplay
from ipywidgets import Output
from aiohttp import ClientSession

from search.core import OneBoxBase
from .query import SubmittableTextBox, TermsButtons
from .response import SearchFeatureCollection, SearchResultButtons, PositionMap, SearchResultJson, SearchResultRadioButtons
from .design import Design

from typing import Callable, ClassVar, Tuple
import asyncio

class OneBoxMap(SubmittableTextBox, OneBoxBase):
    default_results_limit = 10
    default_suggestions_limit = 5
    default_terms_limit = 3
    minimum_zoom_level = 11
    default_search_box_layout = {'width': '240px'}
    default_placeholder = "free text"
    default_output_format = 'text'
    default_resultlist_class = SearchResultButtons

    def __init__(self,
                 language: str,
                 latitude: float, longitude: float,
                 api_key: str=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 design: Callable=None,
                 resultlist_class: ClassVar=None,
                 autosuggest_automatic_recenter: bool=False,
                 **kwargs):

        SubmittableTextBox.__init__(self,
                                    layout=kwargs.pop('layout', self.__class__.default_search_box_layout),
                                    placeholder=kwargs.pop('placeholder', self.__class__.default_placeholder),
                                    **kwargs)

        OneBoxBase.__init__(self,
                            language=language,
                            api_key=api_key,
                            results_limit=results_limit or self.__class__.default_results_limit,
                            suggestions_limit=suggestions_limit or self.__class__.default_suggestions_limit,
                            terms_limit=terms_limit or self.__class__.default_terms_limit)

        self.result_points_w: SearchFeatureCollection = None

        self.query_terms_w = TermsButtons(self.__class__.default_terms_limit)
        self.query_terms_w.on_click(self.__get_terms_buttons_handler())

        self.map_w = PositionMap(api_key=self.api_key, center=[latitude, longitude])

        self.result_list_w = (resultlist_class or self.__class__.default_resultlist_class)(widget=Output(), result_queue=self.result_queue)

        self.app_design_w = (design or Design.two)(self, self.map_w, self.query_terms_w, self.result_list_w)

    def __get_terms_buttons_handler(self):
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
            self.query_terms_w.set([])
        return on_terms_click_handler

    def get_search_center(self):
        return self.map_w.center

    def display_terms(self, autosuggest_resp: dict):
        terms = [term['term'] for term in autosuggest_resp.get('queryTerms', [])]
        self.query_terms_w.set(terms)

    def display_suggestions(self, autosuggest_resp: dict) -> None:
        self.result_list_w.display(autosuggest_resp)

        search_feature = SearchFeatureCollection(autosuggest_resp)
        if search_feature.bbox:
            if self.result_points_w:
                self.map_w.remove_layer(self.result_points_w)
            self.result_points_w = search_feature
            self.map_w.add_layer(self.result_points_w)
        #self.display_result_map(autosuggest_resp, update_search_center=False)

    def handle_suggestion_list(self, autosuggest_resp):
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

    def handle_result_list(self, discover_resp):
        """
        Typically called by OneBoxBase.handle_text_submissions()
        :param autosuggest_resp:
        :return: None
        """
        self.result_list_w.display(discover_resp)
        self.display_result_map(discover_resp, update_search_center=True)
        self.clear_query_text()

    def handle_result_details(self, lookup_resp: dict):
        """
        Typically called by OneBoxBase.handle_result_selections()
        :param autosuggest_resp:
        :return: None
        """
        self.display_result_map({"items": [lookup_resp]}, update_search_center=True)

    def clear_query_text(self):
        self.text.value = ''
        self.query_terms_w.set([])

    def display_result_map(self, resp, update_search_center=False):
        if self.result_points_w:
            self.map_w.remove_layer(self.result_points_w)
        self.result_points_w = SearchFeatureCollection(resp)
        self.map_w.add_layer(self.result_points_w)
        if self.result_points_w.bbox:
            self.map_w.bounds = self.result_points_w.bbox
            if len(resp["items"]) == 1:
                self.map_w.zoom = OneBoxMap.minimum_zoom_level

    def run(self,
            handle_key_strokes: Callable=None,
            handle_text_submissions: Callable=None,
            handle_result_selections: Callable=None):
        Idisplay(self.app_design_w)
        OneBoxBase.run(self, self.handle_key_strokes, self.handle_text_submissions, self.handle_result_selections)


class OneBoxMapCI(OneBoxMap):
    as_url = 'http://ci.opensearch.dev.api.here.com/v1/autosuggest'
    ds_url = 'http://ci.opensearch.dev.api.here.com/v1/discover'
    default_autosuggest_query_params = {'show': 'details,expandedOntologies'}
    default_discover_query_params = {'show': 'ta,ev'}


class OneBoxExt(OneBoxMap):
    default_autosuggest_query_params = {'show': 'ontologyDetails,expandedOntologies'}

    def __init__(self,
                 language: str,
                 latitude: float, longitude: float,
                 api_key: str=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 design: Callable=None,
                 resultlist_class: ClassVar=None,
                 autosuggest_automatic_recenter: bool=False,
                 **kwargs):

        super().__init__(language, latitude, longitude, api_key,
                         results_limit, suggestions_limit, terms_limit,
                         design, resultlist_class, autosuggest_automatic_recenter, **kwargs)
        self.find_ontology = None
        self.find_query = None
        self.near_ontology = None
        self.near_query = None

    def parse_query(self, query: str) -> Tuple[int, str, str]:
        query_parts = query.split(' ')
        query_with_conjunction_head, _, query_with_conjunction_tail = query.partition(' near ')
        # 0: no conjunction
        # 1: conjunction first or followed by spaces
        # 2: conjunction last
        # 3: conjunction last, followed by spaces
        # 4: conjunction surrounded by tokens
        # 5: tokens followed by first letters of conjunction
        if len(query_parts) > 1 and query_parts[-1] == 'near':
            conjunction_mode = 2
        elif len(query_parts) > 1 and query_parts[-1] in ("n", "ne", "nea"):
            conjunction_mode = 5
        elif query_with_conjunction_head.strip() and query_with_conjunction_tail and not query_with_conjunction_tail.strip():
            conjunction_mode = 3
        elif query_with_conjunction_head.strip() and query_with_conjunction_tail.strip():
            conjunction_mode = 4
        elif query == 'near' or query.startswith('near '):
            conjunction_mode = 1
        else:
            conjunction_mode = 0
        return conjunction_mode, query_with_conjunction_head, query_with_conjunction_tail

    async def handle_key_strokes(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        params = {"show": 'details,expandedOntologies', "types": "categoryQuery,chainQuery,place,city,country"}
        out = Output()
        async with ClientSession(raise_for_status=True, headers=OneBoxMap.default_headers) as session:
            while True:
                q = await self.wait_for_new_key_stroke()
                if q is None:
                    break
                if q:

                    latitude, longitude = self.get_search_center()
                    autosuggest_resp = None
                    conjunction_mode, query_with_conjunction_head, query_with_conjunction_tail = self.parse_query(q)
                    if conjunction_mode == 5:
                        self.find_query = q
                        autosuggest_resp = await asyncio.ensure_future(self.autosuggest(session, q, latitude, longitude, **self.autosuggest_query_params))
                        if len(autosuggest_resp["items"]) > 0 and autosuggest_resp["items"][0]["resultType"] == "categoryQuery":
                            self.find_ontology = autosuggest_resp["items"][0]
                        else:
                            self.find_ontology = None
                        self.near_query = None
                        self.near_ontology = None
                        autosuggest_resp["queryTerms"] = ([{"term": "near"}] + autosuggest_resp["queryTerms"])[:OneBoxMap.default_terms_limit]
                    elif conjunction_mode == 4:
                        if self.find_query is None:
                            self.find_query = query_with_conjunction_head
                            find_resp = await asyncio.ensure_future(self.autosuggest(session, query_with_conjunction_head, latitude, longitude, **params))
                            if len(find_resp["items"]) > 0 and find_resp["items"][0]["resultType"] == "categoryQuery":
                                self.find_ontology = find_resp["items"][0]
                            else:
                                self.find_ontology = None

                        if self.find_ontology:
                            near_resp = await asyncio.ensure_future(self.autosuggest(session, query_with_conjunction_tail, latitude, longitude, **params))
                            if len(near_resp["items"]) > 0 and near_resp["items"][0]["resultType"] == "categoryQuery":
                                self.near_query = query_with_conjunction_tail
                                self.near_ontology = near_resp["items"][0]
                                # Replace the query below with the calls to Location Graph
                                autosuggest_resp = await asyncio.ensure_future(self.autosuggest(session, q, latitude, longitude, **self.autosuggest_query_params))
                                autosuggest_resp["items"] = ([{"title": f"{self.find_ontology['title']} near {near_resp['items'][0]['title']}",
                                                               "id": f"{self.find_ontology['id']}:near:{self.near_ontology['id']}",
                                                               "resultType": "categoryQuery",
                                                               "href": f"{self.__class__.ds_url}?at={latitude},{longitude}&lang={self.language}&q={q}",
                                                               "highlights": {}}] + autosuggest_resp["items"])[:OneBoxMap.default_results_limit]
                            else:
                                autosuggest_resp = await asyncio.ensure_future(self.autosuggest(session, q, latitude, longitude, **self.autosuggest_query_params))
                            if near_resp["queryTerms"]:
                                autosuggest_resp["queryTerms"] = ([{"term": near_resp["queryTerms"][0]["term"]}] + autosuggest_resp["queryTerms"])[:OneBoxMap.default_terms_limit]
                    elif q.endswith(' ') and self.find_ontology and conjunction_mode != 3:
                        self.find_query = q
                        autosuggest_resp = await asyncio.ensure_future(self.autosuggest(session, q, latitude, longitude, **self.autosuggest_query_params))
                        if len(autosuggest_resp["items"]) > 0 and autosuggest_resp["items"][0]["resultType"] == "categoryQuery":
                            self.find_ontology = autosuggest_resp["items"][0]
                        else:
                            self.find_ontology = None
                        self.near_query = None
                        self.near_ontology = None
                        autosuggest_resp["queryTerms"] = [{"term": "near"}]
                    else:
                        self.find_query = q
                        autosuggest_resp = await asyncio.ensure_future(self.autosuggest(session, q, latitude, longitude, **self.autosuggest_query_params))
                        if len(autosuggest_resp["items"]) > 0 and autosuggest_resp["items"][0]["resultType"] == "categoryQuery":
                            self.find_ontology = autosuggest_resp["items"][0]
                        else:
                            self.find_ontology = None
                        self.near_query = None
                        self.near_ontology = None

                    if autosuggest_resp is None:
                        autosuggest_resp = await asyncio.ensure_future(self.autosuggest(session, q, latitude, longitude, **self.autosuggest_query_params))

                    self.handle_suggestion_list(autosuggest_resp)

                if self.text.value.endswith("near "):
                    self.query_terms_w.set([])
                elif not self.text.value.strip():
                    self.query_terms_w.set([])

    def run(self):
        OneBoxMap.run(self, self.handle_key_strokes, self.handle_text_submissions, self.handle_result_selections)
        