###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################


import asyncio
from unittest.mock import MagicMock

import pytest

from here_search_demo.auth import Credentials
from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.place import PlaceTaxonomy, PlaceTaxonomyItem
from here_search_demo.widgets.input_map import PositionMap
from here_search_demo.widgets.input_text import (
    PlaceTaxonomyButton,
    PlaceTaxonomyButtons,
    SubmittableText,
    SubmittableTextBox,
    TermsButtons,
)
from here_search_demo.widgets.route import RouteController
from here_search_demo.widgets.state import SearchState


@pytest.fixture
def queue():
    return MagicMock(spec=asyncio.Queue)


@pytest.fixture
def credentials():
    return Credentials()


def test_submittable_text_on_submit_and_handle_msg():
    text = SubmittableText()
    called = []

    def cb(widget):
        called.append(widget)

    text.on_submit(cb)
    msg = {"content": {"data": {"method": "custom", "content": {"event": "submit"}}}}
    text._handle_msg(msg)
    assert called and called[0] is text


def test_submittable_textbox_enable_disable(queue):
    box = SubmittableTextBox(queue, SearchState())
    box.disable()
    assert box.text_w.disabled and box.lens_w.disabled
    box.emable()
    assert not box.text_w.disabled and not box.lens_w.disabled


def test_placetaxonomybuttons_click_puts_intent(queue):
    taxonomy = PlaceTaxonomy(name="foo", items=[PlaceTaxonomyItem(name="a")])
    icons = ["fa-question"]
    ptb = PlaceTaxonomyButtons(queue, taxonomy, icons, SearchState())
    ptb.buttons[0].item = taxonomy.items["a"]
    ptb.buttons[0].click()
    assert queue.put_nowait.called


@pytest.mark.asyncio
async def test_termsbuttons_click_handler_none_index(queue):
    # Use a very short debounce delay to make the test fast and reduce flakiness
    box = SubmittableTextBox(queue, SearchState(), debounce_delay=0.0)
    tb = TermsButtons(box, state=SearchState(), values=["foo"], index=None)

    # Seed the text box with some value and simulate a click on the first term button
    box.text_w.value = "something"
    tb.children[0].description = "bar"
    tb.children[0].click()

    # The click handler should synchronously update the text value
    assert box.text_w.value.strip() == "bar"


def test_placetaxonomybutton_icon_handling():
    item = PlaceTaxonomyItem(name="test")
    btn1 = PlaceTaxonomyButton(item, "")
    assert btn1.icon == PlaceTaxonomyButton.default_icon
    btn2 = PlaceTaxonomyButton(item, "fa-star")
    assert btn2.icon == "star"
    btn3 = PlaceTaxonomyButton(item, "custom")
    assert btn3.description == "custom"


def test_placetaxonomybuttons_default_button(queue):
    taxonomy = PlaceTaxonomy(items={}, name="foo")
    ptb = PlaceTaxonomyButtons(queue, taxonomy, [], SearchState())
    assert isinstance(ptb.buttons[0], PlaceTaxonomyButton)


def test_submittable_text_on_submit_remove():
    text = SubmittableText()
    called = []

    def cb(widget):
        called.append(widget)

    text.on_submit(cb)
    text.on_submit(cb, remove=True)
    msg = {"content": {"data": {"method": "custom", "content": {"event": "submit"}}}}
    text._handle_msg(msg)
    assert not called


def test_submittable_textbox_on_submit_remove(queue):
    box = SubmittableTextBox(queue, SearchState())
    called = []

    def cb(_):
        called.append(True)

    box.on_submit(cb)
    box.on_submit(cb, remove=True)
    box.text_w._submission_callbacks(box.text_w)
    assert not called


def test_submittable_textbox_on_click_remove(queue):
    box = SubmittableTextBox(queue, SearchState())
    called = []

    def cb(_):
        called.append(True)

    box.on_click(cb)
    box.on_click(cb, remove=True)
    box.lens_w.click()
    assert not called


def test_termsbuttons_set_fewer_values(queue):
    box = SubmittableTextBox(queue, SearchState())
    tb = TermsButtons(box, state=SearchState(), values=["foo", "bar", "baz"])
    tb.set(["one"])
    assert tb.children[0].description == "one"
    assert tb.children[1].description == " "
    assert tb.children[2].description == " "


def test_placetaxonomybutton_no_icon_and_text():
    item = PlaceTaxonomyItem(name="test")
    btn = PlaceTaxonomyButton(item, None)
    assert btn.icon == PlaceTaxonomyButton.default_icon
    btn2 = PlaceTaxonomyButton(item, "customtext")
    assert btn2.description == "customtext"


