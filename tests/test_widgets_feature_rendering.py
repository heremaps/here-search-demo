###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import pytest

from here_search_demo.widgets import output_helpers as fr


# ---------------------------------------------------------------------------
# fuel_price_text
# ---------------------------------------------------------------------------


def test_fuel_price_text_with_amount_and_currency():
    assert fr.fuel_price_text({"amount": 1.789, "currency": "EUR"}) == "1.789 EUR"


def test_fuel_price_text_with_amount_only():
    assert fr.fuel_price_text({"amount": 1.5}) == "1.5"


def test_fuel_price_text_with_raw_value():
    assert fr.fuel_price_text("1.23") == "1.23"


def test_fuel_price_text_none_returns_none():
    assert fr.fuel_price_text(None) is None


def test_fuel_price_text_empty_dict_returns_none():
    assert fr.fuel_price_text({}) is None


# ---------------------------------------------------------------------------
# diesel_price_text
# ---------------------------------------------------------------------------


def test_diesel_price_text_extracts_price():
    item = {
        "extended": {
            "fuelStation": {
                "fuelTypes": [
                    {"type": "diesel", "price": {"amount": 1.789, "currency": "EUR"}},
                    {"type": "e10", "price": {"amount": 1.699, "currency": "EUR"}},
                ]
            }
        }
    }

    assert fr.diesel_price_text(item) == "1.789 EUR"


def test_diesel_price_text_returns_none_when_no_diesel():
    item = {
        "extended": {
            "fuelStation": {
                "fuelTypes": [
                    {"type": "e10", "price": {"amount": 1.699, "currency": "EUR"}},
                ]
            }
        }
    }

    assert fr.diesel_price_text(item) is None


def test_diesel_price_text_returns_none_when_no_fuel_data():
    assert fr.diesel_price_text({}) is None


# ---------------------------------------------------------------------------
# gas_station_label_parts
# ---------------------------------------------------------------------------


def test_gas_station_label_parts_includes_station_name_and_diesel_price():
    item = {
        "title": "Fuel Hub",
        "categories": [{"primary": True, "id": "700-7600-0116", "name": "Gas Station"}],
        "extended": {
            "fuelStation": {
                "fuelTypes": [
                    {"type": "diesel", "price": {"amount": 1.789, "currency": "EUR"}},
                ]
            }
        },
    }

    assert fr.gas_station_label_parts(item) == ("Fuel Hub", "diesel: 1.789 EUR")


def test_gas_station_label_parts_no_diesel():
    item = {
        "title": "Fuel Hub",
        "categories": [{"primary": True, "id": "700-7600-0116", "name": "Gas Station"}],
        "extended": {
            "fuelStation": {
                "fuelTypes": [
                    {"type": "e10", "price": {"amount": 1.699, "currency": "EUR"}},
                ]
            }
        },
    }

    title, diesel_text = fr.gas_station_label_parts(item)
    assert title == "Fuel Hub"
    assert diesel_text is None


def test_gas_station_label_parts_no_fuel_types():
    item = {
        "title": "Fuel Hub",
        "categories": [{"primary": True, "id": "700-7600-0116", "name": "Gas Station"}],
    }

    title, diesel_text = fr.gas_station_label_parts(item)
    assert title == "Fuel Hub"
    assert diesel_text is None


def test_gas_station_label_parts_returns_none_for_non_fuel_category():
    item = {
        "title": "Bakery",
        "categories": [{"primary": True, "id": "100-1000", "name": "Food"}],
    }

    assert fr.gas_station_label_parts(item) is None


# ---------------------------------------------------------------------------
# ta_label_html
# ---------------------------------------------------------------------------


def _ta_item(rating: float, reviews: int) -> dict:
    return {
        "title": "Great Place",
        "resultType": "place",
        "position": {"lat": 48.8, "lng": 2.3},
        "media": {
            "ratings": {
                "items": [
                    {
                        "average": rating,
                        "count": reviews,
                        "href": "https://ta.example/review",
                    }
                ]
            }
        },
        "references": [{"id": "123", "supplier": {"id": "tripadvisor"}}],
    }


