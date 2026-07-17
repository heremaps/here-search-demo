---
hide-toc: true
---

# OBM 5 Automate Notebook

## API quick reference

This notebook focuses on scripted OneBoxMap interactions and route automation.
Most-used elements:

1. `OneBoxMap()`
2. `SubmittableTextBox.feed(...)`
3. `SubmittableTextBox.submit()`
4. `RouteController.set_route_start/at/stop(...)`
5. `RouteController.set_route_width(...)`

For the complete reference, see [API Reference](../reference/api_reference.md).
For route architecture details, see [Route engine and widget controller architecture](../reference/route_engine.md).

<div style="height: 700px; overflow: hidden; border: 1px solid #ccc; border-radius: 4px;">
  <iframe src="../../notebooks/?path=obm_5_automate.ipynb" loading="lazy" width="100%" height="780px" style="border: 0; margin-top: -70px;"></iframe>
</div>

## API methods used in this notebook

```{eval-rst}
.. autoclass:: here_search_demo.widgets.app.OneBoxMap
   :members: show, run
   :no-index:

.. autoclass:: here_search_demo.widgets.input_text.SubmittableTextBox
   :members: feed, submit
   :no-index:

.. autoclass:: here_search_demo.widgets.route.RouteController
   :members: set_route_start, set_current_position, set_route_stop, set_route_width
   :no-index:
```
