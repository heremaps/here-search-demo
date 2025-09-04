###############################################################################
#
# Copyright (c) 2022-2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from typing import TYPE_CHECKING

from here_search.demo.entity.endpoint import Endpoint

if TYPE_CHECKING:
    from here_search.demo.entity.response import Response

from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass
class Request:
    endpoint: Endpoint = None
    url: str = None
    params: dict[str, str] = None
    x_headers: dict = None
    previous_response: "Response" = None  # Currently unused

    @property
    def key(self) -> str:
        return self.url + "".join(f"{k}{v}" for k, v in self.params.items())

    @property
    def full(self):
        return f"{self.url}?{urlencode(self.params)}"


@dataclass
class RequestContext:
    latitude: float
    longitude: float
    language: str | None = None
    x_headers: dict | None = None
