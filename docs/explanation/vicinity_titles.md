---
hide-toc: true
---

# Vicinity titles

## What is a vicinity title?

Every result displayed by the demo — both the **result buttons** in the sidebar
and the **map marker labels** — shows a short human-readable label that we call
the *vicinity title*.  It is derived from the raw HERE Geocoder / Autosuggest
response and may differ from the item's `title` field.

## Where the title field comes from

The HERE Search API returns a `title` string for every result item.  For
*place* results this is the POI or venue name (e.g. `"McDonald's"`).  For
*street / address / locality* results it is the full address label or the
place name at the matched level (e.g. `"Rue de Rivoli"`,
`"10th Arrondissement"`).

## How vicinity titles differ

The result buttons and map labels use a *disambiguated* label instead of the
raw `title`.  The disambiguation is computed by `_get_vicinity()` in
`src/here_search_demo/widgets/state.py`.

### Source material

Labels are built from the `address.label` string of each item.  That field
contains a comma-separated address hierarchy, e.g.

```
McDonald's, 1 Rue de Rivoli, 1st Arrondissement, Paris, France
```

Split on `", "` this becomes the *parts list*:

| index | value                  |
|-------|------------------------|
| 0     | `McDonald's`           |
| 1     | `1 Rue de Rivoli`      |
| 2     | `1st Arrondissement`   |
| 3     | `Paris`                |
| 4     | `France`               |

`parts[0]` (the place name) is always shown.  Extra parts are added only as
needed to make the label unique within the current result set.

### Multi-item disambiguation

When a result set contains several items that share the same `parts[0]` (e.g.
multiple `"McDonald's"` branches), the algorithm progressively adds address
parts *right-to-left* (state → city → street → …) until every label is unique:

1. **Multi-country sets** — if items come from different countries, the
   country (`parts[-1]`) is pre-appended for *all* items so that
   `"McDonald's, Germany"` is immediately shown alongside
   `"McDonald's, France"`.
2. **Single-country sets** — intermediate parts (`parts[-2]`, `parts[-3]`, …,
   `parts[1]`) are tried in that order; the country is added as a last resort.

Parts are always rendered in their original left-to-right address order
regardless of the order they were selected.

### Bracketed-title exception

When `item["title"]` itself already contains a parenthetical expression
(detected by the regex `\(.*?\)`), the title is **used verbatim** as the
display label.  The item does not participate in the disambiguation loop and
its address parts are never appended.

**Rationale:** parenthetical text in a title is part of the official venue
name or branding (e.g. `"Post Office (Main Branch)"`,
`"Starbucks (Airport Terminal)"`, `"The George (Pub)"`).  Appending address
parts would create redundant and confusing labels, and such titles are already
self-identifying within normal result sets.

Example:

| `item["title"]`          | vicinity title           | address suffix added? |
|--------------------------|--------------------------|----------------------|
| `"Starbucks"`            | `"Starbucks, Centrum"`   | yes (disambiguation) |
| `"Starbucks (Airport)"`  | `"Starbucks (Airport)"`  | **no** (exception)   |

### `_vicinity` field

After `_get_vicinity()` runs, each item dict gets a `_vicinity` key whose
value is the list of address parts that make up the display label.  For a
non-bracketed item with label `"McDonald's, Paris"` it would be
`["McDonald's", "Paris"]`.  For a bracketed item it is always the single-
element list `["<title>"]`.

`_vicinity` is:

* used by the **map marker labels** to split the label across two lines
  (name on the first line, vicinity qualifier on the second);
* copied into the **JSON output widget** so the computed label is visible
  alongside the raw API response for debugging.

## Query / category suggestion items

Items of type `chainQuery` or `categoryQuery` (returned by the Autosuggest
endpoint) are left untouched.  Their `title` field is used as-is and no
`_vicinity` key is set.
