from IPython.display import display as Idisplay, JSON as IJSON
from ipywidgets import (
    Widget,
    HBox,
    VBox,
    Button,
    Output,
    Label,
    HTML,
    Layout,
)

from here_map_widget import GeoJSON
from here_search.entity.request import Response, ResponseItem
from ..entity.endpoint import Endpoint
from here_search.entity.intent import MoreDetailsIntent
from .input import PositionMap

from typing import List
import asyncio

Idisplay(
    HTML(
        "<style>.result-button div, .result-button button { font-size: 10px; }</style>"
    )
)


class SearchResultList(HBox):
    default_layout = {
        "display": "flex",
        "width": "276px",
        "height": "400px",
        "justify_content": "flex-start",
        "overflow_y": "scroll",
        "overflow": "scroll",
    }
    default_max_results_count = 20

    def __init__(
        self,
        widget: Widget = None,
        max_results_number: int = None,
        queue: asyncio.Queue = None,
        layout: dict = None,
        **kwargs,
    ):
        self.widget = widget or Output()
        self.max_results_number = (
            max_results_number or type(self).default_max_results_count
        )
        self.queue = queue or asyncio.Queue()
        self.layout = layout or type(self).default_layout
        self.futures = []
        super().__init__([self.widget], **kwargs)

    def _display(self, resp: Response) -> Widget:
        raise NotImplementedError()

    def _clear(self):
        return Output(layout=self.layout)

    def display(self, resp: Response):
        # https://github.com/jupyterlab/jupyterlab/issues/3151#issuecomment-339476572
        old_out = self.children[0]
        out = self._display(resp)
        self.children = [out]
        old_out.close()

    def clear(self):
        old_out = self.children[0]
        out = self._clear()
        self.children = [out]
        old_out.close()


class SearchResultJson(SearchResultList):
    def _display(self, resp: Response) -> Widget:
        out: Output = self._clear()
        out.append_display_data(IJSON(resp.data, expanded=True))
        return out

    def _clear(self) -> Output:
        return Output(layout=self.layout)


class SearchResultButton(HBox):
    default_layout = {
        "display": "flex",
        "width": "270px",
        "justify_content": "flex-start",
        "height": "24px",
        "min_height": "24px",
        "overflow": "visible",
    }

    def __init__(self, item: ResponseItem, **kvargs):
        self.label = Label(value="", layout={"width": "20px"})
        self.button = Button(
            description="",
            icon="",
            layout=Layout(
                display="flex",
                justify_content="flex-start",
                height="24px",
                min_height="24px",
                width="270px",
            ),
        )
        self.button.value = item
        if item.data is not None:
            self.set_result(item.data, item.rank, item.resp)
        HBox.__init__(
            self,
            [self.label, self.button],
            layout=Layout(**kvargs.pop("layout", self.__class__.default_layout)),
            **kvargs,
        )
        self.add_class("result-button")

    def set_result(self, data: dict, rank: int, resp: Response):
        self.button.value = ResponseItem(data=data, rank=rank or 0, resp=resp)
        self.button.description = data["title"]
        self.label.value = f"{self.button.value.rank+1: <2}"
        self.button.icon = (
            "search" if "Query" in data["resultType"] else ""
        )  # That's a hack...


class SearchResultButtons(SearchResultList):
    buttons: List[SearchResultButton] = []
    default_layout = {
        "display": "flex",
        "width": "276px",
        "height": "400px",
        "justify_content": "flex-start",
        "overflow": "auto",
    }

    def __init__(
        self,
        widget: Widget = None,
        max_results_number: int = None,
        queue: asyncio.Queue = None,
        layout: dict = None,
        **kwargs,
    ):
        super().__init__(widget, max_results_number, queue, layout, **kwargs)
        for i in range(self.max_results_number):
            search_result = SearchResultButton(item=ResponseItem())

            def getvalue(button: Button):
                intent = MoreDetailsIntent(materialization=button.value)
                self.queue.put_nowait(intent)

            search_result.button.on_click(getvalue)
            self.buttons.append(search_result)

    def _display(self, resp: Response) -> Widget:
        items = (
            [resp.data]
            if resp.req.endpoint == Endpoint.LOOKUP
            else resp.data.get("items", [])
        )
        for rank, item_data in enumerate(items):
            self.buttons[rank].set_result(item_data, rank, resp)
        out = self.buttons[: len(items)]
        return VBox(out, layout=self.layout)

    def _clear(self) -> Widget:
        return VBox([])


class ResponseMap(PositionMap):
    minimum_zoom_level = 11
    default_point_style = {
        "strokeColor": "white",
        "lineWidth": 1,
        "fillColor": "blue",
        "fillOpacity": 0.7,
        "radius": 7,
    }

    def __init__(self, **kwargs):
        self.collection = None
        super().__init__(**kwargs)

    def display(self, resp: Response):
        if self.collection:
            self.remove_layer(self.collection)
        bbox = resp.bbox()
        if bbox:
            self.collection = GeoJSON(
                data=resp.geojson(),
                show_bubble=True,
                point_style=ResponseMap.default_point_style,
            )
            self.add_layer(self.collection)
            south, north, east, west = bbox
            height = north - south
            width = east - west
            # https://github.com/heremaps/here-map-widget-for-jupyter/issues/37
            self.bounds = (
                south - height / 8,
                north + height / 8,
                east + width / 8,
                west - width / 8,
            )
            if len(resp.data.get("items", [])) == 1:
                self.zoom = ResponseMap.minimum_zoom_level
