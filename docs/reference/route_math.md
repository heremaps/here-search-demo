---
hide-toc: true
---

# Route math appendix

This page collects the implementation-level equations used by route-aware
search logic.

## Polyline simplification for `route=<polyline>;w=<width>`

When the route polyline is too dense, the app simplifies it before sending it
to Search. It uses the [Ramer-Douglas-Peucker algorithm][rdp-wiki] with a
binary search on tolerance $\varepsilon$ to keep at most $M$ points:

```math
\varepsilon_{n+1}=
\begin{cases}
\frac{\varepsilon_n+\varepsilon_{\text{high}}}{2}, & \text{if } |S(\varepsilon_n)| > M\\
\frac{\varepsilon_{\text{low}}+\varepsilon_n}{2}, & \text{if } |S(\varepsilon_n)| \le M
\end{cases}
```

where $S(\varepsilon)$ is the simplified polyline and $|S(\varepsilon)|$ its
point count.

In plain terms, we keep adjusting a "detail" threshold until the route has at
most the allowed number of points. This keeps the route shape meaningful while
making the payload small enough for Search.

## Corridor geometry from route width

For corridor mode, the route centerline is buffered by width $w$ metres in a
local projected CRS (UTM), then transformed back to WGS84 for map/search use.

In plain terms, we temporarily switch to a metre-based map projection so a
"100 m width" really means 100 metres on the ground, build the corridor there,
then convert it back to latitude/longitude.

## `min from pos` future position

Given $N$ minutes entered by the user:

```math
t_{\text{target}} = t_{\text{origin}} + 60 \cdot N
```

```math
\text{search\_at} = P\!\left(t_{\text{target}}\right)
```

where $t_{\text{origin}}$ is elapsed seconds at the anchor (`pos on route`)
and $P(t)$ is the interpolated route position at elapsed time $t$.

In plain terms, we first compute the trip time at the anchor by summing full
durations of earlier spans plus a proportional fraction of the current span.
Then we add the requested minutes and map that new elapsed time back to a
location on the route.

Span-based interpolation (matching implementation):

```math
t_{\text{origin}}=
\sum_{k < s_o} d_k
\;+\;
d_{s_o}\cdot
\frac{i_o-o_{s_o-1}}{o_{s_o}-o_{s_o-1}}
```

```math
\tau = t_{\text{target}}-\sum_{k < s_t} d_k,\quad
\alpha=\frac{\tau}{d_{s_t}},\quad
\ell=\alpha\cdot L_{s_t}
```

```math
P(t_{\text{target}})
=
\operatorname{interp\_along\_polyline}\!\left(
[w_{o_{s_t-1}},\dots,w_{o_{s_t}}],
\ell
\right)
```

Here, $\operatorname{interp\_along\_polyline}(Q,\ell)$ returns the point at arc-length
$\ell$ along the piecewise-linear polyline $Q$, clamped to the first/last point when
$\ell$ is outside the polyline length.

where $d_s$ is span duration, $L_s$ is span length, $o_s$ is span end
offset (waypoint index), $i_o$ is the closest waypoint index to the anchor,
and $w_i$ are decoded route waypoints.

## Detour reranking

For each result $i$:

```math
\text{exc}_i = d_{to,i}+d_{from,i}-d_{base}
```

where $d_{to,i}$ is distance `at → result`, $d_{from,i}$ is
`result → stop`, and $d_{base}$ is direct `at → stop`.

Filtering rule (if max excursion is configured):

```math
\text{keep } i \iff \text{exc}_i \le E_{\max}
```

Sort key:

```math
k_i=
\begin{cases}
t_{to,i}, & \text{all\_along = off}\\
t_{to,i}+t_{from,i}, & \text{all\_along = on}
\end{cases}
```

Results are sorted by ascending $k_i$.

Displayed title values are integer-truncated for readability:

```math
\text{dur\_to\_min}=\left\lfloor\frac{t_{to}}{60}\right\rfloor,\quad
\text{dur\_from\_min}=\left\lfloor\frac{t_{from}}{60}\right\rfloor,\quad
\text{exc\_km}=\left\lfloor\frac{\text{exc}}{1000}\right\rfloor
```

and when `all_along = on`, the ranking key uses truncated total minutes:

```math
k_i=\left\lfloor\frac{t_{to,i}+t_{from,i}}{60}\right\rfloor
```

In plain terms, each place gets a detour cost compared with driving directly to
the destination. We can drop places with too much detour, then rank the rest by
the fastest relevant travel time (to the place, or to-place-plus-onward).

## References

- [Douglas-Peucker / Ramer-Douglas-Peucker algorithm (Wikipedia)][rdp-wiki]
- [Great-circle distance / Haversine formula (Wikipedia)][haversine-wiki]
- [HERE Routing API v8 docs][here-routing-v8]
- [Flexible Polyline specification][flexpolyline-spec]

[rdp-wiki]: https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm
[haversine-wiki]: https://en.wikipedia.org/wiki/Haversine_formula
[here-routing-v8]: https://www.here.com/docs/bundle/routing-api-v8-api-reference/page/index.html
[flexpolyline-spec]: https://github.com/heremaps/flexible-polyline
