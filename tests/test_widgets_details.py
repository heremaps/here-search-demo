###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################


import pytest

from here_search_demo.widgets.output_details import DetailsMixin, ResultDetailsBox
from here_search_demo.widgets.util import load_css


class _DetailsTester(DetailsMixin):
    """Concrete helper to test DetailsMixin renders."""


@pytest.fixture
def details_tester():
    return _DetailsTester()


def test_details_mixin_html_includes_place_metadata(details_tester):
    data = {
        "resultType": "place",
        "title": "EV Hub",
        "address": {"label": "EV Hub, 123 Road, City"},
        "categories": [{"primary": True, "id": "700-7600-0322", "name": "EV Station"}],
        "openingHours": [
            {
                "categories": [{"id": "700-7600-0322"}],
                "isOpen": True,
                "text": ["Mon-Fri 08:00-20:00"],
            }
        ],
        "extended": {
            "evStation": {
                "connectors": [
                    {
                        "connectorType": {"name": "Type 2 (AC)"},
                        "maxPowerLevel": "22",
                        "chargingPoint": {"numberOfAvailable": 1, "numberOfConnectors": 3},
                    }
                ]
            }
        },
        "contacts": [
            {
                "phone": [{"value": "+123", "categories": [{"id": "700-7600-0322"}]}],
                "www": [{"value": "https://example.com"}],
                "email": [{"value": "info@example.com"}],
            }
        ],
        "media": {
            "images": {"items": [{"variants": {"medium": {"href": "https://img"}}}]},
            "ratings": {"items": [{"average": 4.5, "count": 12, "href": "https://trip"}]},
            "editorials": {"items": [{"href": "https://tripadvisor.com/foo-d123-bar", "description": "Great!"}]},
        },
        "references": [{"supplier": {"id": "tripadvisor"}, "id": "123"}],
    }

    html = details_tester.html(data, image_variant="medium")

    assert "Open" in html
    assert "Type 2" in html  # connector info
    assert "+123" in html
    assert "example.com" in html  # website anchor text
    assert "mailto:" not in html  # email is excluded
    assert "https://img" in html
    assert "Great!" in html
    assert "display:block; width:calc(100% + 8px);" in html


def test_details_mixin_html_handles_non_place(details_tester):
    data = {
        "resultType": "location",
        "address": {"label": "Public Park, Example City"},
    }

    html = details_tester.html(data)
    assert "Public Park" in html
    assert "<div" in html


def test_details_mixin_html_includes_fuel_types_with_price(details_tester):
    data = {
        "resultType": "place",
        "title": "Fuel Hub",
        "address": {"label": "Fuel Hub, 1 Main St, City"},
        "categories": [{"primary": True, "id": "700-7600-0116", "name": "Gas Station"}],
        "openingHours": [],
        "extended": {
            "fuelStation": {
                "fuelTypes": [
                    {"type": "diesel", "available": True, "price": {"amount": 1.789, "currency": "EUR", "unit": "l"}},
                ]
            }
        },
    }

    html = details_tester.html(data)

    assert "diesel" in html
    assert "1.789 EUR" in html


def test_details_mixin_html_includes_fuel_types_without_price(details_tester):
    data = {
        "resultType": "place",
        "title": "Fuel Hub",
        "address": {"label": "Fuel Hub, 1 Main St, City"},
        "categories": [{"primary": True, "id": "700-7600-0116", "name": "Gas Station"}],
        "openingHours": [],
        "extended": {
            "fuelStation": {
                "fuelTypes": [
                    {"type": "e10"},
                ]
            }
        },
    }

    html = details_tester.html(data)

    assert "e10" in html


def test_result_details_box_uses_popup_like_container():
    details = ResultDetailsBox(
        {
            "resultType": "place",
            "title": "Cafe",
            "address": {"label": "Cafe, 1 Main St, City"},
            "categories": [{"primary": True, "id": "123", "name": "Cafe"}],
            "openingHours": [],
        }
    )

    assert len(details.children) == 1
    html_widget = details.children[0]
    assert hasattr(html_widget, "value"), "child should be an HTML widget"
    assert "<div" in html_widget.value, "content should be wrapped in a div container"
    assert "Cafe" in html_widget.value, "container should include the place title"


def test_widget_css_resources_include_label_pointer_and_popup_rules():
    label_css = load_css("label.css")
    popup_css = load_css("popup.css")

    assert ".here-search-demo-label-line" in label_css
    assert ".leaflet-popup-tip" in popup_css
