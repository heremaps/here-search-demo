###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################


from here_search_demo.api_options import (
    default_options_config,
    details,
    fuelDetails,
    fuelPriceDetails,
    recommendPlaces,
    tripadvisorDetails,
    build_api_options,
    Route,
)
from here_search_demo.entity.endpoint import Endpoint


# ---------------------------------------------------------------------------
# _build_api_options – base behaviour
# ---------------------------------------------------------------------------


def test_default_no_extras():
    opts = build_api_options(default_options_config)
    # AUTOSUGGEST: details → show=details
    assert opts.endpoint[Endpoint.AUTOSUGGEST]["show"] == "details"
    # DISCOVER: evDetails → show=ev
    assert opts.endpoint[Endpoint.DISCOVER]["show"] == "ev"
    # evDetails has for_more_details=True, so lookup_has_more_details is True even with defaults
    assert opts.lookup_has_more_details is True


# ---------------------------------------------------------------------------
# tripadvisor flag
# ---------------------------------------------------------------------------


def test_tripadvisor_adds_tripadvisor_details():
    opts = build_api_options(default_options_config, extra_options=[tripadvisorDetails])
    # tripadvisorDetails applies to AUTOSUGGEST_HREF, DISCOVER, BROWSE, LOOKUP
    for endpoint in (Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER, Endpoint.BROWSE, Endpoint.LOOKUP):
        show = opts.endpoint[endpoint]["show"]
        assert "tripadvisor" in show, f"expected tripadvisor in {endpoint}.show, got {show}"
        assert "tripadvisorImageVariants" in show
    # AUTOSUGGEST is NOT in tripadvisorDetails.endpoints → unchanged
    assert "tripadvisor" not in opts.endpoint[Endpoint.AUTOSUGGEST].get("show", "")
    assert opts.lookup_has_more_details is True


# ---------------------------------------------------------------------------
# fuel flag
# ---------------------------------------------------------------------------


def test_fuel_adds_fuel_details_to_autosuggest():
    opts = build_api_options(default_options_config, extra_options=[fuelDetails, fuelPriceDetails])
    autosuggest_show = opts.endpoint[Endpoint.AUTOSUGGEST]["show"]
    assert "fuel" in autosuggest_show


def test_fuel_adds_fuel_price_details_to_other_endpoints():
    opts = build_api_options(default_options_config, extra_options=[fuelDetails, fuelPriceDetails])
    for endpoint in (Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER, Endpoint.BROWSE, Endpoint.LOOKUP):
        show = opts.endpoint[endpoint]["show"]
        assert "fuel" in show, f"expected fuel in {endpoint}.show, got {show}"
        assert "fuelPrices" in show, f"expected fuelPrices in {endpoint}.show, got {show}"


# ---------------------------------------------------------------------------
# recommendations flag
# ---------------------------------------------------------------------------


def test_recommendations_adds_recommend_places():
    opts = build_api_options(default_options_config, extra_options=[recommendPlaces])
    # recommendPlaces applies to AUTOSUGGEST, AUTOSUGGEST_HREF, DISCOVER
    for endpoint in (Endpoint.AUTOSUGGEST, Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER):
        assert opts.endpoint[endpoint].get("with") == "recommendPlaces", f"expected recommendPlaces in {endpoint}"
    # BROWSE and LOOKUP are not in recommendPlaces.endpoints
    assert "with" not in opts.endpoint.get(Endpoint.BROWSE, {})
    assert "with" not in opts.endpoint.get(Endpoint.LOOKUP, {})
    assert opts.lookup_has_more_details is True


# ---------------------------------------------------------------------------
# Combinations
# ---------------------------------------------------------------------------


def test_tripadvisor_and_fuel():
    opts = build_api_options(default_options_config, extra_options=[tripadvisorDetails, fuelDetails, fuelPriceDetails])
    for endpoint in (Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER, Endpoint.BROWSE, Endpoint.LOOKUP):
        show = opts.endpoint[endpoint]["show"]
        assert "tripadvisor" in show
        assert "fuel" in show
        assert "fuelPrices" in show


def test_tripadvisor_and_recommendations():
    opts = build_api_options(default_options_config, extra_options=[tripadvisorDetails, recommendPlaces])
    for endpoint in (Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER):
        assert "tripadvisor" in opts.endpoint[endpoint]["show"]
        assert opts.endpoint[endpoint].get("with") == "recommendPlaces"
    assert opts.lookup_has_more_details is True


def test_fuel_and_recommendations():
    opts = build_api_options(default_options_config, extra_options=[fuelDetails, fuelPriceDetails, recommendPlaces])
    assert "fuel" in opts.endpoint[Endpoint.AUTOSUGGEST]["show"]
    assert opts.endpoint[Endpoint.AUTOSUGGEST].get("with") == "recommendPlaces"
    assert "fuelPrices" in opts.endpoint[Endpoint.DISCOVER]["show"]
    assert opts.endpoint[Endpoint.DISCOVER].get("with") == "recommendPlaces"


def test_all_flags():
    opts = build_api_options(
        default_options_config,
        extra_options=[tripadvisorDetails, fuelDetails, fuelPriceDetails, recommendPlaces],
    )
    for endpoint in (Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER):
        show = opts.endpoint[endpoint]["show"]
        assert "tripadvisor" in show
        assert "fuel" in show
        assert "fuelPrices" in show
        assert opts.endpoint[endpoint].get("with") == "recommendPlaces"
    # AUTOSUGGEST: fuel but no tripadvisor/fuelPrices; has recommendPlaces
    autosuggest_show = opts.endpoint[Endpoint.AUTOSUGGEST]["show"]
    assert "fuel" in autosuggest_show
    assert "tripadvisor" not in autosuggest_show
    assert opts.endpoint[Endpoint.AUTOSUGGEST].get("with") == "recommendPlaces"


# ---------------------------------------------------------------------------
# No duplicate options when the same option appears in config and extras
# ---------------------------------------------------------------------------


def test_no_duplicate_extra_options():
    """Passing an option that is already in the base config must not duplicate it."""
    opts_single = build_api_options(default_options_config, extra_options=[details])
    opts_baseline = build_api_options(default_options_config)
    assert opts_single.endpoint[Endpoint.AUTOSUGGEST] == opts_baseline.endpoint[Endpoint.AUTOSUGGEST]


# ---------------------------------------------------------------------------
# Route incompatibility with recommendPlaces
# ---------------------------------------------------------------------------


def test_route_excludes_recommend_places():
    """When searching along a route, with=recommendPlaces must not be used."""
    route = Route(polyline="BlBoz5xJ67i1B", width=100)
    opts = build_api_options(default_options_config, extra_options=[route, recommendPlaces])
    for endpoint in (Endpoint.AUTOSUGGEST, Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER):
        assert "with" not in opts.endpoint.get(endpoint, {}), (
            f"with=recommendPlaces must not be set for {endpoint} when Route is used"
        )


def test_recommend_places_without_route_still_works():
    """Without a route, with=recommendPlaces is set as usual."""
    opts = build_api_options(default_options_config, extra_options=[recommendPlaces])
    for endpoint in (Endpoint.AUTOSUGGEST, Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER):
        assert opts.endpoint[endpoint].get("with") == "recommendPlaces"
