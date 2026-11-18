---
hide-toc: true
---

# `RouteController`

## Quick reference

This notebook focuses on rendering detours: the `ipyleaflet` adapter around the route
model, the reranked result overlays and the detour legs. Most-used elements:

1. `ResponseMap(credentials, center=..., zoom=...)` and its `route` attribute
2. `RouteController.set_route_start/set_route_stop/set_route_width(...)`
3. `RouteController.draw_detour_routes(...)` / `clear_detour_routes()`
4. `ResponseMap.display(resp, fit=True)`
5. `SearchState.hydrate(resp)` / `SearchState.title_for(rank)`
6. `ResponseMap.click_result(rank)`

For the complete reference, see the [API reference](../../../reference/api_reference.md).
For the layering rationale, see [Route engine and widget controller architecture](../../../explanation/route_engine.md).

<div class="notebook-embed">
  <iframe src="../../../../../notebooks?path=route/high_level/ch_hl_route_3_render.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.widgets.output_map.ResponseMap
   :members: display, click_result, clear_results
   :no-index:

.. autoclass:: here_search_demo.widgets.route.RouteController
   :members: set_route_start, set_route_stop, set_current_position, set_route_width, set_travel_time_option, draw_detour_routes, clear_detour_routes, on_drawn, on_removed
   :no-index:

.. autoclass:: here_search_demo.widgets.state.SearchState
   :members: hydrate, title_for, ranks, get_item_data
   :no-index:
```
