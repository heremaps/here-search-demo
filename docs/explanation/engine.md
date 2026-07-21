# App engine architecture

## Overview

The application is structured around three composable layers that deliberately keep async
search logic, personalization, and widget rendering as separate concerns.

For route-specific layering (`RouteEngine` vs `RouteController`), see
[Route engine and widget controller architecture](route_engine.md).

```
OneBoxCore                  ← async search engine (headless)
    │
UserProfileMixin            ← composable personalization side-class
    │
SearchHead (Protocol)       ← explicit contract for response rendering
    │
OneBoxMap(UserProfileMixin, OneBoxCore)   ← full ipyleaflet/ipywidgets UI
```

---

## OneBoxCore

**File:** `src/here_search_demo/base.py`

The invariant, headless async search engine. It has no dependency on any widget library,
credential system, or user profile concept.

**Responsibilities:**
- Async event loop lifecycle (`run()` / `stop()`)
- `asyncio.Queue`-based intent consumption
- Transient-text coalescing (debounce without a timer)
- Intent triage: resolves a `SearchIntent` into a typed `SearchEvent`, a handler, and an
  `EndpointConfig` via the `TRIAGES` dispatch table
- `HTTPSession` management and postprocess callback chain
- `_get_context()` — produces a bare `RequestContext` from `search_center` + `preferred_language`
- No-op response stubs (`handle_suggestion_list`, `handle_result_list`, …) that satisfy
  the `SearchHead` Protocol by default

**Usage (headless, e.g. in tests or API servers):**
```python
from here_search_demo.base import OneBoxCore

app = OneBoxCore()
app.queue.put_nowait(intent)
intent_out, event, resp = await app.handle_search_event(session)
```

---

## UserProfileMixin

**File:** `src/here_search_demo/base.py`

A composable mixin that binds a `UserProfile` to any `OneBoxCore` subclass. It is a
*side concern* — it adds personalization without coupling to any specific rendering head.

**Responsibilities:**
- Seeds `OneBoxCore` with position and language from the profile at construction time
- Enriches `_get_context()` with `share_experience` and `user_id` (via cooperative `super()`)
- Hooks `handle_search_event` to call `adapt_language()` after full-text or taxonomy searches
- Language adaptation: detects the dominant country code in a result set and switches
  `preferred_language` to match the user's country preference
- `set_search_center()` utility

**Cooperative MRO usage:**
```python
class MyApp(UserProfileMixin, OneBoxCore):
    ...
# MRO: MyApp → UserProfileMixin → OneBoxCore
# Every super() call chains correctly without explicit class references.
```

**Isolation:** `UserProfileMixin` can be tested by mixing it with a minimal `OneBoxCore`
subclass; it has no ipywidget or credential dependency.

---

## SearchHead Protocol

**File:** `src/here_search_demo/base.py`

A `typing.Protocol` that documents the *override contract* for any class acting as a
search result head. `OneBoxCore` already satisfies it via its no-op stubs — structural
subtyping means no explicit registration is needed.

```python
from here_search_demo.base import SearchHead
```

**Protocol methods:**
| Method | Called when |
|---|---|
| `handle_suggestion_list(intent, response)` | Autosuggest results arrive |
| `handle_result_list(intent, response)` | Full-text / taxonomy results arrive |
| `handle_result_details(intent, response)` | Lookup details arrive |
| `handle_empty_text_submission(intent, response)` | Empty query submitted |
| `handle_action(intent, response)` | User clicks a result item |
| `search_events_preprocess(session)` | Before the event loop starts |

**Building an alternative head:**
```python
class TerminalHead(OneBoxCore):
    """Rich/Textual-based rendering head."""
    def handle_suggestion_list(self, intent, response):
        rich.print(response.data)
    def handle_result_list(self, intent, response):
        rich.print(response.data)
    ...

class TerminalApp(UserProfileMixin, TerminalHead):
    ...
```

---

## OneBoxMap

**File:** `src/here_search_demo/widgets/app.py`

The full interactive demo widget. Inherits from both `UserProfileMixin` and `OneBoxCore`,
wiring ipyleaflet map rendering and ipywidgets UI into the search engine.

**MRO:** `OneBoxMap → UserProfileMixin → OneBoxCore`

**Responsibilities (pure UI/rendering):**
- Credential and `API` construction
- Widget instantiation: `ResponseMap`, `SubmittableTextBox`, `PlaceTaxonomyButtons`,
  `SearchResultButtons`, `SearchResultJson`, `TableLogWidget`
- Widget layout composition (VBox / HBox / WidgetControl)
- Full `SearchHead` method implementations (render suggestions, results, details on the map)
- Routing / detour integration
- Recommendation reranking
- CORS / `X-User-ID` management
- Signals lifecycle (`search_events_preprocess`, `stop`)

**Construction:**
```python
from here_search_demo.widgets.app import OneBoxMap

app = OneBoxMap(map_only=True, on_map=True)
app.show()
app.run()
```

---

## Separation of concerns summary

| Concern | Class |
|---|---|
| Async event loop, intent queue, triage | `OneBoxCore` |
| UserProfile, language adaptation, context enrichment | `UserProfileMixin` |
| Response handler contract | `SearchHead` Protocol |
| Widget rendering, map, credentials, layout | `OneBoxMap` |

---

## Adding a new head

To build a non-map head (e.g. a terminal UI or a REST API responder):

1. Create a class that inherits `(UserProfileMixin, OneBoxCore)` (or just `OneBoxCore`
   if personalization is not needed).
2. Override the `SearchHead` methods to render results in your medium.
3. Optionally override `search_events_preprocess` for startup logic.

No changes to `OneBoxCore` or `UserProfileMixin` are required.
