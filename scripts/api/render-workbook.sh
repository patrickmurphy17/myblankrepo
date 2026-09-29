#!/usr/bin/env bash
# render-workbook.sh — export one PNG per page of a published workbook so you can LOOK at it.
#
# Usage: scripts/api/render-workbook.sh <workbook-id> [out-dir]
#
# A workbook that POSTs and compiles can still be wrong on screen (misleading KPIs, clipped
# tiles, unreadable donuts, overlapping map legends). verify-workbook.sh only proves the SQL
# compiles; this proves the page reads. After it finishes, open the PNGs (Read tool / image
# viewer) and check them before reporting the workbook as done.
#
# Wraps the upstream sigma-workbooks `scripts/wb-rep.rb pull` + `render`, so it needs:
#   - ruby
#   - the read-only upstream mirror:  bash scripts/refresh-vendor.sh   (creates vendor/sigma-agent-skills)
# Output: <out-dir>/renders/<page-slug>.png   (default out-dir: workbooks/_renders/<workbook-id>)
set -euo pipefail
source "$(dirname "$0")/_env.sh"
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"

wb_id="${1:?usage: render-workbook.sh <workbook-id> [out-dir]}"
out_dir="${2:-$repo_root/workbooks/_renders/$wb_id}"
rb="$repo_root/vendor/sigma-agent-skills/skills/sigma-workbooks/scripts/wb-rep.rb"

command -v ruby >/dev/null 2>&1 || { echo "render-workbook: ruby is required (upstream wb-rep.rb)." >&2; exit 2; }
[ -f "$rb" ] || { echo "render-workbook: upstream mirror missing. Run: bash scripts/refresh-vendor.sh" >&2; exit 2; }

export SIGMA_API_TOKEN SIGMA_BASE_URL
rm -rf "$out_dir"; mkdir -p "$(dirname "$out_dir")"
ruby "$rb" pull "$wb_id" "$out_dir" >&2
ruby "$rb" render "$out_dir" >&2
echo "render-workbook: PNGs in $out_dir/renders/" >&2
ls -1 "$out_dir"/renders/*.png
