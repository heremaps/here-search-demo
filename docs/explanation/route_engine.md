# Route engine and widget controller architecture

This document explains the split between:

- `RouteEngine` (`src/here_search_demo/route_engine.py`)
- `RouteController` (`src/here_search_demo/widgets/route.py`)

The goal is to keep route logic reusable and head-agnostic while preserving map-specific UX in the widget layer.

## Layering

```
OneBoxCore / OneBoxMap
        │
        ├─ RouteEngine        (head-agnostic route model + routing service)
        └─ RouteController    (ipyleaflet adapter + rendering + controls)
```

## RouteEngine (head-agnostic)

`RouteEngine` owns route state and routing computations without importing `ipyleaflet` or `ipywidgets`.

### Responsibilities

- Route state:
  - `start_position`, `stop_position`, `current_position`, `future_position`
  - `width`, `mins_from_pos`
  - `ranking_mode` (`all_along`, `travel_time`)
- Derived context:
  - `search_at_position`
  - `route_flexpolyline`, `search_flexpolyline`
  - `route_summary_length`, `waypoints_count`
- Routing data retrieval and cache management:
  - `update_route_attributes()`
  - `_route_cache` reuse
- Route option mutators:
  - `set_route_start`, `set_route_stop`, `set_current_position`
  - `set_route_width`
  - Ranking options via the `all_along` / `minimal_detour` properties

### Why it exists

- Reuse route-aware behavior outside map notebooks.
- Make route logic testable in pure unit tests.
- Keep `OneBoxCore` extensible for alternative heads.

## RouteController (map adapter)

`RouteController` remains the map-facing layer used by `PositionMap` / `OneBoxMap`.

### Responsibilities

- Rendering route geometry and markers on ipyleaflet.
- Managing UI controls and map callbacks.
- Scheduling map updates (`fit_bounds`, detour overlays, marker refresh).
- Exposing route state by delegating to the owned `RouteEngine` (the single source of truth) through read/write properties.

### Boundary rule

- If logic can run without widget objects, it belongs in `RouteEngine`.
- If logic manipulates map layers, controls, or map event UX, it belongs in `RouteController`.

## Data flow

1. User sets route points/options from the map controls.
2. `RouteController` updates `RouteEngine`.
3. `RouteEngine` refreshes route attributes and cache.
4. `RouteController` renders/updates map layers, reading engine state through its delegating properties.
5. `OneBoxMap._get_context()` reads route-derived fields (`polyline`, `width`, `all_along`, `search_at_position`, `current_waypoints`) for search requests.

## Detour re-ranking interaction

`DetourRanker` remains a separate head-agnostic component. It can reuse route cache data produced by route acquisition so detour calculations avoid redundant routing calls.

Both `RouteEngine` and `DetourRanker` retrieve their routes through
`routing_api.RoutingAPI`, a thin HERE Routing API v8 client built like `api.API`: it owns
the credentials, the request building, the response cache and the logging hook. Neither
class issues HTTP requests itself, so a routing client can be shared (or replaced) through
their `routing_api=` constructor argument.

The notebooks [RouteEngine](../tutorials/route/high-level/ch_hl_route_1_engine.md),
[DetourRanker](../tutorials/route/high-level/ch_hl_route_2_detour.md) and
[Detour Map](../tutorials/route/high-level/ch_hl_route_3_render.md) walk through this
interaction step by step, from route acquisition to detour rendering.

The notebooks [Routing Client](../tutorials/route/ch_route_1_api.md),
[Detour Re-ranking](../tutorials/route/ch_route_4_detour.md) and
[Detours Rendering](../tutorials/route/ch_route_5_render.md) cover the same
feature built on `RoutingAPI` alone, for applications that keep their own route, ranking
and map classes. Two of the geometry services `RouteEngine` provides are detailed
separately: [Polyline Simplification](../tutorials/route/ch_route_2_simplify.md) for
`build_flexpolyline()` and the `max_waypoints_count` ceiling, and
[Ahead On The Route](../tutorials/route/ch_route_3_ahead.md) for
`set_mins_from_pos()` and the `search_at_position` anchor.

## Route-stratified corridor search

`corridor_search()` (`src/here_search_demo/stratified_search.py`) is the other
route-aware post-processing step: `TextSearchEvent`/`PlaceTaxonomySearchEvent`
(`src/here_search_demo/event.py`) delegate to it instead of calling
`api.discover`/`api.browse` directly. It only stratifies when
`RequestContext.all_along` is set — a default-relevance corridor search
always goes through as a single call. When it is set, it reads
`RequestContext.route_waypoints` (populated from `RouteEngine.current_waypoints`,
delegated through `RouteController` like every other route-derived field) to
decide whether a single whole-route corridor call is dense enough, or
whether the remaining route — from the search position to the destination —
should be split into slices searched in parallel and merged with quota
redistribution.

Both call sites supply only a small closure — "how to fetch one slice" — so
the slicing/fan-out/merge algorithm has no knowledge of `discover` vs.
`browse`. For short remaining routes, or no route at all, it degenerates to
exactly one call, identical to the pre-stratification behavior. See the
[Search Along the Route guide](../guides/route_search.md) for the
user-facing behavior and the
[Route math appendix](../reference/route_math.md) for the threshold and
redistribution rules.

## Testing strategy

- `tests/test_route_engine.py`: headless route model/service behavior.
- `tests/test_route.py`: map adapter rendering and integration behavior.
- `tests/test_widgets_app.py`: route-derived request context and rerank trigger behavior.
- `tests/test_stratified_search.py`: route-slicing, parallel fan-out, and
  quota-redistribution behavior of `corridor_search()`.
- `tests/test_event.py`: delegation from `TextSearchEvent`/`PlaceTaxonomySearchEvent`
  into `corridor_search()`.
