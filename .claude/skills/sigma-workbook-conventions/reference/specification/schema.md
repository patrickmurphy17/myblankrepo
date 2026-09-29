# Workbook spec — top-level schema

The overall shape of the workbook spec passed to `POST /v2/workbooks` (create) and `PUT /v2/workbooks/{id}/contents` (update). Format current as of 2026-09; see SKILL.md -> "API format (2026-09)".

## Consulting the OpenAPI

The Sigma OpenAPI is the canonical schema for every request/response
shape. When this skill and the OpenAPI disagree, the OpenAPI wins; when
docs and a live readback (`GET /v2/workbooks/{id}?includeContents=true`)
disagree, the readback wins. The old `help.sigmacomputing.com/openapi/...json`
URL now 404s; the compiled spec (~6.8MB) is at the `assets.` URL below. Fetch
once per session and inspect with `jq`:

```bash
curl -sf https://assets.sigmacomputing.com/openapi/public-rest-api/sigma-computing-public-rest-api.json > /tmp/sigma-api.json

# Workbook create request body (CreateWorkbook); element kinds hang off WorkbookElement
jq '.components.schemas.CreateWorkbook' /tmp/sigma-api.json
jq '.components.schemas.WorkbookElement' /tmp/sigma-api.json

# A specific element kind's full shape
jq '.components.schemas.BarChart' /tmp/sigma-api.json
jq '.components.schemas.KpiChart' /tmp/sigma-api.json

# List every schema name (when you don't know the right one)
jq -r '.components.schemas | keys[]' /tmp/sigma-api.json | grep -i <hint>
```

Every per-element file in this directory opens with the relevant `jq`
recipe. Use it whenever a field shape has changed or the skill's coverage
doesn't include a feature you need.

### Schema-drift signal

If a POST/PUT fails with `invalid argument`, `unknown field`,
`unexpected property`, `missing required field`, `unrecognized parameter`,
or a 400 about request *shape* rather than data — the API has evolved
since this skill was written. Fallback in `reference/workflows/crud.md` →
"Schema drift." A giant union error whose paths all start `0.document.`
means you sent the pre-2026-09 shape (nested `pages[].elements`,
top-level `layout`/`themeOverrides`) to the legacy `/spec` endpoint.

This file covers what the OpenAPI alone won't tell you: which fields are
response-only, the ID rules, the flat-elements/layout placement rule, and a
minimal working example. For per-element shapes, see the per-element files in
this directory.

## Top-level object

```json
{
  "name": "My Workbook",
  "folderId": "<folder-uuid>",
  "description": "Optional description",
  "contents": {
    "schemaVersion": 1,
    "kind": "workbook",
    "pages": [ {"id": "page-overview", "name": "Overview"} ],
    "elements": [ ... ],
    "layout": "<?xml version=\"1.0\" encoding=\"utf-8\"?><Page ... id=\"page-overview\">...</Page>",
    "settings": { "theme": { "overrides": { ... } }, "navigation": { ... } },
    "overlays": [], "panels": [], "agents": []
  }
}
```

**Outer (CREATE only):** `name`, `folderId` required; `description` optional.
**`contents`:** `schemaVersion`, `kind: "workbook"`, `pages`, `elements`
required; `layout` required by this skill whenever `elements` is non-empty;
`settings`, `overlays`, `panels`, `agents` optional. Always send `contents`
on CREATE - omitting it silently creates an empty workbook.

**Endpoints.**

| Action | Call | Body |
|---|---|---|
| Create | `POST /v2/workbooks` | `{name, folderId, description?, contents}` |
| Update | `PUT /v2/workbooks/{id}/contents` | exactly `{contents, documentVersion?}` - contents-only; `name`/`folderId` are ignored. Rename/move with `PUT /v2/files/{fileId}`. `documentVersion` is an optimistic-concurrency check (fails if stale; omit for last-write-wins). |
| Read | `GET /v2/workbooks/{id}?includeContents=true` | returns `contents` + `documentVersion` |

