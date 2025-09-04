###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################


import pytest
import asyncio
from unittest.mock import MagicMock

from src.here_search.demo.widgets.input import (
    SubmittableText,
    SubmittableTextBox,
    TermsButtons,
    PlaceTaxonomyButton,
    PlaceTaxonomyButtons,
    PositionMap,
)
from src.here_search.demo.entity.place import PlaceTaxonomy, PlaceTaxonomyItem


@pytest.fixture
def queue():
    return MagicMock(spec=asyncio.Queue)


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
    box = SubmittableTextBox(queue)
    box.disable()
    assert box.text_w.disabled and box.lens_w.disabled
    box.emable()
    assert not box.text_w.disabled and not box.lens_w.disabled


def test_placetaxonomybuttons_click_puts_intent(queue):
    taxonomy = PlaceTaxonomy(name="foo", items=[PlaceTaxonomyItem(name="a")])
    icons = ["fa-question"]
    ptb = PlaceTaxonomyButtons(queue, taxonomy, icons)
    ptb.buttons[0].item = taxonomy.items["a"]
    ptb.buttons[0].click()
    assert queue.put_nowait.called


def test_termsbuttons_click_handler_none_index(queue):
    box = SubmittableTextBox(queue)
    tb = TermsButtons(box, values=["foo"], index=None)
    box.text_w.value = "something"
    tb.children[0].description = "bar"
    tb.children[0].click()
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
    ptb = PlaceTaxonomyButtons(queue, taxonomy, [])
    assert isinstance(ptb.buttons[0], PlaceTaxonomyButton)


def test_positionmap_set_position_handler():
    called = []

    def handler(lat, lon):
        called.append((lat, lon))

    map_obj = PositionMap(api_key="key", center=(1.0, 2.0), position_handler=handler)
    map_obj.center = (3.0, 4.0)
    assert called[-1] == (3.0, 4.0)


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
    box = SubmittableTextBox(queue)
    called = []

    def cb(_):
        called.append(True)

    box.on_submit(cb)
    box.on_submit(cb, remove=True)
    box.text_w._submission_callbacks(box.text_w)
    assert not called


def test_submittable_textbox_on_click_remove(queue):
    box = SubmittableTextBox(queue)
    called = []

    def cb(_):
        called.append(True)

    box.on_click(cb)
    box.on_click(cb, remove=True)
    box.lens_w.click()
    assert not called


def test_termsbuttons_set_fewer_values(queue):
    box = SubmittableTextBox(queue)
    tb = TermsButtons(box, values=["foo", "bar", "baz"])
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
    ptb = PlaceTaxonomyButtons(queue, taxonomy, [])
    assert isinstance(ptb.buttons[0], PlaceTaxonomyButton)
    assert ptb.buttons[0].item.name == "_"


def test_positionmap_set_position_handler_zoom(monkeypatch):
    called = []

    def handler(lat, lon):
        called.append((lat, lon))

    map_obj = PositionMap(api_key="key", center=(1.0, 2.0))
    observers = []

    def fake_observe(fn):
        observers.append(fn)

    monkeypatch.setattr(map_obj, "observe", fake_observe)
    map_obj.set_position_handler(handler)

    class Change:
        type = "change"
        name = "zoom"
        new = 15

    observers[0](Change())
    assert called[-1] == (1.0, 2.0)


def test_positionmap_observer_registration(monkeypatch):
    map_obj = PositionMap(api_key="key", center=(1.0, 2.0))
    called = []

    def handler(lat, lon):
        called.append((lat, lon))

    observed = []

    def fake_observe(fn):
        observed.append(fn)

    monkeypatch.setattr(map_obj, "observe", fake_observe)
    map_obj.set_position_handler(handler)
    assert len(observed) == 1
    assert callable(observed[0])
