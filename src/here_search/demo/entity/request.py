###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from here_search.demo.entity.endpoint import Endpoint
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from here_search.demo.entity.response import Response

from typing import Dict
from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass
class Request:

    endpoint: Endpoint = None
    url: str = None
    params: Dict[str, str] = None
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
    language: Optional[str] = None
    x_headers: Optional[dict] = None