The legacy `POST /v2/workbooks/spec` (body `{name, folderId, document:{...}}`)
and `GET /v2/workbooks/{id}/spec` (returns `document`) still work, but the
previous flat shape is rejected there with the `0.document.` union error.
Prefer the endpoints above.

See `reference/workflows/crud.md` -> "schemaVersion - don't hardcode"
for the rule on `schemaVersion`. Current exemplar uses `1`.

## Response-only fields

`GET` returns these outer server-managed fields - they **must not be
sent** in a CREATE or UPDATE body (unknown top-level fields are rejected):

- `workbookId`
- `url`
- `documentVersion` (exception: send it deliberately on PUT, alongside
  `contents`, for the optimistic-concurrency check)
- `latestDocumentVersion`
- `ownerId`
- `createdBy`
- `updatedBy`
- `createdAt`
- `updatedAt`

`scripts/workbook-manifest.py` recognizes these and won't flag them
as unknown. `scripts/validate-spec.py` warns when they're present on
a file being POSTed.

## Pages (metadata only)

`contents.pages[]` carries metadata only:

```json
{ "id": "page-overview", "name": "Overview" }
```

Optional page keys: `visibility` (`"hidden"`, or a specific-users-and-teams
object), `pageWidth`, `backgroundColor`, `backgroundImage`
(`{source:{kind:"url",url}, style:{fit, horizontalAlign: left|center|right,
verticalAlign: top|center|bottom, tiling}}`), `type`.

**`pages[].elements` is REJECTED.** Elements live in the single flat
`contents.elements[]` array (tables, charts, KPIs, controls, containers,
text, dividers, images). Placement on a page or inside a container is
decided **entirely by the layout XML**; an element that is not placed in
layout is rejected. See `reference/specification/layout.md`.

## ID rules

- Element ids must be **unique workbook-wide** (not just per page):
  elements are one flat array, so the same `id` on two pages collides.
  Prefix ids per page (`ov-kpi-revenue`, `tr-line-monthly`). Column ids
  must be unique within their element. Page ids unique among pages.
  (`validate-spec.py` check `element-ids-unique`.)
- Use descriptive kebab-case or short random-looking IDs - both are
  fine. IDs are internal identifiers, not displayed to users.
- **IDs are preserved verbatim on `POST`.** Pages, elements, and
  columns keep the `id` values you sent. Layout `elementId`
  references stay valid across POST/PUT round-trips.
- Every layout `elementId` must match a flat `contents.elements[].id`
  exactly (case-sensitive), and every element must be placed.

Verified 2026-07-02 (legacy path) and 2026-09-29 (new path): kebab-case IDs
survive POST -> GET round-trips.

## Layout

`contents.layout` is one XML string carrying one `<Page id="...">` block
per page (the `id` ties each block to a `pages[].id`); multi-page workbooks
concatenate the per-page XML docs. Tags are `<Page>`, `<Container>`,
`<Element>` (plus `<TabbedContainer>/<Tab>`, `<Panel>`); never the legacy
`<GridContainer>`/`<LayoutElement>`. See `reference/specification/layout.md`.

## `folders` field (legacy; unverified in the new contents shape)

Optional. Carries column-folder groupings for the workbook. Most
workbooks omit it. When present, looks like:

```json
"folders": [
  { "id": "ejtrqOFhcK", "name": "Store Fields", "items": [...] }
]
```

