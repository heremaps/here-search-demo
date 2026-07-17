---
hide-toc: true
---

# OBM 1 API Notebook

## API quick reference

This notebook focuses on direct API calls. Most-used entry points:

1. `API.autosuggest(...)`
2. `API.discover(...)`
3. `HTTPSession()`
4. `Response.geojson()`
5. `Response.req` (request metadata)

For the complete reference, see [API Reference](../reference/api_reference.md).


<div style="height: 700px; overflow: hidden; border: 1px solid #ccc; border-radius: 4px;">
  <iframe
    id="notebook-frame"
    src="../../notebooks/?path=obm_1_api.ipynb"
    width="100%"
    height="780"
    style="border: 0; margin-top: -70px;">
  </iframe>
</div>


## API methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.api.API
   :members: autosuggest, discover
   :no-index:

.. autoclass:: here_search_demo.lite.HTTPSession
   :members: get, post, request, prepare
   :no-index:

``here_search_demo.http.HTTPSession`` resolves to this implementation in browser runtimes (JupyterLite / Pyodide).

.. autoclass:: here_search_demo.entity.response.Response
   :members: geojson, req
   :no-index:

.. autoclass:: here_search_demo.entity.request.Request
   :members:
   :no-index:
```
