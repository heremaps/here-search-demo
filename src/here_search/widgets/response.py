import panel
from panel.pane import JSON as IJSON
from IPython.display import display as Idisplay, Markdown
from ipywidgets import Widget, HBox, VBox, Button, RadioButtons, Output, SelectMultiple, Label, HTML, Layout

from here_map_widget import GeoJSON

from here_search.entities import Response, ResponseItem, Endpoint

from typing import Tuple, List
from dataclasses import dataclass
import asyncio


panel.extension()


@dataclass
class SearchResultList(HBox):
    widget: Widget
    max_results_number: int
    result_queue: asyncio.Queue=None
    layout: dict=None

    default_layout = {'display': 'flex', 'width': '276px', 'height': '400px', 'justify_content': 'flex-start', 'overflow_y': 'scroll', 'overflow': 'scroll'}

    def __post_init__(self):
        if self.layout is None:
            self.layout = self.__class__.default_layout
        VBox.__init__(self, [self.widget])
        self.futures = []

    @classmethod
    def get_primary_category(cls, place_item):
        primary_category = [c for c in place_item.get("categories", []) if c.get("primary")][0]
        category_id = primary_category["id"]
        category_name = primary_category["name"]
        return category_id, category_name

    @classmethod
    def get_www(cls, place_item, category_id) -> str:
        for contact in place_item["contacts"]:
            for www in contact.get("www", []):
                for category in www.get("categories", []):
                    if category_id == category["id"]:
                        return www["value"]
        else:
            for contact in place_item["contacts"]:
                for www in contact.get("www", []):
                    return www["value"]
            else:
                return None

    @classmethod
    def get_image(cls, place_item) -> str:
        return place_item["media"]["images"]["items"][0]["href"]

    def _display(self, resp: Response) -> Widget:
        out = Output(layout=self.layout)
        text = ['| | |', '|:-|:-|']
        for i, item in enumerate(resp.data["items"]):
            if "contacts" in item:
                category_id, category_name = self.get_primary_category(item)
                www = self.get_www(item, category_id)
                title = f"**[{item['title']}]({www})**" if www else f"**{item['title']}**"
            else:
                title = f"**{item['title']}**"
            text.append(f"| <font size='1px'>{i: <2}</font> | <font size='1px'>{title}</font> |")
            if item["resultType"] in ("categoryQuery", "chainQuery"):
                text.append(f"| | <font size='1px'><sup>{item['resultType']}</sup></font> |")
            elif item["resultType"] == 'place':
                address = item['address']['label'].partition(', ')[-1]
                text.append(f"| | <font size='1px'><sup>{address}</sup></font> |")
                if "media" in item and "images" in item["media"]:
                    text.append(f'| | <img src="{item["media"]["images"]["items"][0]["href"]}" width="32" height="32"/> |')
        out.append_display_data(Markdown("\n".join(text)))
        return out

    def _clear(self):
        return Output(layout=self.layout)

    def display(self, resp: Response):
        # https://stackoverflow.com/questions/66704546/why-cannot-i-print-in-jupyter-lab-using-ipywidgets-class
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
        out = self._clear()
        out.append_display_data(IJSON({"data": resp.data, "x_headers": resp.x_headers,
                                            "request": {"url": resp.req.url,
                                                        "params": resp.req.params,
                                                        "x_headers": resp.req.x_headers}},
                                            height=600, theme="light", depth=4))
        return out

    def _clear(self) -> Widget:
        return Output(layout=self.layout)


class SearchResultSelectMultiple(SearchResultList):
    def _display(self, resp: Response) -> Widget:
        return SelectMultiple(options=[item["title"] for item in resp.data["items"]],
                              rows=len(resp["items"]),
                              disabled=False)


class SearchResultButton(HBox):
    default_layout = {'display': 'flex', 'width': '270px', 'justify_content': 'flex-start', 'height': '24px', 'min_height': '24px', 'overflow': 'visible'}

    def __init__(self, item: ResponseItem, **kvargs):
        self.label = Label(value='', layout={'width': '20px'})
        # TODO: create a class derived from Both Button and ResponseItem
        self.button = Button(description='',  icon='',
                             layout=Layout(display='flex', justify_content='flex-start', height='24px', min_height='24px', width='270px')
                             )
        self.button.value = item
        if item.data is not None:
            self.set_result(item.data, item.rank, item.resp)
        HBox.__init__(self, [self.label, self.button], layout=Layout(**kvargs.pop('layout', self.__class__.default_layout)), **kvargs)
        self.add_class('result-button')

    def set_result(self, data: dict, rank: int, resp: Response):
        self.button.value = ResponseItem(data=data, rank=rank or 0, resp=resp)
        self.button.description = data["title"]
        self.label.value = f'{self.button.value.rank+1: <2}'
        self.button.icon = 'search' if "Query" in data["resultType"] else '' # That's a hack...


class SearchResultButtons(SearchResultList):
    buttons: List[SearchResultButton] = []
    default_layout = {'display': 'flex', 'width': '276px', 'height': '400px', 'justify_content': 'flex-start', 'overflow': 'auto'}

    def __post_init__(self):
        for i in range(self.max_results_number):
            search_result = SearchResultButton(item=ResponseItem())
            def getvalue(button: Button):
                self.result_queue.put_nowait(button.value)
            search_result.button.on_click(getvalue)
            self.buttons.append(search_result)
        Idisplay(HTML("<style>.result-button div, .result-button button { font-size: 10px; }</style>"))
        super().__post_init__()

    def _display(self, resp: Response) -> Widget:
        items = [resp.data] if resp.req.endpoint == Endpoint.LOOKUP else resp.data["items"]
        for rank, item_data in enumerate(items):
            self.buttons[rank].set_result(item_data, rank, resp)
        out = self.buttons[:len(items)]
        return VBox(out, layout=Layout(**self.layout))

    def _clear(self) -> Widget:
        return VBox([])


class SearchResultRadioButtons(SearchResultList):
    css_displayed = False

    def __post_init__(self):
        if not SearchResultButtons.css_displayed:
            Idisplay(HTML("<style>.result-radio label { font-size: 10px; }</style>"))
            SearchResultButtons.css_displayed = True
        super().__post_init__()

    def _display(self, resp: Response) -> Widget:
        buttons = RadioButtons(options=[item["title"] for item in resp.data["items"]],
                               disabled=False)
        buttons.add_class('result-radio')
        # TODO: create a class derived from RadioButtons, able to host an item (A SearchResultRadioButton class)
        return buttons


class SearchFeatureCollection(GeoJSON):
    bbox: Tuple[float, float, float, float]

    def __init__(self, resp: Response):
        collection = resp.geojson()
        bbox = resp.bbox()
        if bbox:
            bb_south, bb_west, bb_north, bb_east = collection["bbox"] = bbox
            height = bb_north-bb_south
            width = bb_east-bb_west
            self.bbox = (bb_south-height/8, bb_north+height/8, bb_east+width/8, bb_west-width/8)
        else:
            self.bbox = None

        GeoJSON.__init__(self, data=collection,
                         show_bubble=True,
                         point_style={
                             "strokeColor": "white",
                             "lineWidth": 1,
                             "fillColor": "blue",
                             "fillOpacity": 0.7,
                             "radius": 7}
                         )


