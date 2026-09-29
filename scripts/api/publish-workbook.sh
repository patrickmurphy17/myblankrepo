#!/usr/bin/env bash
# Publish workbook specs to Sigma — POST a new workbook, PUT contents, GET back, metadata,
# render. Wraps the publish pipeline so callers don't compose eval/export/curl chains by hand.
#
# Usage:
#   scripts/api/publish-workbook.sh post     <spec-file>
#   scripts/api/publish-workbook.sh put      <workbook-id> <spec-file>
#   scripts/api/publish-workbook.sh get-spec <workbook-id>
#   scripts/api/publish-workbook.sh get-meta <workbook-id>
#   scripts/api/publish-workbook.sh render   <workbook-id> [out-dir]
#
# Current API (per the upstream sigma-workbooks skill; verified live 2026-09-29):
#   POST /v2/workbooks                      {name, folderId, description?, contents:{...}}
#   PUT  /v2/workbooks/{id}/contents        {contents:{...}, documentVersion?}   (contents-only)
#   GET  /v2/workbooks/{id}?includeContents=true
#
# `post` accepts a spec file in ANY shape (current `contents`, legacy-endpoint `document`, or the
# old flat pages[].elements shape) and converts it with scripts/convert-legacy-spec.py first.
# `put` accepts a full spec or a bare {contents} file and sends {contents, documentVersion}; when
# the file has no documentVersion it GETs the current one first, so a PUT never silently
# overwrites edits someone made in the UI (a stale version is rejected by the API).
# Rename/move a workbook with PUT /v2/files/{fileId} (PUT /contents ignores name/folderId).
#
# Auth, Accept: application/json header, and 401 auto-retry are all handled by the sigma_curl
# helper in _env.sh. Spec validation runs automatically before every write (validate-spec.py).
# No `delete` subcommand here — deletion stays on the direct-curl path so it always hits the
# DELETE ask pattern in .claude/settings.json.
set -euo pipefail
source "$(dirname "$0")/_env.sh"
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"

# Print the spec file's shape: contents | document | legacy
spec_shape_of() {
  python3 - "$1" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print("contents" if isinstance(d.get("contents"), dict) else "document" if isinstance(d.get("document"), dict) else "legacy")
PY
}

cmd="${1:-}"
case "$cmd" in
  post)
    spec="${2:?usage: publish-workbook.sh post <spec-file>}"
    [ -f "$spec" ] || { echo "publish-workbook: spec file not found: $spec" >&2; exit 2; }
    tmp="$(mktemp -t sigma-post.XXXXXX.json)"; trap 'rm -f "$tmp"' EXIT
    if [ "$(spec_shape_of "$spec")" = "contents" ]; then
      cp "$spec" "$tmp"
    else
      echo "publish-workbook: converting $(spec_shape_of "$spec") shape -> contents shape" >&2
      python3 "$repo_root/scripts/convert-legacy-spec.py" "$spec" -o "$tmp" >&2
    fi
    python3 "$repo_root/scripts/validate-spec.py" "$tmp"
    sigma_curl -X POST \
      -H "Content-Type: application/json" \
      --data-binary "@$tmp" \
      "$SIGMA_BASE_URL/v2/workbooks"
    ;;
  put)
    wb_id="${2:?usage: publish-workbook.sh put <workbook-id> <spec-file>}"
    spec="${3:?usage: publish-workbook.sh put <workbook-id> <spec-file>}"
    [ -f "$spec" ] || { echo "publish-workbook: spec file not found: $spec" >&2; exit 2; }
    tmp="$(mktemp -t sigma-put.XXXXXX.json)"; body="$(mktemp -t sigma-putbody.XXXXXX.json)"
    trap 'rm -f "$tmp" "$body"' EXIT
    if [ "$(spec_shape_of "$spec")" = "contents" ]; then
      cp "$spec" "$tmp"
    else
      echo "publish-workbook: converting $(spec_shape_of "$spec") shape -> contents shape" >&2
      python3 "$repo_root/scripts/convert-legacy-spec.py" "$spec" -o "$tmp" >&2
    fi
    python3 "$repo_root/scripts/validate-spec.py" "$tmp"
    have_ver="$(jq -r '.documentVersion // empty' "$tmp")"
    if [ -z "$have_ver" ]; then
      have_ver="$(sigma_curl "$SIGMA_BASE_URL/v2/workbooks/$wb_id?includeContents=true" | jq -r '.documentVersion // empty')"
      [ -n "$have_ver" ] && echo "publish-workbook: using current documentVersion=$have_ver" >&2
    fi
    if [ -n "$have_ver" ]; then
      jq --argjson v "$have_ver" '{contents: .contents, documentVersion: $v}' "$tmp" > "$body"
    else
      jq '{contents: .contents}' "$tmp" > "$body"
    fi
    sigma_curl -X PUT \
      -H "Content-Type: application/json" \
      --data-binary "@$body" \
      "$SIGMA_BASE_URL/v2/workbooks/$wb_id/contents"
    ;;
  get-spec)
    wb_id="${2:?usage: publish-workbook.sh get-spec <workbook-id>}"
    sigma_curl "$SIGMA_BASE_URL/v2/workbooks/$wb_id?includeContents=true"
    ;;
  get-meta)
    wb_id="${2:?usage: publish-workbook.sh get-meta <workbook-id>}"
    sigma_curl "$SIGMA_BASE_URL/v2/workbooks/$wb_id"
    ;;
  render)
    shift
    exec "$(dirname "$0")/render-workbook.sh" "$@"
    ;;
  *)
    cat >&2 <<'USAGE'
usage:
  publish-workbook.sh post     <spec-file>
  publish-workbook.sh put      <workbook-id> <spec-file>
  publish-workbook.sh get-spec <workbook-id>
  publish-workbook.sh get-meta <workbook-id>
  publish-workbook.sh render   <workbook-id> [out-dir]
USAGE
    exit 2
    ;;
esac
