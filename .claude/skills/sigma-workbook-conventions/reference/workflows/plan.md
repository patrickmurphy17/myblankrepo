# Plan-first workflow

The ryan-workbook-skill methodology for going from a prose prompt to a
verifiable spec **without** jumping straight to JSON. The plan is the
authorization gate for every subsequent state-changing API call.

This file is **required reading on every build.** The plan's
`Chunks Read:` line must list this file.

## When this workflow applies

Always — for every build-mode session.

The user has named *what* they want (the data, the question) and
*where* they want it (the destination folder). They have NOT named
the visualizations, the filter set, or the layout. The plan turns
prose into a verifiable spec scaffold.

Skip the plan ONLY if the user has already supplied an explicit plan
in their prompt (e.g. "build a KPI row with revenue, profit, AOV at
the top, then a bar chart of revenue by region, then a transactions
detail table").

## Required reading before authoring (HARD GATE)

Before writing ANY spec content, `Read` the chunk files mapped to the
task type. This is not optional, and not a "scan the index then
proceed." The agent must `Read` the actual chunk files in the current
session and cite chunk + section in the plan.

| Task type | Required chunks |
|---|---|
| Every build (always) | `reference/conventions.md` + this file + `reference/specification/schema.md` + `reference/specification/layout.md` (+ `reference/workflows/validate.md` for the render step) |
| Viz-heavy build (>2 chart kinds, KPI rows, pivots) | + each `reference/specification/<kind>.md` for the kinds in the plan |
| Formula-heavy build (custom calcs, metrics, Lookup, Rollup) | + `reference/specification/formulas.md` |
| Conditional-formatting build (table/pivot cell coloring) | + `reference/specification/tables.md` |
| Container-styling-heavy build (Capability 1 patterns) | + `reference/specification/containers.md` |
| Image / divider / dynamic-text build (Capabilities 2-4) | + `reference/specification/others.md` + `reference/specification/text.md` |
| Round-trip / edge-case work (POST failures, axis controls, schema drift) | + `reference/scope-and-edge-cases.md` + `reference/workflows/validate.md` |
| From-image build (screenshot/mockup reproduction) | + `reference/workflows/from-image.md` (load BEFORE data discovery) |

If chunks are skipped, the agent is operating on memory of prior
sessions — which is exactly how the 2026-05-19 regression happened
(passthrough collapse + metric carryover across DM switch). See
`reference/history.md`.

**The plan output must include a `Chunks Read:` line listing every
file consulted. A plan without that line is incomplete and not
approvable.**

## Plan content — 6 required sections

Workbook prompts often underspecify the dashboard — the user names
the data and the question, not the visualizations or the filter set.
Do not jump straight to spec. Before authoring any spec, surface a
written plan with the six sections below and wait for explicit approval.

### 1. Destination

Where the workbook (or data-model update) will be published — folder
`name` + `path` + `urlId`, resolved from the user's prompt via
`scripts/sigma-resolve.py`. If the user named a folder inline,
restate it back so they can correct it. If the user did NOT name a
folder, this becomes an **Open Decision** (item 6) the plan must
ask, not a default the agent picks.

**Plan approval IS the authorization to POST/PUT.** There is no
separate "are you sure?" prompt at publish time. The destination
must be named explicitly in the plan, never implied.

### 2. Data inventory

What table(s) and which columns are actually available — pulled via
`scripts/api/mcp-describe.sh datamodel-element <dm-id> <el-id>`,
NOT assumed. The describe output returns column types, descriptions,
formulas, and the data model's metrics catalog.

Name any column that's missing from your assumed schema (e.g. there
*is* a customer dimension; there *isn't* a margin field) so the user
can correct before you build on a wrong premise.

When recon contradicts the prompt, surface the contradiction in the
plan; don't paper over it with a substitute.

### 3. Inference rationale

For each visualization you propose, one line on *why this chart,
this dimension, this metric* answers the user's question.

Good: "Quantity, not revenue, because popularity is a unit-volume
question."

Bad: "Bar chart of products."

The rationale is the load-bearing piece. It connects the user's
prose intent to a verifiable column choice, and lets the user
correct mismatched interpretations before any spec is written.

**Every formula in the rationale must trace to recon** — see
`reference/conventions.md` → "Inference anchor." `[Metrics/X]`
references must be in the `mcp-describe` metric catalog;
sibling-column references must be declared on a recon-confirmed
source column.

### 4. Filter set with reasoning

Filters aren't free — each one earns its place by mapping to an axis
the user is likely to interrogate. List the filters in priority
order with a one-line reason, and note what you considered and
dropped.

Good:

> 1. **Date range** — every operational question is time-bounded.
> 2. **Region** — the user mentioned territory comparison in the
>    prompt; this is the axis the leaderboard sorts on.
> 3. *Dropped:* Customer segment — the prompt didn't mention
>    segmentation; can be added if the user wants segment-level
>    drill-down.

Watch for **control/column ID collisions** (see
`reference/conventions.md` → "Control/column ID collision"). The
plan should name the `controlId` for each control distinctively;
`validate-spec.py`'s `controlid-collision` check catches errors
pre-POST.

### 5. Layout sketch

A textual block-diagram of the page is enough. Don't draw the XML
yet.

```
Page 1: <Page Title>
  Row 1: <header container — page title + filter controls>
  Row 2: KPI row (4 tiles: <metric a>, <metric b>, <metric c>, <metric d>)
  Row 3: Trend chart (12 cols) | Mix donut (12 cols)
  Row 4: Top performers table (24 cols)
  Row 5: Transactions detail (24 cols)
```

For multi-page builds, sketch each page.

### 6. Open decisions

Anywhere you had to guess (proxy for a missing dimension, scope of
demographic data to bring in, whether to modify a shared data model,
**missing/ambiguous destination folder**). Phrase as questions the
user can yes/no.

Examples:

> - **Destination unclear** — the prompt says "in the sales folder"
>   but I see two folders matching: `My Documents/Sales` and
>   `Org Shared/Sales Q4`. Which?
> - **Margin proxy** — the warehouse has `Cost` and `Revenue` but no
>   `Margin` column. OK to derive `Margin = Revenue - Cost`?
> - **Drop the cohort analysis?** The prompt mentions it but the
>   data only has 3 months of history. Worth building, or wait for
>   more data?

## Plan template

```
## Plan: <workbook name>

**Chunks Read:** reference/conventions.md, reference/workflows/plan.md,
reference/specification/schema.md, reference/specification/layout.md,
reference/specification/charts.md, reference/specification/formulas.md

### 1. Destination
- Folder: `<name>` (`<path>`, urlId `<urlId>`)
- Source data model: `<DM Name>` (id `<uuid>`)
- Source element: `<element-name>` (id `<element-id>`)

### 2. Data inventory
- Recon command: `scripts/api/mcp-describe.sh datamodel-element <dm> <el>`
- Available columns: <list>
- Available metrics: <list>
- Missing from prompt's premise: <list, if any>

### 3. Inference rationale
| Element | Kind | Dimensions | Metric | Why |
|---|---|---|---|---|
| Total revenue tile | kpi-chart | (none) | `[Metrics/Total Revenue]` | Headline scalar; the prompt's first ask |
| Revenue by region | bar-chart (horizontal) | Region | `[Metrics/Total Revenue]` | Categorical comparison; horizontal for readability |
| Revenue trend | line-chart | Month | `[Metrics/Total Revenue]` | "How are we trending" |

### 4. Filter set
1. **DateRange** (`controlId: DateRange`, date-range, default last-90-days) — time-bounding
2. **StoreRegion** (`controlId: StoreRegion`, list, multi-select) — territory cut
3. *Dropped:* product category — prompt didn't mention; add if requested

### 5. Layout sketch
<block diagram>

### 6. Open decisions
- <question 1>
- <question 2>

---

Approve to proceed to build, or push back on any item.
```

## Approval model — plan is the only gate

Plan approval authorizes **every state-changing API call covered by
the plan, except DELETE.**

The rules:

- **POST/PUT inside the workbook / data-model namespace:** silent.
  Plan approval is the authorization. `.claude/settings.json`
  allowlists `Bash(scripts/api/*)` (which covers
  `publish-workbook.sh`) and the direct curl patterns.
- **POST/PUT outside that namespace** (e.g. `/v2/connections`,
  `/v2/files` mutations): not pre-authorized — surface to the user.
- **DELETE on any endpoint:** always asks. The `ask` patterns in
  `.claude/settings.json` (`Bash(curl * -X DELETE *)` and
  `Bash(scripts/api/delete-*)`) override the broad allow. Every
  DELETE call is surfaced for explicit confirmation, regardless of
  whether the plan mentioned deletion.

That contract puts the burden on the agent:

- The plan MUST name the destination folder (item 1) and any shared
  object it intends to mutate (data models, exemplars). If a
  state-changing call wasn't covered in the plan, do not make it —
  go back and amend the plan first.
- Any future deletion-wrapper script must be named
  `scripts/api/delete-*` so the ask pattern catches it. Do not
  bypass via a different name.

## After plan approval — proceed to build

0. **Format reminder.** Author in the current format (SKILL.md -> "API
   format (2026-09)"): `{name, folderId, contents:{schemaVersion:1,
   kind:"workbook", pages (metadata only), elements (FLAT), layout
   (`<Page>`/`<Container>`/`<Element>`), settings.theme}}`. Element ids
   unique workbook-wide (prefix per page). Do NOT clone legacy-shape
   exemplars verbatim; start from
   `examples/data-model-sourced-webstaurant-command-center.json` or run
   `scripts/convert-legacy-spec.py`.
1. **Write the spec** to `workbooks/<name>/spec.json` (or `.yaml` if
   YAML - the API accepts both; this skill's exemplars use JSON).
   Follow the rules in `reference/conventions.md` and the per-element
   shape docs in `reference/specification/`.
2. **Validate** via `scripts/validate-spec.py workbooks/<name>/spec.json`
   (19 checks). Fix everything reported.
3. **Publish** via `scripts/api/publish-workbook.sh post workbooks/<name>/spec.json`
   (`POST /v2/workbooks`; the wrapper validates first). For an existing
   workbook re-pull and check `documentVersion`, then
   `publish-workbook.sh put <wb-id> <spec>` (`PUT .../contents`).
4. **GET-back** via `scripts/api/publish-workbook.sh get-spec <wb-id>`
   (`GET ?includeContents=true`). Save to `workbooks/<name>/spec.json`
   (overwriting the authored version) so subsequent PUTs start from the
   server's source of truth. IDs are preserved verbatim, but the GET-back
   also picks up any UI-side edits made after the POST.
5. **Verify (compile)** via `scripts/api/verify-workbook.sh <wb-id>`. Checks
   that every element's compiled SQL doesn't contain
   `"Unknown column"` or `"Circular reference"` markers - POST
   accepts specs whose formulas don't resolve at render time, and
   only the verify pass catches that.
6. **Render & LOOK.** `scripts/api/render-workbook.sh <wb-id> [out-dir]`
   writes one PNG per page; `Read` each PNG. This is required - compile
   success does not prove a correct workbook. It is what caught the
   KPI latest-month trap, a 5-tile KPI row filling only 20/24 columns, a
   20-slice donut, and a map title/legend overlap. Reconcile KPI headlines
   against the charts. Fix and re-PUT until the render is right.
7. **Report back** with both the workbook URL AND the saved spec
   path, and state what the render check showed.

If the user wants iterative refinement after the initial build, GET
the spec again first (a human may have edited or renamed it; check
`documentVersion`), then edit + PUT. Full PUT semantics in
`reference/workflows/crud.md`.
