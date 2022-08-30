from IPython.display import display as Idisplay
from here_map_widget import Map, Platform, ServiceNames, MapTileUrl, MapTile, TileLayer
from ipywidgets import Widget, CallbackDispatcher, HBox, VBox, Text, Button, Layout, HTML
from traitlets import observe

from here_search.entities import OntologyItem, Ontology
from here_search.util import logger

from typing import Awaitable, Tuple, Callable, Optional, Sequence
from functools import reduce
import asyncio
from dataclasses import dataclass
from enum import Enum, auto
from functools import partial
import re

Idisplay(HTML("<style>.term-button button { font-size: 10px; }</style>"))


class SubmittableText(Text):
    """A ipywidgets Text class enhanced with an on_submit() method"""

    def on_submit(self, callback, remove=False):
        self._submission_callbacks.register_callback(callback, remove=remove)

    @staticmethod
    def _put_buffers(state: dict, buffer_paths: Sequence[Sequence[str]], buffers: list):
        """
        Set specific state dict deeper values to specific buffers values specified by
        the buffer_paths list of paths in the state dict.

        Refactoring of widget._put_buffers(method)
        :param state: Nested dict. Typically only contains {"value": <str>}
        :param buffer_paths: successive of keys in the state nested dict
        :param buffers: list of values to set in state
        """
        for buffer_path, buffer in zip(buffer_paths, buffers):
            reduce(dict.get, buffer_path, state)[buffer_path[-1]] = buffer

    def _handle_msg(self, msg: dict) -> None:
        """
        Called when a msg is received from the front-end

        (Overrides from widgets.Widget._handle_msg)
        :param msg:
        :return:
        """
        data = msg['content']['data']
        method = data['method']

        if method == 'update':
            if 'state' in data:
                state = data['state']
                if 'buffer_paths' in data:
                    SubmittableText._put_buffers(state, data['buffer_paths'], msg['buffers'])
                self.set_state(state)
        elif method == 'request_state':
            self.send_state()
        elif method == 'custom':
            if 'content' in data:
                if data['content'].get('event') == 'submit':
                    self._submission_callbacks(self)


class SubmittableTextBox(HBox):
    """A ipywidgets HBox made of a SubmittableText and a lens Button"""
    default_icon = 'search'
    default_button_width = '32px'

    def __init__(self, *args, **kwargs):
        self.lens_w = Button(icon=kwargs.pop('icon', SubmittableTextBox.default_icon),
                             layout={'width': SubmittableTextBox.default_button_width}
                             )
        self.text_w = SubmittableText(*args, layout=kwargs.pop('layout', Layout()), **kwargs)
        super().__init__([self.text_w, self.lens_w], **kwargs)

    def observe_text(self, *args):
        self.text_w.observe(*args)

    def unobserve_text(self, *args):
        self.text_w.unobserve(*args)

    def on_submit(self, callback, remove=False):
        self.text_w.on_submit(callback, remove=remove)

    def on_click(self, callback, remove=False):
        self.lens_w.on_click(callback, remove=remove)

    def disable(self):
        self.text_w.disabled = True
        self.lens_w.disabled = True

    def emable(self):
        self.text_w.disabled = False
        self.lens_w.disabled = False

    def get_key_stroke_future(self) -> Awaitable:
        """
        Returns an awaitable future set to the observed Text widget value
        :return: asyncio.Future instance
        """
        # This method allows to control the call to the widget
        # handler outside of the jupyter event loop
        future = asyncio.Future()
        def getvalue(change: dict):
            value = change.new
            future.set_result(value if not value.endswith("~") else None)
            self.unobserve_text(getvalue, 'value')
        self.observe_text(getvalue, 'value')
        return future

    def get_submitted_value_future(self) -> Awaitable:
        """
        Returns an awaitable future set to the submitted Text widget value
        :return: asyncio.Future instance
        """
        future = asyncio.Future()
        def getvalue(_):
            value = self.text_w.value
            future.set_result(value if not value.endswith("~") else None)
            self.on_submit(getvalue, remove=True)
            self.on_click(getvalue, remove=True)
        self.on_submit(getvalue)
        self.on_click(getvalue)
        return future


