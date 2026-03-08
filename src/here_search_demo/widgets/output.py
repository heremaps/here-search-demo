###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
import re
import time
from collections.abc import Callable
from urllib.parse import urlparse

from ipyleaflet import GeoJSON, Popup, wait_for_change
from IPython.display import JSON as IJSON, display as Idisplay
from ipywidgets import HTML, Button, HBox, Label, Layout, Output, VBox, Widget
from traitlets import Any

from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.response import LocationResponseItem, Response
from here_search_demo.entity.response_data import LocationDataItemDict, PlaceDataItemDict
from here_search_demo.widgets.state import MapState, SearchState

from .input import PositionMap

BoundsType = tuple[tuple[float, float], tuple[float, float]]


class SearchResultList(VBox):
    default_layout = {
        "display": "flex",
        "width": "276px",
        "height": "400px",
        "justify_content": "flex-start",
        "overflow_y": "scroll",
        "overflow": "scroll",
    }
    default_max_results_count = 20

    def __init__(
        self,
        widget: Widget = None,
        max_results_number: int = None,
        queue: asyncio.Queue = None,
        layout: dict = None,
        **kwargs,
    ):
        self.widget = widget or Output()
        self.max_results_number = max_results_number or self.default_max_results_count
        self.queue = queue or asyncio.Queue()
        self.layout = layout or self.default_layout
        self.futures = []
        super().__init__([self.widget], **kwargs)

    def _display(self, resp: Response, intent: SearchIntent = None) -> Widget:
        raise NotImplementedError()

    def _modify(self, resp: Response, intent: SearchIntent = None) -> Widget:
        raise NotImplementedError()

    def _clear(self):
        return Output(layout=self.layout)

    def display(self, resp: Response, intent: SearchIntent = None) -> None:
        # https://github.com/jupyterlab/jupyterlab/issues/3151#issuecomment-339476572
        old_out = self.children[0]
        out = self._display(resp, intent=intent)
        self.children = [out]
        old_out.close()

    def modify(self, resp: Response, intent: SearchIntent = None) -> None:
        self._modify(resp, intent=intent)

    def clear(self):
        old_out = self.children[0]
        out = self._clear()
        self.children = [out]
        old_out.close()


class SearchResultJson(SearchResultList):
    def _display(self, resp: Response, intent: SearchIntent = None) -> Widget:
        out: Output = self._clear()
        out.append_display_data(IJSON(dict(resp.data), expanded=True, root="data"))
        out.append_display_data(IJSON(resp.x_headers, expanded=True, root="headers"))
        return out

    def _clear(self) -> Output:
        return Output(layout=self.layout)


