---
hide-toc: true
---

# Route math appendix

This page collects the implementation-level equations used by route-aware
search logic. A [code-snippet version of this page](route_code.md) shows the
same logic as it is actually implemented.

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

For corridor mode, the route centerline is buffered by the requested width in
metres in a local tangent-plane projection centred on the route centroid, then
transformed back to WGS84 for map/search use.

In plain terms, we temporarily switch to a metre-based projection so a "100 m
width" really means 100 metres on the ground, build the corridor there, then
convert it back to latitude/longitude.

## `min from pos` future position

Given a number of minutes entered by the user, the app converts it to seconds
and adds it to the elapsed trip time at the anchor (`pos on route`), then maps
that new elapsed time back to a location on the route.

The elapsed time at the anchor is the sum of the durations of all route spans
before the anchor's span, plus the fraction of the anchor's own span already
travelled — measured by waypoint index within that span.

To turn the target elapsed time back into a position, the app finds the span
that contains it, converts the leftover time into a proportional distance along
that span, and walks the span's waypoints accumulating great-circle
([haversine][haversine-wiki]) segment lengths until that distance is reached.
The final position is interpolated linearly inside the segment that straddles
it, and clamped to the last waypoint when the target lies beyond the end of the
route.

## Detour reranking

Each result gets an *excursion distance*: the distance `at → result` plus
`result → stop`, minus the direct `at → stop` distance. When a maximum
excursion is configured, results above that threshold are dropped.

The remaining results are sorted by ascending travel time — time to reach the
result when `all_along` is off, and time to reach it plus the onward time to
the stop when `all_along` is on.

Durations and excursions shown in result titles are integer-truncated to whole
minutes and whole kilometres for readability, and the ranking key itself is
expressed in minutes.

In plain terms, each place gets a detour cost compared with driving directly to
the destination. We can drop places with too much detour, then rank the rest by
the fastest relevant travel time (to the place, or to-place-plus-onward).

## Route-stratified corridor search

This only applies to `ranking=excursionDistance` (**all along**) searches —
a default-relevance corridor search always uses a single whole-route call,
since only excursion-distance ranking is prone to bunching every result near
one end of the route.

A single corridor call is split into $n = \min(\text{limit}, 20)$
equal-distance slices whenever the *remaining* route — from the search
position to the destination, not the full route — is long enough relative to
the number of requested results:

```math
\frac{D_{\text{remaining}}}{\text{limit}} > 1000\ \text{m}
```

Each slice boundary is found by walking the cumulative great-circle
([haversine][haversine-wiki]) distance along the remaining route and cutting
it into $n$ equal-length spans; adjacent slices share their boundary
waypoint so the sub-polylines stay geometrically contiguous.

Each slice is searched independently, anchored at its own first waypoint, and
over-fetches $\lceil \text{limit} / n \rceil + 2$ candidates (floor 4, cap
100) so redistribution rarely needs a second network round-trip.

Results are then merged tier by tier: every slice's best not-yet-picked
candidate is taken before any slice's second-best, in route order, until
*limit* is reached or every slice is exhausted. A slice with no candidates
therefore loses its slot to whichever other slice has the next-best backup
candidate, rather than always to the same neighbor. Duplicate ids (adjacent
slices can share a boundary waypoint) are skipped in place, pulling that
slice's next buffered candidate instead of dropping the slot.

In plain terms: instead of one search over the whole remaining trip — which
can bunch every result near one end — the app searches several shorter
stretches in parallel and spreads the requested result count across them,
giving an empty stretch's leftover slots to whichever other stretch has more
to offer.

## References

- [Douglas-Peucker / Ramer-Douglas-Peucker algorithm (Wikipedia)][rdp-wiki]
- [Great-circle distance / Haversine formula (Wikipedia)][haversine-wiki]
- [HERE Routing API v8 docs][here-routing-v8]
- [Flexible Polyline specification][flexpolyline-spec]

[rdp-wiki]: https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm
[haversine-wiki]: https://en.wikipedia.org/wiki/Haversine_formula
[here-routing-v8]: https://www.here.com/docs/bundle/routing-api-v8-api-reference/page/index.html
[flexpolyline-spec]: https://github.com/heremaps/flexible-polyline
