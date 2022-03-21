from ipywidgets import HBox, VBox, Widget
from here_map_widget import WidgetControl

from .query import SubmittableTextBox, TermsButtons
from .response import PositionMap, SearchResultButtons, SearchResultJson

from typing import List


class Design:
    out_classes = []
    @staticmethod
    def widget(query_text: SubmittableTextBox,
               map: PositionMap,
               terms: TermsButtons,
               out: List[HBox]) -> Widget:
        raise NotImplementedError()


class EmbeddedList(Design):
    out_classes = [SearchResultButtons]
    @staticmethod
    def widget(query_text: SubmittableTextBox,
            map: PositionMap,
            terms: TermsButtons,
            out: List[HBox]) -> Widget:
        """Map with an embedded search form and clickable result list"""
        search_box = VBox([query_text, terms, out[0]], layout={'width': "280px"})
        widget_control = WidgetControl(widget=search_box, alignment="TOP_LEFT", name="search", transparent_bg=False)
        map.add_control(widget_control)
        map.zoom_control_instance.alignment = "RIGHT_TOP"
        return map


class Leftist(Design):
    out_classes = [SearchResultButtons]
    @staticmethod
    def widget(query_text: SubmittableTextBox,
            map: PositionMap,
            terms: TermsButtons,
            out: List[HBox]) -> Widget:
        """Map with a search form and clickable result list to its left side"""
        search_box = VBox([query_text, terms, out[0]])
        return HBox([search_box, map])


class MapJSON(Design):
    out_classes = [SearchResultButtons, SearchResultJson]
    @staticmethod
    def widget(query_text: SubmittableTextBox,
          map: PositionMap,
          terms: TermsButtons,
          out: List[HBox]) -> Widget:
        """Map with an embedded search form and clickable result list. The result list is duplicated as a JSON, on the right of the map"""
        search_box = VBox([query_text, terms, out[0]], layout={'width': "280px"})
        widget_control = WidgetControl(widget=search_box, alignment="TOP_LEFT", name="search", transparent_bg=False)
        map.add_control(widget_control)
        map.zoom_control_instance.alignment = "RIGHT_TOP"
        out[1].layout = {'width': "500px"}
        return HBox([map, out[1]])