class DetailsMixin:
    ev_icon = (
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20010904//EN" "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd">'
        '<svg version="1.0" xmlns="http://www.w3.org/2000/svg" width="12px" height="12px; margin-right:4px; margin-top:2px;" '
        'viewBox="0 0 5030 3990" preserveAspectRatio="xMidYMid meet"><g id="layer1" fill="#000000" '
        'stroke="none"><path d="M164 3686 c-3 -8 16 -57 43 -109 42 -84 100 -159 456 -591 224 -272 407 '
        "-497 "
        "407 -500 0 -3 -74 -6 -164 -6 -103 0 -167 -4 -171 -10 -4 -6 40 -74 97 -150 l103 -140 483 -405 483 "
        "-405 -56 -25 c-31 -13 -167 -48 -302 -77 -135 -29 -252 -58 -261 -64 -14 -10 -15 -14 -2 -30 32 -40 "
        "853 -1030 865 -1042 9 -11 233 -5 1230 32 803 30 1222 50 1229 57 8 7 3 17 -15 32 -15 12 -58 47 -95 "
        "78 -39 32 -393 248 -817 499 -411 244 -744 447 -740 450 5 4 87 26 183 50 183 44 216 59 190 84 -8 7 "
        "-289 221 -625 476 -335 254 -616 468 -624 475 -11 11 2 16 68 30 86 19 115 33 103 51 -4 6 -128 93 "
        '-276 194 -409 278 -1719 1060 -1776 1060 -6 0 -13 -6 -16 -14z"/></g></svg>'
    )
    ev_categories = {"700-7600-0322", "700-7600-0323", "700-7600-0324"}
    ta_logo = """<div style='display: flex; align-items: center; margin: 0px;'>
                 <!-- See https://developer-tripadvisor.com/content-api/business-content/images -->
                 <img src='https://static.tacdn.com/img2/brand_refresh_2025/logos/logo.svg' style='height: 14px; margin-right: 4px;' />
                 <img src='https://static.tacdn.com/img2/ratings/traveler/ss{rating}.svg' style='height: 14px;' />
                 <span style='font-size: 10px; color: #333;'>/ Reviews: {reviews}</span></div>"""

    def html(self, data: PlaceDataItemDict | LocationDataItemDict, image_variant: str | None = None) -> str:
        html_parts = []

        address_label = data.get("address", {}).get("label", "")

        item_type = data["resultType"]
        if item_type != "place":
            html_parts.append(f"<div style='margin: 0; padding: 0; line-height: 1.2;'>{address_label}</div>")
        else:
            no_place_name_address_label = ", ".join(address_label.split(", ")[1:])
            html_parts.append(
                f"<div style='margin: 0; padding: 0; line-height: 1.2;'>{no_place_name_address_label}</div>"
            )
            primary_category = next((c for c in data.get("categories", []) if c.get("primary")), None)
            category_id = primary_category.get("id") if primary_category else None
            category_name = primary_category.get("name", "") if primary_category else ""

            html_parts.append(f"<div style='margin: 0; padding: 0; line-height: 1.2;'>{category_name}</div>")

            opening_hours_list = data.get("openingHours", [])
            if category_id and opening_hours_list:
                is_open = None
                text_lines = []
                for oh in opening_hours_list:
                    if any(cat.get("id") == category_id for cat in oh.get("categories", [])):
                        is_open = oh.get("isOpen")
                        text_lines = oh.get("text", [])
                        break
                else:
                    # No opening hours for the primary category, take the first one without category restriction
                    for oh in opening_hours_list:
                        if "categories" not in oh or not oh["categories"]:
                            is_open = oh.get("isOpen")
                            text_lines = oh.get("text", [])
                            break

                if is_open is not None:
                    status = "&#x1F7E2; Open" if is_open else "&#x1F534; Closed"
                    details_html = (
                        "<details style='margin: 4px 0; display: block;'>"
                        "<summary style='"
                        "display: list-item; "
                        "margin: 0;  padding: 0; line-height: 1.2;"
                        "font-weight: normal; "
                        "font-size: 10px; "
                        "line-height: 1.2; "
                        "color: inherit; "
                        "font-family: inherit;"
                        "'>"
                        f"{status}</summary>"
                        + "".join(
                            f"<div style='margin: 0; padding: 0; line-height: 1.2;'>{line}</div>" for line in text_lines
                        )
                        + "</details>"
                    )

                    html_parts.append(details_html)

            if primary_category["id"] in self.ev_categories and "extended" in data:
                for group in data["extended"].get("evStation", {}).get("connectors", []):
                    connector_name = group["connectorType"]["name"]
                    if connector_name[-1] == ")":
                        connector_name = connector_name[: connector_name.rindex("(")].strip()
                    power_kw = int(group.get("maxPowerLevel"))
                    number_of_available = group.get("chargingPoint", {}).get("numberOfAvailable")
                    number_of_connectors = group.get("chargingPoint", {}).get("numberOfConnectors")
                    line = (
                        f"<div style='margin: 0; padding: 0; line-height: 1.2;'>{self.ev_icon}"
                        f"{connector_name} / {power_kw}kW"
                    )

                    if number_of_available is not None:
                        line = f"{line} [{number_of_available}/{number_of_connectors}]</div>"
                        html_parts.append(line)
                    else:
                        line = f"{line} [{number_of_connectors}]</div>"
                        html_parts.append(line)

            contacts = data.get("contacts", [])
            for contact_type in ("phone", "www", "email"):
                contact = self.__get_labeled_contact_item(contacts, contact_type, category_id)
                if contact:
                    if contact_type == "www":
                        html_parts.append(
                            f"<div style='margin: 0; padding: 0; line-height: 1.2;'><a href='{contact}' target='_blank'>{urlparse(contact).netloc or contact}</a></div>"
                        )
                    elif contact_type == "email":
                        html_parts.append(
                            f"<div style='margin: 0; padding: 0; line-height: 1.2;'><a href='mailto:{contact}'>{contact}</a></div>"
                        )
                    else:
                        html_parts.append(f"<div style='margin: 0; padding: 0; line-height: 1.2;'>{contact}</div>")

            media = data.get("media", {})
            images = media.get("images", {}).get("items", [{}])
            ratings = media.get("ratings", {}).get("items", [{}])
            editorials = {
                re.search(r"-d(\d+)-", ed["href"]).group(1): ed["description"]
                for ed in media.get("editorials", {}).get("items", [])
            }
            if media:
                ta_references = [
                    ref["id"] for ref in data.get("references", []) if ref["supplier"]["id"] == "tripadvisor"
                ]
                primary_reference = min(ta_references)

                image_url = images[0].get("variants", {}).get(image_variant or "medium", {}).get("href")

                try:
                    rating = float(ratings[0].get("average", 0.0))
                    reviews = ratings[0].get("count", 0)
                except (TypeError, ValueError):
                    rating = 0.0
                    reviews = 0

                try:
                    deep_link = ratings[0].get("href")
                except (TypeError, ValueError):
                    deep_link = None

                if deep_link and image_url:
                    html_parts.append(
                        f"""<a href="{deep_link}" target="_blank">
                                  <img src='{image_url}' style='width:100%; max-width:270px; border-radius:4px; margin-top:10px;' />
                                </a>
                            """
                    )
                    html_parts.append(
                        '<a href="{deep_link}" target="_blank">{ta_logo}</a>'.format(
                            deep_link=deep_link,
                            ta_logo=self.ta_logo.format(rating=round(rating * 2) / 2, reviews=reviews),
                        )
                    )

                if editorials and primary_reference in editorials:
                    html_parts.append(
                        f"""<div style='margin: 0; padding: 0; line-height: 1;'>{editorials[primary_reference]}</div>"""
                    )

        html = "<div style='font-family: sans-serif; font-size: 14px;'>" + "\n".join(html_parts) + "</div>"
        return html

    @staticmethod
    def __get_labeled_contact_item(contacts, key, primary_category_id) -> str | None:
        for contact in contacts:
            for item in contact.get(key, []):
                if any(cat["id"] == primary_category_id for cat in item.get("categories", [])):
                    return item["value"]
        for contact in contacts:
            for item in contact.get(key, []):
                if "categories" not in item:
                    return item["value"]

        return None