class SearchTermsBox(VBox):
    def __init__(self, text: "SubmittableTextBox", terms_buttons: "TermsButtons"):
        self.text = text
        self.terms_buttons = terms_buttons
        VBox.__init__(self, [text, terms_buttons])


class TermsButtons(HBox):
    """A HBox containing a list of terms Buttons"""
    default_layout = {'width': '280px'}
    default_buttons_count = 3

    def __init__(self, target_text_box: SubmittableTextBox, values: list[str]=None, buttons_count: int=None, index: int=None, layout: dict=None):
        self.target_text_box = target_text_box
        self.values = values or []
        if values:
            buttons_count = len(values)
        elif not isinstance(buttons_count, int):
            buttons_count = TermsButtons.default_buttons_count
        width = int(100/buttons_count)
        self.token_index = index
        box_layout = Layout(display="flex", justify_content="center", width=f"{width}%", border="solid 1px")
        buttons = []
        on_click_handler = self.__get_click_handler()
        for i in range(buttons_count):
            button = Button(layout=box_layout)
            button.on_click(on_click_handler)
            buttons.append(button)
        HBox.__init__(self, buttons, layout=layout or TermsButtons.default_layout)
        self.set(self.values)
        self.add_class('term-button')

    def __get_click_handler(self) -> Callable:
        def handler(button):
            # replace the last token with the clicked button description and a whitespace
            if False: # target_text_box.text_w.value.endswith(' '):
                self.target_text_box.text_w.value = f"{self.target_text_box.text_w.value}{button.description.strip()} "
            else:
                tokens = self.target_text_box.text_w.value.strip().split(' ')
                if tokens:
                    if self.token_index is None:
                        head, target, tail = [], [button.description.strip()], []
                    elif self.token_index == -1:
                        head, target, tail = tokens[:self.token_index], [button.description.strip()], ['']
                    else:
                        head, target, tail = (tokens[:self.token_index],
                                              [button.description.strip()],
                                              tokens[self.token_index+1:])
                    self.target_text_box.text_w.value = ' '.join(head + target + tail)

            #self.set(self.values)
        return handler

    def set(self, values: list[str]):
        self.values = values
        for i, button in enumerate(self.children):
            try:
                button.description = values[i]
            except IndexError:
                button.description = ' '


class OntologyButton(Button):
    """
    A Button returning an Ontology future
    """
    item: OntologyItem
    default_icon = 'question'
    default_layout = {'width': '32px'}

    def __init__(self, item: OntologyItem, icon: str, **kwargs):
        """
        Creates a Button for an Ontology instance with a specific Font-Awesome icon.
        See: https://fontawesome.com/v5/search?m=free&s=regular
        And: https://use.fontawesome.com/releases/v5.12.0/fontawesome-free-5.12.0-web.zip

        :param icon: fontawesome-free v5.12.0 icon name (with fa- prefix) or text
        :param ontology: Ontology instance
        :param kwargs: Button class other attributes
        """
        self.item = item
        if not icon:
            kwargs.update({"icon": OntologyButton.default_icon})
        elif icon.startswith("fa-"):
            kwargs.update({"icon": icon[3:]})
        else:
            kwargs.update({"description": icon})
        super().__init__(layout=OntologyButton.default_layout, **kwargs)


class OntologyButtons(HBox):
    default_buttons = [OntologyButton(item=OntologyItem(name="_"), icon="")]

    def __init__(self, ontology: Ontology, icons: Sequence[str]):
        self.buttons = [OntologyButton(item, icon) for item, icon in zip(ontology._asdict().values(), icons)] or OntologyButtons.default_buttons
        HBox.__init__(self, self.buttons)

    def get_ontology_future(self) -> Awaitable:
        future = asyncio.Future()
        for button in self.buttons or OntologyButtons.default_buttons:
            def getvalue(clicked_button):
                future.set_result(clicked_button.item)
                for other_button in self.buttons:
                    other_button._click_handlers.callbacks.clear()
            button.on_click(getvalue)
        return future


