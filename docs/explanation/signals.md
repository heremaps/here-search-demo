---
hide-toc: true
---

# Signals

The HERE Search **Signals** endpoint lets the client report user actions on search
results back to the backend. This page explains what it is for and how the client
handles it. For the step-by-step call, see the
[Report a user action](../guides/signals.md) guide; for the method signature, see the
[API Reference](../reference/api_reference.md).

## Purpose

Reporting interactions (viewing, selecting, or otherwise acting on a result) gives
HERE feedback that can be used for analytics, personalization, and improving search
relevance.

Typical actions include:

- viewing a result;
- selecting a result as start / end / stop;
- other custom actions (e.g. `here:gs:action:view`, `start`, `end`).

## What is sent

Each signal carries:

| Field | Meaning |
|---|---|
| `resourceId` | The HERE result id the action was performed on |
| `correlationId` | The `X-Correlation-ID` from the response that produced the result |
| `rank` | The position of the result in its result list |
| `action` | The action performed (e.g. `here:gs:action:view`) |
| `version` | Signals protocol version (currently `1`) |
| *(optional)* | Additional body fields such as `userId`, `asSessionId` |

From an end-user perspective this is transparent and does not affect the experience.
No personal data is sent unless the developer explicitly configures it (e.g. by passing
`userId` or an `X-User-ID` header).

## How the client handles it

`API.signals` (`src/here_search_demo/api.py`):

- builds a form-encoded POST body from the fields above (plus any extra keyword
  arguments);
- sends it to the `/v1/signals` endpoint;
- returns `None` on failure instead of raising, so a failed signal never interrupts
  the search flow;
- logs the action when logging is enabled, which is the easiest way to confirm signals
  are being emitted.

Because signals are fire-and-forget and non-blocking, they are safe to emit from UI
event handlers without guarding the surrounding interaction.

## See also

- [HERE Search API documentation](https://docs.here.com/geocoding-and-search/reference/post_signals)
