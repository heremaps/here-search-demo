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

class FQuery(Text):
    default_results_limit = 5
    default_terms_limit = 3
    minimum_zoom_level = 11

    def __init__(self, api_key: str,
                 language: str,
                 latitude: float, longitude: float,
                 output_widget: DisplayObject,
                 a_map: Map,
                 results_limit: int=None,
                 terms_limit: int=None,
                 autosuggest_automatic_recenter: bool=False,
                 **kwargs):
        self.text = ""
        self.placeholder = "free text"
        self.language = language
        self.api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.results_limit = results_limit or FQuery.default_results_limit
        self.terms_limit = terms_limit or FQuery.default_terms_limit
        self.map = a_map
        self.layer = None
        self.as_url = f'https://autosuggest.search.hereapi.com/v1/autosuggest?apiKey={self.api_key}'
        self.ds_url = f'https://discover.search.hereapi.com/v1/discover?apiKey={self.api_key}'
        self.session = Session()
        self.autosuggest_done = False
        self.output_widget = output_widget

        box_layout = Layout(display="flex", justify_content="center", width="33%", border="solid 1px")
        labels = []
        def on_click(change):
            tokens = self.value.strip().split(' ')
            if tokens:
                head, tail = tokens[:-1], tokens[-1]
                head.extend([change.description.strip(), ''])
                self.text = self.value = ' '.join(head)

        for i in range(FQuery.default_terms_limit):
            label = Button(layout=box_layout)
            label.on_click(on_click)
            labels.append(label)
        self.query_terms = HBox(labels, layout={'width': '280px'})

        Text.__init__(self, **kwargs)

        # bind the Text form key strokes events to autosuggest and discover
        asyncio.ensure_future(self.on_key_stroke())
        self.on_submit(self.on_enter_key_stroke)
        def observe(change):
            if change.type == "change":
                if change.name in "center":
                    self.latitude, self.longitude = change.new[:2]
                elif change.name == "zoom":
                    self.latitude, self.longitude = self.map.center
        self.map.observe(observe)

        self.lens = Button(icon='fa-search', layout={'width': '10px'})
        self.lens.on_click(self.on_lens_click)

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

    async def on_key_stroke(self):
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

    def on_enter_key_stroke(self, change):
        """
        This method is called when the use hits enter/return in the Text form
        """
        q = change.value
        if q:
            self.do_search(q)

    def on_lens_click(self, change):
        """
        This method is called when the use hits enter/return in the Text form
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

    #results = [[Label('query', layout={'width': '250px'})]]
    output_widget = Output(layout={'width': '450px'})
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
    m = Map(api_key=api_key, center=[latitude, longitude], zoom=12, basemap=maptile_layer)


    wquery = FQuery(language=language, api_key=api_key, latitude=latitude, longitude=longitude, output_widget=output_widget,
                    a_map=m, value="",
                    autosuggest_automatic_recenter=autosuggest_automatic_recenter,
                    placeholder="", disabled=False, layout={'width': '240px'})
    widget_control = WidgetControl(widget=VBox([HBox([wquery, wquery.lens]), wquery.query_terms]), alignment="TOP_LEFT", name="search")
    m.add_control(widget_control)
    m.zoom_control_instance.alignment="RIGHT_TOP"
    #with out:
    #    print(m.center)
    Idisplay(HBox([m, output_widget]))