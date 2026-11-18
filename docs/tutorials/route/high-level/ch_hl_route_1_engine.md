---
hide-toc: true
---

# `RouteEngine`

## Quick reference

This notebook focuses on route acquisition, the head-agnostic route model and the
search-along-route request. Most-used elements:

1. `RouteEngine(credentials, on_routing_request=..., route_cache=...)`
2. `RouteEngine.set_route_start/set_route_stop/set_route_width(...)`
3. `RouteEngine.update_route_attributes()`
4. `RouteEngine.search_at_position` / `search_flexpolyline`
5. `build_corridor(...)` / `simplify_polyline(...)`
6. `API.browse(..., polyline=..., width=...)`

For the complete reference, see the [API reference](../../../reference/api_reference.md).
For route architecture details, see [Route engine and widget controller architecture](../../../explanation/route_engine.md).
For the end-user behaviour, see [Search Along the Route](../../../guides/route_search.md).

<div class="notebook-embed">
  <iframe src="../../../../../notebooks?path=route/high_level/ch_hl_route_1_engine.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.route_engine.RouteEngine
   :members: update_route_attributes, set_route_start, set_route_stop, set_current_position, set_mins_from_pos, set_route_width, build_flexpolyline, search_at_position, minimal_detour
   :no-index:

.. autofunction:: here_search_demo.widgets.route_geometry.build_corridor
   :no-index:

.. autofunction:: here_search_demo.widgets.route_geometry.simplify_polyline
   :no-index:

.. autoclass:: here_search_demo.api.API
   :members: browse, discover, autosuggest
   :no-index:
```
