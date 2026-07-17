###############################################################################
#
# Copyright (c) 2022-2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from typing import TYPE_CHECKING

from here_search_demo.entity.endpoint import Endpoint

if TYPE_CHECKING:
    from here_search_demo.entity.response import Response

from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass
class Request:
    """Normalized HERE Search request payload.

    :ivar endpoint: target HERE Search endpoint enum
    :ivar base_url: endpoint base URL
    :ivar params: query-string parameters
    :ivar data: optional request body (used for POST route payloads)
    :ivar x_headers: optional request-scoped ``X-*`` headers
    :ivar previous_response: optional previous response used for follow-up flows
    """

    endpoint: Endpoint | None = None
    base_url: str | None = None
    params: dict[str, str] | None = None
    data: str | None = None
    x_headers: dict | None = None
    previous_response: "Response" = None  # Currently unused

    @property
    def key(self) -> str:
        """Return a deterministic cache key for this request.

        :return: cache key string derived from base URL and params
        """
        return self.base_url + "".join(f"{k}{v}" for k, v in self.params.items()) + (self.data or "")

    @property
    def full(self):
        """Return full request URL including encoded query string.

        :return: full request URL
        """
        return f"{self.base_url}?{urlencode(self.params)}"


@dataclass
class RequestContext:
    """Context used to transform intents into concrete endpoint requests.

    :ivar latitude: search latitude
    :ivar longitude: search longitude
    :ivar language: preferred language
    :ivar polyline: optional route polyline
    :ivar all_along: whether to apply all-along routing mode
    :ivar x_headers: optional request-scoped ``X-*`` headers
    :ivar share_experience: whether user opted into experience sharing
    :ivar user_id: optional user id for signaling endpoints
    """

    latitude: float
    longitude: float
    language: str | None = None
    polyline: str | None = None
    width: int | None = None
    all_along: bool | None = None
    x_headers: dict | None = None
    share_experience: bool = False
    user_id: str | None = None
