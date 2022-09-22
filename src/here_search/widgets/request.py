from IPython.display import display_html
from here_map_widget import Map, Platform, ServiceNames, MapTileUrl, MapTile, TileLayer
from ipywidgets import HBox, VBox, Text, Button, Layout, HTML
from traitlets.utils.bunch import Bunch


from here_search.entities import PlaceTaxonomyItem, PlaceTaxonomy
from here_search.util import set_dict_values
from here_search.entities import (Response, Endpoint, ResponseItem, PlaceTaxonomyItem, SearchContext, AutosuggestConfig,
                       EndpointConfig, DiscoverConfig, BrowseConfig, LookupConfig)
from here_search.api import PartialTextSearchEvent, SearchIntent, FormulatedIntent, NoIntent

from typing import Awaitable, Tuple, Callable, Sequence
from functools import reduce
import asyncio


display_html("<style>.term-button button { font-size: 10px; }</style>")


class SubmittableText(Text):
    """A ipywidgets Text class enhanced with an on_submit() method"""

    def on_submit(self, callback, remove=False):
        self._submission_callbacks.register_callback(callback, remove=remove)

    def _handle_msg(self, msg: dict) -> None:
        """
        Called when a msg is received from the front-end

        (Overrides from widgets.Widget._handle_msg)
        :param msg:
        :return:
        """
        data = msg["content"]["data"]
        method = data["method"]

        if method == "update":
            if "state" in data:
                state = data["state"]
                if "buffer_paths" in data:
                    state = set_dict_values(state, data["buffer_paths"], msg["buffers"])
                self.set_state(state)
        elif method == "request_state":
            self.send_state()
        elif method == "custom":
            if "content" in data:
                if data["content"].get("event") == "submit":
                    self._submission_callbacks(self)


class SubmittableTextBox(HBox):
    """A ipywidgets HBox made of a SubmittableText and a lens Button"""

    default_icon = "search"
    default_button_width = "32px"

    def __init__(self, queue: asyncio.Queue, *args, **kwargs):
        self.lens_w = Button(
            icon=kwargs.pop("icon", SubmittableTextBox.default_icon),
            layout={"width": SubmittableTextBox.default_button_width},
        )
        self.queue = queue
        self.text_w = SubmittableText(*args, layout=kwargs.pop("layout", Layout()), **kwargs)

        def get_instant_value(change: Bunch):
            value = change.new
            event = SearchIntent(materialization=value) if value else NoIntent()
            self.queue.put_nowait(event)
        self.text_w.observe(get_instant_value, "value")

        def get_value(_):
            value = self.text_w.value
            event = FormulatedIntent(materialization=value) if value else NoIntent()
            self.queue.put_nowait(event)
        self.on_submit(get_value)
        self.on_click(get_value)

        super().__init__([self.text_w, self.lens_w], **kwargs)

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


class SearchTermsBox(VBox):
    def __init__(self, text: "SubmittableTextBox", terms_buttons: "TermsButtons"):
        self.text = text
        self.terms_buttons = terms_buttons
        VBox.__init__(self, [text, terms_buttons])


class TermsButtons(HBox):
    """A HBox containing a list of terms Buttons"""

    default_layout = {"width": "280px"}
    default_buttons_count = 3

    def __init__(
        self,
        target_text_box: SubmittableTextBox,
        values: list[str] = None,
        buttons_count: int = None,
        index: int = None,
        layout: dict = None,
    ):
        self.target_text_box = target_text_box
        self.values = values or []
        if values:
            buttons_count = len(values)
        elif not isinstance(buttons_count, int):
            buttons_count = TermsButtons.default_buttons_count
        width = int(100 / buttons_count)
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
        self.add_class("term-button")

    def __get_click_handler(self) -> Callable:
        def handler(button):
            # replace the last token with the clicked button description and a whitespace
            if False:  # target_text_box.text_w.value.endswith(' '):
                self.target_text_box.text_w.value = f"{self.target_text_box.text_w.value}{button.description.strip()} "
            else:
                tokens = self.target_text_box.text_w.value.strip().split(" ")
                if tokens:
                    if self.token_index is None:
                        head, target, tail = [], [button.description.strip()], []
                    elif self.token_index == -1:
                        head, target, tail = tokens[: self.token_index], [button.description.strip()], [""]
                    else:
                        head, target, tail = (
                            tokens[: self.token_index],
                            [button.description.strip()],
                            tokens[self.token_index + 1 :],
                        )
                    self.target_text_box.text_w.value = " ".join(head + target + tail)

            # self.set(self.values)

        return handler

    def set(self, values: list[str]):
        self.values = values
        for i, button in enumerate(self.children):
            try:
                button.description = values[i]
            except IndexError:
                button.description = " "


