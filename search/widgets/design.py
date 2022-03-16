from ipywidgets import HBox, VBox, Widget
from here_map_widget import WidgetControl

from .query import SubmittableTextBox, TermsButtons
from .response import PositionMap


class Design(Widget):
    @classmethod
    def one(cls,
            query_text: SubmittableTextBox,
            map: PositionMap,
            terms: TermsButtons,
            out: HBox):
        search_box = VBox([query_text, terms])
        widget_control = WidgetControl(widget=search_box, alignment="TOP_LEFT", name="search", transparent_bg=False)
        map.add_control(widget_control)
        map.zoom_control_instance.alignment = "RIGHT_TOP"
        return HBox([map, out])

    @classmethod
    def two(self,
            query_text: SubmittableTextBox,
            map: PositionMap,
            terms: TermsButtons,
            out: HBox):
        search_box = VBox([query_text, terms, out])
        return HBox([search_box, map])

    @classmethod
    def three(cls,
              query_text: SubmittableTextBox,
              map: PositionMap,
              terms: TermsButtons,
              out: HBox):
        search_box = VBox([query_text, terms, out], layout={'width': "280px"})
        widget_control = WidgetControl(widget=search_box, alignment="TOP_LEFT", name="search", transparent_bg=False)
        map.add_control(widget_control)
        map.zoom_control_instance.alignment = "RIGHT_TOP"
        return map
