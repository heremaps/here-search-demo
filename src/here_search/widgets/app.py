from IPython.display import display as Idisplay
from ipywidgets import Output
import nest_asyncio

from here_search.base import OneBoxBase
from here_search.user import Profile
from here_search.entities import Response, PlaceTaxonomyExample

from .util import TableLogWidgetHandler
from .request import SubmittableTextBox, TermsButtons, PlaceTaxonomyButtons
from .response import FeatureCollection, ResponseMap
import here_search.widgets.design as design

from typing import Callable, Awaitable
import asyncio
import logging


class OneBoxMap(OneBoxBase):

    default_results_limit = 20
    default_suggestions_limit = 5
    default_terms_limit = 3
    default_search_box_layout = {'width': '240px'}
    default_placeholder = "free text"
    default_output_format = 'text'
    default_design = design.EmbeddedList
    default_taxonomy, default_icons = PlaceTaxonomyExample.taxonomy, PlaceTaxonomyExample.icons

    def __init__(self,
                 user_profile: Profile=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 place_taxonomy_buttons: PlaceTaxonomyButtons=None,
                 extra_api_params: dict=None,
                 design: Callable=None,
                 **kwargs):

        self.logger = logging.getLogger("here_search")
        self.result_queue: asyncio.Queue = asyncio.Queue()
        OneBoxBase.__init__(self,
                            user_profile=user_profile,
                            results_limit=results_limit or OneBoxMap.default_results_limit,
                            suggestions_limit=suggestions_limit or OneBoxMap.default_suggestions_limit,
                            terms_limit=terms_limit or OneBoxMap.default_terms_limit,
                            extra_api_params=extra_api_params,
                            result_queue=self.result_queue, **kwargs)

        self.query_box_w = SubmittableTextBox(layout=kwargs.pop('layout', self.__class__.default_search_box_layout),
                                              placeholder=kwargs.pop('placeholder', self.__class__.default_placeholder),
                                              **kwargs)
        self.query_terms_w = TermsButtons(self.query_box_w, buttons_count=self.__class__.default_terms_limit)
        self.design = design or self.__class__.default_design
        self.buttons_box_w = place_taxonomy_buttons or PlaceTaxonomyButtons(taxonomy=OneBoxMap.default_taxonomy, icons=OneBoxMap.default_icons)
        self.result_list_w = tuple(out_class(widget=Output(),
                                             max_results_number=max(self.results_limit, self.suggestions_limit),
                                             result_queue=self.result_queue)
                              for out_class in self.design.out_classes)

        self.log_handler = TableLogWidgetHandler()
        self.map_w = ResponseMap(api_key=self.api.api_key, center=self.search_center, position_handler=self.set_search_center)
        self.app_design_w = self.design.widget(self.query_box_w, self.map_w, self.query_terms_w, self.buttons_box_w, self.result_list_w)

    def wait_for_text_extension(self) -> Awaitable:
        return self.query_box_w.get_text_change()

    def wait_for_text_submission(self) -> Awaitable:
        return self.query_box_w.get_text_submission()

    def wait_for_taxonomy_selection(self) -> Awaitable:
        return self.buttons_box_w.get_taxonomy_item()

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
        Displays a results list in various widgets
        Typically called by OneBoxBase.handle_text_submissions()
        :param autosuggest_resp:
        :return: None
        """
        for result_list_w in self.result_list_w:
            result_list_w.display(discover_resp)
        self.display_result_map(discover_resp)
        self.clear_query_text()

    def handle_result_details(self, lookup_resp: Response):
        """
        Typically called by OneBoxBase.handle_result_selections()
        :param autosuggest_resp:
        :return: None
        """
        if len(self.result_list_w) > 1:
            self.result_list_w[1].display(lookup_resp)
        lookup_resp.data = {"items": [lookup_resp.data]}
        self.display_result_map(lookup_resp)

    def display_terms(self, autosuggest_resp: Response):
        terms = {term['term']: None for term in autosuggest_resp.data.get('queryTerms', [])}
        self.query_terms_w.set(list(terms.keys()))

    def display_suggestions(self, autosuggest_resp: Response) -> None:
        for result_list_w in self.result_list_w:
            result_list_w.display(autosuggest_resp)

    def clear_query_text(self):
        self.query_box_w.text_w.value = ''
        self.query_terms_w.set([])

    def display_result_map(self, resp: Response):
        self.map_w.display(resp)

    def show_logs(self, level: int=None) -> "OneBoxMap":
        self.logger.addHandler(self.log_handler)
        self.logger.setLevel(level or logging.INFO)
        self.log_handler.show_logs()
        return self

    def clear_logs(self):
        self.logger.removeHandler(self.log_handler)
        self.log_handler.clear_logs()
        self.log_handler.close()

    def run(self,
            handle_user_profile_setup: Callable=None,
            handle_key_strokes: Callable=None,
            handle_text_submissions: Callable=None,
            handle_result_selections: Callable=None,
            handle_taxonomy_selections: Callable=None):

        nest_asyncio.apply()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        Idisplay(self.app_design_w)
        OneBoxBase.run(self,
                       handle_user_profile_setup,
                       handle_key_strokes or self.handle_key_strokes,
                       handle_text_submissions or self.handle_text_submissions,
                       handle_result_selections or self.handle_result_selections,
                       handle_taxonomy_selections or self.handle_taxonomy_selections)
        self.show_logs()

    def __del__(self):
        self.logger.removeHandler(self.log_handler)
