from ipywidgets import Box, HBox, VBox, Widget
from here_map_widget import WidgetControl

from .query import SubmittableTextBox, TermsButtons, OntologyBox
from .response import PositionMap, SearchResultButtons, SearchResultJson

from typing import List, Tuple


class Design:
    out_classes = []
    @staticmethod
    def widget(query_text: SubmittableTextBox,
               map: PositionMap,
               terms: TermsButtons,
               buttons: OntologyBox,
               out: Tuple[Box]) -> Widget:
        raise NotImplementedError()


class EmbeddedList(Design):
    out_classes = [SearchResultButtons]
    @staticmethod
    def widget(query_text: SubmittableTextBox,
            map: PositionMap,
            terms: TermsButtons,
            buttons: OntologyBox,
            out: Tuple[Box]) -> Widget:
        """Map with an embedded search form and clickable result list"""
        if buttons:
            search_box = VBox([buttons, query_text, terms, out[0]], layout={'width': "280px"})
        else:
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
            buttons: OntologyBox,
            out: Tuple[Box]) -> Widget:
        """Map with a search form and clickable result list to its left side"""
        if buttons:
            search_box = VBox([buttons, query_text, terms, out[0]])
        else:
            search_box = VBox([query_text, terms, out[0]])
        return HBox([search_box, map])


class MapJSON(Design):
    out_classes = [SearchResultButtons, SearchResultJson]
    @staticmethod
    def widget(query_text: SubmittableTextBox,
          map: PositionMap,
          terms: TermsButtons,
          buttons: OntologyBox,
          out: Tuple[Box]) -> Widget:
        """Map with an embedded search form and clickable result list. The result list is duplicated as a JSON, on the right of the map"""
        if buttons:
            search_box = VBox([buttons, query_text, terms, out[0]], layout={'width': "280px"})
        else:
            search_box = VBox([query_text, terms, out[0]], layout={'width': "280px"})
        widget_control = WidgetControl(widget=search_box, alignment="TOP_LEFT", name="search", transparent_bg=False)
        map.add_control(widget_control)
        map.zoom_control_instance.alignment = "RIGHT_TOP"
        out[1].layout = {'width': "500px"}
        return HBox([map, out[1]])
