---
hide-toc: true
---

# Report a user action (Signals)

This guide shows how to report a user interaction on a search result via the HERE
Search **Signals** endpoint. For what signals are and why they exist, see the
[Signals explanation](../explanation/signals.md); for the full method signature, see
the [API Reference](../reference/api_reference.md).

## Steps

Call the async `API.signals` method with the result you want to report:

```python
await api.signals(
    session,                        # HTTPSession instance
    resource_id="here:poi:1234",    # HERE result id
    correlation_id="abcd-efgh-5678",# X-Correlation-ID from the response that produced it
    rank=2,                         # result position in its list
    action="here:gs:action:view",  # action performed
)
```

The four required arguments are `resource_id`, `correlation_id`, `rank`, and `action`.
`version=1` is added for you.

## Attach optional fields

Extra body fields (for example `userId` or `asSessionId`) are passed as keyword
arguments and forwarded into the POST body. Custom `X-*` headers go through
`x_headers`:

```python
await api.signals(
    session,
    resource_id="here:poi:1234",
    correlation_id="abcd-efgh-5678",
    rank=2,
    action="here:gs:action:view",
    userId="user-42",                       # extra body field
    x_headers={"X-User-ID": "user-42"},     # extra header
)
```

## Verify it worked

- `API.signals` returns a `Response` on success and `None` on failure — it never raises,
  so it is safe to call from a UI event handler.
- If you get `None`, confirm all four required fields are set and correct.
- Enable logging to see the emitted signal in the log output.
