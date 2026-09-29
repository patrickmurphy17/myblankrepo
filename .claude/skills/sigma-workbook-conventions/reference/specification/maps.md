# Map elements (geography-map, point-map, region-map)

Three map visualizations. They share the standard element envelope —
`source`, `columns` (each `{ id, formula }`), and the same `color`
channel as charts (`by: single | category | scale`) — and differ only
in how the geography is bound.

Pull the exact shape (`mapStyle`, `legend`, `tooltip`, and any newer
sub-objects) from the OpenAPI:

```bash
jq --arg k region-map 'first(.. | objects | select((.allOf? and any(.allOf[]?; .properties?.kind?.enum==[$k])) or .properties?.kind?.enum==[$k]))' /tmp/sigma-api.json
# swap k for geography-map / point-map
```

## The binding per kind

| Kind | Geography field | Notes |
|---|---|---|
| `geography-map` | `geography: { columnId }` | Single GeoJSON-geometry column |
| `point-map` | `latitude: { columnId }` + `longitude: { columnId }` | Optional `size: { columnId }` → bubble map |
| `region-map` | `region: { columnId, regionType }` | See `regionType` enum below |

### `regionType` enum

For `region-map`, the column's values must match the region system:

- `country`
- `us-state`
- `us-county`
- `us-zipcode`
- `us-cbsa`
- `us-postal-place`
- `ca-province`

## Shape gotcha

The binding fields — `geography`, `latitude`, `longitude`, `size`,
`region` — are **single `{ columnId }` objects**. But `label` and `tooltip`
are **arrays** of `{ columnId }`. `{ id }` on any of these channels is a
400 (use `columnId`). Getting this wrong is a common trip.

```json
"region": { "columnId": "col-state", "regionType": "us-state" },    // single object
"label":  [ { "columnId": "col-revenue" } ],                          // array
"tooltip":[ { "columnId": "col-revenue" }, { "columnId": "col-margin" } ]   // array
```

## Verified examples

### region-map (verified 2026-07-02)

```json
{
  "id": "map-sales-by-state",
  "kind": "region-map",
  "source": {
    "kind": "table",
    "elementId": "tbl-transactions"
  },
  "columns": [
    { "id": "col-state",   "formula": "[Transactions/Store State]" },
    { "id": "col-margin",  "formula": "[Metrics/Total Profit Margin]" },
    { "id": "col-revenue", "formula": "[Metrics/Total Revenue]" }
  ],
  "region": { "columnId": "col-state", "regionType": "us-state" },
  "color":  { "by": "scale", "column": "col-margin" },
  "label":  [ { "columnId": "col-revenue" } ]
}
```

### point-map (verified 2026-07-02)

```json
{
  "id": "map-store-locations",
  "kind": "point-map",
  "source": {
    "kind": "table",
    "elementId": "tbl-transactions"
  },
  "columns": [
    { "id": "col-lat",     "formula": "[Transactions/Latitude]" },
    { "id": "col-lon",     "formula": "[Transactions/Longitude]" },
    { "id": "col-profit",  "formula": "[Metrics/Total Profit]" },
    { "id": "col-margin",  "formula": "[Metrics/Total Profit Margin]" }
  ],
  "latitude":  { "columnId": "col-lat" },
  "longitude": { "columnId": "col-lon" },
  "size":      { "columnId": "col-profit" },
  "color":     { "by": "scale", "column": "col-margin" }
}
```

### geography-map

Not observed in harvested reference workbooks yet — the OpenAPI shape
above is the current source of truth. Expect the same envelope
(`source`, `columns`, `color`, `label`, `tooltip`) plus:

```json
"geography": { "columnId": "col-geojson" }
```

## Common pitfalls

- **`{id}` pointers.** Map channel pointers use `{columnId}`; `{id}` is a
  400. (Older examples in this repo used `{id}`.)
- **Title / legend overlap.** A 2026-09-29 render showed the map title
  overlapping the legend; check the rendered PNG and shorten the title or
  hide/move the legend.
- **Wrong shape on binding fields.** Writing `region: [{columnId, regionType}]`
  as an array will fail — it's a single object.
- **regionType mismatch.** If your column contains ZIP codes but you set
  `regionType: "us-state"`, the map will render empty (no error).
- **Passthrough columns.** Just like KPIs, include the source table's
  passthrough columns in the map's `columns[]` to support drill-through.
  See `reference/conventions.md` → "Passthrough mandate."

## Cross-references

- Full element envelope, `source` shape, `columns` semantics —
  [`../specification/tables.md`](tables.md) and
  [`../specification/sources.md`](sources.md).
- `color` channel shape (used identically here) — [`charts.md`](charts.md).
- Layout placement (`<Element>`) — [`layout.md`](layout.md).
