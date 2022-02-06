from IPython.display import display as Idisplay, JSON as IJSON, clear_output
from ipywidgets import HBox, VBox, Text, Label, Combobox, Dropdown, Button, Output, Layout
from ipywidgets.widgets.widget import CallbackDispatcher
from traitlets import observe

from ujson import dumps, loads
from requests import Session, get
from aiohttp import ClientSession

from here_map_widget import GeoJSON, WidgetControl
from here_map_widget import Platform, MapTile, TileLayer, Map
from here_map_widget import ServiceNames, MapTileUrl

from getpass import getpass
from typing import Callable, Tuple, List
import asyncio
from functools import reduce
import os

out = Output()
Idisplay(out)


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
            categories = [c["name"][:10] for c in item["categories"]
                          if c.get("primary")][0] if "categories" in item else None
            collection["features"].append({"type": "Feature",
                                           "geometry": {
                                               "type": "Point",
                                               "coordinates": [longitude, latitude]},
                                           "properties": {"title": item["title"][:10],
                                                          "categories": categories}})
        if latitudes:
            south, west, north, east = min(latitudes), min(longitudes), max(latitudes), max(longitudes)
            collection["bbox"] = [south, west, north, east]
            height = north-south
            width = east-west
            self.bbox = (south-height/6, north+height/6, east+width/6, west-width/6)
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


class SearchTermsBox(VBox):
    def __init__(self, wquery: "FQuery", query_terms: TermsButtons):
        VBox.__init__(self, [wquery, query_terms])


class PositionMap(Map):
    default_zoom_level = 12

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
                     basemap=maptile_layer)
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


class SubmittableText(Text):
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
    default_icon = 'fa-search'

    def __init__(self, *args, **kwargs):
        self.lens = Button(icon=kwargs.pop('icon', SubmittableTextBox.default_icon), layout={'width': '32px'})
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

    def wait_for_new_change(self, name: str) -> asyncio.Future:
        # This methods allows to control the call to the widget handler outside of the jupyter event loop
        future = asyncio.Future()
        def getvalue(change: dict):
            future.set_result(change.new)
            self.unobserve_text(getvalue, name)
            pass
        self.observe_text(getvalue, name)
        return future

    def wait_for_submitted_value(self) -> asyncio.Future:
        future = asyncio.Future()
        def getvalue(_):
            value = self.text.value
            future.set_result(value)
            self.on_submit(getvalue, remove=True)
            self.on_click(getvalue, remove=True)
        self.on_submit(getvalue)
        self.on_click(getvalue)
        return future