The `items` are column IDs grouped under the folder name. UI-side
organization; doesn't affect render. Inspect via `mcp-describe.sh
workbook <wb-id>` if you need the structure.

## `contents.settings.theme` (replaces `themeName` / `themeOverrides`)

`themeName` and top-level `themeOverrides` are **removed**. Workbook-wide
theme, page width, and spacing live under `contents.settings.theme`:

```json
"settings": {
  "theme": {
    "name": "Light",
    "overrides": {
      "colors": { "text": "#3b4238", "highlight": "#198d00", "surface": "#ffffff",
                  "success": "#198d00", "warning": "#f5a623", "danger": "#d0021b" },
      "categoricalScheme": ["#198d00", "#00aeef", "#1d5c00"],
      "sequentialScheme": ["#a6d690", "#198d00"],
      "divergingScheme": ["#d0021b", "#ffffff", "#198d00"],
      "fonts": { "textFont": "Inter", "dataFont": "Inter" },
      "titleFont": { "color": "#1d5c00", "fontSize": 18, "fontWeight": "bold" },
      "pageWidth": "large",
      "space": { "unit": "small", "showElementPadding": true },
      "hasCards": true,
      "borderRadius": "round"
    }
  },
  "navigation": { "pageHeader": "disabled", "pageSidebar": "disabled" }
}
```

`pageWidth` is `full | large | medium | custom` (`maxPageWidth` with
`custom`); `space.unit` is `small | medium | large`; `borderRadius` is
`square | round | pill`. Other override keys exist (`elementBorder`,
`tableStyles`, ...) - inspect `CreateWorkbook` before using an unfamiliar
one (the exact value shapes for `sequentialScheme`, `divergingScheme`,
`fonts` above are illustrative; verify against a readback - unverified).
`navigation` panels are workspace-gated; omit unless needed.

## `theme` element kind

A named theme reference that can appear in the flat element array
alongside data-viz elements in `contents.elements[]` (unverified in the new format):

```json
{
  "kind": "theme",
  "ref": "colors-textNeutral"
}
```

Observed in `sales-mbr-sentinel` (2 instances). Applies theme-level
styling by reference. Inspect the OpenAPI for the enum of valid `ref`
values before authoring. Kept minimal here until a fuller pattern
emerges.

## Minimal working example

The smallest spec that creates a workable workbook (`POST /v2/workbooks`):

```json
{
  "name": "Sales Dashboard",
  "folderId": "<folder-uuid>",
  "contents": {
    "schemaVersion": 1,
    "kind": "workbook",
    "pages": [ { "id": "page-1", "name": "Overview" } ],
    "elements": [
      {
        "id": "ov-sales-table",
        "kind": "table",
        "name": "Sales Data",
        "source": {
          "kind": "warehouse-table",
          "connectionId": "<conn-uuid>",
          "path": ["SALES_DB", "PUBLIC", "ORDERS"]
        },
        "columns": [
          { "id": "col-order-id", "name": "Order ID", "formula": "[ORDERS/order_id]" },
          { "id": "col-amount",   "name": "Amount",   "formula": "[ORDERS/amount]" },
          { "id": "col-total",    "name": "Total",    "formula": "Sum([Amount])" }
        ]
      }
    ],
    "layout": "<?xml version=\"1.0\" encoding=\"utf-8\"?><Page type=\"grid\" gridTemplateColumns=\"repeat(24, 1fr)\" gridTemplateRows=\"auto\" id=\"page-1\"><Element elementId=\"ov-sales-table\" gridColumn=\"1 / 25\" gridRow=\"1 / 16\"/></Page>"
  }
}
```

Notes:

- `[ORDERS/order_id]` references a warehouse column (table prefix required).
- `Sum([Amount])` references the "Amount" column defined in the same
  element (no prefix).
- The element is on the page only because the layout places it.

For a realistic multi-page reference, see
`examples/data-model-sourced-webstaurant-command-center.json` (current
format; generator at `workbooks/webstaurant-sales-command-center/build_spec.py`).
Other files in `examples/` are LEGACY-SHAPE - run
`scripts/convert-legacy-spec.py` first. For a full official example in the current format, see the
upstream `vendor/sigma-agent-skills/skills/sigma-workbooks/reference/specification/example-full.yaml`
(the local `example-full.yaml` here is legacy-shape).
