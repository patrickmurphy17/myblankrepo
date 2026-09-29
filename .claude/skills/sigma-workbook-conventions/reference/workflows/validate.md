# Validation

Validation runs in three phases:

1. **Pre-submit** — `scripts/validate-spec.py` catches what's visible
   in the spec text (19 checks).
2. **Post-create** — `scripts/api/verify-workbook.sh` catches what
   Sigma's compiler discovers but the spec parser tolerates.
3. **Visual** — `scripts/api/render-workbook.sh <wb-id> [out-dir]`, then
   `Read` the PNGs (or open the workbook URL) and confirm it renders correctly.

Both API phases matter. Silent compilation failures are the largest
hidden failure mode.

Load this before any POST or PUT.

## 1. Pre-submit — `scripts/validate-spec.py`

```bash
scripts/validate-spec.py workbooks/<name>/spec.json
```

19 checks (as of 2026-09-29; 13 original + 6 added for the 2026-09 API format).
The file is auto-detected as `contents`-wrapped (current), `document`-wrapped
(legacy `/spec` endpoint), or old flat-legacy (warns "convert first"); see
`scripts/spec_shape.py`.

| # | Check | What it catches |
|---|---|---|
| 1 | `no-per-page-layout` | A per-page `layout` field (silently discarded by Sigma). `layout` is one XML string in `contents`, a sibling of `pages`. |
| 2 | `elements-placed-in-layout` | Elements not placed in the layout XML (rejected by the current API), or layout `elementId`s that match no element (silent-drop trap). |
| 3 | `containers-have-children` | `kind: container` elements whose `<Container>` has no children, or that are placed as `<Element>` leaves. |
| 4 | `column-format-shape` | Column `format` not shaped `{kind, formatString}` (the UI-emitted `{type, format}` shape is rejected with a misleading "Missing 'kind' field"). |
| 5 | `control-id-unique` | Duplicate `controlId` across control elements. |
| 6 | `passthrough-coverage` | Chart elements with ≤2 cols sourced from tables with ≥5 cols (the passthrough-collapse signature). FAIL on charts; WARN on thin-but-not-collapsed. KPIs excluded. See `reference/conventions.md` → "Passthrough mandate." |
| 7 | `controlid-collision` | Controls whose `controlId` matches a column `name` or `id` on the filtered element. See `reference/conventions.md` → "Control/column ID collision." |
| 8 | `bare-ref-resolution` | Bare `[column_name]` references (no `/`) that don't match any sibling column or controlId. **WARN-level** — Sigma auto-infers some column names (e.g. `DateTrunc("week", [Date])` → "Week of Date") that this regex-based check can't predict, so flags require inspection. Added 2026-05-21 — ported from upstream `validate-spec.sh`. See `reference/specification/formulas.md` → "The #1 formula mistake." |
| 9 | `control-filter-column-exists` | Control `filters[].columnId` values that don't exist on the target element. Catches typos that pass POST but silently break every downstream query on the page. Added 2026-07-02 after a fresh-agent build test surfaced this class of bug. Includes "did you mean" suggestions for near-match column IDs. |
| 10 | `kpi-value-references-aggregation` | KPI value formulas that bare-ref sibling columns whose formulas contain aggregation functions (`Sum`, `Avg`, `Count*`, etc.). The bare ref evaluates per-row, an aggregation has no per-row value, and the KPI renders `null`. WARN-level — regex-based, so occasional false positives are possible. Fix: inline the aggregation into the value formula, or promote to a data-model metric. Added 2026-07-02 after `Marketing-and-Promotions-Performance`'s Promo Lift KPI rendered null. See `reference/specification/kpis.md` → "Value formula pitfall." |
| 11 | `summary-calc-collision` | Column IDs that appear in both `summary[]` and a `groupings[].calculations[]` list on the same table. POST rejects with `Duplicate column or folder reference`. Fix: split into two column definitions with distinct IDs. Added 2026-07-02 after `exec-scorecard` v1 hit this mid-build. See `reference/specification/tables.md` → "summary — summary-bar pattern." |
| 12 | `description-object-on-kpi-and-table` | Plain-string `description` on `kpi-chart`, `table`, `pivot-table`, or `input-table` elements. POST rejects with `Invalid object: string`. Fix: wrap as `{"text": "..."}` or `{"visibility": "hidden"}`. Chart elements accept the string form. Added 2026-07-02 after `inventory-health` build hit this. See `reference/specification/kpis.md` → "Description must be an object." |
| 13 | `pivot-missing-rows-and-columns` | Pivot-tables that have `values` but neither `rowsBy` nor `columnsBy` — the pivot compiles cleanly (passes POST + verify) but renders as a single grand-total row. Fix: add at least one `rowsBy` or `columnsBy` entry (`[{"id": "<dim-col-id>"}]`). Added 2026-07-02 after `Product-and-Basket-Performance` shipped two pivots that rendered as grand-total-only in the UI. See `reference/specification/tables.md` → "Shape" (pivot section). |
| 14 | `request-shape` | Wrapped shape (`contents`/`document`) that still has `pages[].elements`, or `themeOverrides`/`themeName` = FAIL. A bare legacy top-level file (old flat shape) = WARN "convert first" (`scripts/convert-legacy-spec.py`). Added 2026-09-29. |
| 15 | `legacy-layout-tags` | `<GridContainer>` / `<LayoutElement>` in layout XML = FAIL. Use `<Container>` / `<Element>`. Added 2026-09-29. |
| 16 | `element-ids-unique` | Duplicate element ids anywhere in the workbook (ids are workbook-wide, not per page) = FAIL. Prefix ids per page. Added 2026-09-29. |
| 17 | `text-vertical-align` | `text.verticalAlign` not in `top`, `center`, or `bottom` (e.g. `middle`/`start`/`end`) = FAIL; otherwise surfaces as the cryptic `Invalid kind: "text"`. Added 2026-09-29. |
| 18 | `channel-binding-shape` | `{id}` pointers on donut/pie (`value`, `color`, `holeValue`) and map (`latitude`, `longitude`, `size`, `region`, `geography`, `label`, `tooltip`) channels = FAIL; use `{columnId}`. Added 2026-09-29. |
| 19 | `kpi-latest-period-trap` | WARN: a `kpi-chart` titled total / overall / all-time that has `timeline` / `periodComparison` (shows the latest period only). See `reference/specification/kpis.md` -> "Totals vs latest-period trap." Added 2026-09-29. |

