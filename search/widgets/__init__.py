from IPython.display import display as Idisplay, JSON as IJSON, Markdown, clear_output, display_markdown
from ipywidgets import HBox, VBox, Text, Button, Output, Layout, SelectMultiple, Label, HTML
from ipywidgets.widgets.widget import CallbackDispatcher, Widget
from traitlets import observe

from here_map_widget import GeoJSON, WidgetControl, Icon
from here_map_widget import Platform, MapTile, TileLayer, Map
from here_map_widget import ServiceNames, MapTileUrl

from search.core import OneBoxBase, __version__, debounce

from typing import Callable, Tuple, List, Awaitable, ClassVar
from functools import reduce
from dataclasses import dataclass
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
        @debounce(200)
        def getvalue(change: dict):
            future.set_result(change.new)
            self.unobserve_text(getvalue, 'value')
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
        south, west, north, east = None, None, None, None
        for item in results["items"]:
            if "position" not in item:
                continue
            longitude, latitude = item["position"]["lng"], item["position"]["lat"]
            latitudes.append(latitude)
            longitudes.append(longitude)
            if "mapView" in item:
                latitudes.append(item["mapView"]["north"])
                latitudes.append(item["mapView"]["south"])
                longitudes.append(item["mapView"]["west"])
                longitudes.append(item["mapView"]["east"])
            categories = [c["name"] for c in item["categories"]
                          if c.get("primary")][0] if "categories" in item else None
            collection["features"].append({"type": "Feature",
                                           "geometry": {
                                               "type": "Point",
                                               "coordinates": [longitude, latitude]},
                                           "properties": {"title": item["title"],
                                                          "categories": categories}})
            if False and "mapView" in item:
                collection["features"].append({"type": "Feature",
                                               "geometry": {
                                                   "type": "Polygon",
                                                   "coordinates":    [
                                                       [ [item["mapView"]["west"], item["mapView"]["south"]],
                                                         [item["mapView"]["east"], item["mapView"]["south"]],
                                                         [item["mapView"]["east"], item["mapView"]["north"]],
                                                         [item["mapView"]["west"], item["mapView"]["north"]],
                                                         [item["mapView"]["west"], item["mapView"]["south"]] ]
                                                   ]}})
        if latitudes:
            south, west, north, east = min(latitudes), min(longitudes), max(latitudes), max(longitudes)
            collection["bbox"] = [south, west, north, east]
            height = north-south
            width = east-west
            self.bbox = (south-height/8, north+height/8, east+width/8, west-width/8)
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
                             "radius": 7}
                         )


class TermsButtons(HBox):
    """A HBox containing a list of Buttons"""
    default_layout = {'width': '280px'}
    default_buttons_count = 3
    css_displayed = False

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
        if not TermsButtons.css_displayed:
            TermsButtons.css_displayed = True
            Idisplay(HTML("<style>.term-button button { font-size: 10px; }</style>"))
        self.add_class('term-button')

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


@dataclass
class SearchResultList(VBox):
    widget: Widget
    result_queue: asyncio.Queue=None
    layout: dict=None

    default_layout = {'display': 'flex', 'width': '276px', 'justify_content': 'flex-start'}

    def __post_init__(self):
        if self.layout is None:
            self.layout = SearchResultList.default_layout
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

    def _display(self, resp: dict) -> Widget:
        out = Output(layout=self.layout)
        text = ['| | |', '|:-|:-|']
        for i, item in enumerate(resp["items"]):
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

    def display(self, resp: dict):
        # https://stackoverflow.com/questions/66704546/why-cannot-i-print-in-jupyter-lab-using-ipywidgets-class
        old_out = self.children[0]
        out = self._display(resp)
        self.children = [out]
        old_out.close()

class SearchResultJson(SearchResultList):
    def _display(self, resp: dict) -> Widget:
        out = Output(layout=self.layout)
        out.append_display_data(IJSON(data=resp, expanded=False, root='response'))
        return out

class SearchResultSelectMultiple(SearchResultList):
    def _display(self, resp: dict) -> Widget:
        return SelectMultiple(options=[item["title"] for item in resp["items"]],
                              rows = len(resp["items"]),
                              disabled=False)

class SearchResultButton(HBox):
    default_layout = {'display': 'flex', 'width': '270px', 'justify_content': 'flex-start'}

    def __init__(self, item: dict, rank: int, **kvargs):
        #self.item = item
        label = Label(value=f'{rank+1: <2}', layout={'width': '20px'})
        icon = 'search' if item["resultType"] in ("categoryQuery", "chainQuery") else ''
        self.button = Button(description=item["title"],
                             icon=icon,
                             layout=kvargs.pop('layout', self.__class__.default_layout))
        self.button.item = item
        HBox.__init__(self, [label, self.button], **kvargs)
        self.add_class('result-button')


