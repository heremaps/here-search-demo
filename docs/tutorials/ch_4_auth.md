---
hide-toc: true
---

# Authorization

## Quick reference

This notebook focuses on credential loading and token retrieval in different runtimes.
Most-used elements:

1. `Credentials()`
2. `Credentials.atoken`
3. `Credentials.token`
4. `Credentials.api_key`
5. `IS_BROWSER_RUNTIME`

For the complete reference, see the [API reference](../reference/api_reference.md).
For how credentials are resolved, applied, and what degrades when they are missing, see [Credentials](../explanation/credentials.md).

<div class="notebook-embed" style="--notebook-embed-height: 650px;">
  <iframe src="../../../notebooks?path=ch_4_auth.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.auth.Credentials
   :members: atoken, token, api_key
   :no-index:

.. autodata:: here_search_demo.http.IS_BROWSER_RUNTIME
   :no-index:
```
