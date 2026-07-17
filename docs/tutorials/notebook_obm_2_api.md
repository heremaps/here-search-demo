---
hide-toc: true
---

# OBM 2 API Notebook

## API quick reference

This notebook focuses on browse queries and low-level request/response handling.
Most-used entry points:

1. `API.browse(...)`
2. `API.send(...)`
3. `HTTPSession()`
4. `Request(...)`
5. `Request.full`

For the complete reference, see [API Reference](../reference/api_reference.md).

<div style="height: 700px; overflow: hidden; border: 1px solid #ccc; border-radius: 4px;">
  <iframe src="../../notebooks/?path=obm_2_api.ipynb" loading="lazy" width="100%" height="780px" style="border: 0; margin-top: -70px;"></iframe>
</div>

## API methods used in this notebook

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
