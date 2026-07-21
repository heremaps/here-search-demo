---
hide-toc: true
---

# Credentials

`OneBoxMap` relies on **two independent credential mechanisms**. Understanding which
one drives which feature is the key to reasoning about degraded states.

| Mechanism | Source                                | Consumed by                     | Failure impact                |
|---|---------------------------------------|---------------------------------|-------------------------------|
| **API key** | `here.api.key` property / `HERE_API_KEY` env variable | HERE map tiles; Logging window  | Map falls back to non-HERE tiles |
| **OAuth2 token** | access key id/secret → token endpoint | `Authorization: Bearer` header on Search/Routing API requests | Requests cannot be authorized |

The two are resolved and stored by `here_search_demo.auth.Credentials`, then wired into
the widget by `here_search_demo.widgets.app.OneBoxMap`.

**Files:** `src/here_search_demo/auth.py`, `src/here_search_demo/widgets/app.py`,
`src/here_search_demo/widgets/credentials.py`, `src/here_search_demo/api.py`,
`src/here_search_demo/widgets/input_map.py`.

---

## 1. `Credentials`: where values come from

`Credentials()` resolves values once at construction (`_config()`), from environment
variables and/or a credentials file. Environment variables take precedence over file
values.

**API key** resolution order:

1. `API_KEY`
2. `HERE_API_KEY`
3. file key `here.api.key` (or legacy `apikey`)

**OAuth2** values:

| Purpose | Env var | File key |
|---|---|---|
| Token endpoint | `HERE_TOKEN_ENDPOINT_URL` | `here.token.endpoint.url` |
| Access key id | `HERE_ACCESS_KEY_ID` | `here.access.key.id` |
| Access key secret | `HERE_ACCESS_KEY_SECRET` | `here.access.key.secret` |
| Scope (optional) | `HERE_TOKEN_SCOPE` | `here.token.scope` |

Credentials files are matched by name (`credentials.properties.txt`,
`credentials.properties`, `.credentials.properties`) in this directory order:
`/drive` → cwd → `.` → home → `~/.here/`.

> **The API key and the OAuth2 pair are independent.** A config can yield a working
> API key with no OAuth2 token, or vice versa. `_config()` records whichever it finds.

---

## 2. How each credential authorizes requests

This is the most common source of confusion, so it is worth stating precisely.

### Search API requests → **OAuth2 token**

`API.do_send()` authorizes every backend request with a Bearer token, **not** the API key:

```python
# src/here_search_demo/api.py
token = await self._credentials.atoken if IS_BROWSER_RUNTIME else self._credentials.token
req_headers = {"Authorization": f"Bearer {token}"}
```

- In a browser runtime (Pyodide/JupyterLite) the async property `Credentials.atoken` is used.
- In CPython the synchronous property `Credentials.token` is used.
- Both cache the token in memory and refresh it shortly before expiry.
- The API key is only appended to the `browser_url` shown in logs
  (`_build_display_urls`) for users to directly use them in a Browser, outside of the Jupyter app.

### Map tiles → **API key**

The base layer URL is built from the API key (`PositionMap._base_layer_url`):

```python
# src/here_search_demo/widgets/input_map.py
def _base_layer_url(self, style):
    if self._credentials.api_key:
        return self._here_url(style)   # https://maps.hereapi.com/v3/... &apiKey=...
    return self._positron_url(style)   # CARTO Positron fallback
```

---

## 3. Runtime wiring in `OneBoxMap`

At construction, `OneBoxMap`:

1. accepts a `Credentials` instance (or creates one).
2. builds the map and the search widgets; the search box starts **hidden**.
3. creates a `CredentialsLoader` widget and, if `Credentials.active_config` is already
   complete, seeds the loader with it.
4. subscribes to loader changes via `_on_credentials_properties_change`.
5. calls `_apply_credentials_properties(...)` for the initial config, then
   `_schedule_search_box_visibility()`.

Whenever credentials change (initial load **or** a widget upload),
`_apply_credentials_properties` runs:

```python
# src/here_search_demo/widgets/app.py
def _apply_credentials_properties(self, properties):
    if not properties:
        return
    self.credentials.apply_active_config(properties)  # update in-memory Credentials
    self.map_w.refresh_base_layer()                   # re-pick HERE vs Positron tiles
    self._schedule_search_box_visibility()            # re-evaluate search box gating
```

### `active_config` is all-or-nothing

`Credentials.active_config` only returns a non-empty mapping when the token endpoint,
access key id, access key secret **and** API key are all present and not placeholders
(`"..."`). Consequently the loader is only pre-seeded from a *complete* config; a partial
one leaves the loader empty.

---

## 4. The `CredentialsLoader` widget does not touch files

When a user uploads a `.properties` file through the widget:

1. the frontend validates the text (`credentials_loader.mjs`);
2. the raw content is stored in the browser's **IndexedDB** under the logical key
   `credentials.properties`;
3. the parsed values are pushed into the widget model and up to Python
   (`CredentialsLoader.active_config`);
4. `OneBoxMap` applies them to the **in-memory** `Credentials` for the current session.

> The widget overrides the **effective runtime credentials** only. It does **not** rewrite
> `credentials.properties*` on disk (repository, working directory, or `~/.here/`).

---

## 5. The search box is credential-gated

The search UI (`query_box_w`, `query_terms_w`, `buttons_box_w`, `result_buttons_w`) is
hidden until **both** hold:

1. `credentials.api_key` is set, and
2. `credentials.atoken` successfully returns a token.

The check runs asynchronously (`_credentials_are_valid` → `_update_search_box_visibility`),
scheduled on the running event loop by `_schedule_search_box_visibility`. If no loop is
running (e.g. plain construction in tests) or token retrieval raises, the box stays hidden.

---

## 6. Behavior matrix

| API key | OAuth2 token retrievable | Map tiles | Search UI | Search requests |
|---|---|---|---|---|
| ✅ | ✅ | HERE tiles | shown | authorized |
| ✅ | ❌ | HERE tiles | hidden | unauthorized (no valid Bearer token) |
| ❌ | ✅ | CARTO Positron fallback | hidden | authorized, but UI to trigger them is hidden |
| ❌ | ❌ | CARTO Positron fallback | hidden | unauthorized |

Takeaways:

- A **missing API key** never breaks the map — it only downgrades tiles to the Positron
  fallback (and hides the search UI, because gating also requires the API key).
- **Missing/invalid OAuth2** does not break tile rendering, but it hides the search UI and
  leaves backend requests unauthorized.

---

## 7. Providing credentials

For the full experience, provide both:

1. an API key — `HERE_API_KEY` (or `API_KEY`, or `here.api.key` in a file);
2. OAuth2 credentials — `HERE_ACCESS_KEY_ID`, `HERE_ACCESS_KEY_SECRET`, and optionally
   `HERE_TOKEN_ENDPOINT_URL` / `HERE_TOKEN_SCOPE`.

Either supply them via environment variables / a `credentials.properties` file before
constructing `OneBoxMap`, or upload a `.properties` file at runtime through the loader
widget in the map's top-right corner.

## API

The class-level API for `Credentials` and the `CredentialsLoader` widget is documented
in the [API Reference](../reference/api_reference.md).
