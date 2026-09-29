# `data-model-sourced-webstaurant-command-center.json` — design intent

**Current-format (contents-wrapped, flat elements) 3-page multi-page exemplar.** Built and verified
live on 2026-09-29: POST/PUT accepted, `verify-workbook.sh` — all 53 elements compile, pages rendered
with `render-workbook.sh` and inspected. **First exemplar to load for any modern multi-page build.**
(All other exemplars in this folder are legacy-shape pattern references — convert with
`scripts/convert-legacy-spec.py` before publishing.)

Source: `Model-Webstaurant Sales` (single fact element `Webstaurant Sales`, 36 usable columns incl.
`Revenue`/`COGS`/`Profit`, `web_*` product hierarchy, store lat/long; no DM metrics → every measure is a
column aggregate). Prompt of record: "Sales command center — multi-page exec workbook for a Webstaurant
customer demo, branded from webstaurantstore.com."

## Placeholders to replace before POST
- `folderId` — destination folder UUID.
- `elements[] | select(.source.kind == "data-model")` → `dataModelId`, `elementId`.
- Formula prefixes `[Webstaurant Sales/...]` — the DM element's display name (source-table formulas);
  `[Sales Detail/...]`, `[Product Sales Data/...]`, `[Store Sales Data/...]` — the per-page source table
  names (plain-string names; formulas reference these).

## Patterns demonstrated
- **Per-page source table + visuals sourcing it** (`tbl-p1/p2/p3`, full-width "source data" table at the
  bottom of each page); controls filter the source table so every visual inherits the filter.
- **Element ids prefixed per page** (`kpi-p1-*`, `chart-p2-*`, `ctrl-p3-*`) — ids must be unique workbook-wide.
- **KPI totals, not latest-period**: one value column, `value.fontSize: 30`, no timeline/comparison
  (see `kpis.md` → totals-vs-latest-period trap). 5-tile row uses uneven spans 5/5/5/5/4.
- **Charts**: horizontal categorical bars with `top-n` filters; donut with distinct `value`/`holeValue`
  columns using `{columnId}` pointers (donut only where categories ≤ ~7 — page 1 uses a top-10 bar instead
  of a 20-slice donut); line trend whose grain is driven by a `segmented` control referenced in the
  formula (`DateTrunc([OvGrain], …)`).
- **Tables**: single-level `groupings` (family → line → product) with `dataBars` `conditionalFormats`.
- **Point map**: `latitude`/`longitude`/`size` as `{columnId}`, `color: {by: scale}`.
- **Theme via `settings.theme.overrides`** (colors, categorical scheme, fonts, `titleFont`, page width, space) —
  brand color lives in the theme; element `style` carries only border/radius; text hero uses white inline
  spans on a green container.
- **Layout**: `<Container>`/`<Element>` tags only; hero, filter bar, KPI row, chart grid containers.

## Known cosmetic issue
- Point-map color legend overlaps the start of the map title (setting `legend.position` did not move it);
  shorten or hide the title, or hide the legend.

## Not shown / unverified
- Element-level KPI `layout.anchor`, `description`, and viz `style.backgroundColor` were omitted (not observed
  in live readbacks of this org); `label`/`tooltip` on the map were omitted.
