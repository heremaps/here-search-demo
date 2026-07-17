###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from dataclasses import dataclass
from typing import Sequence

from here_search_demo.entity.endpoint import Endpoint


@dataclass
class APIOption:
    """Base representation of a query option contributed to one or more endpoints.

    :ivar str key: Query parameter name (for example ``"show"`` or ``"at"``).
    :ivar Sequence[str] values: One or more values attached to ``key``.
    :ivar list endpoints: Endpoints where this option is valid.
    :ivar bool for_more_details: Whether option implies lookup-based enrichment.
    :ivar list incompatible_with: Option classes that cannot coexist with this option.
    """

    key: str
    values: Sequence[str]
    endpoints = []
    for_more_details = False
    incompatible_with = []


class At(APIOption):
    """Location center option (`at=<lat>,<lon>`) for search endpoints."""

    endpoints = Endpoint.DISCOVER, Endpoint.AUTOSUGGEST, Endpoint.BROWSE, Endpoint.REVGEOCODE

    def __init__(self, latitude: float, longitude: float):
        """Build an ``at`` option.

        :param latitude: Latitude component.
        :param longitude: Longitude component.
        """
        self.key = "at"
        self.values = [f"{latitude},{longitude}"]


class Route(APIOption):
    """Route corridor option (`route=<polyline>;w=<width>`) for search endpoints."""

    endpoints = Endpoint.DISCOVER, Endpoint.AUTOSUGGEST, Endpoint.BROWSE

    def __init__(self, polyline: str, width: int):
        """Build a ``route`` option.

        :param polyline: Flexible polyline string.
        :param width: Corridor width in meters.
        """
        self.key = "route"
        self.values = [f"{polyline};w={width}"]


class TripadvisorDetails(APIOption):
    """Request TripAdvisor details in responses."""

    endpoints = (Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)
    for_more_details = True

    def __init__(self):
        self.key = "show"
        self.values = ["tripadvisor", "tripadvisorImageVariants"]


class RecommendPlaces(APIOption):
    """Request recommendation enrichment (`with=recommendPlaces`)."""

    endpoints = (Endpoint.AUTOSUGGEST, Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER)
    for_more_details = True
    incompatible_with = [Route]

    def __init__(self):
        self.key = "with"
        self.values = ["recommendPlaces"]


class Triggers400(APIOption):
    """Testing option intentionally producing an invalid ``show`` value."""

    endpoints = (Endpoint.AUTOSUGGEST, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)

    def __init__(self):
        self.key = "show"
        self.values = ["foobar"]


class Details(APIOption):
    """Request autosuggest details payload (`show=details`)."""

    endpoints = (Endpoint.AUTOSUGGEST,)

    def __init__(self):
        self.key = "show"
        self.values = ["details"]


class EVDetails(APIOption):
    """Request electric-vehicle details (`show=ev`)."""

    endpoints = (Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)
    for_more_details = True

    def __init__(self):
        self.key = "show"
        self.values = ["ev"]


class FuelDetails(APIOption):
    """Request fuel-station metadata (`show=fuel`)."""

    endpoints = (Endpoint.AUTOSUGGEST, Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)

    def __init__(self):
        self.key = "show"
        self.values = ["fuel"]


class TruckDetails(APIOption):
    """Request truck-related metadata (`show=truck`)."""

    endpoints = (Endpoint.AUTOSUGGEST, Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)

    def __init__(self):
        self.key = "show"
        self.values = ["truck"]


class FuelPriceDetails(APIOption):
    """Request fuel and fuel-price data (`show=fuel,fuelPrices`)."""

    endpoints = (Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)

    def __init__(self):
        self.key = "show"
        self.values = ["fuel", "fuelPrices"]


class TruckFuelPriceDetails(APIOption):
    """Request truck and fuel-price data (`show=truck,fuelPrices`)."""

    endpoints = (Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)

    def __init__(self):
        self.key = "show"
        self.values = ["truck", "fuelPrices"]