class PlaceTaxonomyButton(Button):
    """
    A Button returning an taxonomy future
    """

    item: PlaceTaxonomyItem
    default_icon = "question"
    default_layout = {"width": "32px"}

    def __init__(self, item: PlaceTaxonomyItem, icon: str, **kwargs):
        """
        Creates a Button for an taxonomy instance with a specific Font-Awesome icon.
        See: https://fontawesome.com/v5/search?m=free&s=regular
        And: https://use.fontawesome.com/releases/v5.12.0/fontawesome-free-5.12.0-web.zip

        :param icon: fontawesome-free v5.12.0 icon name (with fa- prefix) or text
        :param taxonomy: taxonomy instance
        :param kwargs: Button class other attributes
        """
        self.item = item
        if not icon:
            kwargs.update({"icon": PlaceTaxonomyButton.default_icon})
        elif icon.startswith("fa-"):
            kwargs.update({"icon": icon[3:]})
        else:
            kwargs.update({"description": icon})
        super().__init__(layout=PlaceTaxonomyButton.default_layout, **kwargs)


class PlaceTaxonomyButtons(HBox):
    default_buttons = [PlaceTaxonomyButton(item=PlaceTaxonomyItem(name="_"), icon="")]

    def __init__(self, queue: asyncio.Queue, taxonomy: PlaceTaxonomy, icons: Sequence[str]):
        self.buttons = []
        self.queue = queue
        for item, icon in zip(taxonomy.items.values(), icons):
            button = PlaceTaxonomyButton(item, icon)
            def get_value(button: Button):
                intent = FormulatedIntent(materialization=button.item)
                self.queue.put_nowait(intent)
            button.on_click(get_value)
            self.buttons.append(button)
        self.buttons = self.buttons or PlaceTaxonomyButtons.default_buttons

        HBox.__init__(self, self.buttons)


class PositionMap(Map):
    default_zoom_level = 12
    default_layout = {"height": "600px"}

    def __init__(
        self,
        api_key: str,
        center: Tuple[float, float],
        position_handler: Callable[[float, float], None] = None,
        **kvargs,
    ):

        platform = Platform(
            api_key=api_key,
            services_config={
                ServiceNames.maptile: {
                    MapTileUrl.scheme: "https",
                    MapTileUrl.host: "maps.ls.hereapi.com",
                    MapTileUrl.path: "maptile/2.1",
                }
            },
        )
        map_tile = MapTile(tile_type="maptile", scheme="normal.day", tile_size=256, format="png", platform=platform)
        maptile_layer = TileLayer(provider=map_tile, style={"max": 22})
        Map.__init__(
            self,
            api_key=api_key,
            center=center,
            zoom=kvargs.pop("zoom", PositionMap.default_zoom_level),
            basemap=maptile_layer,
            layout=kvargs.pop("layout", PositionMap.default_layout),
        )
        if position_handler:
            self.set_position_handler(position_handler)

    def set_position_handler(self, position_handler: Callable[[float, float], None]):
        def observe(change):
            if change.type == "change":  # TODO: test if this test is necessary
                if change.name in "center":
                    position_handler(*change.new[:2])
                elif change.name == "zoom":
                    position_handler(*self.center)

        self.observe(observe)
