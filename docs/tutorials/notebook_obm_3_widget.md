---
hide-toc: true
---

# OBM 3 Widget Notebook

## API quick reference

This notebook focuses on UI building blocks and their interaction flow.
Most-used elements:

1. `SubmittableTextBox`
2. `TermsButtons`
3. `PlaceTaxonomyButtons`
4. `ResponseMap`
5. `OneBoxCore.run()`

For the complete reference, see [API Reference](../reference/api_reference.md).

<div style="height: 700px; overflow: hidden; border: 1px solid #ccc; border-radius: 4px;">
  <iframe src="../../notebooks/?path=obm_3_widget.ipynb" loading="lazy" width="100%" height="780px" style="border: 0; margin-top: -70px;"></iframe>
</div>

## API methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.widgets.input_text.SubmittableText
   :members: on_submit, trigger_submit
   :no-index:

.. autoclass:: here_search_demo.widgets.input_text.SubmittableTextBox
   :members: on_submit, on_click, submit, feed
   :no-index:

.. autoclass:: here_search_demo.widgets.input_text.TermsButtons
   :members: set, render
   :no-index:

.. autoclass:: here_search_demo.widgets.input_text.PlaceTaxonomyButtons
   :members:
   :no-index:

.. autoclass:: here_search_demo.widgets.output_map.ResponseMap
   :members: display
   :no-index:

.. autoclass:: here_search_demo.base.OneBoxCore
   :members: run, handle_suggestion_list, handle_result_list
   :no-index:
```
