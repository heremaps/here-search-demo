---
hide-toc: true
---

# Demo Notebook

## API quick reference

This notebook focuses on building a personalized end-to-end OneBoxMap demo.
Most-used elements:

1. `UserProfile(...)`
2. `OneBoxMap(...)`
3. `OneBoxMap.show()`
4. `OneBoxMap.run()`
5. `UserProfile.get_current_language()`

For the complete reference, see [API Reference](../reference/api_reference.md).

<div style="height: 700px; overflow: hidden; border: 1px solid #ccc; border-radius: 4px;">
  <iframe src="../../notebooks/?path=demo.ipynb" loading="lazy" width="100%" height="780px" style="border: 0; margin-top: -70px;"></iframe>
</div>

## API methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.user.UserProfile
   :members: use_positioning, share_experience, get_preferred_country_language, get_current_language
   :no-index:

.. autoclass:: here_search_demo.widgets.app.OneBoxMap
   :members: show, run
   :no-index:
```
