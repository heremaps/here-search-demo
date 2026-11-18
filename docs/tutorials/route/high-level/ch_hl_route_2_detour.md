---
hide-toc: true
---

# `DetourRanker`

## Quick reference

This notebook focuses on the client-side detour reranking: via-route Routing API calls,
caching, excursion filtering and result annotations. Most-used elements:

1. `DetourRanker(credentials, at_pos, stop_pos, on_routing_request=..., route_cache=...)`
2. `DetourRanker.retrieve_detours(...)`
3. `DetourRanker.get_route_with_via(...)`
4. `DetourRanker.rerank(resp, max_excursion=...)`
5. The `_detour` item annotation (`label`, `excursion_m`, `polyline_to`, `polyline_from`)

For the complete reference, see the [API reference](../../../reference/api_reference.md).
For the ranking behaviour and label semantics, see [Search Along the Route](../../../guides/route_search.md).
For the reranking rules, see [Route math](../../../reference/route_math.md).

<div class="notebook-embed">
  <iframe src="../../../../../notebooks?path=route/high_level/ch_hl_route_2_detour.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.ranking.RankingMode
   :members:
   :no-index:

.. autoclass:: here_search_demo.detour.DetourRanker
   :members: rerank, retrieve_detours, get_route_with_via
   :no-index:

.. autoclass:: here_search_demo.entity.response.Response
   :members: titles, geojson, bbox
   :no-index:
```