@dataclass
class NearbySimpleParser:
    language: str

    class Mode(Enum):
        TOKENS = auto()
        TOKENS_SPACES = auto()
        TOKENS_INCOMPLETE_CONJUNCTION = auto()   # tokens followed by first letters of conjunction
        TOKENS_CONJUNCTION = auto()
        TOKENS_CONJUNCTION_SPACES = auto()  # conjunction last, followed by spaces
        TOKENS_CONJUNCTION_TOKENS = auto()   # conjunction surrounded by tokens

    CONJUNCTIONS = {'cs': ['nedaleko'],
                    'da': ['nærheden'],
                    'de': ['bei', 'neben', 'nähe'],
                    'el': ['κοντά σε'],
                    'en': ['near', 'nearby', 'close to'],
                    'es': ['cerca', 'junto'],
                    'fi': ['lähellä paikkaa'],
                    'fr': ['près de', 'proche de'],
                    'it': ['vicino a'],
                    'no': ['nærheten'],
                    'pt': ['perto de'],
                    'ru': ['рядом с'],
                    'sv': ['nära'],
                    'th': ['ใกล้กับ'],
                    'uk': ['біля'],
                    'vi': ['gần']}

    CONJUNCTION_PARTS = {}
    for language, terms in CONJUNCTIONS.items():
        for term in terms:
            for i in range(len(term)-1):
                CONJUNCTION_PARTS.setdefault(language, {}).setdefault(term[:i+1], []).append(term)

    @staticmethod
    def __no_cunjunction_function(text) -> Tuple[Mode, str, str, str]:
        return NearbySimpleParser.Mode.TOKENS, '', '', ''

    @staticmethod
    def __get_conjunction_mode(text: str, conjunctions: list, conjunction_parts: dict) -> Tuple[Mode, Optional[str], str, str]:
        """
        Example of auery parsing:
        >>> text = '  sep  foo  sep  bar  sep  '
        >>> for t in [text[:i+1] for i in range(len(text)-1)]:
        ...   t = t.lstrip()
        ...   print(f">{t}< {re.sub(' +', ' ', t).split(' ')} {re.sub(' +', ' ', t).partition(' sep ')}")
        ...
        >< [''] ('', '', '')                                                                                # TOKENS default
        >< [''] ('', '', '')                                                                                #   ''
        >s< ['s'] ('s', '', '')                                                                             #   ''
        >se< ['se'] ('se', '', '')                                                                          #   ''
        >sep< ['sep'] ('sep', '', '')                                                                       #   ''
        >sep < ['sep', ''] ('sep ', '', '')                                                                 # TOKENS_SPACES last_token=='' and middle==''
        >sep  < ['sep', ''] ('sep ', '', '')                                                                #   ''
        >sep  f< ['sep', 'f'] ('sep f', '', '')                                                             # TOKENS
        >sep  fo< ['sep', 'fo'] ('sep fo', '', '')                                                          #   ''
        >sep  foo< ['sep', 'foo'] ('sep foo', '', '')                                                       #   ''
        >sep  foo < ['sep', 'foo', ''] ('sep foo ', '', '')                                                 # TOKENS_SPACES
        >sep  foo  < ['sep', 'foo', ''] ('sep foo ', '', '')                                                #   ''
        >sep  foo  s< ['sep', 'foo', 's'] ('sep foo s', '', '')                                             # TOKENS_INCOMPLETE_CONJUNCTION middle=='' and last_token in conjunction_parts
        >sep  foo  se< ['sep', 'foo', 'se'] ('sep foo se', '', '')                                          #   ''
        >sep  foo  sep< ['sep', 'foo', 'sep'] ('sep foo sep', '', '')                                       # TOKENS_CONJUNCTION len(query_tokens)>1 and query_tokens[-1]==conjunction and middle==''
        >sep  foo  sep < ['sep', 'foo', 'sep', ''] ('sep foo', ' sep ', '')                                 # TOKENS_CONJUNCTION_SPACES middle!='' and tail==''
        >sep  foo  sep  < ['sep', 'foo', 'sep', ''] ('sep foo', ' sep ', '')                                #   ''
        >sep  foo  sep  b< ['sep', 'foo', 'sep', 'b'] ('sep foo', ' sep ', 'b')                             # TOKENS_CONJUNCTION_TOKENS middle!='' and tail!=''
        >sep  foo  sep  ba< ['sep', 'foo', 'sep', 'ba'] ('sep foo', ' sep ', 'ba')                          #   ''
        >sep  foo  sep  bar< ['sep', 'foo', 'sep', 'bar'] ('sep foo', ' sep ', 'bar')                       #   ...
        >sep  foo  sep  bar < ['sep', 'foo', 'sep', 'bar', ''] ('sep foo', ' sep ', 'bar ')
        >sep  foo  sep  bar  < ['sep', 'foo', 'sep', 'bar', ''] ('sep foo', ' sep ', 'bar ')
        >sep  foo  sep  bar  s< ['sep', 'foo', 'sep', 'bar', 's'] ('sep foo', ' sep ', 'bar s')
        >sep  foo  sep  bar  se< ['sep', 'foo', 'sep', 'bar', 'se'] ('sep foo', ' sep ', 'bar se')
        >sep  foo  sep  bar  sep< ['sep', 'foo', 'sep', 'bar', 'sep'] ('sep foo', ' sep ', 'bar sep')
        >sep  foo  sep  bar  sep < ['sep', 'foo', 'sep', 'bar', 'sep', ''] ('sep foo', ' sep ', 'bar sep ') #   ''
        """
        norm_text = re.sub(' +', ' ', text.lstrip())
        query_tails = {}
        query_heads = {}
        for conjunction in conjunctions:
            query_head, query_middle, query_tail = norm_text.partition(f' {conjunction} ')
            query_tail = query_tail.strip()
            if query_middle:
                query_tails[conjunction] = query_tail
                query_heads[conjunction] = query_head

        if not query_tails:
            query_tokens = text.split(' ')
            last_token = query_tokens[-1]
            if last_token=='':
                return NearbySimpleParser.Mode.TOKENS_SPACES, None, '', text
            elif last_token in conjunctions and (query_head, query_middle, query_tail) == (norm_text, '', ''):
                return NearbySimpleParser.Mode.TOKENS_CONJUNCTION, last_token, '', text
            elif last_token in conjunction_parts:
                return NearbySimpleParser.Mode.TOKENS_INCOMPLETE_CONJUNCTION, conjunction_parts[last_token][0], '', text
            else:
                return NearbySimpleParser.Mode.TOKENS, None, '', text
        else:
            conjunction = min(query_tails)
            query_tail = query_tails[conjunction]
            query_head = query_heads[conjunction]
            if query_tail == '':
                return NearbySimpleParser.Mode.TOKENS_CONJUNCTION_SPACES, None, '', ''
            else:
                return NearbySimpleParser.Mode.TOKENS_CONJUNCTION_TOKENS, conjunction, query_head, query_tail

    def conjunction_mode_function(self) -> Callable:
        if not self.language:
            return self.__no_cunjunction_function
        language = self.language.split('-')[0].lower()
        if language not in NearbySimpleParser.CONJUNCTIONS:
            return self.__no_cunjunction_function

        conjunctions = NearbySimpleParser.CONJUNCTIONS[language]
        conjunction_parts = NearbySimpleParser.CONJUNCTION_PARTS[language]

        return partial(self.__get_conjunction_mode, conjunctions=conjunctions, conjunction_parts=conjunction_parts)


class PositionMap(Map):
    default_zoom_level = 12
    default_layout = {'height': '600px'}

    def __init__(self, api_key: str,
                 center: Tuple[float, float],
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
            #self.set_position_handler(position_handler)
            self.observe(position_handler)

    def set_position_handler(self, position_handler: Callable[[float, float], None]):
        def observe(change):
            if change.type == "change": # TODO: test if this test is necessary
                if change.name in "center":
                    position_handler(*change.new[:2])
                elif change.name == "zoom":
                    position_handler(*self.center)
        self.observe(observe)
