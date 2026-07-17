###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Widgets for rendering HERE response item details.

This module provides two components:

* :class:`DetailsMixin` — a mixin that generates an HTML summary string for a
  single HERE response item (place or location).  It covers opening hours,
  EV-connector availability, fuel prices, TripAdvisor ratings and images, phone
  numbers, and website links.  The mixin is used both by
  :class:`~here_search_demo.widgets.output_map.ResponseMap` (marker popups) and
  by :class:`ResultDetailsBox` (standalone panel).

* :class:`ResultDetailsBox` — a ``VBox`` ipywidget that wraps
  :class:`DetailsMixin` output in a popup-styled container, suitable for
  embedding directly in a notebook or panel layout.

Pure price-formatting helpers live in
:mod:`here_search_demo.widgets.feature_rendering`; ``DetailsMixin`` delegates
``_fuel_price_text`` there.
"""

import re
from urllib.parse import urlparse

from ipywidgets import HTML, Layout, VBox

from here_search_demo.entity.place import ev_category_ids, gas_category_ids
from here_search_demo.entity.response_data import LocationDataItemDict, PlaceDataItemDict
from here_search_demo.widgets import output_helpers as fr


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
    fuel_icon = (
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20010904//EN" "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd">'
        '<svg version="1.0" xmlns="http://www.w3.org/2000/svg" width="12px" height="12px; margin-right:4px; margin-top:2px;" '
        'viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet"><g fill="#000000" stroke="none">'
        '<rect x="10" y="30" width="45" height="60" rx="4"/>'
        '<rect x="18" y="38" width="29" height="18" rx="2" fill="white"/>'
        '<rect x="55" y="20" width="8" height="40" rx="2"/>'
        '<rect x="63" y="20" width="18" height="8" rx="2"/>'
        '<rect x="75" y="28" width="8" height="25" rx="4"/>'
        '<rect x="55" y="56" width="28" height="8" rx="2"/>'
        "</g></svg>"
    )
    ev_categories = set(ev_category_ids)
    fuel_categories = set(gas_category_ids)
    ta_logo = """<div style='display: flex; align-items: center; margin: 0px;'>
                 <!-- See https://developer-tripadvisor.com/content-api/business-content/images -->
                 <img src='https://static.tacdn.com/img2/brand_refresh_2025/logos/logo.svg' style='height: 14px; margin-right: 4px;' />
                 <img src='https://static.tacdn.com/img2/ratings/traveler/ss{rating}.svg' style='height: 14px;' />
                 <span style='font-size: 10px; color: #333;'>/ Reviews: {reviews}</span></div>"""
    _html_cache: dict[tuple[int, str], str] = {}
    _html_cache_max_entries = 512

    # Delegating alias — canonical implementation lives in feature_rendering.
    _fuel_price_text = staticmethod(fr.fuel_price_text)

    def html(self, data: PlaceDataItemDict | LocationDataItemDict, image_variant: str | None = None) -> str:
        cache_key = (id(data), image_variant or "")
        cached_html = self._html_cache.get(cache_key)
        if cached_html is not None:
            return cached_html

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

            if category_id in self.ev_categories and "extended" in data:
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

            if category_id in self.fuel_categories and "extended" in data:
                for fuel_type_element in data["extended"].get("fuelStation", {}).get("fuelTypes", []):
                    fuel_type = fuel_type_element.get("type")
                    price_txt_raw = self._fuel_price_text(fuel_type_element.get("price"))
                    price_txt = f" - {price_txt_raw}" if price_txt_raw else ""

                    html_parts.append(
                        f"<div style='margin: 0; padding: 0; line-height: 1.2;'>{self.fuel_icon}{fuel_type}{price_txt}</div>"
                    )

            contacts = data.get("contacts", [])
            for contact_type in ("phone", "www"):
                contact = self.__get_labeled_contact_item(contacts, contact_type, category_id)
                if contact:
                    if contact_type == "www":
                        html_parts.append(
                            f"<div style='margin: 0; padding: 0; line-height: 1.2;'><a href='{contact}' target='_blank'>{urlparse(contact).netloc or contact}</a></div>"
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
                                  <img src='{image_url}' style='display:block; width:calc(100% + 8px); max-width:none; border-radius:1px; margin:2px -4px 0 -4px;' />
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
        self._html_cache[cache_key] = html
        if len(self._html_cache) > self._html_cache_max_entries:
            self._html_cache.pop(next(iter(self._html_cache)))
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
    popup_like_container_style = (
        "background: #fff;"
        "border: 1px solid #ccc;"
        "border-radius: 6px;"
        "box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);"
        "padding: 6px 8px 8px 8px;"
    )

    def __init__(self, data: PlaceDataItemDict | LocationDataItemDict, **kvargs):
        children = [
            HTML(
                value=(
                    f"<div style='{self.popup_like_container_style}'>{self.html(data, image_variant='medium')}</div>"
                )
            )
        ]

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
