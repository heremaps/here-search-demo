###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from here_search.demo.entity.endpoint import Endpoint

from dataclasses import dataclass
from typing import Sequence


@dataclass
class APIOption:
    key: str
    values: Sequence[str]
    endpoints = []


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


class APIOptions(dict):
    def __init__(self, options: dict):
        _options = {}
        for endpoint, ep_options in options.items():
            for option in ep_options:
                assert not option.endpoints or endpoint in option.endpoints, f"Option {option.__class__.__name__} illegal for endpoint {endpoint}"
                _options.setdefault(endpoint, {}).setdefault(option.key, set()).update(option.values)
        for endpoint, ep_options in _options.items():
            for key in ep_options.keys():
                ep_options[key] = ",".join(sorted(ep_options[key]))

        super().__init__(_options)