@dataclass
class APIOptions:
    """Normalized endpoint-to-query-options map used by :class:`here_search_demo.api.API`.

    ``endpoint`` stores merged query parameters per endpoint where repeated
    values are deduplicated and joined with commas.

    :ivar dict endpoint: Mapping ``Endpoint -> {query_key: csv_values}``.
    :ivar bool lookup_has_more_details: Whether any option requires lookup enrichment.
    """

    endpoint: dict[str, dict[str, str]]
    lookup_has_more_details: bool

    def __init__(self, options: dict):
        """Normalize options by endpoint and aggregate values per query key.

        :param options: Mapping of endpoint to option objects.
        :raises ValueError: If an option is attached to an invalid endpoint.
        """
        self.endpoint = {}
        self.lookup_has_more_details = False
        _options = {}
        for endpoint, ep_options in options.items():
            for option in ep_options:
                if option.endpoints and endpoint not in option.endpoints:
                    raise ValueError(f"Option {option.__class__.__name__} illegal for endpoint {endpoint}")
                _options.setdefault(endpoint, {}).setdefault(option.key, set()).update(option.values)
                if option.for_more_details:
                    self.lookup_has_more_details = True
        for endpoint, ep_options in _options.items():
            for key in ep_options.keys():
                ep_options[key] = ",".join(sorted(ep_options[key]))
        self.endpoint = _options


details = Details()
tripadvisorDetails = TripadvisorDetails()
recommendPlaces = RecommendPlaces()
evDetails = EVDetails()
fuelDetails = FuelDetails()
fuelPriceDetails = FuelPriceDetails()
truckDetails = TruckDetails()
truckFuelPriceDetails = TruckFuelPriceDetails()
triggers400 = Triggers400()  # Can be used for tests

default_options_config = {
    Endpoint.AUTOSUGGEST: (details,),
    Endpoint.AUTOSUGGEST_HREF: (evDetails,),
    Endpoint.DISCOVER: (evDetails,),
    Endpoint.BROWSE: (evDetails,),
    Endpoint.LOOKUP: (evDetails,),
}

premium_ta_options_config = {
    Endpoint.AUTOSUGGEST: (details,),
    Endpoint.AUTOSUGGEST_HREF: (tripadvisorDetails, evDetails),
    Endpoint.DISCOVER: (tripadvisorDetails, evDetails),
    Endpoint.BROWSE: (tripadvisorDetails, evDetails),
    Endpoint.LOOKUP: (tripadvisorDetails, evDetails),
}

premium_fuel_options_config = {
    Endpoint.AUTOSUGGEST: (details, fuelDetails),
    Endpoint.AUTOSUGGEST_HREF: (fuelPriceDetails, evDetails),
    Endpoint.DISCOVER: (fuelPriceDetails, evDetails),
    Endpoint.BROWSE: (fuelPriceDetails, evDetails),
    Endpoint.LOOKUP: (fuelPriceDetails, evDetails),
}


def build_api_options(config, extra_options=()) -> APIOptions:
    """Build :class:`APIOptions` from base config and optional extra options.

    Extra options are appended per endpoint only when applicable, then options
    declared as incompatible are removed.

    :param config: Base mapping ``Endpoint -> sequence[APIOption]``.
    :param extra_options: Additional options to merge into the base config.
    :return: Normalized options container.
    :rtype: APIOptions
    """
    all_options = list(extra_options)
    for base_options in config.values():
        all_options.extend(base_options)

    options = {}
    for endpoint, base_options in config.items():
        endpoint_options = list(base_options)
        for opt in extra_options:
            if endpoint in opt.endpoints and opt not in endpoint_options:
                endpoint_options.append(opt)
        # Remove options incompatible with any other option present
        endpoint_options = [
            opt
            for opt in endpoint_options
            if not any(isinstance(other, tuple(opt.incompatible_with)) for other in all_options if other is not opt)
        ]
        options[endpoint] = endpoint_options
    return APIOptions(options)