class ResultDetailsBox(VBox, DetailsMixin):
    default_layout = {
        "display": "flex",
        "justify_content": "flex-start",
        "align_items": "flex-start",
        "width": "95%",
    }

    def __init__(self, data: PlaceDataItemDict | LocationDataItemDict, **kvargs):
        children = [HTML(value=self.html(data, image_variant="medium"))]

        VBox.__init__(
            self,
            children,
            layout=Layout(**kvargs.pop("layout", self.default_layout), overflow="visible"),
            **kvargs,
        )

    @staticmethod
    def get_labeled_contact_item(contacts, key, primary_category_id) -> str | None:
        for contact in contacts:
            for item in contact.get(key, []):
                if any(cat["id"] == primary_category_id for cat in item.get("categories", [])):
                    return item["value"]
        for contact in contacts:
            for item in contact.get(key, []):
                if "categories" not in item:
                    return item["value"]

        return None


class DebouncedButton(Button):
    # Used against https://github.com/jupyter-widgets/ipywidgets/issues/3996
    _debounce_interval: float
    _last_click_time: float
    _click_lock: asyncio.Lock
    _actual_handler: callable

    default_debounce_ms = 250
    default_layout = {
        "width": "95%",
        "justify_content": "flex-start",
        "display": "flex",
    }

    def __init__(self, *args, debounce_ms: int = None, **kwargs):
        super().__init__(*args, layout=Layout(**DebouncedButton.default_layout), **kwargs)
        self._debounce_interval = (debounce_ms or self.default_debounce_ms) / 1000
        self._last_click_time = 0.0
        self._click_lock = asyncio.Lock()
        self._actual_handler = None

    def set_handler(self, handler: callable):
        self._actual_handler = handler
        self._click_handlers.callbacks.clear()
        self.on_click(self._safe_click_handler)

    def _safe_click_handler(self, button: Button):
        asyncio.create_task(self._debounced_call(button))

    async def _debounced_call(self, button: Button):
        async with self._click_lock:
            now = time.monotonic()
            if now - self._last_click_time < self._debounce_interval:
                # debounced click
                return
            self._last_click_time = now

        if self._actual_handler:
            if asyncio.iscoroutinefunction(self._actual_handler):
                await self._actual_handler(button)
            else:
                self._actual_handler(button)


class SearchResultButton(DebouncedButton):
    rank = Any(allow_none=True)

    def __init__(self, queue: asyncio.Queue, **kwargs):
        kwargs = kwargs.pop("layout", {})
        DebouncedButton.__init__(self, **kwargs)

    def set_metadata(self, rank: int, icon: str, title: str):
        self.rank = rank
        self.icon = icon
        self.description = title


