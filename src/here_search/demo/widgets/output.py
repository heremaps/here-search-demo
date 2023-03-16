###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from ipyleaflet import GeoJSON, wait_for_change
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

from here_search.demo.entity.request import Response, ResponseItem, QuerySuggestionItem, LocationSuggestionItem
from here_search.demo.entity.endpoint import Endpoint
from here_search.demo.entity.intent import MoreDetailsIntent
from .input import PositionMap

from typing import List, Tuple
import asyncio

Idisplay(
    HTML(
        "<style>.result-button div, .result-button button { font-size: 10px; }</style>"
    )
)

BoundsType = Tuple[Tuple[float, float], Tuple[float, float]]


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
        data = resp.data
        if resp.x_headers:
            data["_x_headers"] = resp.x_headers
        out.append_display_data(IJSON(data, expanded=True))
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
        # TODO: create a class derived from Both Button and ResponseItem
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
        self.button.icon = ""
        if resp.req.endpoint == Endpoint.AUTOSUGGEST:
            if data["resultType"] in ("categoryQuery", "chainQuery"):  # That's a hack...
                self.button.value = QuerySuggestionItem(data=data, rank=rank or 0, resp=resp)
                self.button.icon = "search"
            else:
                self.button.value = LocationSuggestionItem(data=data, rank=rank or 0, resp=resp)
        else:
            self.button.value = ResponseItem(data=data, rank=rank or 0, resp=resp)
        self.button.description = data["title"]
        self.label.value = f"{self.button.value.rank+1: <2}"


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
    maximum_zoom_level = 18
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

    def fit_bounds2(self, bounds: BoundsType) -> asyncio.Task:
        """
        Sets a map view that contains the given geographical bounds
        with the maximum zoom level possible.
        :param bounds: Pair of Pair of floats ((south_lat, west_lon), (north_lat, east_lon))
        :return: asyncio Task
        """
        return asyncio.ensure_future(self._fit_bounds(bounds))

    async def _fit_bounds2(self, bounds: BoundsType):
        (b_south, b_west), (b_north, b_east) = bounds

        self.center = (b_south + b_north) / 2, (b_east + b_west) / 2
        self.zoom = 1
        await wait_for_change(self, 'bounds')

        fit = False
        while not fit or self.zoom <= 0.0:
            if self.zoom == ResponseMap.maximum_zoom_level:
                break
            (map_south, map_west), (map_north, map_east) = self.bounds
            if map_south-b_south < 0 and map_north-b_north > 0 and map_west-b_west < 0 and map_east-b_east > 0:
                self.zoom += 1
            else:
                self.zoom -= 1
                fit = True
            await wait_for_change(self, 'bounds')

    def display(self, resp: Response, fit: bool=False):
        if self.collection:
            self.remove(self.collection)
            self.collection = None
        bbox = resp.bbox()
        if bbox:
            self.collection = GeoJSON(
                data=resp.geojson(),
                show_bubble=True,
                point_style=ResponseMap.default_point_style,
            )
            self.add(self.collection)
            if fit and bbox[0] != bbox[1] and bbox[2] != bbox[3]:
                south, north, east, west = bbox
                height = north - south
                width = east - west
                bounds = ((south - height / 8, west - width / 8), (north + height / 8, east + width / 8))
                self.fit_bounds(bounds)