> The pre-2026-09 version of this table listed `name-required-on-passthrough`,
> `id-uniqueness`, `schema-keys`, `layout-element-ids`, and `metrics-existence`.
> Those names do not appear in the current `validate-spec.py` `CHECKS` list
> (the placement check is now #2, id uniqueness #16); treat the rules they
> described (explicit `name` on passthrough, `[Metrics/...]` must exist in
> recon) as manual-pass items - see `reference/conventions.md`.

Fix everything reported before continuing. If exit 0, proceed to the
manual pass.

The validator is part of `publish-workbook.sh post` — POSTing via the
wrapper runs validation first.

## 2. Manual formula pass (do not skip)

For each column's `formula`:

1. **List every bracketed reference** in the formula. E.g.,
   `Sum([Master/Sales]) - [Cost]` → refs are `Master/Sales` and `Cost`.
2. **For each reference, it must resolve to exactly one of:**
   - A **sibling** — the portion inside the brackets (no `/`) exactly
     matches a `name` in THIS element's `columns[]` array.
   - A **data-model metric** — `[Metrics/<X>]` where `<X>` is in the
     source element's metric catalog (from `mcp-describe`).
   - A **qualified ref** — contains `/`, and the prefix matches one of:
     - The last segment of the `path` array (if source is
       `warehouse-table`)
     - Another element's `name` (if source is `table` referencing
       that element)
     - A join leg's `name`, or the join's top-level `name` for
       `primarySource` columns
