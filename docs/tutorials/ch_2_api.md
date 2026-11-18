---
hide-toc: true
---

# Search Client 2

## Quick reference

This notebook focuses on browse queries and low-level request/response handling.
Most-used entry points:

1. `API.browse(...)`
2. `API.send(...)`
3. `HTTPSession()`
4. `Request(...)`
5. `Request.full`

For the complete reference, see the [API reference](../reference/api_reference.md).

<div class="notebook-embed">
  <iframe src="../../../notebooks?path=ch_2_api.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.api.API
   :members: browse, send
   :no-index:

.. autoclass:: here_search_demo.lite.HTTPSession
   :members: get, post, request, prepare
   :no-index:

``here_search_demo.http.HTTPSession`` resolves to this implementation in browser runtimes (JupyterLite / Pyodide).

.. autoclass:: here_search_demo.entity.request.Request
   :members: full, key
   :no-index:

.. autoclass:: here_search_demo.entity.response.Response
   :members: req
   :no-index:
```
