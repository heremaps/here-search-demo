from IPython.display import display as Idisplay, JSON as IJSON, clear_output, DisplayObject
from ipywidgets import HBox, VBox, Text, Label, Combobox, Dropdown, Button, Output, Layout
from ujson import dumps, loads
from getpass import getpass
from requests import Session, get
from aiohttp import ClientSession
from pprint import pprint
from typing import Callable
import asyncio, http.client, json, sys, time

from here_map_widget import GeoJSON, WidgetControl, InfoBubble, ZoomControl, MapTile
from here_map_widget import Platform, MapTile, TileLayer, Map
from here_map_widget import ServiceNames, MapTileUrl
import os
from typing import Tuple


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

out = Output()
Idisplay(out)


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


class FQuery(Text):
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

        self.text = ""
        Text.__init__(self,
                      value=self.text,
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

        def get_position_handler(latitude, longitude):
            self.latitude, self.longitude = latitude, longitude
        self.map = FQuery.get_map(api_key, latitude, longitude, get_position_handler)
        self.lens = Button(icon='fa-search', layout={'width': '32px'})
        self.add_search_control_to_map()

        self.output_widget = Output(layout={'width': '450px'})

        # bind the Text form key strokes events to autosuggest
        asyncio.ensure_future(self.on_key_stroke_handler())

        # bind the Text form key strokes events to discover
        self.lens.on_click(self.on_lens_click_handler)
        self.on_submit(self.on_enter_key_stroke_handler)

    def init_termsButtons(self):
        self.query_terms = TermsButtons(FQuery.default_terms_limit)

        def on_terms_click_handler(change):
            tokens = self.value.strip().split(' ')
            if tokens:
                head, tail = tokens[:-1], tokens[-1]
                head.extend([change.description.strip(), ''])
                self.text = self.value = ' '.join(head)

        self.query_terms.on_click(on_terms_click_handler)

    def add_search_control_to_map(self):
        widget_control = WidgetControl(widget=VBox([HBox([self, self.lens]), self.query_terms]), alignment="TOP_LEFT",
                                       name="search")
        self.map.add_control(widget_control)
        self.map.zoom_control_instance.alignment = "RIGHT_TOP"

    @classmethod
    def get_map(cls, api_key, latitude, longitude, get_position_handler: Callable[[float, float], None]) -> Map:
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
        map = Map(api_key=api_key, center=[latitude, longitude], zoom=12, basemap=maptile_layer)
        def observe(change):
            if change.type == "change":
                if change.name in "center":
                    get_position_handler(*change.new[:2])
                elif change.name == "zoom":
                    get_position_handler(*map.center)
        map.observe(observe)

        return map

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

    def discover(self, q: str, latitude: float, longitude: float,
                 language: str=None) -> dict:
        """
        Calls HERE Search Discover endpoint
        https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html

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
        resp = self.session.get(self.ds_url, params=params)
        resp.raise_for_status()
        return loads(resp.content)

    @staticmethod
    def _wait_for_change(widget, name: str) -> asyncio.Future:
        # This methods allows to observe widgets changes
        future = asyncio.Future()
        def getvalue(change: dict):
            # make the new value available
            future.set_result(change.new)
            widget.unobserve(getvalue, name)
        widget.observe(getvalue, name)
        return future

    async def on_key_stroke_handler(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True) as session:
            while not self.autosuggest_done:
                q = await FQuery._wait_for_change(self, 'value')
                self.output_widget.clear_output(wait=True)
                if not q:
                    continue
                lat, lng = self.latitude, self.longitude
                # lat, lng = self.map.center[1], self.map.center[0]
                _q, resp = await asyncio.ensure_future(self.autosuggest(session, q, lat, lng))
                self.text = q
                self.output_widget.append_display_data(IJSON(resp))
                search_resp = SearchFeatureCollection(resp)
                if search_resp.bbox:
                    if self.layer:
                        self.map.remove_layer(self.layer)
                    self.layer = search_resp
                    self.map.add_layer(self.layer)
                for i in range(FQuery.default_terms_limit):
                    self.query_terms.children[i].description = ' '
                for i, term in enumerate(resp['queryTerms']):
                    self.query_terms.children[i].description = term['term']
                #if self.layer.bbox:
                #    self.map.bounds = self.layer.bbox

    def on_enter_key_stroke_handler(self, change):
        """
        This method is called when the user hits enter/return in the Text form
        """
        q = change.value
        if q:
            self.do_search(q)

    def on_lens_click_handler(self, change):
        """
        This method is called when the use select the lens
        """
        q = self.text
        if q:
            self.do_search(q)

    def do_search(self, q):
        resp = self.discover(q, self.latitude, self.longitude)
        self.autosuggest_done = True
        with self.output_widget:
            clear_output(wait=False)
            Idisplay(IJSON(resp))
        if self.layer:
            self.map.remove_layer(self.layer)
        self.layer = SearchFeatureCollection(resp)
        self.map.add_layer(self.layer)
        if self.layer.bbox:
            self.map.bounds = self.layer.bbox
            if len(resp["items"]) == 1:
                self.map.zoom = FQuery.minimum_zoom_level
            self.latitude, self.longitude = self.map.center[1], self.map.center[0]
        self.value = self.text = ''
        for i in range(FQuery.default_terms_limit):
            self.query_terms.children[i].description = ' '
        self.autosuggest_done = False


def onebox(language: str, latitude: float, longitude: float, api_key: str=None,
           autosuggest_automatic_recenter: bool=False,
           render_json: bool=False):
    if not api_key:
        api_key = os.environ.get('API_KEY') or getpass()

    # TODO: clearly decide if FQuery rendering is really independant from the map... Below looks really ugly
    # Probably separate the widgets classes and the search client classes.
    # need to find a well known architecture for event based programming in Python...
    wquery = FQuery(api_key=api_key, language=language, latitude=latitude, longitude=longitude,
                    autosuggest_automatic_recenter=autosuggest_automatic_recenter,
                    placeholder="", disabled=False)

    #with out:
    #    print(m.center)
    Idisplay(HBox([wquery.map, wquery.output_widget]))