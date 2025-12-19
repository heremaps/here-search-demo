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

from here_search.demo.entity.endpoint import Endpoint


@dataclass
class APIOption:
    key: str
    values: Sequence[str]
    endpoints = []
    for_more_details = False


class At(APIOption):
    endpoints = Endpoint.DISCOVER, Endpoint.AUTOSUGGEST, Endpoint.BROWSE, Endpoint.REVGEOCODE

    def __init__(self, latitude: float, longitude: float):
        self.key = "at"
        self.values = [f"{latitude},{longitude}"]


class Route(APIOption):
    endpoints = Endpoint.DISCOVER, Endpoint.AUTOSUGGEST, Endpoint.BROWSE

    def __init__(self, polyline: str, width: int):
        self.key = "route"
        self.values = [f"{polyline};w={width}"]


class TripadvisorDetails(APIOption):
    endpoints = (Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)
    for_more_details = True

    def __init__(self):
        self.key = "show"
        self.values = ["tripadvisor", "tripadvisorImageVariants"]


class RecommendPlaces(APIOption):
    endpoints = (Endpoint.AUTOSUGGEST, Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER)
    for_more_details = True

    def __init__(self):
        self.key = "with"
        self.values = ["recommendPlaces"]


class Triggers400(APIOption):
    endpoints = (Endpoint.AUTOSUGGEST, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)

    def __init__(self):
        self.key = "show"
        self.values = ["foobar"]


class Details(APIOption):
    endpoints = (Endpoint.AUTOSUGGEST,)

    def __init__(self):
        self.key = "show"
        self.values = ["details"]


class EVDetails(APIOption):
    endpoints = (Endpoint.AUTOSUGGEST_HREF, Endpoint.DISCOVER, Endpoint.LOOKUP, Endpoint.BROWSE)
    for_more_details = True

    def __init__(self):
        self.key = "show"
        self.values = ["ev"]


@dataclass
class APIOptions:
    endpoint: dict[str, dict[str, str]]
    lookup_has_more_details: bool

    def __init__(self, options: dict):
        self.endpoint = {}
        self.lookup_has_more_details = False
        _options = {}
        for endpoint, ep_options in options.items():
            for option in ep_options:
                assert not option.endpoints or endpoint in option.endpoints, (
                    f"Option {option.__class__.__name__} illegal for endpoint {endpoint}"
                )
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
triggers400 = Triggers400()  # Can be used for tests
