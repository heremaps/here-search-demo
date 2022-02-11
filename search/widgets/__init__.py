from IPython.display import display as Idisplay, JSON as IJSON, Markdown, clear_output, display_markdown
from ipywidgets import HBox, VBox, Text, Button, Output, Layout
from ipywidgets.widgets.widget import CallbackDispatcher, Widget
from traitlets import observe

from here_map_widget import GeoJSON, WidgetControl
from here_map_widget import Platform, MapTile, TileLayer, Map
from here_map_widget import ServiceNames, MapTileUrl

from search.core import OneBoxBase

from typing import Callable, Tuple, List, Awaitable
from functools import reduce
import asyncio


class SubmittableText(Text):
    """A ipywidgets Text class enhanced with a on_submit() method"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._submission_callbacks = CallbackDispatcher()

    def on_submit(self, callback, remove=False):
        self._submission_callbacks.register_callback(callback, remove=remove)

    @observe('comm')
    def _comm_changed(self, change):
        if change['new'] is None:
            return
        self._model_id = self.model_id
        self.comm.on_msg(self.handle_msg)

    def handle_msg(self, msg):
        data = msg['content']['data']
        method = data['method']
        if method == 'update' and 'state' in data:
            state = data['state']
            if 'buffer_paths' in data:
                for buffer_path, buffer in zip(data['buffer_paths'], msg['buffers']):
                    reduce(dict.get, buffer_path, state)[buffer_path[-1]] = buffer
            self.set_state(state)
        elif method == 'request_state':
            self.send_state()
        elif method == 'custom' and 'content' in data and data['content'].get('event') == 'submit':
            self._submission_callbacks(self)


class SubmittableTextBox(HBox):
    """A ipywidgets HBox made of a SubmittableText and a lens Button"""
    default_icon = 'fa-search'
    default_button_width = '32px'

    def __init__(self, *args, **kwargs):
        self.lens = Button(icon=kwargs.pop('icon', SubmittableTextBox.default_icon),
                           layout={'width': SubmittableTextBox.default_button_width})
        self.text = SubmittableText(*args, layout=kwargs.pop('layout', Layout()), **kwargs)
        super().__init__([self.text, self.lens], **kwargs)

    def observe_text(self, *args):
        self.text.observe(*args)

    def unobserve_text(self, *args):
        self.text.unobserve(*args)

    def on_submit(self, callback, remove=False):
        self.text.on_submit(callback, remove=remove)

    def on_click(self, callback, remove=False):
        self.lens.on_click(callback, remove=remove)

    def disable(self):
        self.text.disabled = True
        self.lens.disabled = True

    def emable(self):
        self.text.disabled = False
        self.lens.disabled = False

    def wait_for_new_key_stroke(self) -> Awaitable:
        # This methods allows to control the call to the widget handler outside of the jupyter event loop
        future = asyncio.Future()
        def getvalue(change: dict):
            future.set_result(change.new)
            self.unobserve_text(getvalue, 'value')
            pass
        self.observe_text(getvalue, 'value')
        return future

    def wait_for_submitted_value(self) -> Awaitable:
        future = asyncio.Future()
        def getvalue(_):
            value = self.text.value
            future.set_result(value)
            self.on_submit(getvalue, remove=True)
            self.on_click(getvalue, remove=True)
        self.on_submit(getvalue)
        self.on_click(getvalue)
        return future


class SearchFeatureCollection(GeoJSON):
    bbox: Tuple[float, float, float, float]

    def __init__(self, results: dict):
        collection = {"type": "FeatureCollection", "features": []}
        latitudes, longitudes = [], []
        for item in results["items"]:
            if "position" not in item:
                continue
            longitude, latitude = item["position"]["lng"], item["position"]["lat"]
            latitudes.append(latitude)
            longitudes.append(longitude)
            categories = [c["name"] for c in item["categories"]
                          if c.get("primary")][0] if "categories" in item else None
            collection["features"].append({"type": "Feature",
                                           "geometry": {
                                               "type": "Point",
                                               "coordinates": [longitude, latitude]},
                                           "properties": {"title": item["title"],
                                                          "categories": categories}})
        if latitudes:
            south, west, north, east = min(latitudes), min(longitudes), max(latitudes), max(longitudes)
            collection["bbox"] = [south, west, north, east]
            height = north-south
            width = east-west
            self.bbox = (south-height/6, north+height/6, east+width/6, west-width/6)
            # [33.65, 49.46, 175.41, -109.68]
        else:
            self.bbox = None

        GeoJSON.__init__(self, data=collection,
                         show_bubble=True,
                         point_style={
                             "strokeColor": "white",
                             "lineWidth": 1,
                             "fillColor": "blue",
                             "fillOpacity": 0.7,
                             "radius": 5}
                         )


class TermsButtons(HBox):
    """A HBox containing a list of Buttons"""
    default_layout = {'width': '280px'}
    default_buttons_count = 3

    def __init__(self, buttons_count: int=None, layout: dict=None):
        if not isinstance(buttons_count, int):
            buttons_count = TermsButtons.default_buttons_count
        width = int(100/buttons_count)
        box_layout = Layout(display="flex", justify_content="center", width=f"{width}%", border="solid 1px")
        buttons = []
        for i in range(buttons_count):
            button = Button(layout=box_layout)
            buttons.append(button)
        HBox.__init__(self, buttons, layout=layout or TermsButtons.default_layout)

    def on_click(self, handler):
        for button in self.children:
            button.on_click(handler)

    def set(self, values: list[str]):
        for i, button in enumerate(self.children):
            try:
                button.description = values[i]
            except IndexError:
                button.description = ' '


class SearchTermsBox(VBox):
    def __init__(self, text: "SubmittableTextBox", terms_buttons: TermsButtons):
        self.text = text
        self.terms_buttons = terms_buttons
        VBox.__init__(self, [text, terms_buttons])


class PositionMap(Map):
    default_zoom_level = 12
    default_layout = {'height': '700px'}

    def __init__(self, api_key: str,
                 center: List[float],
                 position_handler: Callable[[float, float], None]=None,
                 **kvargs):

        platform = Platform(api_key=api_key, services_config={
            ServiceNames.maptile: {
                MapTileUrl.scheme: "https",
                MapTileUrl.host: "maps.ls.hereapi.com",
                MapTileUrl.path: "maptile/2.1",
            }
        })
        map_tile = MapTile(
            tile_type="maptile",
            scheme="normal.day",
            tile_size=256,
            format="png",
            platform=platform
        )
        maptile_layer = TileLayer(provider=map_tile, style={"max": 22})
        Map.__init__(self,
                     api_key=api_key,
                     center=center,
                     zoom=kvargs.pop('zoom', PositionMap.default_zoom_level),
                     basemap=maptile_layer,
                     layout = kvargs.pop('layout', PositionMap.default_layout))
        if position_handler:
            self.set_position_handler(position_handler)

    def set_position_handler(self, position_handler: Callable[[float, float], None]):
        def observe(change):
            if change.type == "change": # TODO: test if this test is necessary
                if change.name in "center":
                    position_handler(*change.new[:2])
                elif change.name == "zoom":
                    position_handler(*self.center)
        self.observe(observe)


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


class OneBoxMap(SubmittableTextBox, OneBoxBase):
    default_results_limit = 10
    default_suggestions_limit = 5
    default_terms_limit = 3
    minimum_zoom_level = 11
    default_search_box_layout = {'width': '240px'}
    default_placeholder = "free text"
    default_output_format = 'text'

    def __init__(self,
                 language: str,
                 latitude: float, longitude: float,
                 api_key: str=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 design: Callable=None,
                 output_format: str=None,
                 autosuggest_automatic_recenter: bool=False,
                 **kwargs):

        SubmittableTextBox.__init__(self,
                                    layout=kwargs.pop('layout', OneBoxMap.default_search_box_layout),
                                    placeholder=kwargs.pop('placeholder', OneBoxMap.default_placeholder),
                                    **kwargs)

        OneBoxBase.__init__(self,
                            language=language,
                            api_key=api_key,
                            results_limit=results_limit or OneBoxMap.default_results_limit,
                            suggestions_limit=suggestions_limit or OneBoxMap.default_suggestions_limit,
                            terms_limit=terms_limit or OneBoxMap.default_terms_limit)

        self.layer = None
        self.query_terms = TermsButtons(OneBoxMap.default_terms_limit)
        self.query_terms.on_click(self.__get_terms_buttons_handler())
        self.map = PositionMap(api_key=self.api_key, center=[latitude, longitude])
        self.out_layout = {'display': 'flex', 'width': '276px', 'justify_content': 'flex-start'}
        self.out = VBox([Output(layout=self.out_layout)])
        self.design = (design or Design.two)(self, self.map, self.query_terms, self.out)
        self.output_format = output_format or OneBoxMap.default_output_format

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
        return self.map.center

    def display_terms(self, autosuggest_resp):
        self.query_terms.set([term['term'] for term in autosuggest_resp.get('queryTerms', [])])

    def display_suggestions(self, autosuggest_resp):
        self.display_result_list(autosuggest_resp)

        search_feature = SearchFeatureCollection(autosuggest_resp)
        if search_feature.bbox:
            if self.layer:
                self.map.remove_layer(self.layer)
            self.layer = search_feature
            self.map.add_layer(self.layer)
        #self.display_result_map(autosuggest_resp, update_search_center=False)

        self.display_terms(autosuggest_resp)

    def display_results(self, discover_resp):
        self.display_result_list(discover_resp)
        self.display_result_map(discover_resp, update_search_center=True)
        self.clear_query_text()

    def clear_query_text(self):
        self.text.value = ''
        self.query_terms.set([])

    def display_result_map(self, resp, update_search_center=False):
        if self.layer:
            self.map.remove_layer(self.layer)
        self.layer = SearchFeatureCollection(resp)
        self.map.add_layer(self.layer)
        if self.layer.bbox:
            self.map.bounds = self.layer.bbox
            if len(resp["items"]) == 1:
                self.map.zoom = OneBoxMap.minimum_zoom_level

    @staticmethod
    def get_primary_category(place_item):
        primary_category = [c for c in place_item.get("categories", []) if c.get("primary")][0]
        category_id = primary_category["id"]
        category_name = primary_category["name"]
        return category_id, category_name

    @staticmethod
    def get_www(place_item, category_id) -> str:
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

    def display_result_list(self, resp):
        # https://stackoverflow.com/questions/66704546/why-cannot-i-print-in-jupyter-lab-using-ipywidgets-class
        old_out = self.out.children[0]
        out = Output(layout=self.out_layout)
        if self.output_format == 'json':
            out.append_display_data(IJSON(data=resp, expanded=False, root='response'))
        else:
            text = ['| | |', '|:-|:-|']
            for i, item in enumerate(resp["items"]):
                if "contacts" in item:
                    category_id, category_name = OneBoxMap.get_primary_category(item)
                    www = OneBoxMap.get_www(item, category_id)
                    title = f"**[{item['title']}]({www})**" if www else f"**{item['title']}**"
                else:
                    title = f"**{item['title']}**"
                text.append(f"| <font size='1px'>{i: <2}</font> | <font size='1px'>{title}</font> |")
                if item["resultType"] in ("categoryQuery", "chainQuery"):
                    text.append(f"| | <font size='1px'><sup>{item['resultType']}</sup></font> |")
                elif item["resultType"] == 'place':
                    address = item['address']['label'].partition(', ')[-1]
                    text.append(f"| | <font size='1px'><sup>{address}</sup></font> |")
            out.append_display_data(Markdown("\n".join(text)))
        self.out.children = [out]
        old_out.close()

    def run(self):
        Idisplay(self.design)
        OneBoxBase.run(self)