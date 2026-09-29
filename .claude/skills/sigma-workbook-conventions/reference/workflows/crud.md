# Workbook CRUD

Create / read / update workbooks (format current as of 2026-09; see
SKILL.md -> "API format (2026-09)"). Load this when creating,
retrieving, or updating a workbook.

| Action | Call | Body |
|---|---|---|
| CREATE | `POST /v2/workbooks` | `{name, folderId, description?, contents:{schemaVersion:1, kind:"workbook", pages, elements, layout, settings, overlays?, panels?, agents?}}` |
| UPDATE | `PUT /v2/workbooks/{id}/contents` | exactly `{contents:{...}, documentVersion?}` - **contents-only**; `name`/`folderId` are ignored. Rename/move via `PUT /v2/files/{fileId}`. |
| READ | `GET /v2/workbooks/{id}?includeContents=true` | returns `contents` + `documentVersion` |

**Legacy path (still works, not recommended):** `POST /v2/workbooks/spec`
(body `{name, folderId, document:{...}}`) and `GET /v2/workbooks/{id}/spec`
(returns `document`). The session's first Webstaurant workbook was created
that way. The pre-2026-09 flat shape (`pages[].elements`, top-level
`layout`, `themeOverrides`) is rejected there with a giant union error whose
paths all start `0.document.` - that signature means "you sent the old
shape."

The value here is calling out the **non-obvious behaviors**: PUT being
full-replacement of `contents`, `documentVersion` concurrency, response-only
fields returned by GET, and how the repo's `publish-workbook.sh` wrapper
layers validation + auth on top of curl. IDs you send on POST are preserved
verbatim - see "ID preservation" below.

## OpenAPI reference

```bash
curl -sf https://assets.sigmacomputing.com/openapi/public-rest-api/sigma-computing-public-rest-api.json > /tmp/sigma-api.json
jq '.components.schemas.CreateWorkbook' /tmp/sigma-api.json
jq '.paths."/v2/workbooks".post, .paths."/v2/workbooks/{workbookId}/contents".put' /tmp/sigma-api.json
```

(~6.8MB. The old `help.sigmacomputing.com/openapi/...json` URL 404s.
Per-endpoint pages: `https://help.sigmacomputing.com/reference/<slug>`.)

## The repo wrapper - `publish-workbook.sh`

Prefer this over direct curl:

```bash
scripts/api/publish-workbook.sh post     workbooks/<name>/spec.json   # validate -> POST /v2/workbooks (auto-converts legacy files)
scripts/api/publish-workbook.sh put      <workbookId> workbooks/<name>/spec.json  # validate -> PUT /contents
scripts/api/publish-workbook.sh get-spec <workbookId> > workbooks/<name>/spec.json  # GET ?includeContents=true
scripts/api/publish-workbook.sh get-meta <workbookId>                 # url, name, path, folderId
scripts/api/publish-workbook.sh render   <workbookId> [out-dir]       # alias of render-workbook.sh
```

The wrapper:
- Sources `_env.sh` for auth (caches OAuth token at `/tmp/.sigma_token`)
- Runs `scripts/validate-spec.py` before POST/PUT (fails fast; 19 checks)
- `post` auto-converts legacy-shape files (see `scripts/convert-legacy-spec.py`)
- `put` sends `{contents, documentVersion}`; it fetches the current
  `documentVersion` first unless the file already contains one
- Uses `sigma_curl` for auth-injected, 401-retrying requests
- Reports the HTTP status alongside the body

**No `delete` subcommand** - DELETE goes via direct curl on purpose so
it triggers the `ask` pattern in `.claude/settings.json`. See
`reference/workflows/plan.md` -> "Approval model" for the rationale.

## PUT - `documentVersion` and re-pull first

```bash
scripts/api/publish-workbook.sh put <workbook-id> workbooks/<name>/spec.json
```

`documentVersion` is an optimistic-concurrency check: the PUT fails if
it is stale; omit it for last-write-wins. **Re-pull the workbook and check
`documentVersion` before any PUT** - a human may have edited or renamed it in
the UI. `PUT .../contents` never renames or moves; use `PUT /v2/files/{fileId}`.

## DELETE - direct curl (intentional)

```bash
curl -sS -X DELETE -H "Authorization: Bearer $SIGMA_API_TOKEN" \
  "$SIGMA_BASE_URL/v2/workbooks/<workbook-id>"
```

DELETE stays on the direct-curl path so it hits the `ask` pattern in
`.claude/settings.json` (`Bash(curl * -X DELETE *)`). Any deletion wrapper
must be named `scripts/api/delete-*` so the corresponding `ask` rule
catches it - see `reference/workflows/plan.md` -> "Approval model."

The API accepts both `application/json` and `application/yaml`. This
skill's exemplars are JSON for tooling consistency with
`validate-spec.py` and `workbook-manifest.py`, but YAML POSTs work
identically. Use `--data-binary @file` (NOT `-d @file`) - `-d` strips
newlines and breaks multi-line specs.

## Required fields on CREATE

The `POST /v2/workbooks` body must include:

- `name` (string)
- `folderId` (string - usually the user's `homeFolderId` or a folder
  resolved via `scripts/sigma-resolve.py`)
- `contents` - technically optional at the API level, but omitting it
  silently creates an EMPTY workbook. Always send it. It requires
  `schemaVersion`, `kind: "workbook"`, `pages` (metadata only), and a flat
  `elements` array; add `layout` (XML) so every element is placed.

Optional: `description`; in `contents`: `settings` (`theme`,
`navigation`), `overlays`, `panels`, `agents`.

### schemaVersion - don't hardcode

