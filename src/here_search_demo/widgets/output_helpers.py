###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Pure functions for rendering a single HERE response item or GeoJSON feature.

All functions in this module are stateless and dependency-free with respect to
widget infrastructure — they operate only on plain dicts and primitive values.
"""

import math

from here_search_demo.entity.place import ev_category_ids, gas_category_ids

_ev_categories: frozenset[str] = frozenset(ev_category_ids)
_fuel_categories: frozenset[str] = frozenset(gas_category_ids)


def fuel_price_text(price_element) -> str | None:
    """Convert a HERE price element to a human-readable string.

    :param price_element: ``{"amount": ..., "currency": ...}`` dict, a raw value, or *None*
    :return: formatted price string or *None*
    """
    if isinstance(price_element, dict):
        amount = price_element.get("amount")
        currency = price_element.get("currency")
        if amount is not None and currency:
            return f"{amount} {currency}"
        if amount is not None:
            return f"{amount}"
        return None
    if price_element is not None:
        return str(price_element)
    return None


def diesel_price_text(item: dict) -> str | None:
    """Return a formatted diesel price string for *item*, or *None* if absent.

    :param item: HERE response item dict
    :return: formatted diesel price string or *None*
    """
    fuel_types = item.get("extended", {}).get("fuelStation", {}).get("fuelTypes", [])
    for fuel_type in fuel_types:
        fuel_type_name = str(fuel_type.get("type") or fuel_type.get("name") or fuel_type.get("id") or "")
        if fuel_type_name.lower() != "diesel":
            continue
        return fuel_price_text(fuel_type.get("price"))
    return None


def gas_station_label_parts(item: dict) -> tuple[str, str | None] | None:
    """Return ``(title, diesel_price_text | None)`` for a fuel-station item.

    :param item: HERE response item dict
    :return: ``(title, diesel_text)`` tuple or *None* when *item* is not a fuel station
    """
    primary_category = next((c for c in item.get("categories", []) if c.get("primary")), None)
    category_id = primary_category.get("id") if primary_category else None
    if category_id not in _fuel_categories:
        return None
    title = item.get("title")
    if not title:
        return None
    diesel_price = diesel_price_text(item)
    return title, f"diesel: {diesel_price}" if diesel_price else None


def ta_label_html(item: dict) -> str | None:
    """Return a TripAdvisor rating ``<img>`` HTML snippet for the map label.

    :param item: HERE response item dict
    :return: HTML string or *None* when no TA rating data is present
    """
    media = item.get("media")
    if not media:
        return None
    ratings_items = media.get("ratings", {}).get("items", [])
    if not ratings_items or not ratings_items[0]:
        return None
    ta_refs = [ref for ref in item.get("references", []) if ref.get("supplier", {}).get("id") == "tripadvisor"]
    if not ta_refs:
        return None
    try:
        rating = float(ratings_items[0].get("average", 0.0))
    except (TypeError, ValueError):
        return None
    rating_rounded = round(rating * 2) / 2
    return f"<img src='https://static.tacdn.com/img2/ratings/traveler/ss{rating_rounded}.svg' style='height: 10px;' />"


def item_color(feature: dict) -> str:
    """Return a fill-colour string (``"blue"``, ``"green"``, or ``"red"``) for *feature*.

    Colour encodes opening status; EV-station availability refines the ``"green"``
    case when charger availability data is present.

    :param feature: GeoJSON Feature whose ``"properties"`` hold a HERE item dict
    :return: colour name
    """
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

    if is_open is True and category_id in _ev_categories and "extended" in item:
        availability = [
            available
            for group in item.get("extended", {}).get("evStation", {}).get("connectors", [])
            if (available := group.get("chargingPoint", {}).get("numberOfAvailable")) is not None
        ]
        is_open = any(availability) if availability else None

    return {None: "blue", True: "green", False: "red"}.get(is_open, "blue")


def style_callback(feature: dict) -> dict:
    """Return an ipyleaflet style dict for *feature*.

    :param feature: GeoJSON Feature
    :return: ``{"fillColor": <colour>}``
    """
    return {"fillColor": item_color(feature)}


def label_pixel_bbox(
    lat: float,
    lng: float,
    zoom: int,
    icon_width: int,
    icon_height: int,
    icon_anchor_x: int,
    icon_anchor_y: int,
) -> tuple[float, float, float, float]:
    """Return the pixel bounding box ``(x_min, y_min, x_max, y_max)`` of a DivIcon label.

    :param lat: label latitude
    :param lng: label longitude
    :param zoom: current map zoom level
    :param icon_width: icon width in pixels
    :param icon_height: icon height in pixels
    :param icon_anchor_x: horizontal anchor offset
    :param icon_anchor_y: vertical anchor offset
    :return: ``(x_min, y_min, x_max, y_max)`` in web-Mercator pixel space
    """
    scale = 256 * (2**zoom)
    px = (lng + 180) / 360 * scale
    sin_lat = math.sin(math.radians(lat))
    sin_lat = max(-0.9999, min(0.9999, sin_lat))
    py = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale
    x_min = px - icon_anchor_x
    y_min = py - icon_anchor_y
    return x_min, y_min, x_min + icon_width, y_min + icon_height


def pixel_bboxes_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    """Return ``True`` when two axis-aligned pixel bounding boxes intersect.

    :param a: ``(x_min, y_min, x_max, y_max)``
    :param b: ``(x_min, y_min, x_max, y_max)``
    :return: ``True`` when the boxes overlap
    """
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]
