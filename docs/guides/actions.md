---
hide-toc: true
---

# Signals Endpoint: Developer and User Guide

This document explains the purpose, usage, and integration of the HERE Search **Signals** endpoint in this project. It is intended for both developers and end users, similar in style to the [route search guide](route_search.md).

---

## What is the Signals Endpoint?

The Signals endpoint allows the client to report user actions (such as viewing, selecting, or interacting with a search result) back to the HERE backend. This feedback can be used for analytics, personalization, or improving search relevance.

Typical actions include:
- Viewing a result
- Selecting a result as start/end/stop
- Other custom actions (e.g., 'here:gs:action:view', 'start', 'end')

---

## User Guide: How Signals Work

When you interact with a search result (e.g., click, tap, or select), the app may send a signal to the backend. This is transparent to the user and does not affect your experience, but it helps HERE improve the service.

### What is sent?
- **resourceId**: The unique HERE result ID you interacted with
- **correlationId**: The X-Correlation-ID from the response that produced this result
- **rank**: The position of the result in the result list
- **action**: The action you performed (e.g., view, start, end)
- **version**: Protocol version (currently 1)
- **Optional**: Additional fields (e.g., userId, asSessionId)

No personal data is sent unless explicitly configured by the developer.

---

## Developer Guide: Integrating Signals

### Calling the Signals Endpoint

Use the `API.signals` async method to report a user action:

```python
await api.signals(
    session,                # HTTPSession instance
    resource_id,            # HERE result id
    correlation_id,         # X-Correlation-ID from the response
    rank,                   # Result rank (int)
    action,                 # Action string (e.g., 'here:gs:action:view')
    x_headers=None,         # Optional: extra headers (e.g., X-User-ID)
    userId=None,            # Optional: user id
    asSessionId=None        # Optional: session id
)
```

#### Example

```python
await api.signals(
    session,
    resource_id="here:poi:1234",
    correlation_id="abcd-efgh-5678",
    rank=2,
    action="here:gs:action:view",
    userId="user-42"
)
```

### What Happens Internally?
- The method builds a POST request with form-encoded data.
- Sends to the `/v1/signals` endpoint.
- Handles errors gracefully (returns None on failure).
- Logs the action for debugging if logging is enabled.

### Customizing Signals
You can add extra fields (e.g., `userId`, `asSessionId`) as keyword arguments. These will be included in the POST body.

---

## Troubleshooting
- If the endpoint returns an error, the method returns `None`.
- Check that you pass all required fields: `resource_id`, `correlation_id`, `rank`, `action`.
- Use logging to verify that signals are being sent as expected.

---

## API Reference

See the `API.signals` method in `src/here_search_demo/api.py` for implementation details.

---

## See Also
- [HERE Search API documentation](https://docs.here.com/geocoding-and-search/reference)
