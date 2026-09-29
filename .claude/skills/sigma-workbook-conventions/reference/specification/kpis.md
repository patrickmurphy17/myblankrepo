# KPIs

The `kpi-chart` element — single-value stat card.

```bash
jq '.components.schemas.KpiChart' /tmp/sigma-api.json
```

Typically a KPI points at a table as its source and computes one
aggregated value.

> ⚠️ The docs sometimes call this `kpi` — the API rejects with
> `Invalid kind: "kpi"`. Use `kpi-chart`.

## Shape

```json
{
  "id": "total-sales",
  "kind": "kpi-chart",
  "name": "Total Sales",
  "source": { "kind": "table", "elementId": "sales-table" },
  "columns": [
    {
      "id": "kpi-val",
      "formula": "[Metrics/Total Revenue]",
      "format": { "kind": "number", "formatString": "$,.0f" }
    }
  ],
  "value": { "columnId": "kpi-val" }
}
```

- `columns` — define at least one column (the value to display).
  More columns are allowed but only `value.columnId` is rendered as
  the headline.
- `value.columnId` — the column ID to show in the card.
  **Verified 2026-07-02 across all harvested KPIs (26 instances):
  the field is `columnId`, not `id`.** Sending `value.id` will be
  silently ignored or rejected depending on the server version.
- `format` on the column controls displayed format. See
  `formatting.md`.

## Totals vs latest-period trap (READ BEFORE ADDING A TIMELINE)

> **Observed by rendering on this org (2026-09-29).** A `kpi-chart` with
> `timeline: {columnId}` + `periodComparison: "month"` +
> `comparison: {display: "delta", colorGood, colorBad}` renders a sparkline
> and a "Sep vs Aug" delta - **but the headline value becomes the LATEST
> PERIOD's value, not the all-time total.** A tile titled "Total Revenue"
> showed $222M while the charts on the same page summed to $10.3B. The
> spec POSTed and compiled cleanly; only the rendered PNG exposed it.

```json
{
  "id": "ov-kpi-latest-month-revenue",
  "kind": "kpi-chart",
  "name": "Latest Month Revenue",
  "source": { "kind": "table", "elementId": "ov-src" },
  "columns": [
    { "id": "v", "formula": "Sum([ov-src/Revenue])", "format": { "kind": "number", "formatString": "$,.0f" } },
    { "id": "m", "formula": "DateTrunc(\"month\", [ov-src/Date])", "name": "Month" }
  ],
  "value": { "columnId": "v", "fontSize": 30 },
  "timeline": { "columnId": "m" },
  "periodComparison": "month",
  "comparison": { "display": "delta", "colorGood": "#198d00", "colorBad": "#d0021b" }
}
```

**Rules:**

- **"Total ..." tiles:** use ONE value column. No `timeline`, no
  `periodComparison`, no `comparison`, and never add a non-aggregated date
  column to `columns` (it can turn the tile into a latest-period value).
- Use `timeline` / `periodComparison` / `comparison` **only** for tiles
  explicitly labelled "latest month" (or similar), e.g. "Latest Month
  Revenue".
- **Reconcile after render:** the KPI headline should equal the sum of the
  chart that shows the same measure. Look at the PNG (`render-workbook.sh`).
- `value` accepts `fontSize` (30 stopped big-number clipping in the
  Webstaurant build).

**Local vs upstream disagree (both recorded):** upstream says
sparklines / period-comparison are UI-bound, and the spec-authorable delta
is `comparisonColumn: {columnId}` + `comparison: {display: "delta"}`
comparing two columns you compute (e.g. current vs prior value). The
org-observed behavior above (`timeline` + `periodComparison` accepted and
rendered, with the latest-period headline) is what actually happened on
2026-09-29; `comparisonColumn` was not tested here (unverified locally).
Older versions of this file claimed the date-dimension column alone
"enables" a sparkline/comparison automatically - treat that as stale and
unverified.

## Title styling (styled-name object form)

`name` is polymorphic — accepts a plain string OR a styled object:

```json
"name": {
  "text": "Total Revenue",
  "color": "#3A2E26",
  "fontSize": 32,
  "fontWeight": "bold"
}
```

Or hide the title bar entirely:

```json
"name": { "visibility": "hidden" }
```

Verified fields: `text`, `color` (hex), `fontWeight` (`"bold"`,
`"normal"`, likely `"600"` etc.), `fontSize` (pixel number),
`visibility` (`"hidden"` so far). See `examples/styled-card-dashboard.json`
(legacy-shape exemplar) for KPI tiles using the styled-name form with `fontSize: 32`.

## Element-level styling

KPI tiles accept the same top-level `style` object as other viz
elements:

```json
"style": {
  "borderRadius": "round",
  "borderColor":  "#E8DFD3",
  "borderWidth":  1
}
```

`backgroundColor` is also accepted but often omitted on KPI tiles so
the container behind shows through. See `containers.md` →
"Common style recipes" for the full recipe catalog.

## Element-level `layout` object (legacy; unverified in the current format)

Older exemplars put `"layout": { "anchor": "middle" }` on a KPI to anchor
the value in the tile (observed 2026-07-02 on `sales-mbr-sentinel`). The
2026-09-29 new-format build dropped it as unverified. Omit it unless you
confirm it against a live readback. See `layout.md` -> "Two flavors".

## Description must be an object

`description` on KPIs is **object-only**. A plain-string
`description` is rejected at POST with `Invalid object: string`.

Correct shapes:

