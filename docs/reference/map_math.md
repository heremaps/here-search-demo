---
hide-toc: true
---

# Map math appendix

This page collects the implementation-level equations used by map rendering.

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

Bounding box (icon width $w$, height $h$, anchor $(a_x,a_y)$):

```math
B=(x-a_x,\ y-a_y,\ x-a_x+w,\ y-a_y+h)
```

AABB overlap test:

```math
\text{overlap}(A,B)\iff
A_{x\min}<B_{x\max}\land A_{x\max}>B_{x\min}\land
A_{y\min}<B_{y\max}\land A_{y\max}>B_{y\min}
```

In plain terms, we convert each label to a screen rectangle and place it only
if that rectangle does not overlap rectangles already placed. This avoids
labels drawing on top of each other.

## Fit-bounds zoom computation

Given current zoom $z$, current visible span, and target bounds span:

```math
z_{\lambda}=z+\log_2\!\left(\frac{\Delta\lambda_{\text{visible}}}{\Delta\lambda_{\text{target}}}\right)
```

```math
z_{\varphi}=z+\log_2\!\left(\frac{\Delta y_{\text{visible}}}{\Delta y_{\text{target}}}\right)
```

with Mercator latitude:

```math
y(\varphi)=\ln\!\tan\!\left(\frac{\pi}{4}+\frac{\varphi}{2}\right)
```

Final zoom:

```math
z_{\text{new}}=\left\lfloor\min(z_{\lambda},z_{\varphi})\right\rfloor,\quad
z_{\text{new}}\in[z_{\min},z_{\max}]
```

In plain terms, we compute how much we must zoom out so the target bounds fit
both horizontally and vertically, then choose the stricter one and clamp it to
allowed min/max zoom levels.

### Viewport padding before fitting

Before fitting, bounds are expanded by one eighth of their size on each side:

```math
h=\varphi_{\max}-\varphi_{\min},\quad
w=\lambda_{\max}-\lambda_{\min}
```

```math
[\varphi_{\min}',\varphi_{\max}']=
[\varphi_{\min}-h/8,\ \varphi_{\max}+h/8],\quad
[\lambda_{\min}',\lambda_{\max}']=
[\lambda_{\min}-w/8,\ \lambda_{\max}+w/8]
```

In plain terms, we add a 12.5% visual margin around the content so markers and
route overlays are not glued to the map edges after auto-fit.

## References

- [Web Mercator projection (Wikipedia)][web-mercator-wiki]
- [Slippy map tilenames / zoom scale law (OpenStreetMap Wiki)][osm-slippy]
- [Axis-aligned bounding box intersection (MDN)][mdn-aabb]

[web-mercator-wiki]: https://en.wikipedia.org/wiki/Web_Mercator_projection
[osm-slippy]: https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
[mdn-aabb]: https://developer.mozilla.org/en-US/docs/Games/Techniques/2D_collision_detection