class FQuery(SubmittableTextBox):
    default_results_limit = 5
    default_terms_limit = 3
    minimum_zoom_level = 11
    default_layout = {'width': '240px'}
    default_placeholder = "free text"

    def __init__(self, api_key: str,
                 language: str,
                 latitude: float, longitude: float,
                 results_limit: int=None,
                 terms_limit: int=None,
                 autosuggest_automatic_recenter: bool=False,
                 **kwargs):

        SubmittableTextBox.__init__(self,
                                    layout=kwargs.pop('layout', FQuery.default_layout),
                                    placeholder=kwargs.pop('placeholder', FQuery.default_placeholder),
                                    **kwargs)

        self.language = language
        self.api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.results_limit = results_limit or FQuery.default_results_limit
        self.terms_limit = terms_limit or FQuery.default_terms_limit
        self.layer = None
        self.as_url = f'https://autosuggest.search.hereapi.com/v1/autosuggest?apiKey={self.api_key}'
        self.ds_url = f'https://discover.search.hereapi.com/v1/discover?apiKey={self.api_key}'
        self.session = Session()
        self.autosuggest_done = False

        self.init_termsButtons()

        def position_handler(latitude, longitude):
            self.latitude, self.longitude = latitude, longitude
        self.map = PositionMap(api_key=api_key, center=[latitude, longitude], position_handler=position_handler)

        self.add_search_control_to_map()

        self.output_widget = Output(layout={'width': '450px'})

        # bind the Text form key strokes events to autosuggest
        asyncio.ensure_future(self.key_strokes())

        # bind the Text form key strokes events to discover
        asyncio.ensure_future(self.text_submissions())

    def init_termsButtons(self):
        self.query_terms = TermsButtons(FQuery.default_terms_limit)
        def on_terms_click_handler(change):
            tokens = self.text.value.strip().split(' ')
            if tokens:
                head, tail = tokens[:-1], tokens[-1]
                head.extend([change.description.strip(), ''])
                self.text.value = ' '.join(head)
        self.query_terms.on_click(on_terms_click_handler)

    def add_search_control_to_map(self):
        self.search_box = SearchTermsBox(self, self.query_terms)
        widget_control = WidgetControl(widget=self.search_box, alignment="TOP_LEFT", name="search")
        self.map.add_control(widget_control)
        self.map.zoom_control_instance.alignment = "RIGHT_TOP"

    async def autosuggest(self, session: ClientSession,
                          q: str, latitude: float, longitude: float,
                          language: str=None) -> Tuple[str, dict]:
        """
        Calls HERE Search Autosuggest endpoint
        https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param language: preferred result language (by default self.language)
        :return: a tuple made of the input query text and the response dictionary
        """
        params = {'q': q,
                  'at': f'{latitude},{longitude}',
                  'lang': language or self.language,
                  'limit': self.results_limit,
                  'termsLimit': self.terms_limit}

        async with session.get(self.as_url, params=params) as response:
            return q, await response.json(loads=loads)

    async def discover(self, session: ClientSession,
                       q: str, latitude: float, longitude: float,
                       language: str=None) -> dict:
        """
        Calls HERE Search Discover endpoint
        https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :param language: preferred result language (by default self.language)
        :return: a response dictionary
        """
        params = {'q': q,
                  'at': f'{latitude},{longitude}',
                  'lang': language or self.language,
                  'limit': self.results_limit}

        async with session.get(self.ds_url, params=params) as response:
            return await response.json(loads=loads)

    async def key_strokes(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True) as session:
            while not self.autosuggest_done:
                q = await self.wait_for_new_change('value')

                self.output_widget.clear_output(wait=True)
                if not q:
                    continue
                lat, lng = self.latitude, self.longitude
                # lat, lng = self.map.center[1], self.map.center[0]
                _q, autosuggest_resp = await asyncio.ensure_future(self.autosuggest(session, q, lat, lng))
                self.output_widget.append_display_data(IJSON(autosuggest_resp))
                search_feature = SearchFeatureCollection(autosuggest_resp)
                if search_feature.bbox:
                    if self.layer:
                        self.map.remove_layer(self.layer)
                    self.layer = search_feature
                    self.map.add_layer(self.layer)
                for i in range(FQuery.default_terms_limit):
                    self.query_terms.children[i].description = ' '
                for i, term in enumerate(autosuggest_resp['queryTerms']):
                    self.query_terms.children[i].description = term['term']
                #if self.layer.bbox:
                #    self.map.bounds = self.layer.bbox

    async def text_submissions(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:
                q = await self.wait_for_submitted_value()
                discover_resp = await asyncio.ensure_future(self.do_search(session, q, self.latitude, self.longitude))
                pass

    async def do_search(self, session, q, latitude, longitude):
        discover_resp = await self.discover(session, q, latitude, longitude)
        search_feature = SearchFeatureCollection(discover_resp)

        # temporarily stop to check for suggestions
        self.autosuggest_done = True

        with self.output_widget:
            clear_output(wait=False)
            Idisplay(IJSON(discover_resp))

        if self.layer:
            self.map.remove_layer(self.layer)

        self.layer = search_feature
        self.map.add_layer(self.layer)

        if self.layer.bbox:
            self.map.bounds = self.layer.bbox
            if len(discover_resp["items"]) == 1:
                self.map.zoom = FQuery.minimum_zoom_level
            self.latitude, self.longitude = self.map.center[1], self.map.center[0]

        self.text.value = ''
        for i in range(FQuery.default_terms_limit):
            self.query_terms.children[i].description = ' '
        self.autosuggest_done = False
        return discover_resp


def onebox(language: str, latitude: float, longitude: float, api_key: str=None,
           autosuggest_automatic_recenter: bool=False,
           render_json: bool=False):
    if not api_key:
        api_key = os.environ.get('API_KEY') or getpass()

    wquery = FQuery(api_key=api_key, language=language, latitude=latitude, longitude=longitude,
                    autosuggest_automatic_recenter=autosuggest_automatic_recenter,
                    placeholder="", disabled=False)

    Idisplay(HBox([wquery.map, wquery.output_widget]))
