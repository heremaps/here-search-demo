###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
from time import perf_counter_ns
from typing import Callable, Sequence, Tuple

import xyzservices.providers
from ipyleaflet import (
    FullScreenControl,
    Map,
    Popup,
    ScaleControl,
    ZoomControl,
)
from IPython.display import display as Idisplay
from ipywidgets import HTML, Button, Checkbox, HBox, Layout, Select, Text, VBox, Widget
from traitlets.utils.bunch import Bunch

from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.place import PlaceTaxonomy, PlaceTaxonomyItem
from here_search_demo.widgets.util import FakeRouteController
from here_search_demo.util import set_dict_values

try:
    from here_search_demo.widgets.route import RouteController
except ImportError:
    RouteController = FakeRouteController

from here_search_demo.widgets.state import SearchState


class SubmittableText(Text):
    """A ipywidgets Text class enhanced with an on_submit() method"""

    def on_submit(self, callback, remove=False):
        self._submission_callbacks.register_callback(callback, remove=remove)

    def trigger_submit(self) -> None:
        """Programmatically invoke all registered submit callbacks.

        This mirrors the behavior when the front-end fires a ``submit``
        custom event, without reaching into private attributes from
        outside this subclass.
        """
        self._submission_callbacks(self)

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
                    self.trigger_submit()


class SubmittableTextBox(HBox):
    """A ipywidgets HBox made of a SubmittableText and a lens Button"""

    default_icon = "search"
    default_button_width = "32px"
    default_debounce_delay = 0.1  # We keep it low to improve UX
    min_debounce_delay = 0.05
    max_debounce_delay = 0.4
    queue_backlog_threshold = 3
    default_simulation_delay_sec = 0.02

    def __init__(self, queue: asyncio.Queue, state: SearchState, *args, **kwargs):
        self.lens_w = Button(
            icon=kwargs.pop("icon", SubmittableTextBox.default_icon),
            layout={"width": SubmittableTextBox.default_button_width},
        )
        self.queue = queue
        self._queue_put = queue.put_nowait
        self._queue_get_nowait = queue.get_nowait
        self.state = state
        self._debounce_delay = kwargs.pop("debounce_delay", self.default_debounce_delay)
        self.max_transient_keep = kwargs.pop("max_transient_keep", 3)
        self._debounce_task: asyncio.Task | None = None
        self._pending_transient_value: str | None = None
        self.text_w = SubmittableText(*args, layout=kwargs.pop("layout", Layout()), **kwargs)
        self.text_w.value = state.current_query

        def cancel_debounce():
            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()
            self._debounce_task = None

        def _trim_transients(max_keep: int):
            if not max_keep:
                return
            items: list = []
            try:
                while True:
                    items.append(self._queue_get_nowait())
            except asyncio.QueueEmpty:
                pass
            transients = [it for it in items if getattr(it, "kind", None) == "transient_text"]
            keep_tail = transients[-max_keep:]
            rebuilt = []
            to_skip = len(transients) - len(keep_tail)
            for it in items:
                if getattr(it, "kind", None) == "transient_text":
                    if to_skip:
                        to_skip -= 1
                        continue
                rebuilt.append(it)
            for it in rebuilt:
                self._queue_put(it)

        async def emit_transient():
            try:
                await asyncio.sleep(self._debounce_delay)
                value = (self._pending_transient_value or "").strip()
                self.state.set_query_text(value)
                if value:
                    self._queue_put(SearchIntent(kind="transient_text", materialization=value, time=perf_counter_ns()))
                    _trim_transients(self.max_transient_keep)
                else:
                    self._queue_put(SearchIntent(kind="empty", materialization=None, time=perf_counter_ns()))
            except asyncio.CancelledError:
                pass
            finally:
                self._debounce_task = None

        def adjust_debounce_delay():
            try:
                qsize_fn = getattr(self.queue, "qsize", None)
                raw_depth = qsize_fn() if callable(qsize_fn) else getattr(self.queue, "qsize", 0)
                depth = int(raw_depth)
            except Exception:
                depth = 0
            if depth >= self.queue_backlog_threshold:
                self._debounce_delay = min(self.max_debounce_delay, self._debounce_delay * 1.5)
            else:
                self._debounce_delay = max(self.min_debounce_delay, self._debounce_delay * 0.9)

        def on_value_change(change: Bunch):
            self._pending_transient_value = change.new or ""
            adjust_debounce_delay()
            cancel_debounce()
            self._debounce_task = asyncio.create_task(emit_transient())

        self.text_w.observe(on_value_change, "value")

        def commit(_):
            cancel_debounce()
            value = (self.text_w.value or "").strip()
            self.state.set_query_text(value)
            if value:
                self._queue_put(SearchIntent(kind="submitted_text", materialization=value, time=perf_counter_ns()))

        self.on_submit(commit)
        self.on_click(commit)

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

    async def feed(self, text, delay: float = None):
        delay = delay or SubmittableTextBox.default_simulation_delay_sec
        self.text_w.value = ""
        for ch in text:
            self.text_w.value = self.text_w.value[:-1] if ch == "\b" else self.text_w.value + ch
            await asyncio.sleep(delay)
        await asyncio.sleep(2 * SubmittableTextBox.default_debounce_delay)

    def submit(self):
        """Programmatically trigger a submit."""
        self.text_w.trigger_submit()


