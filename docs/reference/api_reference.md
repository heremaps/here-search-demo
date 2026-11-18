# API Reference

This page centralizes the public API surface used by the demo and notebooks.

## Core modules

### here_search_demo.api

```{eval-rst}
.. automodule:: here_search_demo.api
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: api_key, auth_headers, cors_allow_nlp_testing_header, do_log, do_send, send, get_x_headers, lookup_has_more_details, options, raise_for_status, url_builder
```

### here_search_demo.widgets.app

```{eval-rst}
.. automodule:: here_search_demo.widgets.app
   :members:
   :undoc-members:
   :show-inheritance:
```

### here_search_demo.widgets.credentials

```{eval-rst}
.. automodule:: here_search_demo.widgets.credentials
   :members:
   :undoc-members:
   :show-inheritance:
```

### here_search_demo.api_options

```{eval-rst}
.. automodule:: here_search_demo.api_options
   :members:
   :undoc-members:
   :show-inheritance:
```

### here_search_demo.user

```{eval-rst}
.. automodule:: here_search_demo.user
   :members:
   :undoc-members:
   :show-inheritance:
```

## Classes used in `obm_*.ipynb`

```{eval-rst}
.. autoclass:: here_search_demo.base.OneBoxCore
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.auth.Credentials
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.widgets.input_text.SubmittableTextBox
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.widgets.input_text.SubmittableText
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.widgets.input_text.TermsButtons
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.widgets.input_text.PlaceTaxonomyButtons
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.widgets.state.SearchState
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.widgets.util.Output
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.widgets.output_map.ResponseMap
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.widgets.route.RouteController
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.routing_api.RoutingAPI
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.routing_api.Waypoint
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.routing_api.RouteSection
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.routing_api.RoutingOptions
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.route_engine.RouteEngine
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.ranking.RankingMode
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.detour.DetourRanker
   :members:
   :show-inheritance:

.. automodule:: here_search_demo.stratified_search
   :members: should_stratify, compute_slice_ranges, merge_with_quota_redistribution, corridor_search
   :show-inheritance:

.. automodule:: here_search_demo.widgets.route_geometry
   :members: build_corridor, simplify_polyline, elapsed_sec_at_position, position_at_x_sec_ahead, haversine_m

.. autoclass:: here_search_demo.widgets.output_json.SearchResultJson
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.widgets.output_buttons.SearchResultButtons
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.entity.place.PlaceTaxonomyExample
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.entity.request.Request
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.entity.endpoint.Endpoint
   :members:
   :show-inheritance:

.. autoclass:: here_search_demo.entity.intent.ActionIntent
   :members:
   :show-inheritance:

```