```json
"description": { "text": "Current-month bookings from Opps table" }
```

```json
"description": { "visibility": "hidden" }
```

Setting `visibility: "hidden"` removes the description line from the
tile entirely (dropped as unverified in the 2026-09-29 new-format build -
omit `description` instead unless you need it). Verified 2026-07-02 across `sales-mbr-sentinel` KPIs
and `inventory-health` build (1 POST retry on string-form rejection).
Same rule applies to tables — see `tables.md` → "Styled name +
description + noDataText."

## Formula qualification

Every KPI sources another element, so the column's formula must use
either:

- `[Metrics/<Name>]` for data-model metrics (when sourcing a DM
  element via a sibling table)
- `[<SourceName>/<column>]` for warehouse-table or sibling-element
  references

A bare `[col]` is only valid for referencing another column defined
in this KPI's own `columns[]` array. This is the single most common
mistake — see `formulas.md`.

Run `scripts/validate-spec.py` before publishing to catch it.

## Value formula pitfall: can't reference sibling aggregation columns

A `value.columnId` formula that uses bare `[Sibling]` refs to other
columns in the same KPI **renders as `null`** when those siblings
themselves contain aggregation functions (`Sum`, `Avg`, `Count`,
`CountDistinct`, `Median`, `Percentile`, etc.).

**Why it fails:** Sigma evaluates the value formula per-row of the
source table first, then aggregates. Bare `[Sibling]` refs resolve
to the sibling's per-row value — but an aggregation column has no
per-row value, so the ref evaluates to `null` and the whole
expression collapses to `null`.

### Wrong — silently renders null

```json
"columns": [
  { "id": "kpi-lift",
    "formula": "([Promo AOV] - [Non-Promo AOV]) / [Non-Promo AOV]",
    "name": "Lift %" },
  { "id": "kpi-promo-aov",
    "formula": "Sum(If([Promo Flag]=\"Promo\",[Rev],0)) / CountDistinct(If([Promo Flag]=\"Promo\",[Order],Null))",
    "name": "Promo AOV" },
  { "id": "kpi-nonpromo-aov",
    "formula": "Sum(If([Promo Flag]=\"Non-Promo\",[Rev],0)) / CountDistinct(If([Promo Flag]=\"Non-Promo\",[Order],Null))",
    "name": "Non-Promo AOV" }
],
"value": { "columnId": "kpi-lift" }
```

Verified 2026-07-02 against `Marketing-and-Promotions-Performance`:
`Promo Lift vs Non-Promo AOV` KPI rendered `null` because
`kpi-lift`'s formula referenced two sibling aggregation columns
via bare refs.

### Right — self-contained value formula

Inline the aggregations directly in the value column's formula so
it evaluates as a single scalar over the source table:

```json
"columns": [
  { "id": "kpi-lift",
    "formula": "(Sum(If([Promo Flag]=\"Promo\",[Rev],0)) / CountDistinct(If([Promo Flag]=\"Promo\",[Order],Null))) / (Sum(If([Promo Flag]=\"Non-Promo\",[Rev],0)) / CountDistinct(If([Promo Flag]=\"Non-Promo\",[Order],Null))) - 1",
    "name": "Lift %",
    "format": { "kind": "number", "formatString": ".1%" } }
],
"value": { "columnId": "kpi-lift" }
```

Verbose but correct — each aggregation evaluates over the whole source
table, and the ratio computes over the resulting scalars.

### Alternatives when the formula gets unwieldy

- **Promote the ratio to a data-model metric.** Define `Promo Lift %`
  on the DM element and reference `[Metrics/Promo Lift %]` in the
  KPI. Keeps the KPI spec small and reuses the definition across
  workbooks.
- **Compute upstream in a derived table.** Create a sibling table
  element with one row per (dimension) and pre-aggregated Promo/
  Non-Promo columns, then source the KPI from that. The KPI can
  reference its columns without hitting the aggregation-nesting
  problem because the source is already at the right grain.

`scripts/validate-spec.py`'s `kpi-value-references-aggregation`
check (added 2026-07-02) warns pre-POST when a KPI value formula
uses bare refs to sibling columns whose formulas contain
aggregation functions. Warn-level, not fail — a false positive is
possible when the sibling's aggregation happens to evaluate to a
single valid scalar (rare); inspect flagged cases.

## Passthrough columns

The KPI's `columns` array should include the source table's
passthrough columns alongside the headline `value` and date
dimension. This enables drill-down from the KPI to detail.

KPIs are intentionally **excluded from `validate-spec.py`'s
`passthrough-coverage` check** because their col count varies a lot
based on whether the user wants drill-down support. Use judgment.

## Known limitations

- **Period comparison changes the headline value.** See "Totals vs
  latest-period trap" above: `timeline` + `periodComparison` + `comparison`
  are accepted and render a sparkline + delta, but the headline becomes the
  latest period. Do not use them on "Total ..." tiles. Upstream's
  spec-authorable alternative is `comparisonColumn` + `comparison`
  (unverified here). To force a fixed comparison, you can also stack two
  `kpi-chart` elements side-by-side via layout XML.
- **No `target` / `goal` field.** To show a value vs. a target,
  build a chart with two columns (value + target) instead.

## Tile sizing

A KPI with a sparkline needs ~8-10 grid rows of vertical space. A
3-row KPI with timeline comparison renders the sparkline too small
to read. For a row of N tiles that does not divide 24, use uneven spans
(5 tiles -> 5,5,5,5,4) so the row fills all 24 columns. See `layout.md` for grid placement.