def test_ta_label_html_returns_html_with_rating():
    item = _ta_item(4.3, 150)
    html = fr.ta_label_html(item)
    assert html is not None
    # Rounded to nearest 0.5 → 4.5
    assert "ss4.5" in html
    assert "height: 10px" in html


def test_ta_label_html_rounds_rating_to_nearest_half():
    item = _ta_item(3.7, 50)
    html = fr.ta_label_html(item)
    assert html is not None
    assert "ss3.5" in html


def test_ta_label_html_returns_none_when_no_media():
    item = {"title": "No TA", "resultType": "place"}
    assert fr.ta_label_html(item) is None


def test_ta_label_html_returns_none_when_no_ratings():
    item = {
        "title": "No Ratings",
        "resultType": "place",
        "media": {},
        "references": [{"id": "1", "supplier": {"id": "tripadvisor"}}],
    }
    assert fr.ta_label_html(item) is None


def test_ta_label_html_returns_none_without_tripadvisor_reference():
    item = {
        "title": "Other Supplier",
        "resultType": "place",
        "media": {"ratings": {"items": [{"average": 4.0, "count": 10}]}},
        "references": [{"id": "1", "supplier": {"id": "other"}}],
    }
    assert fr.ta_label_html(item) is None


def test_ta_label_html_returns_none_when_references_absent():
    item = {
        "title": "No Refs",
        "resultType": "place",
        "media": {"ratings": {"items": [{"average": 4.0, "count": 10}]}},
    }
    assert fr.ta_label_html(item) is None


# ---------------------------------------------------------------------------
# item_color
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("is_open", "expected"),
    [
        (True, "green"),
        (False, "red"),
        (None, "blue"),
    ],
)
def test_item_color_from_opening_hours(is_open, expected):
    feature = {
        "properties": {
            "categories": [{"primary": True, "id": "123"}],
            "resultType": "place",
            "openingHours": [
                {
                    "categories": [{"id": "123"}],
                    "isOpen": is_open,
                }
            ],
        }
    }

    assert fr.item_color(feature) == expected


def test_item_color_uses_ev_availability():
    feature = {
        "properties": {
            "categories": [{"primary": True, "id": "700-7600-0322"}],
            "resultType": "place",
            "openingHours": [
                {
                    "categories": [{"id": "700-7600-0322"}],
                    "isOpen": True,
                }
            ],
            "extended": {
                "evStation": {
                    "connectors": [
                        {
                            "chargingPoint": {"numberOfAvailable": 0},
                        },
                        {
                            "chargingPoint": {"numberOfAvailable": 2},
                        },
                    ]
                }
            },
        }
    }

    assert fr.item_color(feature) == "green"


# ---------------------------------------------------------------------------
# style_callback
# ---------------------------------------------------------------------------


def test_style_callback_delegates_to_item_color(monkeypatch):
    called = {}

    def fake_item_color(feature):
        called["feature"] = feature
        return "purple"

    monkeypatch.setattr(fr, "item_color", fake_item_color)

    feature = {"properties": {"resultType": "place"}}
    style = fr.style_callback(feature)

    assert called["feature"] is feature
    assert style == {"fillColor": "purple"}


# ---------------------------------------------------------------------------
# label_pixel_bbox
# ---------------------------------------------------------------------------


def test_label_pixel_bbox_accounts_for_anchor():
    bbox = fr.label_pixel_bbox(0.0, 0.0, 0, 250, 60, 125, 60)

    assert bbox == (3.0, 68.0, 253.0, 128.0)


# ---------------------------------------------------------------------------
# pixel_bboxes_overlap
# ---------------------------------------------------------------------------


def test_pixel_bboxes_overlap_detects_intersection():
    assert fr.pixel_bboxes_overlap((0, 0, 10, 10), (5, 5, 15, 15)) is True


def test_pixel_bboxes_overlap_detects_no_intersection():
    assert fr.pixel_bboxes_overlap((0, 0, 10, 10), (20, 20, 30, 30)) is False


def test_pixel_bboxes_overlap_adjacent_boxes_do_not_overlap():
    assert fr.pixel_bboxes_overlap((0, 0, 10, 10), (10, 0, 20, 10)) is False
