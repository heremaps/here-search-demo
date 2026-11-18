---
hide-toc: true
---

# Search Client 1

## Quick reference

This notebook focuses on Search client calls. Most-used entry points:

1. `API.autosuggest(...)`
2. `API.discover(...)`
3. `HTTPSession()`
4. `Response.geojson()`
5. `Response.req` (request metadata)

For the complete reference, see the [API reference](../reference/api_reference.md).


<div class="notebook-embed">
  <iframe id="notebook-frame" src="../../../notebooks/?path=ch_1_api.ipynb" loading="lazy"></iframe>
</div>

<!-- div style="height: 1950px; overflow: hidden; border: 1px solid #ccc; border-radius: 4px;">
  <iframe
    id="notebook-frame"
    src="../../notebooks/?path=ch_1_api.ipynb"
    width="100%"
    height="2030"
    style="border: 0; margin-top: -70px;">
  </iframe>
</div -->

## Methods used in this notebook

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