class SearchResultButtonBox(HBox):
    queue: asyncio.Queue
    default_layout = {"width": "100%", "min_width": "0"}

    def __init__(self, queue: asyncio.Queue, state: SearchState, **kvargs):
        self.queue = queue
        self.state = state
        self.label = Label(value="", layout={"width": "20px"})
        self.button = SearchResultButton(queue)
        self.button_box = VBox(children=[self.button], layout=Layout(**self.default_layout))
        HBox.__init__(
            self,
            [self.label, self.button_box],
            layout=Layout(**kvargs.pop("layout", self.default_layout), overflow="visible"),
            **kvargs,
        )
        self.add_class("result-button")

    def _button_handler(self) -> Callable[["SearchResultButton"], None]:
        def handle(button: SearchResultButton):
            if button.rank is None:
                return
            item = self.state.get_item(button.rank)
            if item is None:
                return
            if isinstance(item, LocationResponseItem):
                if button.rank in self.state.expanded_ranks:
                    self.state.expanded_ranks.remove(button.rank)
                    self.button_box.children = [self.button]
                else:
                    self.state.expanded_ranks.add(button.rank)
                    details = ResultDetailsBox(item.data)
                    self.button_box.children = [self.button, details]
            else:
                intent = SearchIntent(kind="details", materialization=item, time=time.perf_counter_ns())
                self.queue.put_nowait(intent)

        return handle

    def render(self, rank: int):
        item = self.state.get_item(rank)
        if not item:
            return
        self.label.value = f"{rank + 1: <2}"
        icon = self.state.icon_for(rank)
        title = self.state.title_for(rank)
        self.button.set_metadata(rank=rank, icon=icon, title=title)
        self.button.set_handler(self._button_handler())
        if rank in self.state.expanded_ranks:
            details = ResultDetailsBox(item.data)
            self.button_box.children = [self.button, details]
        else:
            self.button_box.children = [self.button]


class SearchResultButtons(VBox):
    default_layout = dict(max_height="400px", width="290px")
    default_overflow_y = "auto"
    default_overflow_x = "hidden"
    default_max_results_count = 20
    _style_applied = False

    def __init__(
        self,
        widget: Widget = None,
        max_results_number: int = None,
        queue: asyncio.Queue = None,
        state: SearchState | None = None,
        layout: dict = None,
        **kwargs,
    ):
        self.queue = queue or asyncio.Queue()
        self.layout = Layout(**(layout or self.default_layout))
        self.layout.overflow_y = self.default_overflow_y
        self.layout.overflow_x = self.default_overflow_x
        super().__init__([widget or Output()], layout=self.layout, **kwargs)

        self.state = state or SearchState()
        self._max = max_results_number or self.default_max_results_count
        self.buttons = [SearchResultButtonBox(self.queue, self.state) for _ in range(self._max)]

    def display(self, resp: Response, intent: SearchIntent = None) -> None:
        old_out: Output | VBox = self.children[0]
        if isinstance(old_out, VBox):
            old_out.close()
        else:
            old_out.close()

        self.state.hydrate(resp)
        visible_ranks = self.state.ranks()
        for rank in visible_ranks:
            if rank < len(self.buttons):
                self.buttons[rank].render(rank)

        try:
            out = VBox(children=[self.buttons[rank] for rank in visible_ranks], layout=self.layout)
        except IndexError:
            import traceback

            traceback.print_exc()
            print(f"rank={rank} len(visible_ranks)={len(visible_ranks)} len(self.buttons)={len(self.buttons)}")
            raise
        self.children = [out]

    def apply_style(self) -> None:
        # (SearchResultButton.__init__ already calls add_class("result-button")).
        if not SearchResultButtons._style_applied:
            # Note the leading dot in .result-button so we target the class, not a tag name.
            Idisplay(
                HTML("<style>.result-button div, .result-button button { font-size: 10px; }</style>"), display_id=True
            )
            SearchResultButtons._style_applied = True

    def modify(self, resp: Response, intent: SearchIntent = None) -> None:
        target_rank = intent.materialization.rank
        self.state.update_item(target_rank, resp.data, resp)
        if target_rank < len(self.buttons):
            self.buttons[target_rank].render(target_rank)