3. **If a reference doesn't match any of these, the formula is wrong.**
   Most common fix: add the source prefix — see
   `reference/specification/formulas.md` → "Column reference rules."

## 3. Final shape checks

- A column's `formula` references a name matching its own `name`
  field → circular reference (silent fail at render).
- A formula references a column name that doesn't exist on the source
  → re-confirm column names via `mcp-describe`.
- Donut chart requires `value` + `color` (or `holeValue` if used).
- Layout XML: no `<Element>` with children - use `<Container>` for
  nesting (children are silently dropped otherwise). Never the legacy
  `<GridContainer>` / `<LayoutElement>` tags.
- Element ids unique workbook-wide; every element placed in layout.
- KPI "Total ..." tiles have no `timeline` / `periodComparison` / `comparison`.
- Donut/pie/map channel pointers are `{columnId}`; `text.verticalAlign`
  is `top|center|bottom`.
- Controls bind via `filters[].columnId` matching a column `id` on
  the target element (NOT `name`).

## 4. Post-create — `scripts/api/verify-workbook.sh`

**Do not skip.** A successful POST is necessary but not sufficient.
Sigma accepts specs whose column formulas don't actually resolve,
then surfaces the failures *at query time* by embedding the error as
a string literal in the compiled SQL:

```sql
select V_44 "Total Revenue" from (select 'Unknown column "[ORDER_TOTAL]"' V_44) Q1
select V_11 "Quarter" from (select distinct 'Circular column reference to [Quarter]' V_11 ...) Q1
```

Affected elements render empty in the UI. Catching this from the
spec text alone is impossible — only Sigma's compiler knows.

After every CREATE and after every PUT that touches columns or
formulas, run:

```bash
scripts/api/verify-workbook.sh <wb-id>
```

It hits `GET /v2/workbooks/<id>/elements/<eid>/query` for each
element and reports any whose SQL contains `Unknown column "..."`
or `Circular column reference to [...]` markers.

Non-zero exit means at least one element's formulas don't resolve.
Fix the spec, PUT, re-verify.

Most common causes of post-create failure:

- **Bare warehouse refs.** `Sum([ORDER_TOTAL])` instead of
  `Sum([ORDERS/ORDER_TOTAL])`. The single biggest trap. The
  `bare-ref-resolution` validator check catches most of these
  pre-POST, but not all.
- **Friendly-name mismatch.** The columns endpoint returns raw
  warehouse names (`V userId`, `UNIT PRICE`); formulas need Sigma's
  normalized friendly names (`V User Id`, `Unit Price`). Sigma is
  permissive at POST and normalizes casing for many simple cases,
  but won't rescue all of them. See `reference/workflows/discover.md`
  → "Column names — friendly vs raw warehouse."
- **Circular reference.** A column named `Quarter` with formula
  `[Quarter]` — easy when copying warehouse column names verbatim
  into a sibling-reference position. Rename one side.

## 5. Render & LOOK (required)

After verify-workbook returns clean, render and inspect:

```bash
scripts/api/render-workbook.sh <wb-id> [out-dir]   # one PNG per page
```

(Wraps upstream `scripts/wb-rep.rb pull` + `render`; needs `ruby` and the
vendor mirror from `scripts/refresh-vendor.sh`.) Then `Read` each PNG.
Opening the workbook URL in the UI is the fallback. The API and the
compile check do not validate:

- KPI headline correctness (2026-09-29: a "Total Revenue" tile showed the
  latest month, $222M, vs $10.3B of chart totals - compiled fine)
- Layout fill (5 KPI tiles x 4 cols filled only 20/24 columns; use spans
  5,5,5,5,4)
- Chart legibility (a 20-slice donut; use a top-10 horizontal bar when
  categories > ~7)
- Title/legend overlap (seen on a map)
- Cross-element column resolution at render (verify catches most,
  not all)
- Whether filter wiring produces the expected user experience
- Whether `[Metrics/<X>]` references resolve at render

