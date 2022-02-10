import collections

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
from typing import Callable, Tuple, List, Awaitable
from functools import reduce
import os
import abc
import asyncio
import contextlib
import sys
import termios
from array import array


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
    def __init__(self, wquery: "OneBoxMap", query_terms: TermsButtons):
        VBox.__init__(self, [wquery, query_terms])


class PositionMap(Map):
    default_zoom_level = 12
    default_layout = {'height': '600px'}

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


class OneBoxBase:
    as_url = 'https://autosuggest.search.hereapi.com/v1/autosuggest'
    ds_url = 'https://discover.search.hereapi.com/v1/discover'
    default_results_limit = 20
    default_suggestions_limit = 5
    default_terms_limit = 0

    def __init__(self,
                 api_key: str=None,
                 language: str=None,
                 suggestions_limit: int=None,
                 results_limit: int=None,
                 terms_limit: int=None):
        self.api_key = api_key or os.environ.get('API_KEY') or getpass(prompt="apiKey")
        self.language = language
        self.results_limit = results_limit or self.__class__.default_results_limit
        self.suggestions_limit = suggestions_limit or self.__class__.default_suggestions_limit
        self.terms_limit = terms_limit or self.__class__.default_terms_limit

    def run(self):
        asyncio.ensure_future(self.handle_key_strokes())
        asyncio.ensure_future(self.handle_text_submissions())

    async def autosuggest(self, session: ClientSession,
                          q: str, latitude: float, longitude: float) -> dict:
        """
        Calls HERE Search Autosuggest endpoint
        https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :return: a tuple made of the input query text and the response dictionary
        """
        params = {'q': q,
                  'at': f'{latitude},{longitude}',
                  'limit': self.suggestions_limit,
                  'termsLimit': self.terms_limit,
                  'apiKey': self.api_key}
        language = self.get_language()
        if language:
            params['lang'] = language

        async with session.get(self.as_url, params=params) as response:
            return await response.json(loads=loads)

    async def discover(self, session: ClientSession,
                       q: str, latitude: float, longitude: float) -> dict:
        """
        Calls HERE Search Discover endpoint
        https://developer.here.com/documentation/geocoding-search-api/api-reference-swagger.html

        :param session: instance of ClientSession
        :param q: query text
        :param latitude: search center latitude
        :param longitude: search center longitude
        :return: a response dictionary
        """
        params = {'q': q,
                  'at': f'{latitude},{longitude}',
                  'limit': self.results_limit,
                  'apiKey': self.api_key}
        language = self.get_language()
        if language:
            params['lang'] = language

        async with session.get(self.ds_url, params=params) as response:
            return await response.json(loads=loads)

    async def handle_key_strokes(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:
                q = await self.wait_for_new_key_stroke()
                if q is None:
                    break
                if not q:
                    continue

                latitude, longitude = self.get_search_center()
                autosuggest_resp = await asyncio.ensure_future(self.autosuggest(session, q, latitude, longitude))

                self.display_suggestions(autosuggest_resp)

    async def handle_text_submissions(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True) as session:
            while True:
                q = await self.wait_for_submitted_value()
                if q is None:
                    break
                if not q:
                    continue

                latitude, longitude = self.get_search_center()
                discover_resp = await asyncio.ensure_future(self.discover(session, q, latitude, longitude))

                self.display_results(discover_resp)

    def get_language(self):
        return self.language

    def get_search_center(self) -> Tuple[float, float]:
        raise NotImplementedError()

    def wait_for_new_key_stroke(self) -> Awaitable:
        raise NotImplementedError()

    def wait_for_submitted_value(self) -> Awaitable:
        raise NotImplementedError()

    def display_suggestions(self, response: dict) -> None:
        raise NotImplementedError()

    def display_results(self, response: dict) -> None:
        raise NotImplementedError()


class OneBoxConsole(OneBoxBase):
    default_results_limit = 5

    def __init__(self,
                 language: str,latitude: float, longitude: float,
                 api_key: str=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 term_keys: bytes=None):
        self.center = latitude, longitude
        self.term_keys = array('B', term_keys)
        self.key_queue = None
        self.line_queue = None
        self.reset()
        super().__init__(api_key, language, results_limit=results_limit, suggestions_limit=suggestions_limit, terms_limit=len(term_keys))

    def reset(self):
        # TODO: this function needs to be awaited... Check a better way to have the b.run() reantrant
        # Maybe bu centralizing a self.loop and explicitely have all call using it???
        try:
            self.key_queue.join()
            self.line_queue.join()
        except AttributeError:
            pass
        self.keys = array('B')
        self.terms = []

    def get_search_center(self) -> Tuple[float, float]:
        return self.center

    def display_results(self, response: dict) -> None:
        out = [f"{'->' :<100s}", ' '*100]
        i = -1
        for i, item in enumerate(response["items"]):
            out.append(f'{item["title"]: <100s}')
        for j in range(self.results_limit-i-1):
            out.append(' '*100)
        out.append(f"\r\033[{self.results_limit+2}A")
        print('\n'.join(out), end="")

    def display_suggestions(self, response: dict) -> None:
        self.terms = [term['term'] for term in response["queryTerms"]]
        terms_line = f'| {" | ".join(f"{i}: {term}" for i, term in enumerate(self.terms))} |'
        out = [f'{terms_line: <100s}']
        i = -1
        for i, item in enumerate(response["items"]):
            out.append(f'{item["title"]: <100s}')
        for j in range(self.results_limit-i-1):
            out.append(' '*100)
        out.append(f"\r\033[{self.results_limit+2}A")
        print('\n'.join(out), end="")

    def wait_for_new_key_stroke(self) -> Awaitable:
        return self.key_queue.get()

    def wait_for_submitted_value(self) -> Awaitable:
        return self.line_queue.get()

    @staticmethod
    @contextlib.contextmanager
    def _raw_mode(file):
        old_attrs = termios.tcgetattr(file.fileno())
        new_attrs = old_attrs[:]
        new_attrs[3] = new_attrs[3] & ~(termios.ECHO | termios.ICANON)
        try:
            termios.tcsetattr(file.fileno(), termios.TCSADRAIN, new_attrs)
            yield
        finally:
            termios.tcsetattr(file.fileno(), termios.TCSADRAIN, old_attrs)

    async def dispath(self):
        """Dispatches keystrokes and aggregated lines to two different queues"""
        with OneBoxConsole._raw_mode(sys.stdin):
            reader = asyncio.StreamReader()
            loop = asyncio.get_event_loop()
            await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

            while not reader.at_eof():
                ch = await reader.read(1)
                if not ch or ord(ch) <= 4:
                    await self.key_queue.put(None)
                    await self.line_queue.put(None)
                    break
                if ch == b'\n':
                    await self.line_queue.put(self.keys.tobytes().decode())
                    self.keys = array('B')
                else:
                    try:
                        term_index = self.term_keys.index(ord(ch))
                        try:  # to remove the last word
                            while self.keys.pop() != 32:
                                pass
                        except IndexError:
                            pass
                        self.keys.frombytes(b' ')
                        self.keys.frombytes(self.terms[term_index].strip().encode())
                        self.keys.frombytes(b' ')
                    except ValueError:
                        self.keys.frombytes(ch)
                    line = self.keys.tobytes().decode()
                    print(f'-> {line: <100s}')
                    await self.key_queue.put(line)

    async def main(self):
        self.key_queue = asyncio.Queue()
        self.line_queue = asyncio.Queue()
        t1 = asyncio.create_task(self.dispath())
        t2 = asyncio.create_task(self.handle_key_strokes())
        t3 = asyncio.create_task(self.handle_text_submissions())
        await asyncio.gather(t1, t2, t3)

    def run(self):
        self.reset()
        asyncio.run(self.main())


class OneBoxMap(SubmittableTextBox, OneBoxBase):
    default_results_limit = 20
    default_suggestions_limit = 5
    default_terms_limit = 3
    minimum_zoom_level = 11
    default_layout = {'width': '240px'}
    default_placeholder = "free text"

    def __init__(self,
                 language: str,
                 latitude: float, longitude: float,
                 api_key: str=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 autosuggest_automatic_recenter: bool=False,
                 **kwargs):

        SubmittableTextBox.__init__(self,
                                    layout=kwargs.pop('layout', OneBoxMap.default_layout),
                                    placeholder=kwargs.pop('placeholder', OneBoxMap.default_placeholder),
                                    **kwargs)

        OneBoxBase.__init__(self,
                            language=language,
                            api_key=api_key,
                            results_limit=results_limit,
                            suggestions_limit=suggestions_limit,
                            terms_limit=terms_limit)

        self.layer = None
        self.as_url = f'https://autosuggest.search.hereapi.com/v1/autosuggest?apiKey={self.api_key}'
        self.ds_url = f'https://discover.search.hereapi.com/v1/discover?apiKey={self.api_key}'
        self.session = Session()

        self.init_terms_buttons()
        self.map = PositionMap(api_key=self.api_key, center=[latitude, longitude])
        self.add_search_control_to_map()
        self.output_widget = Output(layout={'width': '450px'})

    def run(self):
        Idisplay(HBox([self.map, self.output_widget]))
        OneBoxBase.run(self)

    def get_search_center(self):
        return self.map.center

    def init_terms_buttons(self):
        self.query_terms = TermsButtons(OneBoxMap.default_terms_limit)
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

    def display_terms(self, autosuggest_resp):
        for i in range(OneBoxMap.default_terms_limit):
            self.query_terms.children[i].description = ' '
        for i, term in enumerate(autosuggest_resp.get('queryTerms', [])):
            self.query_terms.children[i].description = term['term']

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
        for i in range(OneBoxMap.default_terms_limit):
            self.query_terms.children[i].description = ' '

    def display_result_map(self, resp, update_search_center=False):
        if self.layer:
            self.map.remove_layer(self.layer)
        self.layer = SearchFeatureCollection(resp)
        self.map.add_layer(self.layer)
        if self.layer.bbox:
            self.map.bounds = self.layer.bbox
            if len(resp["items"]) == 1:
                self.map.zoom = OneBoxMap.minimum_zoom_level

    def display_result_list(self, resp):
        if True:
            self.output_widget.clear_output(wait=True)
            self.output_widget.append_display_data(IJSON(resp))
        else: # does not work for key strokes... TODO: Check why
            with self.output_widget:
                clear_output(wait=True)
                Idisplay(IJSON(resp))


def onebox(language: str, latitude: float, longitude: float, api_key: str=None,
           results_limit: int=None,
           suggestions_limit: int=None,
           autosuggest_automatic_recenter: bool=False,
           render_json: bool=False):


    ionebox = OneBoxMap(api_key=api_key, language=language, latitude=latitude, longitude=longitude,
                        results_limit=results_limit, suggestions_limit=suggestions_limit,
                        autosuggest_automatic_recenter=autosuggest_automatic_recenter,
                        placeholder="", disabled=False)

    Idisplay(HBox([ionebox.map, ionebox.output_widget]))
    return ionebox
