from IPython.display import display as Idisplay
from ipywidgets import Widget, CallbackDispatcher, HBox, VBox, Text, Button, Layout, HTML
from ipywidgets.widgets.widget import _remove_buffers, __protocol_version__, Comm
from traitlets import observe

from ..util import debounce

from typing import List, Awaitable, Tuple, Callable
from functools import reduce
import asyncio
from dataclasses import dataclass
from enum import Enum, auto


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
        Widget.widgets[self.model_id] = self

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

    def get_key_stroke_future(self) -> Awaitable:
        # This methods allows to control the call to the widget handler outside of the jupyter event loop
        future = asyncio.Future()
        @debounce(200)
        def getvalue(change: dict):
            future.set_result(change.new)
            self.unobserve_text(getvalue, 'value')
        self.observe_text(getvalue, 'value')
        return future

    def get_submitted_value_future(self) -> Awaitable:
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

    def __init__(self, target_text_box: SubmittableTextBox, buttons_count: int=None, layout: dict=None):
        if not isinstance(buttons_count, int):
            buttons_count = TermsButtons.default_buttons_count
        width = int(100/buttons_count)
        box_layout = Layout(display="flex", justify_content="center", width=f"{width}%", border="solid 1px")
        buttons = []
        on_click_handler = self.__get_handler(target_text_box)
        for i in range(buttons_count):
            button = Button(layout=box_layout)
            button.on_click(on_click_handler)
            buttons.append(button)
        HBox.__init__(self, buttons, layout=layout or TermsButtons.default_layout)
        Idisplay(HTML("<style>.term-button button { font-size: 10px; }</style>"))
        self.add_class('term-button')


    def __get_handler(self, target_text_box: SubmittableTextBox) -> Callable:
        def on_terms_click_handler(button):
            # replace the last token with the clicked button description and a whitespace
            if target_text_box.text.value.endswith(' '):
                target_text_box.text.value = f"{target_text_box.text.value}{button.description.strip()} "
            else:
                tokens = target_text_box.text.value.strip().split(' ')
                if tokens:
                    head = tokens[:-1]
                    head.extend([button.description.strip(), ''])
                    target_text_box.text.value = ' '.join(head)
            self.set([])
        return on_terms_click_handler

    def set(self, values: list[str]):
        for i, button in enumerate(self.children):
            try:
                button.description = values[i]
            except IndexError:
                button.description = ' '

@dataclass
class QuerySimpleParser:
    text: str
    class ConjunctionMode(Enum):
        no_conjunction = auto()
        only_conjunction = auto()         # conjunction first or followed by spaces
        conjunction_last = auto()
        conjunction_spaces_last = auto()  # conjunction last, followed by spaces
        conjunction_surrounded = auto()   # conjunction surrounded by tokens
        incomplete_conjunction = auto()   # tokens followed by first letters of conjunction

    conjunction = {'en': 'near', 'de': 'bei', 'fr': 'pret de'}

    def get_conjunction_mode(self, language: str) -> Tuple[str, ConjunctionMode, str, str]:
        if not language:
            return QuerySimpleParser.conjunction_mode.no_conjunction, self.text, ''
        language = language.split('-')[0].lower()
        if language not in QuerySimpleParser.conjunction:
            return QuerySimpleParser.conjunction_mode.no_conjunction, self.text, ''
        conjunction = QuerySimpleParser.conjunction[language]

        query_parts = self.text.split(' ')
        query_with_conjunction_head, _, query_with_conjunction_tail = self.text.partition(f' {conjunction} ')
        if len(query_parts) > 1 and query_parts[-1] == conjunction:
            conjunction_mode = QuerySimpleParser.ConjunctionMode.conjunction_last
        elif len(query_parts) > 1 and query_parts[-1] in set(conjunction[:i+1] for i in range(len(conjunction)-1)):
            conjunction_mode = QuerySimpleParser.ConjunctionMode.incomplete_conjunction
        elif query_with_conjunction_head.strip() and query_with_conjunction_tail and not query_with_conjunction_tail.strip():
            conjunction_mode = QuerySimpleParser.ConjunctionMode.conjunction_last
        elif query_with_conjunction_head.strip() and query_with_conjunction_tail.strip():
            conjunction_mode = QuerySimpleParser.ConjunctionMode.conjunction_surrounded
        elif self.text == conjunction or self.text.startswith(f'{conjunction} '):
            conjunction_mode = QuerySimpleParser.ConjunctionMode.only_conjunction
        else:
            conjunction_mode = QuerySimpleParser.ConjunctionMode.no_conjunction
        return conjunction, conjunction_mode, query_with_conjunction_head, query_with_conjunction_tail