If anything looks wrong, the issue is downstream of the API contract.
Iterate: edit the spec, re-pull and check `documentVersion`, PUT,
re-verify, re-render.

## Decoding cryptic validation errors

Server-side validation errors point at a JSON path but don't say
what shape was expected. Use the path as the root-cause hint, then
check the spec reference file for that feature to compare shapes.

| Error pattern | Most likely cause | Where to look |
|---|---|---|
| Giant union error where every path starts `0.document.` | You sent the pre-2026-09 shape (`pages[].elements`, top-level `layout`, `themeOverrides`) to the (legacy) `/v2/workbooks/spec` endpoint. The "0." is the first union branch tried; every branch fails on the same structural problem. | Convert with `scripts/convert-legacy-spec.py`, or author `{name, folderId, contents}` per `reference/specification/schema.md`. Parse by path prefix, not by the first message. |
| `document.elements[i]: Invalid kind: "text"` (or any `Invalid kind: "<x>"` on an element) | Generic error - the fault is an enum/field INSIDE that element, not the kind. For `text`, almost always `verticalAlign: "middle"` (or `start`/`end`); valid is `top`, `center`, or `bottom`. | `reference/specification/text.md`; suspect enums inside the named element. |
| 400 on a donut/pie/map channel (`value`, `color`, `holeValue`, `latitude`, `region`, ...) | `{id: ...}` pointer; channels use `{columnId: ...}`. | `reference/specification/charts.md`, `maps.md`; validator check `channel-binding-shape`. |
| `backgroundImage.source: Invalid value: undefined` | Container `backgroundImage` sent flat `{url}`; needs `{source:{kind:"url",url}, style}`. | `reference/specification/containers.md`. |
| `Invalid kind: pages[0].elements[N], got "..."` (legacy-shape paths) | Almost always the element's **inner shape** is wrong for the `controlType`/`kind` it claims, **not** that the kind is unsupported. Sigma's parser picks a schema by `kind` + `controlType` and reports the parent path when the inner match fails. | `reference/specification/controls.md` (slider is the most common trap), or the relevant per-element file (`charts.md`, `kpis.md`, `tables.md`). |
| `Invalid value: pages[0].elements[N].filters[M], got object` | The field is typed as an array of a specific shape and you sent something that doesn't match. | A working reference workbook (`GET` an existing workbook) for that exact field. |
| `Invalid kind: pages[0].elements[N].columns[M]` | Usually missing `id`, `name`, or `formula`, or `format.kind` mismatched. | `reference/specification/formatting.md`. |
| `Cannot resolve columns on table '<chart-id>': dependency not found: formula reference '<old-name>/<col>'` | Renamed source-of-truth table broke sibling formulas. | `reference/conventions.md` → "Rename-cascade corollary." |
| `Column has a recursive formula` | A column references itself via `name` collision, OR a chart formula re-aggregates an already-aggregated metric. | `reference/conventions.md` → "Summary-bar pattern" for the aggregate-then-categorize case. |
| **Silent bad data** — no error, but the value/element is missing or `null` on readback | (a) A boolean-operator formula written as a function call (`Not(...)` instead of `Not ...`) — parses successfully but evaluates `null` per row; (b) layout XML naming an `elementId` that doesn't exist on the page (typo, deleted element, case mismatch); (c) a control field that doesn't round-trip (e.g., `number-range` `values`). | `reference/specification/formulas.md` for (a), `reference/specification/layout.md` for (b), `reference/specification/controls.md` for (c). |
| `service_error` / 500 on GET-spec | Workbook contains a UI feature the serializer can't represent (confirmed: pivot cell heatmaps; suspected: maps, complex color-by). | `reference/scope-and-edge-cases.md` → "GET-spec can 500 when UI features aren't representable." |

**General strategy:** the error path names the offending field; the
spec reference file for that feature shows the shape. If after
checking both you still can't see the mismatch, fetch a known-good
reference workbook via `scripts/api/publish-workbook.sh get-spec
<wb-id>` (`GET ?includeContents=true`) and diff your shape against it.
