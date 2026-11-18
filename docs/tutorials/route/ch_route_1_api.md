---
hide-toc: true
---

# Routing Client

## Quick reference

This notebook introduces `RoutingAPI`, the low-level HERE Routing API v8 client used by
`RouteEngine` and `DetourRanker`, two classes used in the `OneBoxMap` application.
It is the entry point for a team that wants to add detour
reranking to an application built on its own route and ranking classes. Most-used
elements:

1. `RoutingAPI(credentials, cache=..., options=..., on_request_sent=...)`
2. `RoutingAPI.routes(session, origin, destination, via=..., return_fields=..., spans=...)`
3. `Waypoint(latitude, longitude, name_hint=...)` / `RoutingOptions(...)`
4. `RoutingAPI.sections(response)` → `RouteSection(duration, length, polyline, spans)`
5. `flexpolyline.decode/encode` and `simplify_polyline(...)`
6. `API.browse(..., polyline=..., width=...)`

For the high-level equivalent, see [Route Engine](high-level/ch_hl_route_1_engine.md) page.
For the complete reference, see the [API reference](../../reference/api_reference.md).

<div class="notebook-embed">
  <iframe src="../../../../notebooks?path=route/ch_route_1_api.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.routing_api.RoutingAPI
   :members: routes, send, sections, auth_headers, query
   :no-index:

.. autoclass:: here_search_demo.routing_api.Waypoint
   :members:
   :no-index:

.. autoclass:: here_search_demo.routing_api.RouteSection
   :no-index:

.. autoclass:: here_search_demo.routing_api.RoutingOptions
   :no-index:

.. autofunction:: here_search_demo.widgets.route_geometry.simplify_polyline
   :no-index:

.. autoclass:: here_search_demo.api.API
   :members: browse, discover, autosuggest
   :no-index:
```
