---
hide-toc: true
---

# OBM 4 Auth Notebook

## API quick reference

This notebook focuses on credential loading and token retrieval in different runtimes.
Most-used elements:

1. `Credentials()`
2. `Credentials.atoken`
3. `Credentials.token`
4. `Credentials.api_key`
5. `IS_BROWSER_RUNTIME`

For the complete reference, see [API Reference](../reference/api_reference.md).
For how credentials are resolved, applied, and what degrades when they are missing, see [Credentials](../explanation/credentials.md).

<div style="height: 700px; overflow: hidden; border: 1px solid #ccc; border-radius: 4px;">
  <iframe src="../../notebooks/?path=obm_4_auth.ipynb" loading="lazy" width="100%" height="780px" style="border: 0; margin-top: -70px;"></iframe>
</div>

## API methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.auth.Credentials
   :members: atoken, token, api_key
   :no-index:

.. autodata:: here_search_demo.http.IS_BROWSER_RUNTIME
   :no-index:
```