def test_placetaxonomybuttons_default_fallback(queue):
    taxonomy = PlaceTaxonomy(name="foo", items={})
    ptb = PlaceTaxonomyButtons(queue, taxonomy, [], SearchState())
    assert isinstance(ptb.buttons[0], PlaceTaxonomyButton)
    assert ptb.buttons[0].item.name == "_"


def test_route_controller_stores_credentials(credentials):
    """RouteController must own the Credentials, not an api_key borrowed from the map."""
    map_route = PositionMap(credentials=credentials, center=(1.0, 2.0), route_post=True)
    assert isinstance(map_route.route, RouteController)
    assert map_route.route.credentials is credentials


# ---------------------------------------------------------------------------
# _trim_transients — queue management algorithm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trim_transients_keeps_last_n_and_preserves_non_transients():
    """
    Pre-populate the queue with 4 transient intents + 1 non-transient, then
    fire a new transient via a text change. After the debounce fires,
    _trim_transients(max_keep=2) should leave at most 2 transients in the
    queue (the newest ones) while keeping non-transient items intact.
    """
    real_queue = asyncio.Queue()
    box = SubmittableTextBox(real_queue, SearchState(), debounce_delay=0, max_transient_keep=2)

    for i in range(4):
        real_queue.put_nowait(SearchIntent(kind="transient_text", materialization=f"t{i}", time=0))
    real_queue.put_nowait(SearchIntent(kind="submitted_text", materialization="keep", time=0))

    box.text_w.value = "hello"
    await asyncio.sleep(0.05)  # let the debounce (0 s) fire

    items = []
    while not real_queue.empty():
        items.append(real_queue.get_nowait())

    transients = [it for it in items if it.kind == "transient_text"]
    non_transients = [it for it in items if it.kind != "transient_text"]

    assert len(transients) <= box.max_transient_keep
    assert len(non_transients) == 1
    assert non_transients[0].materialization == "keep"


@pytest.mark.asyncio
async def test_trim_transients_zero_max_keep_is_noop():
    """max_transient_keep=0 disables trimming entirely."""
    real_queue = asyncio.Queue()
    box = SubmittableTextBox(real_queue, SearchState(), debounce_delay=0, max_transient_keep=0)

    for i in range(5):
        real_queue.put_nowait(SearchIntent(kind="transient_text", materialization=f"t{i}", time=0))

    box.text_w.value = "x"
    await asyncio.sleep(0.05)

    items = []
    while not real_queue.empty():
        items.append(real_queue.get_nowait())

    # Without trimming all pre-existing + the new transient survive
    assert len([it for it in items if it.kind == "transient_text"]) == 6


@pytest.mark.asyncio
async def test_emit_transient_skips_duplicate_normalized_value():
    real_queue = asyncio.Queue()
    box = SubmittableTextBox(real_queue, SearchState(), debounce_delay=0, max_transient_keep=3)

    box.text_w.value = "pizza"
    for _ in range(20):
        if not real_queue.empty():
            break
        await asyncio.sleep(0.01)
    box.text_w.value = "pizza "
    await asyncio.sleep(0.05)

    if box._debounce_task and not box._debounce_task.done():
        box._debounce_task.cancel()

    items = []
    while not real_queue.empty():
        items.append(real_queue.get_nowait())

    transients = [it for it in items if it.kind == "transient_text"]
    assert [it.materialization for it in transients] == ["pizza"]


# ---------------------------------------------------------------------------
# adjust_debounce_delay — adaptive back-pressure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adjust_debounce_delay_increases_when_backlog():
    """When qsize >= queue_backlog_threshold the debounce delay must grow."""
    real_queue = asyncio.Queue()
    # Pre-fill queue to reach the threshold (3)
    for i in range(SubmittableTextBox.queue_backlog_threshold):
        real_queue.put_nowait(SearchIntent(kind="transient_text", materialization=f"t{i}", time=0))

    box = SubmittableTextBox(real_queue, SearchState(), debounce_delay=0.1)
    initial_delay = box._debounce_delay

    # on_value_change (and therefore adjust_debounce_delay) fires synchronously
    box.text_w.value = "x"

    assert box._debounce_delay > initial_delay
    if box._debounce_task and not box._debounce_task.done():
        box._debounce_task.cancel()


@pytest.mark.asyncio
async def test_adjust_debounce_delay_decreases_when_no_backlog():
    """When qsize < threshold the debounce delay must shrink (back-off)."""
    real_queue = asyncio.Queue()  # empty — no backlog

    box = SubmittableTextBox(real_queue, SearchState(), debounce_delay=0.2)
    initial_delay = box._debounce_delay

    box.text_w.value = "y"

    assert box._debounce_delay < initial_delay
    if box._debounce_task and not box._debounce_task.done():
        box._debounce_task.cancel()