class ResponseMap(PositionMap, DetailsMixin):
    maximum_zoom_level = 18
    default_point_style = {
        "strokeColor": "white",
        "lineWidth": 1,
        "fillOpacity": 0.7,
        "radius": 7,
    }

    def __init__(
        self,
        queue: asyncio.Queue = None,
        state: SearchState | None = None,
        search_center_handler: Callable[[tuple[float, float]], None] = None,
        **kwargs,
    ):
        self.queue = queue
        self.state = state or SearchState()
        self.collection = None
        self.map_state = MapState()
        super().__init__(position_handler=search_center_handler, **kwargs)

    async def _fit_bounds(self, bounds):
        (b_south, b_west), (b_north, b_east) = bounds
        center = b_south + (b_north - b_south) / 2, b_west + (b_east - b_west) / 2
        if center != self.center:
            self.center = center
            await wait_for_change(self, "bounds")

        # Zoom out until the map contains the bounds
        while self.zoom > 1:
            (south, west), (north, east) = self.bounds
            if south > b_south or north < b_north or west > b_west or east < b_east:
                self.zoom -= 1
                await wait_for_change(self, "bounds")
            else:
                break

        # Zoom in as much as possible while still containing the bounds
        while True:
            (south, west), (north, east) = self.bounds
            if (
                south < b_south
                and north > b_north
                and west < b_west
                and east > b_east
                and self.zoom < ResponseMap.maximum_zoom_level
            ):
                self.zoom += 1
                await wait_for_change(self, "bounds")
            else:
                self.zoom -= 1
                await wait_for_change(self, "bounds")
                break

    @staticmethod
    def item_color(feature) -> str:
        item = feature["properties"]
        primary_category = next((c for c in item.get("categories", []) if c.get("primary")), None)
        category_id = primary_category.get("id") if primary_category else None
        is_open = None
        if "openingHours" in item:
            for oh in item["openingHours"]:
                if any(cat.get("id") == category_id for cat in oh.get("categories", [])):
                    is_open = oh.get("isOpen")
                    break
            else:
                for oh in item["openingHours"]:
                    if "categories" not in oh or not oh["categories"]:
                        is_open = oh.get("isOpen")
                        break

        if is_open is True and category_id in DetailsMixin.ev_categories and "extended" in item:
            availability = [
                available
                for group in item.get("extended", {}).get("evStation", {}).get("connectors", [])
                if (available := group.get("chargingPoint", {}).get("numberOfAvailable")) is not None
            ]
            is_open = any(availability) if availability else None

        color = {None: "blue", True: "green", False: "red"}.get(is_open, "blue")
        return color

    @staticmethod
    def style_callback(feature) -> dict:
        return {
            "fillColor": ResponseMap.item_color(feature),
        }

    def display(self, resp: Response, intent: SearchIntent = None, fit: bool = False):
        if self.collection:
            self.remove(self.collection)
            self.collection = None
        self.close_popups()
        bbox = resp.bbox()
        if bbox:
            self.collection = GeoJSON(
                data=resp.geojson(),
                show_bubble=True,
                point_style=ResponseMap.default_point_style,
                style_callback=ResponseMap.style_callback,
            )
            self.add(self.collection)
            if fit and bbox[0] != bbox[1] and bbox[2] != bbox[3]:
                south, north, east, west = bbox
                height = north - south
                width = east - west
                bounds = ((south - height / 8, west - width / 8), (north + height / 8, east + width / 8))
                if None in (south, north, east, west):
                    return
                asyncio.ensure_future(self._fit_bounds(bounds))

            def show_feature_popup(event, feature, **kwargs):
                if self.long_press_popup is not None:
                    return
                self.close_short_press_popup()
                item = feature["properties"]

                html = HTML(
                    value=f"<div>{item['_rank'] + 1}: {item['title']}</div>" + self.html(item, image_variant="original")
                )

                close_btn = Button(
                    icon="close",
                    layout=Layout(width="32px", align_self="flex-end"),
                )

                def on_click_handler(btn: Button):
                    self.close_short_press_popup()

                close_btn.on_click(on_click_handler)
                content = VBox([close_btn, html])
                self.short_press_popup = Popup(
                    location=feature["geometry"]["coordinates"][::-1],
                    child=content,
                    close_button=False,  # We have our own close button
                    auto_close=False,
                    close_on_escape_key=True,
                    auto_pan=True,
                    keep_in_view=False,
                    min_width=260,
                )

                self.add(self.short_press_popup)

            # def hide_feature_popup(event, feature, **kwargs):
            #    self.item_popup.close_popup()

            def get_more_details(event, feature, **kwargs):
                rank = feature["properties"].get("_rank")
                item = self.state.get_item(rank)
                if not item:
                    return
                intent = SearchIntent(kind="details", materialization=item, time=time.perf_counter_ns())
                self.queue.put_nowait(intent)

            self.collection.on_click(show_feature_popup)
            # self.collection.on_mouseout(hide_feature_popup)
