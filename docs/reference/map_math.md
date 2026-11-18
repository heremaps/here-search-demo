---
hide-toc: true
---

# Map math appendix

This page collects the implementation-level equations used by map rendering.
A [code-snippet version of this page](map_code.md) shows the same logic as it
is actually implemented.

## Label collision placement

Each label is projected to pixel coordinates at zoom $z$, converted to an
axis-aligned bounding box, then checked against boxes already placed.

Web-Mercator pixel projection:

```math
S = 256\cdot 2^z,\quad
x = \frac{\lambda+180}{360}\,S
```

```math
y = \left(\frac{1}{2} - \frac{1}{4\pi}\ln\frac{1+\sin\varphi}{1-\sin\varphi}\right)S
```

The bounding box is that pixel position offset by the icon anchor, extended by
the icon width and height. Two labels collide when their boxes overlap on both
axes ([axis-aligned bounding box test][mdn-aabb]).

In plain terms, we convert each label to a screen rectangle and place it only
if that rectangle does not overlap rectangles already placed. This avoids
labels drawing on top of each other.

## Fit-bounds zoom computation

The [slippy-map zoom scale law][osm-slippy] halves the visible extent per
zoom-in step, so the zoom that makes a target extent fit the current visible
extent is:

```math
z_{\text{new}}=z+\log_2\!\left(\frac{\Delta_{\text{visible}}}{\Delta_{\text{target}}}\right)
```

applied on both axes, where the latitude axis uses the Mercator ordinate

```math
y(\varphi)=\ln\!\tan\!\left(\frac{\pi}{4}+\frac{\varphi}{2}\right)
```

because tile rows are spaced uniformly in Mercator space, not in degrees. The
stricter of the two axis results is taken, truncated to an integer, and clamped
to the allowed min/max zoom levels.

In plain terms, we compute how much we must zoom out so the target bounds fit
both horizontally and vertically, then choose the stricter one and clamp it to
allowed min/max zoom levels.

### Viewport padding before fitting

Before fitting, bounds are expanded by one eighth of their height and width on
each side.

In plain terms, we add a 12.5% visual margin around the content so markers and
route overlays are not glued to the map edges after auto-fit.

## References

- [Web Mercator projection (Wikipedia)][web-mercator-wiki]
- [Slippy map tilenames / zoom scale law (OpenStreetMap Wiki)][osm-slippy]
- [Axis-aligned bounding box intersection (MDN)][mdn-aabb]

[web-mercator-wiki]: https://en.wikipedia.org/wiki/Web_Mercator_projection
[osm-slippy]: https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
[mdn-aabb]: https://developer.mozilla.org/en-US/docs/Games/Techniques/2D_collision_detection
