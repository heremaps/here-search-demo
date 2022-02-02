from IPython.display import display as Idisplay, JSON as IJSON, clear_output
from ipywidgets import HBox, VBox, Text, Label, Combobox, Dropdown, Button, Output
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


class SearchResults(GeoJSON):
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
            self.bbox = [south-height/6, north+height/6, east+width/6, west-width/6]
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

    def __init__(self, api_key: str, language: str, latitude: float, longitude: float, output_widget: IJSON, a_map: Map, **kwargs):
        self.text = ""
        self.language = language
        self.api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.map = a_map
        self.layer = None
        self.as_url = f'https://search.hereapi.com/v1/autosuggest?lang={self.language}&apiKey={self.api_key}&' \
                      f'limit=5&termsLimit=3'
        self.ds_url = f'https://search.hereapi.com/v1/discover?lang={self.language}&apiKey={self.api_key}&limit=5'
        self.as_session = ClientSession()
        self.autosuggest_done = False
        self.output_widget = output_widget

        Text.__init__(self, **kwargs)

        asyncio.ensure_future(self.on_key_stroke())
        self.on_submit(self.on_return)

    @staticmethod
    def wait_for_change(widget, name: str) -> asyncio.Future:
        future = asyncio.Future()
        def getvalue(change: dict):
            # make the new value available
            future.set_result(change.new)
            widget.unobserve(getvalue, name)
        widget.observe(getvalue, name)
        return future

    async def on_key_stroke(self):

        async def _fetch(q: str, url: str, params: dict, session):
            async with session.get(url, params=params) as response:
                return q, await response.json()

        async with ClientSession(raise_for_status=True) as session:
            while not self.autosuggest_done:
                q = await FQuery.wait_for_change(self, 'value')
                self.output_widget.clear_output(wait=True)
                if not q:
                    continue
                lat, lng = self.latitude, self.longitude
                # lat, lng = self.map.center[1], self.map.center[0]
                params = {'q': q, 'at': f'{lat},{lng}'}
                _q, resp = await asyncio.ensure_future(_fetch(q, self.as_url, params, session))
                self.output_widget.append_display_data(IJSON(resp))
                if self.layer:
                    self.map.remove_layer(self.layer)
                self.layer = SearchResults(resp)
                self.map.add_layer(self.layer)
                #if self.layer.bbox:
                #    self.map.bounds = self.layer.bbox

    def on_return(self, change):
        q = change.value
        if q:
            lat, lng = self.latitude, self.longitude
            params = {'q': q, 'at': f'{lat},{lng}'}
            resp = get(self.ds_url, params=params)
            resp.raise_for_status()
            self.autosuggest_done = True
            resp = resp.json()
            with self.output_widget:
                clear_output(wait=False)
                Idisplay(IJSON(resp))
            if self.layer:
                self.map.remove_layer(self.layer)
            self.layer = SearchResults(resp)
            self.map.add_layer(self.layer)
            if self.layer.bbox:
                self.map.bounds = self.layer.bbox
                self.latitude, self.longitude = self.map.center[1], self.map.center[0]



def onebox(language: str, latitude: float, longitude: float, api_key: str=None):
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
        scheme="normal.night",
        format="png",
        platform=platform
    )
    m = Map(api_key=api_key, center=[latitude, longitude], zoom=12, map_tile=map_tile)

    wquery = FQuery(language=language, api_key=api_key, latitude=latitude, longitude=longitude, output_widget=output_widget, a_map=m, value="", placeholder="", disabled=False, layout={'width': '250px'})
    widget_control = WidgetControl(widget=wquery, alignment="TOP_LEFT", name="search")
    m.add_control(widget_control)
    m.zoom_control_instance.alignment="RIGHT_TOP"
    #with out:
    #    print(m.center)
    Idisplay(HBox([m, output_widget]))