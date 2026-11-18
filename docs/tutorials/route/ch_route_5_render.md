---
hide-toc: true
---

# Detours rendering

## Quick reference

This notebook draws routes and detours with plain [`ipyleaflet`](https://ipyleaflet.readthedocs.io)
objects instead of the demo `ResponseMap`/`RouteController` pair, to show how the feature
plugs into an existing map. Most-used elements:

1. `flexpolyline.decode(polyline)` → `ipyleaflet.Polyline(locations=...)`
2. `ipyleaflet.Map` / `Marker` / `GeoJSON` and `Map.add` / `Map.remove`
3. `GeoJSON.on_click(...)` carrying the detour annotation in the feature properties
4. a green `at → result` leg and a purple `result → stop` leg, drawn from the cached
   polylines returned by the reranking — no extra Routing API call

For the high-level equivalent, see the page about [Detour Map](high-level/ch_hl_route_3_render.md).
For the complete reference, see the [API reference](../../reference/api_reference.md).

<div class="notebook-embed">
  <iframe src="../../../../notebooks?path=route/ch_route_5_render.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.routing_api.RoutingAPI
   :members: routes, sections
   :no-index:

.. autoclass:: here_search_demo.widgets.route.RouteController
   :members: draw_detour_routes, clear_detour_routes
   :no-index:

.. autoclass:: here_search_demo.widgets.output_map.ResponseMap
   :members: display, click_result
   :no-index:
```
