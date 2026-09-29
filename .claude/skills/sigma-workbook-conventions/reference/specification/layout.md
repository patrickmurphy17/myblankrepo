# Layout

`contents.layout` XML — when to write it, the two-tag grammar, the
flat-elements placement rule, and the silent-failure traps the OpenAPI
doesn't surface. (Format current as of 2026-09.)

**Default to writing explicit `layout` XML for multi-element workbooks.**

For container element bodies (the `kind: "container"` JSON placeholders
that pair with `<Container>` in this XML), see `containers.md`.

## When to write layout vs. let Sigma auto-arrange

Write explicit `layout` when **any** of these apply:

- The page has **mixed element kinds** (charts + KPIs, controls +
  charts, text/image/divider polish). Auto-arrange treats them as a
  vertical stack and gives every element the same height — KPIs end
  up the size of charts, dividers get huge gutters around them.
- The user asked for specific positioning ("logo on left, title on
  right", "KPIs across the top", side-by-side charts).
- There's a `kind: "container"` element on the page. Containers
  without a matching `<Container>` are functionally no-ops.
- The workbook has more than ~4 elements on a page. Auto-arrange
  becomes a long scroll.

Do not rely on auto-arrange: the current API **rejects a flat element that
has no placement in layout**, so `layout` is effectively required whenever
`contents.elements` is non-empty. Writing one is cheap (the patterns below
are copy-paste); a visually broken dashboard is expensive.

## Elements are flat; layout is the only placement

`contents.elements[]` is ONE flat array for the whole workbook. Pages
(`contents.pages[]`) are metadata only, and `pages[].elements` is
rejected. An element belongs to a page, container, tab, overlay, or panel
**solely by where its `<Element elementId>` appears in the layout XML**.
Do not infer ownership from array order. Every element must be placed, and
every `elementId` must match a declared element (case-sensitive). Element
ids are unique workbook-wide - prefix them per page.

## Layout is a sibling of `pages` (NOT per-page)

`layout` lives in `contents`, next to `pages` and `elements`, not nested
under `pages[i]`. Multi-page workbooks concatenate per-page XML documents:

```json
{
  "contents": {
    "pages": [ {"id": "page-1", "name": "Overview"}, {"id": "page-2", "name": "Trend"} ],
    "elements": [ ... ],
    "layout": "<?xml ...?><Page id=\"page-1\" ...>...</Page><?xml ...?><Page id=\"page-2\" ...>...</Page>"
  }
}
```

Each `<Page id="...">` matches a `pages[].id`. Per-page layout
placed under `pages[i]` is silently discarded - verified
2026-05-11. See `reference/history.md`.

## Two flavors: XML layout vs. element-level `layout` object

The `contents.layout` field discussed here is an **XML string** that
positions elements on the page grid.

Some legacy exemplars also show an element carrying a `layout` **object**
(not XML) for in-element positioning. **Unverified in the current format**:
the 2026-09-29 Webstaurant build dropped it (along with
`description: {visibility: hidden}` on KPIs) rather than test it. Omit it
unless you confirm it against a live readback:

```json
{
  "kind": "kpi-chart",
  "id": "kpi-revenue",
  "layout": { "anchor": "middle" },
  ...
}
```

Observed (legacy, 2026-07-02): `anchor: "middle"` on KPIs. Other values
unverified - inspect the OpenAPI.

These are two different things using the same key name:

| Where | Value type | Purpose |
|---|---|---|
| `contents.layout` | XML string | Places elements on the page grid |
| On each element (`element.layout`) | JSON object | Positions content within the element's box |

If used, both coexist - the XML places the KPI on the grid; the object
sets the content's anchor within its allocated cell.

## Two-tag grammar

`<Page>` roots, then `<Container>` (has children) and `<Element>` (leaf).
`<TabbedContainer>` / `<Tab>` and `<Panel>` also exist (see upstream
`vendor/sigma-agent-skills/skills/sigma-workbooks/reference/specification/layout.md`).

```xml
<?xml version="1.0" encoding="utf-8"?>
<Page type="grid" gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto" id="<pageId>">
  <Container elementId="<containerId>" type="grid" gridColumn="1 / 25" gridRow="1 / 4"
             gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
    <Element elementId="<childId>" gridColumn="1 / 13" gridRow="1 / 4"/>
  </Container>
  <Element elementId="<elementId>" gridColumn="1 / 25" gridRow="4 / 16"/>
</Page>
```

Each `<Page id>` matches a `pages[].id`. Each `elementId` matches a flat
`contents.elements[].id`. `gridColumn` / `gridRow` use standard CSS grid
line syntax (`start / end`); the grid is **24 columns wide**.

> **Never emit the legacy `<GridContainer>` / `<LayoutElement>` tags.**
> Upstream live verification rejects `<Element>`. They appear only in
> old exemplars; `scripts/convert-legacy-spec.py` rewrites them, and
> `validate-spec.py` check `legacy-layout-tags` fails on them.

## `<Container>` vs `<Element>` - silent failure

> Use `<Container>` for any tag that has children nested inside it.
> An `<Element>` with children parses successfully **as a leaf** and the
> children are silently dropped - no error, the child elements just
> disappear from the page (and, since unplaced elements are rejected,
> often surface as a placement error).

- `<Element elementId="X" .../>` - **leaf**. Positions a single
  element. No children.
- `<Container elementId="X" ...>...</Container>` - **container**.
  Wraps child `<Element>`s inside its own inner grid.

`scripts/validate-spec.py` checks `elements-placed-in-layout` and
`containers-have-children` catch the common variants; the manual layout
pass in `validate.md` and the rendered PNGs catch the rest.

## `gridTemplateRows`: keep it `"auto"`

> Silent normalization: `gridTemplateRows` is accepted on PUT with
> any value but normalizes back to `"auto"` on GET. Writing `"1fr"`,
> `"100px"`, `"repeat(3, 1fr)"` etc. doesn't error — the server drops
> your value and treats the row track as `"auto"`. Always write
> `"auto"` explicitly so the round-trip is stable.

Because row tracks collapse to `"auto"`, height comes from children,
not from the container's `gridTemplateRows`. Two patterns work:

### Side-by-side

Children share the container's row range, differ by `gridColumn`:

```xml
<Container elementId="kpi-row" type="grid"
               gridColumn="1 / 25" gridRow="1 / 4"
               gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
  <Element elementId="kpi-1" gridColumn="1 / 9"   gridRow="1 / 4"/>
  <Element elementId="kpi-2" gridColumn="9 / 17"  gridRow="1 / 4"/>
  <Element elementId="kpi-3" gridColumn="17 / 25" gridRow="1 / 4"/>
</Container>
```

### Stacked rows inside a container

Children have disjoint `gridRow` spans. The server normalizes the
container's outer `gridRow` to encompass its children — declare
generously and let normalization clamp:

```xml
<Container elementId="header-row" type="grid"
               gridColumn="1 / 25" gridRow="1 / 12"
               gridTemplateColumns="repeat(24, 1fr)" gridTemplateRows="auto">
  <Element elementId="title"  gridColumn="1 / 25" gridRow="1 / 4"/>
  <Element elementId="kpi-1"  gridColumn="1 / 9"  gridRow="4 / 12"/>
  <Element elementId="kpi-2"  gridColumn="9 / 17" gridRow="4 / 12"/>
  <Element elementId="kpi-3"  gridColumn="17 / 25" gridRow="4 / 12"/>
</Container>
```

Use stacked rows when you want a section header above a row of
charts inside the same container, instead of moving those elements
out to the page level.

## After CREATE: IDs are preserved

IDs you `POST` are preserved verbatim - pages, elements, columns keep
the `id` values you sent. You can save the spec, edit it, and `PUT`
its `contents` back directly. Layout `elementId` references stay valid
across POST/PUT.

Layout `elementId` references must match a flat element `id` exactly
(case-sensitive); the API rejects unplaced elements and undeclared ids.

Verified 2026-07-02 (legacy path) and 2026-09-29 (new path): kebab-case
IDs survived POST -> GET round-trip unchanged.

## Page-structure pattern (apply by default)

Every page should follow a recognizable visual structure. The
default pattern:

```
Page 1: <Page Title>
  Container 1 — header (page title + filter controls)
  Container 2 — KPI row (4 KPI tiles, equal width)
  Container 3+ — content (charts, tables, in side-by-side or
                          full-width sections)
```

For multi-section pages, nest containers:

- Outer container per logical section (24-col span).
- Inner container per side-by-side pair (each 12-col span inside the outer).
- Section-header text element above each section.

See `examples/data-model-sourced-webstaurant-command-center.json` for a
current-format page-structure exemplar (each page ends with a full-width
"source data" table so the tables its visuals source from exist on a page).
KPI rows: if N tiles do not divide 24 evenly, use uneven spans (5 tiles ->
5,5,5,5,4), otherwise the row fills only 20/24 columns (caught by rendering).

## Cross-cutting rules

For the per-element layout rules that affect every spec — column
declaration mandate, drill-down corollary, rename-cascade
corollary, summary-bar pattern — see `reference/conventions.md`.

## What `layout` does NOT capture

- `padding` / "padding enabled" toggle — UI-only.
- `ContainerSpacing` / inter-element gap — UI-only.
- `gap` between grid cells — UI-only.

Layout XML attributes are limited to `gridColumn`, `gridRow`,
`gridTemplateColumns`, `gridTemplateRows`, `elementId`, `type`, `id`.
See `containers.md` → "What style does NOT capture."