class SearchTermsBox(VBox):
    def __init__(self, text: "SubmittableTextBox", terms_buttons: "TermsButtons"):
        self.text = text
        self.terms_buttons = terms_buttons
        VBox.__init__(self, [text, terms_buttons])


class TermsButtons(HBox):
    """A HBox containing a list of terms Buttons"""

    default_layout = {"width": "280px"}
    default_buttons_count = 3
    _style_applied = False

    def __init__(
        self,
        target_text_box: SubmittableTextBox,
        state: SearchState,
        values: list[str] | None = None,
        buttons_count: int = None,
        index: int = -1,
        layout: dict = None,
    ):
        self.target_text_box = target_text_box
        self.state = state
        if values is not None:
            self.state.set_term_suggestions(values)
        if state.term_suggestions:
            buttons_count = len(state.term_suggestions)
        elif not isinstance(buttons_count, int):
            buttons_count = TermsButtons.default_buttons_count
        width = int(100 / buttons_count)
        self.token_index = index
        box_layout = Layout(
            display="flex",
            justify_content="center",
            width=f"{width}%",
            # border="solid 1px",
        )
        buttons = []
        on_click_handler = self.__get_click_handler()
        for _ in range(buttons_count):
            button = Button(layout=box_layout)
            button.on_click(on_click_handler)
            buttons.append(button)
        HBox.__init__(self, buttons, layout=layout or TermsButtons.default_layout)
        self.render()

    def apply_style(self):
        self.add_class("term-button")
        if not TermsButtons._style_applied:
            Idisplay(HTML("<style>.term-button button { font-size: 10px; }</style>"), display_id=True)
            TermsButtons._style_applied = True

    def __get_click_handler(self) -> Callable:
        def handler(button):
            tokens = self.target_text_box.text_w.value.strip().split(" ")
            if tokens:
                if self.token_index is None:
                    head, target, tail = [], [button.description.strip()], []
                elif self.token_index == -1:
                    head, target, tail = (
                        tokens[: self.token_index],
                        [button.description.strip()],
                        [""],
                    )
                else:
                    head, target, tail = (
                        tokens[: self.token_index],
                        [button.description.strip()],
                        tokens[self.token_index + 1 :],
                    )
                new_value = " ".join(head + target + tail)
                self.target_text_box.text_w.value = new_value
                self.state.set_query_text(new_value)

        return handler

    def render(self):
        values = self.state.term_suggestions
        for i, button in enumerate(self.children):
            button.description = values[i] if i < len(values) else " "

    def set(self, values: list[str]):
        self.state.set_term_suggestions(values)
        self.render()