class SearchResultButtons(SearchResultList):
    css_displayed = False
    def __post_init__(self):
        if not SearchResultButtons.css_displayed:
            Idisplay(HTML("<style>.result-button div, .result-button button { font-size: 10px; }</style>"))
            SearchResultButtons.css_displayed = True
        super().__post_init__()

    def _display(self, resp: dict) -> Widget:
        out = []
        self.tasks = []
        for rank, item in enumerate(resp["items"]):
            search_result = SearchResultButton(item=item, rank=rank)
            future = asyncio.Future()
            def getvalue(button: Button):
                value = button.item
                self.result_queue.put_nowait(value)
            search_result.button.on_click(getvalue)
            out.append(search_result)
        return VBox(out)



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
    default_resultlist_class = SearchResultList

    def __init__(self,
                 language: str,
                 latitude: float, longitude: float,
                 api_key: str=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 design: Callable=None,
                 resultlist_class: ClassVar=None,
                 autosuggest_automatic_recenter: bool=False,
                 **kwargs):

        SubmittableTextBox.__init__(self,
                                    layout=kwargs.pop('layout', self.__class__.default_search_box_layout),
                                    placeholder=kwargs.pop('placeholder', self.__class__.default_placeholder),
                                    **kwargs)

        OneBoxBase.__init__(self,
                            language=language,
                            api_key=api_key,
                            results_limit=results_limit or self.__class__.default_results_limit,
                            suggestions_limit=suggestions_limit or self.__class__.default_suggestions_limit,
                            terms_limit=terms_limit or self.__class__.default_terms_limit)

        self.result_points: SearchFeatureCollection = None

        self.query_terms_w = TermsButtons(self.__class__.default_terms_limit)
        self.query_terms_w.on_click(self.__get_terms_buttons_handler())

        self.map_w = PositionMap(api_key=self.api_key, center=[latitude, longitude])

        self.result_list_w = (resultlist_class or self.__class__.default_resultlist_class)(widget=Output(), result_queue=self.result_queue)

        self.app_design_w = (design or Design.two)(self, self.map_w, self.query_terms_w, self.result_list_w)

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
        return self.map_w.center

    def display_terms(self, autosuggest_resp: dict):
        self.query_terms_w.set([term['term'] for term in autosuggest_resp.get('queryTerms', [])])

    def display_suggestions(self, autosuggest_resp: dict) -> None:
        self.result_list_w.display(autosuggest_resp)

        search_feature = SearchFeatureCollection(autosuggest_resp)
        if search_feature.bbox:
            if self.result_points:
                self.map_w.remove_layer(self.result_points)
            self.result_points = search_feature
            self.map_w.add_layer(self.result_points)
        #self.display_result_map(autosuggest_resp, update_search_center=False)

    def handle_suggestion_list(self, autosuggest_resp):
        """
        Typically called by OneBoxBase.handle_key_strokes()
        :param autosuggest_resp:
        :return: None
        """
        self.display_suggestions(autosuggest_resp)
        self.display_terms(autosuggest_resp)

    def handle_result_list(self, discover_resp):
        """
        Typically called by OneBoxBase.handle_text_submissions()
        :param autosuggest_resp:
        :return: None
        """
        self.result_list_w.display(discover_resp)
        self.display_result_map(discover_resp, update_search_center=True)
        self.clear_query_text()

    def handle_result_details(self, lookup_resp: dict):
        """
        Typically called by OneBoxBase.handle_result_selections()
        :param autosuggest_resp:
        :return: None
        """
        self.display_result_map({"items": [lookup_resp]}, update_search_center=True)

    def clear_query_text(self):
        self.text.value = ''
        self.query_terms_w.set([])

    def display_result_map(self, resp, update_search_center=False):
        if self.result_points:
            self.map_w.remove_layer(self.result_points)
        self.result_points = SearchFeatureCollection(resp)
        self.map_w.add_layer(self.result_points)
        if self.result_points.bbox:
            self.map_w.bounds = self.result_points.bbox
            if len(resp["items"]) == 1:
                self.map_w.zoom = OneBoxMap.minimum_zoom_level

    def run(self):
        Idisplay(self.app_design_w)
        OneBoxBase.run(self)


class OneBoxMapCI(OneBoxMap):
    as_url = 'http://ci.opensearch.dev.api.here.com/v1/autosuggest'
    ds_url = 'http://ci.opensearch.dev.api.here.com/v1/discover'
    default_autosuggest_query_params = {'show': 'details,expandedOntologies'}
    default_discover_query_params = {'show': 'ta,ev'}