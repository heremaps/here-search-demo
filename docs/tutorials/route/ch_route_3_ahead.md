---
hide-toc: true
---

# Ahead On The Route

## Quick reference

Anchoring the search at the driver's current position answers *what is around me*. Planning
a pause asks *what will be around me in half an hour*, so that a break — and the detour it
costs — can be chosen upfront rather than at the next exit. This notebook moves the search
anchor *n* minutes forward along the route, out of the route spans and without any extra API
call: reading the spans, measuring the elapsed time at the driver's position, interpolating
the point one horizon further, and drawing the horizons on a map. Most-used elements:

1. `RoutingAPI.routes(..., spans=("duration", "dynamicSpeedInfo", "length"))` → `RouteSection.spans`
2. `elapsed_sec_at_position(spans, waypoints, lat, lon)`
3. `position_at_x_sec_ahead(spans, waypoints, elapsed, x_sec)`
4. `RouteEngine.set_mins_from_pos(mins)` / `RouteEngine.search_at_position`
5. `RouteController.build_mins_from_pos_text_w()` / `RouteController.draw_future_position()`
6. `API.browse(..., polyline=..., width=...)` anchored at the future position

`dynamicSpeedInfo` is what splits the route into spans: `spans=("duration", "length")` alone
returns a single span covering the whole route.
For the complete reference, see the [API reference](../../reference/api_reference.md).

<div class="notebook-embed">
  <iframe src="../../../../notebooks?path=route/ch_route_3_ahead.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

```{eval-rst}
.. autofunction:: here_search_demo.widgets.route_geometry.elapsed_sec_at_position
   :no-index:

.. autofunction:: here_search_demo.widgets.route_geometry.position_at_x_sec_ahead
   :no-index:

.. autofunction:: here_search_demo.widgets.route_geometry.haversine_m
   :no-index:

.. autoclass:: here_search_demo.routing_api.RoutingAPI
   :members: routes, sections
   :no-index:

.. autoclass:: here_search_demo.route_engine.RouteEngine
   :members: set_mins_from_pos, set_current_position, search_at_position
   :no-index:

.. autoclass:: here_search_demo.api.API
   :members: browse
   :no-index:
```
