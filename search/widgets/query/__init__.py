from IPython.display import display as Idisplay
from ipywidgets import Widget, CallbackDispatcher, HBox, VBox, Text, Button, Layout, HTML
from traitlets import observe

from search.core import debounce

from typing import List, Awaitable
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

class SearchTermsBox(VBox):
    def __init__(self, text: "SubmittableTextBox", terms_buttons: "TermsButtons"):
        self.text = text
        self.terms_buttons = terms_buttons
        VBox.__init__(self, [text, terms_buttons])

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
