from IPython.display import display as Idisplay
from ipywidgets import Output

from search.core import OneBoxBase
from .query import SubmittableTextBox, TermsButtons
from .response import SearchFeatureCollection, SearchResultButtons, PositionMap, SearchResultJson
from .design import Design

from typing import Callable, ClassVar


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
            tokens = self.text.value.strip().split(' ')
            if tokens:
                head = tokens[:-1]
                head.extend([button.description.strip(), ''])
                self.text.value = ' '.join(head)
        return on_terms_click_handler

    def get_search_center(self):
        return self.map_w.center

    def display_terms(self, autosuggest_resp: dict):
        self.query_terms_w.set([term['term'] for term in autosuggest_resp.get('queryTerms', [])])

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

    def run(self):
        Idisplay(self.app_design_w)
        OneBoxBase.run(self)


class OneBoxMapCI(OneBoxMap):
    as_url = 'http://ci.opensearch.dev.api.here.com/v1/autosuggest'
    ds_url = 'http://ci.opensearch.dev.api.here.com/v1/discover'
    default_autosuggest_query_params = {'show': 'details,expandedOntologies'}
    default_discover_query_params = {'show': 'ta,ev'}