class PlaceTaxonomyButton(Button):
    """
    A Button returning a taxonomy future
    """

    item: PlaceTaxonomyItem
    default_icon = "question"
    default_layout = {"width": "32px"}

    def __init__(self, item: PlaceTaxonomyItem, icon: str, **kwargs):
        """
        Creates a Button for a taxonomy instance with a specific Font-Awesome icon.
        See:
          - https://fontawesome.com/v5/search?m=free&s=regular
          - https://fontawesome.com/v5/cheatsheet/
          - https://use.fontawesome.com/releases/v5.12.0/fontawesome-free-5.12.0-web.zip

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

    def __init__(self, queue: asyncio.Queue, taxonomy: PlaceTaxonomy, icons: Sequence[str], state: SearchState):
        self.buttons = []
        self.queue = queue
        self.state = state
        for item, icon in zip(taxonomy.items.values(), icons):
            button = PlaceTaxonomyButton(item, icon)

            def handle(btn: Button):
                self.state.select_taxonomy_item(btn.item)
                intent = SearchIntent(kind="taxonomy", materialization=btn.item, time=perf_counter_ns())
                self.queue.put_nowait(intent)

            button.on_click(handle)
            self.buttons.append(button)
        self.buttons = self.buttons or PlaceTaxonomyButtons.default_buttons

        HBox.__init__(self, self.buttons)


class PositionMap(Map):
    default_zoom_level = 12
    default_layout = {"height": "600px"}
    long_press_threshold = 0.5

    def __init__(
        self,
        api_key: str,
        center: Tuple[float, float],
        position_handler: Callable[[tuple[float, float]], None] = None,
        route_post: bool = False,
        preferred_language: str = None,
        **kvargs,
    ):
        """
        PositionMap instance initializer

        https://github.com/geopandas/xyzservices/blob/main/provider_sources/leaflet-providers-parsed.json

        :param api_key: apiKey expected by HERE basemaps
        :param center:
        :param position_handler:
        :param kvargs:
        """
        self.api_key = api_key
        basemap = xyzservices.providers.HERE.exploreDay
        basemap["url"] = (
            "https://maps.hereapi.com/v3/base/mc/{z}/{x}/{y}/png"
            "?style=explore.day&ppi=400&size=512&apiKey={apiKey}&lang={language}"
        )  # Workaround against https://github.com/geopandas/xyzservices/issues/193
        basemap["apiKey"] = api_key
        basemap["language"] = preferred_language or "en"

        Map.__init__(
            self,
            center=center,
            zoom=kvargs.pop("zoom", PositionMap.default_zoom_level),
            basemap=basemap,
            layout=kvargs.pop("layout", PositionMap.default_layout),
            zoom_control=False,
            scroll_wheel_zoom=True,
            close_popup_on_click=False,
            double_click_zoom=False,
            box_zoom=True,
        )
        self.add(ScaleControl(position="bottomright"))
        self.add(FullScreenControl(position="bottomright"))
        self.add(ZoomControl(position="bottomright"))
        self.bind_position_handler(self.set_center)
        if position_handler:
            self.bind_position_handler(position_handler)

        # Track one long-press and one short-press popup at most.
        self.short_press_popup: Popup | None = None
        self.long_press_popup: Popup | None = None
        self.long_press_task: asyncio.Task | None = None

        # Route-related logic lives in a dedicated controller.
        self.route = RouteController(self) if route_post else FakeRouteController(self)

        # Configure long-press interaction (map options for center / route).
        if RouteController != FakeRouteController:
            long_press_select_options = {"map center": self.set_center}
            long_press_select_options.update(self.route.get_route_select_options())
            long_press_checkbox_options = self.route.get_route_checkbox_options()
            widgets = self.route.get_widgets(self.close_long_press_popup)
            self.set_long_press_interaction(long_press_select_options, long_press_checkbox_options, *widgets)

        if False:

            def observe(change: Bunch):
                print(f"observe: {change.name, change.new}")

            self.observe(observe)

        if False:

            def interact(**change):
                print(f"on_interaction: {change}")

            self.on_interaction(interact)

    def set_center(self, latlon: tuple[float, float]):
        self.center = latlon

    def long_press_handler(self, position, long_press_select_options, long_press_checkbox_options, *widgets: Widget):
        """Handle a long press at the given position.

        Ensures only a single long-press popup is visible, and closes any
        existing short-press popup to avoid overlapping controls.
        """
        self.close_popups()

        close_btn = self.build_close_btn()

        map_action_selection_w = Select(
            options=long_press_select_options,
            rows=len(long_press_select_options),
            value=None,
            layout=Layout(
                width="100px",
                align_self="flex-start",
                # border='1px solid black'
            ),
        )

        def action_choice_handler(change: Bunch):
            handler: Callable[[tuple[float, float]], None] = long_press_select_options[change["new"]]
            handler(position)
            self.close_long_press_popup()

        map_action_selection_w.observe(action_choice_handler, names="label")

        checkboxes = []
        for text, (get_function, set_function) in long_press_checkbox_options.items():
            checkbox = Checkbox(
                description=text,
                value=get_function(),
                layout=Layout(width="100px"),
                style={"description_width": "initial"},
            )

            def handler(change: Bunch):
                set_function(change["new"])

            checkbox.observe(handler, names="value")
            checkboxes.append(checkbox)
        map_action_checkbox_w = VBox(checkboxes)

        content = VBox(
            [close_btn, map_action_selection_w, *widgets, map_action_checkbox_w],
            layout=Layout(
                width="106px",
                align_items="flex-start",
                marging="0px",
                padding="0px",
                # border='1px solid black'
            ),
        )
        self.long_press_popup = Popup(
            location=position,
            child=content,
            close_button=False,  # We provide our own close button
            auto_close=False,
            close_on_escape_key=True,
            auto_pan=False,
            min_width=110,  # match or slightly larger than VBox
            max_width=120,
        )
        self.add(self.long_press_popup)

    def close_long_press_popup(self):
        if self.long_press_popup is not None:
            self.remove(self.long_press_popup)
            self.long_press_popup = None

    def close_short_press_popup(self):
        if self.short_press_popup is not None:
            self.remove(self.short_press_popup)
            self.short_press_popup = None

    def close_popups(self):
        """Close any visible long-press or short-press popup.

        Ensures that at most one of each popup type is visible at any
        time and that they remain mutually exclusive.
        """
        self.close_long_press_popup()
        self.close_short_press_popup()

    def set_short_press_interaction(self, short_press_options: dict | None = None):
        """Configure short-press (simple click) behavior.

        This is separate from long-press handling. A short press should
        only ever show a short_press_popup, and will close any existing
        long-press popup first.
        """
        short_press_options = short_press_options or {}

        def interact(**event):
            if event.get("type") != "click":
                return

            # A short press should not leave a long-press popup visible.
            self.close_long_press_popup()
            # Also close any previous short-press popup so only one exists.
            self.close_short_press_popup()

            # Implement your specific short-press popup creation here.
            # For now we only record the click location if provided.
            position = event.get("coordinates")
            if position is None:
                return

            close_btn = Button(description="Close", layout=Layout(width="32px"))

            def on_click_handler(btn: Button):
                self.close_short_press_popup()

            close_btn.on_click(on_click_handler)
            content = VBox([close_btn, HTML(value="Short press")])
            self.short_press_popup = Popup(
                location=position,
                child=content,
                close_button=True,
                auto_close=True,
                close_on_escape_key=True,
                auto_pan=False,
            )
            self.add(self.short_press_popup)

        self.on_interaction(interact)

    def set_long_press_interaction(
        self,
        long_press_select_options: dict | None = None,
        long_press_checkbox_options: dict | None = None,
        *widgets: Widget,
    ):
        async def defer_map_position_task(position):
            try:
                await asyncio.sleep(self.long_press_threshold)
                # Ensure that this really is a long press by the time the
                # delay elapses; if the task has been cleared, skip.
                if self.long_press_task is not None:
                    self.long_press_handler(position, long_press_select_options, long_press_checkbox_options, *widgets)
            except asyncio.CancelledError:
                pass

        def interact(**event):
            if event["type"] == "mousedown":
                if self.long_press_task is not None and not self.long_press_task.done():
                    self.long_press_task.cancel()
                self.long_press_task = asyncio.create_task(defer_map_position_task(event["coordinates"]))
            elif event["type"] == "mouseup":
                # Mouse released before threshold -> this was a short press;
                # cancel the long-press task and let any click handler deal
                # with short-press behavior.
                if self.long_press_task is not None and not self.long_press_task.done():
                    self.long_press_task.cancel()
                    self.long_press_task = None

        self.on_interaction(interact)

    def build_close_btn(self):
        close_btn = Button(
            icon="close",
            layout=Layout(width="32px", align_self="flex-end"),
        )

        def on_click_handler(btn: Button):
            self.close_long_press_popup()

        close_btn.on_click(on_click_handler)
        return close_btn

    def bind_position_handler(self, position_handler: Callable[[tuple[float, float]], None] | None = None):
        def observe(change: Bunch):
            # Any map movement closes the long-press popup so it does not
            # linger over a different map region.
            self.close_long_press_popup()
            # Optionally also close short-press popup if you don't want
            # it to persist across pans/zooms.
            # self.close_short_press_popup()
            if not position_handler:
                return
            if change.name in "center":
                position_handler(change.new)
            elif change.name == "zoom":
                position_handler(self.center)

        self.observe(observe, ["center", "zoom"])
