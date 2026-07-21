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
5. `OneBoxMap._get_context()` reads route-derived fields (`polyline`, `width`, `all_along`, `search_at_position`) for search requests.

## Detour reranking interaction

`DetourRanker` remains a separate head-agnostic component. It can reuse route cache data produced by route acquisition so detour calculations avoid redundant routing calls.

## Testing strategy

- `tests/test_route_engine.py`: headless route model/service behavior.
- `tests/test_route.py`: map adapter rendering and integration behavior.
- `tests/test_widgets_app.py`: route-derived request context and rerank trigger behavior.

