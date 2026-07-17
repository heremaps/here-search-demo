###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Route-aware ranking modes for search results.

Encapsulates the two orthogonal ranking axes:

* **server-side** (``all_along``): instructs the Search API to rank by
  excursion distance via the ``ranking=excursionDistance`` parameter.
* **client-side** (``travel_time``): post-processes results using the
  Routing API to sort by actual travel time and annotate items with
  detour polylines.

The combination of both flags yields four modes:

+------------------+---------------------+-------------------------------+
| all_along        | travel_time         | Effect                        |
+==================+=====================+===============================+
| False            | False               | Default relevance ranking     |
+------------------+---------------------+-------------------------------+
| True             | False               | Server excursion ranking      |
+------------------+---------------------+-------------------------------+
| False            | True                | Client travel-time reranking  |
+------------------+---------------------+-------------------------------+
| True             | True                | Server + client reranking     |
+------------------+---------------------+-------------------------------+
"""

from dataclasses import dataclass


@dataclass
class RankingMode:
    """Immutable description of the current ranking configuration.

    Parameters
    ----------
    all_along:
        When ``True`` the Search API request includes
        ``ranking=excursionDistance`` so results are pre-sorted by
        proximity to the route on the server side.
    travel_time:
        When ``True`` the client applies :class:`~here_search_demo.detour.DetourRanker`
        to reorder results by actual driving time and annotate each item
        with detour polylines.
    """

    all_along: bool = False
    travel_time: bool = False

    @property
    def server_ranking(self) -> str | None:
        """Value for the ``ranking`` request parameter, or ``None``."""
        return "excursionDistance" if self.all_along else None

    @property
    def needs_client_rerank(self) -> bool:
        """Whether the response requires client-side travel-time reranking."""
        return self.travel_time

    @property
    def needs_route_polyline(self) -> bool:
        """Whether a route (corridor) must be sent with the search request."""
        return self.all_along or self.travel_time
