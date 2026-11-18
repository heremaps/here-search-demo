---
hide-toc: true
---

# Demo Notebook

## Quick reference

This notebook focuses on building a personalized end-to-end OneBoxMap demo.
Most-used elements:

1. `UserProfile(...)`
2. `OneBoxMap(...)`
3. `OneBoxMap.show()`
4. `OneBoxMap.run()`
5. `UserProfile.get_current_language()`

For the complete reference, see the [API reference](../reference/api_reference.md).

<div class="notebook-embed">
  <iframe src="../../../notebooks?path=demo.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.user.UserProfile
   :members: use_positioning, share_experience, get_preferred_country_language, get_current_language
   :no-index:

.. autoclass:: here_search_demo.widgets.app.OneBoxMap
   :members: show, run
   :no-index:
```
