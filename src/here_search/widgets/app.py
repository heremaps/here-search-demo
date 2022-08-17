from IPython.display import display as Idisplay
from ipywidgets import Output
from flexpolyline import decode
from here_map_widget import LineString as LineStringW, Polyline as PolylineW, Polygon as PolygonW, GeoPolygon as GeoPolygonW
from geopandas import GeoSeries
from shapely.geometry import LineString
import nest_asyncio

from here_search.base import OneBoxBase
from here_search.user import Profile
from here_search.entities import Response

from .util import TableLogWidgetHandler
from .request import SubmittableTextBox, TermsButtons, OntologyBox, OntologyButton
from .response import SearchFeatureCollection, PositionMap
import here_search.widgets.design as design

from typing import Callable, Awaitable, Tuple
import asyncio
import logging


class OneBoxMap(OneBoxBase):

    default_results_limit = 20
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
                 ontology_buttons: Tuple[OntologyButton]=None,
                 extra_api_params: dict=None,
                 design: Callable=None,
                 **kwargs):

        self.result_queue: asyncio.Queue = asyncio.Queue()
        OneBoxBase.__init__(self,
                            user_profile,
                            results_limit=results_limit or OneBoxMap.default_results_limit,
                            suggestions_limit=suggestions_limit or OneBoxMap.default_suggestions_limit,
                            terms_limit=terms_limit or OneBoxMap.default_terms_limit,
                            extra_api_params=extra_api_params,
                            result_queue=self.result_queue, **kwargs)

        self.query_box_w = SubmittableTextBox(layout=kwargs.pop('layout', self.__class__.default_search_box_layout),
                                              placeholder=kwargs.pop('placeholder', self.__class__.default_placeholder),
                                              **kwargs)
        self.query_terms_w = TermsButtons(self.query_box_w, buttons_count=self.__class__.default_terms_limit)
        self.result_points_w: SearchFeatureCollection = None
        self.design = design or self.__class__.default_design
        self.buttons_box_w = OntologyBox(buttons=ontology_buttons) if ontology_buttons else None
        self.result_list_w = tuple(out_class(widget=Output(),
                                        max_results_number=max(self.results_limit, self.suggestions_limit),
                                        result_queue=self.result_queue)
                              for out_class in self.design.out_classes)

        self.log_handler = TableLogWidgetHandler()
        self.logger = logging.getLogger("here_search")

        # Below variable will be actually initialized in __ainit method.
        self.map_w = None
        self.app_design_w = None

    async def __ainit(self):
        """
        Initialisation of the asynchronous parts of OneBoxMap. Calls in OneBoxMap.run()
        :return:
        """
        self.map_w = PositionMap(api_key=self.api.api_key, center=[self.latitude, self.longitude], position_handler=self.search_center_observer())
        self.app_design_w = self.design.widget(self.query_box_w, self.map_w, self.query_terms_w, self.buttons_box_w, self.result_list_w)

    def get_search_center(self):
        return round(self.latitude, 5), round(self.longitude, 5)

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

    def wait_for_selected_shortcut(self) -> Awaitable:
        if self.buttons_box_w:
            return self.buttons_box_w.get_ontology_future()
        else:
            return asyncio.Future()

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
        self.query_box_w.text_w.value = ''
        self.query_terms_w.set([])

    def display_result_map(self, resp: Response, update_search_center: bool=False):
        if self.result_points_w:
            self.map_w.remove_layer(self.result_points_w)

        self.result_points_w = SearchFeatureCollection(resp)
        self.map_w.add_layer(self.result_points_w)
        route_pg = self._get_route_polygon(resp)
        if route_pg:
            self.map_w.add_object(route_pg)
        if self.result_points_w.bbox:
            self.map_w.bounds = self.result_points_w.bbox
            if len(resp.data["items"]) == 1:
                self.map_w.zoom = OneBoxMap.minimum_zoom_level
            self.latitude, self.longitude = self.map_w.center

    def _get_route_polyline(self, resp: Response) -> PolylineW:
        if "route" in resp.req.params:
            encoded = resp.req.params["route"][0].split(";")[0]
            points = [p for ps in decode(encoded) for p in [ps[0], ps[1], 0]]
            ls = LineStringW(points=points)
            pl = PolylineW(object=ls, style={"lineWidth": 3})
            return pl

    def _get_route_polygon(self, resp: Response) -> PolygonW:
        if "route" in resp.req.params:
            encoded_width = resp.req.params["route"][0].split(";")
            encoded = encoded_width[0]
            width = int(encoded_width[1].split("=")[1]) if len(encoded_width) > 1 else 1000
            points = [ps[:2] for ps in decode(encoded)]
            gs = GeoSeries(LineString(points), crs = "epsg:4326")
            pg = gs.to_crs("epsg:3174").buffer(width).to_crs("epsg:4326")
            l = [p for ps in pg.exterior.tolist()[0].coords for p in [ps[0], ps[1], 0]]
            return PolygonW(object=GeoPolygonW(linestring=LineStringW(points=l)), style={"lineWidth": 3}, draggable=False)

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
            handle_shortcut_selections: Callable=None):

        nest_asyncio.apply()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        loop.run_until_complete(self.__ainit())
        Idisplay(self.app_design_w)
        self.show_logs()
        OneBoxBase.run(self,
                       handle_user_profile_setup,
                       handle_key_strokes or self.handle_key_strokes,
                       handle_text_submissions or self.handle_text_submissions,
                       handle_result_selections or self.handle_result_selections,
                       handle_shortcut_selections or self.handle_shortcut_selections)

    def __del__(self):
        self.logger.removeHandler(self.log_handler)
