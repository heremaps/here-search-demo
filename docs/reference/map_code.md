---
hide-toc: true
---

# Map logic (code)

Code-snippet counterpart of the [map math appendix](map_math.md). Same
sections, same order — the equations are replaced by the implementation they
describe. Snippets are pulled from the source at build time, so they cannot
drift.

## Label collision placement

Web-Mercator pixel projection and the icon-anchored bounding box:

```{literalinclude} ../../src/here_search_demo/widgets/output_helpers.py
:pyobject: label_pixel_bbox
:language: python
```

Axis-aligned overlap test between two placed labels:

```{literalinclude} ../../src/here_search_demo/widgets/output_helpers.py
:pyobject: pixel_bboxes_overlap
:language: python
```

## Fit-bounds zoom computation

The Mercator ordinate used for the latitude axis:

```{literalinclude} ../../src/here_search_demo/widgets/input_map.py
:pyobject: PositionMap._mercator_y
:language: python
```

The zoom delta itself, from `PositionMap.fit_bounds` — one `log2` ratio per
axis, the stricter axis wins, then clamped:

```python
lng_visible = east - west
lng_target = b_east - b_west

lat_visible_m = PositionMap._mercator_y(north) - PositionMap._mercator_y(south)
lat_target_m = PositionMap._mercator_y(b_north) - PositionMap._mercator_y(b_south)

zoom_for_lng = current_zoom + math.log2(lng_visible / lng_target) if lng_target > 0 else current_zoom
zoom_for_lat = current_zoom + math.log2(lat_visible_m / lat_target_m) if lat_target_m > 0 else current_zoom

new_zoom = max(1, min(self.maximum_zoom_level, int(min(zoom_for_lng, zoom_for_lat))))
```

When the frontend reports an implausibly small viewport, a
viewport-independent fallback is used instead:

```{literalinclude} ../../src/here_search_demo/widgets/input_map.py
:pyobject: PositionMap._zoom_for_target_bounds
:language: python
```

### Viewport padding before fitting

```python
height = north - south
width = east - west
bounds = ((south - height / 8, west - width / 8), (north + height / 8, east + width / 8))
```
