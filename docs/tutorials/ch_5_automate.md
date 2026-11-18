---
hide-toc: true
---

# Automation

## Quick reference

This notebook focuses on scripted interactions with widgets and route automation.
Most-used elements:

1. `OneBoxMap()`
2. `SubmittableTextBox.feed(...)`
3. `SubmittableTextBox.submit()`
4. `RouteController.set_route_start/at/stop(...)`
5. `RouteController.set_route_width(...)`

For the complete reference, see the [API reference](../reference/api_reference.md).
For route architecture details, see [Route engine and widget controller architecture](../explanation/route_engine.md).

<div class="notebook-embed" style="--notebook-embed-height: 1000px;">
  <iframe src="../../../notebooks?path=ch_5_automate.ipynb" loading="lazy"></iframe>
</div>

## Methods used in this notebook

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
