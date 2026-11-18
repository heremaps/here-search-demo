---
hide-toc: true
---

# Polyline Simplification

## Quick reference

The Search API rejects a `route` corridor parameter holding more than 2000 points, while a
route of a few hundred kilometers comes back with several thousand. This notebook opens the
`simplify_polyline(...)` method used in `OneBoxMap`:
- the Douglas–Peucker simplification
- the binary search that turns a tolerance into a point budget
- the deviation it costs in meters
- its effect on the corridor search.

Most-used elements:

1. `RoutingAPI.routes(...)` → `RouteSection.polyline` and `flexpolyline.decode/encode`
2. `shapely.simplify(line, eps, preserve_topology=False)` and `shapely.get_num_coordinates(...)`
3. `simplify_polyline(points, max_points, iterations=15)`
4. `RouteEngine.max_waypoints_count` / `RouteEngine.build_flexpolyline(...)`
5. `API.browse(..., polyline=..., width=...)`
6. `ipyleaflet.Polyline` and a HERE `TileLayer`

The corridor polygon drawn in `OneBoxMap` app by the `build_corridor(...)` method is covered in the
[Route Engine](high-level/ch_hl_route_1_engine.md).
For the complete reference, see the [API reference](../../reference/api_reference.md).

<div class="notebook-embed">
  <iframe src="../../../../notebooks?path=route/ch_route_2_simplify.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

```{eval-rst}
.. autofunction:: here_search_demo.widgets.route_geometry.simplify_polyline
   :no-index:

.. autofunction:: here_search_demo.widgets.route_geometry.build_corridor
   :no-index:

.. autoclass:: here_search_demo.routing_api.RoutingAPI
   :members: routes, sections
   :no-index:

.. autoclass:: here_search_demo.route_engine.RouteEngine
   :members: build_flexpolyline, update_route_attributes
   :no-index:

.. autoclass:: here_search_demo.api.API
   :members: browse
   :no-index:
```