# ---------------------------------------------------------------------------
# TermsButtons click handler — token_index=-1 (append) and index=N (mid-replace)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_termsbuttons_click_handler_minus1_appends_term():
    """
    token_index=-1 (default): the clicked term becomes the last *non-empty*
    token, followed by an empty string (to leave a trailing space so the next
    word can be typed).
    """
    real_queue = asyncio.Queue()
    box = SubmittableTextBox(real_queue, SearchState(), debounce_delay=0.0)
    tb = TermsButtons(box, state=SearchState(), values=["THERE"], index=-1)

    box.text_w.value = "hello world"
    tb.children[0].description = "THERE"
    tb.children[0].click()

    # tokens = ["hello", "world"]; head = tokens[:-1] = ["hello"]
    # target = ["THERE"]; tail = [""]
    # new_value = "hello THERE "
    assert "THERE" in box.text_w.value
    assert box.text_w.value.startswith("hello")


@pytest.mark.asyncio
async def test_termsbuttons_click_handler_positive_index_replaces_token():
    """token_index=0 replaces the first token, keeping the rest."""
    real_queue = asyncio.Queue()
    box = SubmittableTextBox(real_queue, SearchState(), debounce_delay=0.0)
    tb = TermsButtons(box, state=SearchState(), values=["hi"], index=0)

    box.text_w.value = "hello world extra"
    tb.children[0].description = "hi"
    tb.children[0].click()

    # head = tokens[:0] = []; target = ["hi"]; tail = tokens[1:] = ["world", "extra"]
    assert box.text_w.value == "hi world extra"


# ---------------------------------------------------------------------------
# bind_position_handler — None handler early-return (line 661)
# ---------------------------------------------------------------------------


# No assertion needed beyond "no exception"; the handler is a no-op here.


def test_submittable_text_handle_msg_update_with_state():
    """Test _handle_msg with update method and state data."""
    text = SubmittableText()
    msg = {"content": {"data": {"method": "update", "state": {"value": "test"}}}, "buffers": []}
    text._handle_msg(msg)
    assert text.value == "test"


def test_submittable_text_handle_msg_update_with_buffer_paths():
    """Test _handle_msg with update method and buffer_paths."""
    text = SubmittableText()
    msg = {"content": {"data": {"method": "update", "state": {"value": "initial"}, "buffer_paths": []}}, "buffers": []}
    text._handle_msg(msg)
    assert text.value == "initial"


def test_submittable_text_handle_msg_request_state(monkeypatch):
    """Test _handle_msg with request_state method."""
    text = SubmittableText()
    called = []

    def mock_send_state():
        called.append(True)

    monkeypatch.setattr(text, "send_state", mock_send_state)
    msg = {"content": {"data": {"method": "request_state"}}}
    text._handle_msg(msg)
    assert called


@pytest.mark.asyncio
async def test_submittable_textbox_feed():
    """Test feed method."""
    queue = asyncio.Queue()
    box = SubmittableTextBox(queue, SearchState())

    # Test with basic text
    asyncio.create_task(box.feed("hi", delay=0.001))
    await asyncio.sleep(0.05)
    assert box.text_w.value == "hi"


@pytest.mark.asyncio
async def test_submittable_textbox_feed_with_backspace():
    """Test feed with backspace character."""
    queue = asyncio.Queue()
    box = SubmittableTextBox(queue, SearchState())

    # Test with backspace
    asyncio.create_task(box.feed("ab\bc", delay=0.001))
    await asyncio.sleep(0.05)
    assert box.text_w.value == "ac"


def test_submittable_textbox_submit():
    """Test programmatic submit."""
    queue = MagicMock()
    box = SubmittableTextBox(queue, SearchState())
    called = []

    def cb(_):
        called.append(True)

    box.on_submit(cb)
    box.submit()
    assert called


def test_termsbuttons_with_values_shorter_than_buttons():
    """Test TermsButtons initialization with fewer values than default buttons."""
    queue = MagicMock()
    box = SubmittableTextBox(queue, SearchState())
    state = SearchState()
    tb = TermsButtons(box, state, values=["a", "b"])
    assert len(tb.children) == 2


def test_termsbuttons_apply_style():
    """Test TermsButtons style application."""
    queue = MagicMock()
    box = SubmittableTextBox(queue, SearchState())
    tb = TermsButtons(box, SearchState(), values=["test"])
    tb.apply_style()
    # The test should not raise and _style_applied should be True after first call
    assert TermsButtons._style_applied
