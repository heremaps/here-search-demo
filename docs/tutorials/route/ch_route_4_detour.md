---
hide-toc: true
---

# Detour Re-ranking

## Quick reference

This notebook implements detour reranking from scratch on top of `RoutingAPI` only, so
that the logic can be copied into an application that keeps its own ranking layer. It
covers
- the via-route call
- the parallel fetch
- the excursion computation
- the `dur_to` sort key
- the maximum-excursion filter
- the result annotation

Most-used elements:

1. `RoutingAPI.routes(session, origin, destination, via=Waypoint(lat, lon, street))`
2. `RoutingAPI.sections(response)` → the `at → result` and `result → stop` legs
3. `asyncio.gather(...)` over one call per positioned result
4. `excursion = length_to + length_from - baseline_length`
5. sort key `dur_to`, filter on `excursion_m`
6. `DetourRanker(credentials, at_pos, stop_pos, routing_api=...)`, the packaged equivalent

For the high-level equivalent, see the page about [DetourRanker](high-level/ch_hl_route_2_detour.md).
For the complete reference, see the [API reference](../../reference/api_reference.md).

<div class="notebook-embed">
  <iframe src="../../../../notebooks?path=route/ch_route_4_detour.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.routing_api.RoutingAPI
   :members: routes, sections
   :no-index:

.. autoclass:: here_search_demo.routing_api.Waypoint
   :members:
   :no-index:

.. autoclass:: here_search_demo.detour.DetourRanker
   :members: rerank, retrieve_detours, get_route_with_via
   :no-index:

.. autoclass:: here_search_demo.api.API
   :members: browse
   :no-index:
```
