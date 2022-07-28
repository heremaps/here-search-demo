from IPython.display import display as Idisplay
from ipywidgets import Output
import nest_asyncio

from here_search.base import OneBoxBase
from here_search.user import Profile
from here_search.entities import Response

from .query import SubmittableTextBox, TermsButtons, NearbySimpleParser
from .response import SearchFeatureCollection, SearchResultButtons, PositionMap, SearchResultJson, SearchResultRadioButtons
import here_search.widgets.design as design

from typing import Callable, ClassVar, Awaitable
import asyncio
import logging


class OutputWidgetHandler(logging.Handler):
    """ Custom logging handler sending logs to an output widget """

    def __init__(self, *args, **kwargs):
        super(OutputWidgetHandler, self).__init__(*args, **kwargs)
        layout = {
            'width': '100%',
            'height': '160px',
            'border': '1px solid black'
        }
        self.out = Output(layout=layout)

    def emit(self, record):
        """ Overload of logging.Handler method """
        formatted_record = self.format(record)
        new_output = {
            'name': 'stdout',
            'output_type': 'stream',
            'text': formatted_record+'\n'
        }
        self.out.outputs = (new_output, ) + self.out.outputs

    def show_logs(self):
        """ Show the logs """
        Idisplay(self.out)

    def clear_logs(self):
        """ Clear the current logs """
        self.out.clear_output()


class OneBoxMap(OneBoxBase):

    default_results_limit = 10
    default_suggestions_limit = 5
    default_terms_limit = 3
    minimum_zoom_level = 11
    default_search_box_layout = {'width': '240px'}
    default_placeholder = "free text"
    default_output_format = 'text'
    default_design = design.EmbeddedList

    def __init__(self,
                 user_profile: Profile,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 design: Callable=None,
                 **kwargs):

        self.result_queue: asyncio.Queue = asyncio.Queue()
        OneBoxBase.__init__(self,
                            user_profile,
                            results_limit=results_limit or OneBoxMap.default_results_limit,
                            suggestions_limit=suggestions_limit or OneBoxMap.default_suggestions_limit,
                            terms_limit=terms_limit or OneBoxMap.default_terms_limit,
                            result_queue=self.result_queue, **kwargs)

        self.query_box_w = SubmittableTextBox(layout=kwargs.pop('layout', self.__class__.default_search_box_layout),
                                              placeholder=kwargs.pop('placeholder', self.__class__.default_placeholder),
                                              **kwargs)
        self.query_terms_w = TermsButtons(self.query_box_w, buttons_count=self.__class__.default_terms_limit)
        self.result_points_w: SearchFeatureCollection = None
        self.design = design or self.__class__.default_design
        self.map_w = None
        self.app_design_w = None

        self.result_list_w = [out_class(widget=Output(),
                                        max_results_number=max(self.results_limit, self.suggestions_limit),
                                        result_queue=self.result_queue)
                              for out_class in self.design.out_classes]

    def get_search_center(self):
        return self.latitude, self.longitude

    def search_center_observer(self):
        def observe(change):
            if change.type == "change":
                if change.name in "center":
                    self.latitude, self.longitude = change.new[:2]
                elif change.name == "zoom":
                    self.latitude, self.longitude = self.map_w.center
        return observe

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
        for result_list_w in self.result_list_w:
            result_list_w.display(discover_resp)
        self.display_result_map(discover_resp, update_search_center=True)
        self.clear_query_text()
        self.renew_session_id()

    def handle_result_details(self, lookup_resp: Response):
        """
        Typically called by OneBoxBase.handle_result_selections()
        :param autosuggest_resp:
        :return: None
        """
        if len(self.result_list_w) > 1:
            self.result_list_w[1].display(lookup_resp)
        lookup_resp.data = {"items": [lookup_resp.data]}
        self.display_result_map(lookup_resp, update_search_center=True)

    def display_terms(self, autosuggest_resp: Response):
        terms = [term['term'] for term in autosuggest_resp.data.get('queryTerms', [])]
        self.query_terms_w.set(terms)

    def display_suggestions(self, autosuggest_resp: Response) -> None:
        for result_list_w in self.result_list_w:
            result_list_w.display(autosuggest_resp)

        search_feature = SearchFeatureCollection(autosuggest_resp)
        if search_feature.bbox:
            if self.result_points_w:
                self.map_w.remove_layer(self.result_points_w)
            self.result_points_w = search_feature
            self.map_w.add_layer(self.result_points_w)
        #self.display_result_map(autosuggest_resp, update_search_center=False)

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
            self.latitude, self.longitude = self.map_w.center

    async def __ainit_map(self):
        self.map_w = PositionMap(api_key=self.api.api_key, center=[self.latitude, self.longitude], position_handler=self.search_center_observer())
        self.app_design_w = self.design.widget(self.query_box_w, self.map_w, self.query_terms_w, self.result_list_w)

    @staticmethod
    def show_logs() -> None:
        logger = logging.getLogger("here_search")
        handler = OutputWidgetHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        handler.show_logs()

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
        loop.run_until_complete(self.__ainit_map())
        Idisplay(self.app_design_w)

        OneBoxBase.run(self,
                       handle_user_profile_setup,
                       handle_key_strokes or self.handle_key_strokes,
                       handle_text_submissions or self.handle_text_submissions,
                       handle_result_selections or self.handle_result_selections)