Sigma's `schemaVersion` evolves. Hardcoding `1` works today (the current
exemplar uses `1`) but is brittle. Read it back from a recent reference GET:

```bash
scripts/api/publish-workbook.sh get-spec <reference-workbook-id> \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print((d.get('contents') or d.get('document') or d)['schemaVersion'])"
```

When the server rejects a spec for `schemaVersion mismatch`, pull
the current value from any working workbook and use it.

## Response-only fields to strip

`GET /v2/workbooks/<id>?includeContents=true` returns extra server-managed
outer fields. When you take a GET response and PUT it back (the standard
iteration flow), send only `{contents, documentVersion?}` - i.e. strip:

- `workbookId`
- `url`
- `latestDocumentVersion`
- `ownerId`
- `createdBy`
- `updatedBy`
- `createdAt`
- `updatedAt`
- (and `name`/`folderId`/`description`, which PUT ignores)

`documentVersion` is the deliberate exception (keep it for the concurrency
check). `workbook-manifest.py` recognizes these as response-only.

## ID preservation on CREATE

The `id` values you send in `POST /v2/workbooks` - for pages,
elements, columns - are **preserved verbatim**. Layout `elementId`
references stay valid across POST/PUT. Element ids must be unique
**workbook-wide**. You can save the spec, edit it, and `PUT` it back
directly using the same IDs.

Verified 2026-07-02 (legacy path) and 2026-09-29 (new path): kebab-case
IDs survived POST -> GET round-trip unchanged.

Layout `elementId` references need to match the actual flat element `id`
exactly (case-sensitive). The API rejects unplaced elements; mismatches come
from typos, not server-side remapping.

The iteration pattern:

```bash
# 1. Re-pull and check documentVersion (a human may have edited it)
scripts/api/publish-workbook.sh get-meta <wb-id>

# 2. Edit workbooks/<name>/spec.json on disk (using your original IDs)

# 3. Validate
scripts/validate-spec.py workbooks/<name>/spec.json

# 4. PUT (uses the wrapper for validation + auth)
scripts/api/publish-workbook.sh put <wb-id> workbooks/<name>/spec.json

# 5. Verify (compile) and render (LOOK at the PNGs)
scripts/api/verify-workbook.sh <wb-id>
scripts/api/render-workbook.sh <wb-id> [out-dir]
```

If you're editing a GET-back spec (rather than your own saved
version), strip the response-only fields first - see the section
above.

## Persisting the spec

This skill's convention is one folder per workbook under `workbooks/`:

```
workbooks/<name>/
├── spec.json           # latest spec (overwritten each GET-back)
├── prompts/            # one .md per session
│   └── 2026-05-21T22-30-00.md
├── iterations/         # archive of attempts
│   └── 2026-05-21T22-30-00.json
└── notes.md            # ad-hoc observations
```

After CREATE, immediately `get-spec` and overwrite `spec.json` with
the server's readback. This avoids the "old external IDs" trap on the
next PUT. The official skill's `/tmp/workbook-spec-<id>.yaml`
convention is an alternative when you don't want repo state; this
skill's per-workbook folder is preferred for iteration audit trails.

## Common errors

| Error | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Token missing or expired | Delete `/tmp/.sigma_token`, re-run any `scripts/api/*.sh` to re-fetch |
| `403 Forbidden` on POST | Credential can't create in this folder | Ask user's Sigma admin to check folder permissions |
| `schemaVersion mismatch` | Hardcoded `1` against a newer API | Read `schemaVersion` from a reference GET, use that value |
| Giant union error, all paths start `0.document.` | You sent the pre-2026-09 shape (`pages[].elements`, top-level `layout`/`themeOverrides`) | Convert: `scripts/convert-legacy-spec.py`; see `reference/workflows/validate.md` |
| `document.elements[N]: Invalid kind: "<x>"` | Generic - an enum/field INSIDE that element is wrong (not that the kind is unsupported) | See `reference/workflows/validate.md` -> "Decoding cryptic errors" (e.g. text `verticalAlign`) |
| Body returned as `service_error` 500 | UI feature in workbook can't serialize | See `reference/scope-and-edge-cases.md` -> "GET-spec can 500 when UI features aren't representable" |

## Schema drift - when this skill goes stale

If a POST/PUT fails with `invalid argument`, `unknown field`,
`unexpected property`, `missing required field`, `unrecognized
parameter`, or a 400 about request *shape* rather than data - the API
has evolved since this skill was written. Apply the bounded fallback:

1. **Tell the user.** Print:

   > This error looks like a schema mismatch between this skill
   > and the current Sigma API. The skill may be out of date -
   > consider updating it. I'll consult the live OpenAPI and a live
   > workbook readback in the meantime.

2. **Diagnose from evidence, not memory.** (a) Read a working live
   workbook: `GET /v2/workbooks/<id>?includeContents=true` (readback wins
   over docs). (b) Fetch the current OpenAPI (URL at the top of this file;
   `CreateWorkbook`, `WorkbookElement`). (c) **Parse union errors by their
   path prefix**: paths all starting `0.document.` = old shape sent to the
   legacy endpoint; a path like `document.elements[i]` names the failing
   element. (d) `Invalid kind: "<x>"` on an element is generic - suspect an
   enum/field inside that element, not the kind.
3. **Diff** the live schema vs. what the skill assumed - renamed
   fields, new required fields, removed fields, type changes.
4. **One automated retry** with the corrected shape. If it succeeds,
   tell the user exactly what changed.
5. **Do not loop.** One retry, then stop. Surface the diff and let
   the user decide.

When the OpenAPI and this skill disagree, the OpenAPI wins; when docs
and a live readback disagree, the readback wins.
