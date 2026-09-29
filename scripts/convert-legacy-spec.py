#!/usr/bin/env python3
"""Convert an old-shape Sigma workbook spec into the current API shape.

    python3 scripts/convert-legacy-spec.py <in.json> [-o out.json] [--put]

Input may be any of:
  - old flat   {name, folderId, schemaVersion, pages:[{id,name,elements}], layout, themeOverrides}
  - document   {name, folderId, document:{...}}        (legacy /v2/workbooks/spec endpoint)
  - contents   {name, folderId, contents:{...}}        (current; only element-level fixes applied)

Output: {name, folderId, description?, contents:{schemaVersion, kind:"workbook", pages[meta],
elements[flat], layout, settings, ...}} — the body for POST /v2/workbooks.
`--put` emits {contents:{...}} for PUT /v2/workbooks/{id}/contents instead.

What it rewrites (all verified against the live API 2026-09-29; see reference/history.md):
  - pages[].elements  -> one flat `elements` list (placement stays in the layout XML)
  - <GridContainer>/<LayoutElement> -> <Container>/<Element>
  - themeOverrides/themeName -> settings.theme.{name,overrides}
  - text.verticalAlign middle/start/end -> center/top/bottom
  - donut/pie/map channel pointers {id} -> {columnId}
  - container backgroundImage {url,style} -> {source:{kind:url,url},style}
  - response-only fields (workbookId, url, documentVersion, ...) are stripped
  - element ids duplicated across pages are renamed `<pageId>--<id>` (layout, sources and
    control filters are rewritten to match)

Best-effort: always re-run scripts/validate-spec.py and visually render the result
(scripts/api/render-workbook.sh) before relying on it.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec_shape  # noqa: E402

RESPONSE_ONLY = {
    "workbookId", "url", "documentVersion", "latestDocumentVersion", "ownerId",
    "createdBy", "updatedBy", "createdAt", "updatedAt", "path", "latestVersion",
    "workbookUrlId", "isArchived",
}
VALIGN = {"middle": "center", "start": "top", "end": "bottom"}
CHANNELS = {
    "donut-chart": ("value", "color", "holeValue"),
    "pie-chart": ("value", "color"),
    "point-map": ("latitude", "longitude", "size"),
    "region-map": ("region",),
    "geography-map": ("geography",),
}
BG_ALIGN = {"middle": "center", "start": "left", "end": "right"}


def id_to_column_id(v):
    if isinstance(v, dict) and "id" in v and "columnId" not in v:
        v = dict(v)
        v["columnId"] = v.pop("id")
    return v


def fix_element(el: dict, notes: list[str]) -> None:
    kind = el.get("kind")
    if kind == "text" and el.get("verticalAlign") in VALIGN:
        el["verticalAlign"] = VALIGN[el["verticalAlign"]]
    for k in CHANNELS.get(kind, ()):
        if k in el:
            el[k] = id_to_column_id(el[k])
    if kind in ("point-map", "region-map", "geography-map"):
        for k in ("label", "tooltip"):
            if isinstance(el.get(k), list):
                el[k] = [id_to_column_id(x) for x in el[k]]
    if kind == "container":
        bg = el.get("backgroundImage")
        if isinstance(bg, dict) and "url" in bg and "source" not in bg:
            new = {"source": {"kind": "url", "url": bg.pop("url")}}
            if isinstance(bg.get("style"), dict):
                st = dict(bg["style"])
                for k in ("horizontalAlign", "verticalAlign"):
                    if st.get(k) == "middle":
                        st[k] = "center"
                    elif k == "horizontalAlign" and st.get(k) in ("start", "end"):
                        st[k] = "left" if st[k] == "start" else "right"
                    elif k == "verticalAlign" and st.get(k) in ("start", "end"):
                        st[k] = "top" if st[k] == "start" else "bottom"
                new["style"] = st
            el["backgroundImage"] = new


def retag_layout(layout: str) -> str:
    layout = re.sub(r"<(/?)GridContainer\b", r"<\1Container", layout)
    layout = re.sub(r"<LayoutElement\b", "<Element", layout)
    return layout


def rename_duplicates(pages: list[dict], layout: str, notes: list[str]) -> tuple[list[dict], str]:
    """Element ids must be unique workbook-wide in the current API: rename ids that repeat
    across pages to `<pageId>--<id>` and rewrite the layout, `source.elementId` and control
    `filters[].source.elementId` references on that page."""
    counts: dict[str, int] = {}
    for p in pages:
        for e in p.get("elements", []):
            counts[e["id"]] = counts.get(e["id"], 0) + 1
    dups = {i for i, n in counts.items() if n > 1}
    if not dups:
        return pages, layout
    # one chunk per <Page> document so each rename only touches its own page
    chunks = [c for c in re.split(r"(?=<\?xml[^?]*\?>)", layout or "") if c.strip()]
    chunk_page = [(re.search(r'<Page\b[^>]*\bid="([^"]+)"', c) or [None, None])[1] for c in chunks]
    for p in pages:
        pid = p["id"]
        ren = {e["id"]: f"{pid}--{e['id']}" for e in p.get("elements", []) if e["id"] in dups}
        if not ren:
            continue
        notes.append(f"renamed {len(ren)} duplicate element id(s) on page {pid}")
        blob = json.dumps(p["elements"])
        for old, new in ren.items():
            blob = re.sub(rf'("(?:id|elementId)":\s*)"{re.escape(old)}"', rf'\1"{new}"', blob)
        p["elements"] = json.loads(blob)
        for i, cp in enumerate(chunk_page):
            if cp == pid:
                for old, new in ren.items():
                    chunks[i] = chunks[i].replace(f'elementId="{old}"', f'elementId="{new}"')
    return pages, "\n".join(chunks) if chunks else layout


def convert(raw: dict) -> tuple[dict, list[str]]:
    notes: list[str] = []
    shape = spec_shape.detect_shape(raw)
    body = copy.deepcopy(spec_shape.inner_body(raw))
    outer = {k: raw[k] for k in ("name", "folderId", "description") if k in raw}
    for k in list(body):
        if k in RESPONSE_ONLY:
            body.pop(k)
    for k in ("name", "folderId", "description"):
        if shape == "legacy" and k in body:
            outer.setdefault(k, body.pop(k))
        elif k in body:
            body.pop(k)

    layout = retag_layout(body.get("layout", "") or "")
    pages_in = body.get("pages", []) or []

    if shape == "legacy" or any("elements" in p for p in pages_in):
        pages_in, layout = rename_duplicates(pages_in, layout, notes)
        flat = [e for p in pages_in for e in p.get("elements", [])]
        pages = [{k: v for k, v in p.items() if k not in ("elements", "layout", "hidden")}
                 | ({"visibility": "hidden"} if p.get("hidden") and "visibility" not in p else {})
                 for p in pages_in]
        notes.append(f"flattened {len(flat)} elements from {len(pages)} pages")
    else:
        flat = body.get("elements", []) or []
        pages = pages_in

    for el in flat:
        fix_element(el, notes)

    settings = body.get("settings") or {}
    overrides = dict(settings.get("theme", {}).get("overrides", {}))
    theme_name = settings.get("theme", {}).get("name")
    legacy_to = body.pop("themeOverrides", None) or raw.get("themeOverrides")
    legacy_tn = body.pop("themeName", None) or raw.get("themeName")
    if legacy_to:
        overrides.update(legacy_to)
        notes.append("themeOverrides -> settings.theme.overrides")
    if legacy_tn:
        theme_name = legacy_tn
    if overrides or theme_name:
        theme = {}
        if theme_name:
            theme["name"] = theme_name
        if overrides:
            theme["overrides"] = overrides
        settings["theme"] = theme

    contents: dict = {
        "schemaVersion": body.get("schemaVersion", 1),
        "kind": "workbook",
        "pages": pages,
        "elements": flat,
    }
    if layout:
        contents["layout"] = layout
    if settings:
        contents["settings"] = settings
    for k in ("overlays", "panels", "agents"):
        if body.get(k):
            contents[k] = body[k]
    dropped = [k for k in body if k not in contents and k not in
               ("schemaVersion", "kind", "pages", "elements", "layout", "settings", "folders")]
    if body.get("folders"):
        notes.append("dropped top-level `folders` (column-folder groupings; UI-side only)")
    if dropped:
        notes.append(f"dropped unknown top-level keys: {', '.join(sorted(dropped))}")

    out = dict(outer)
    out["contents"] = contents
    return out, notes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--put", action="store_true", help="emit {contents} for PUT /contents")
    a = ap.parse_args()
    with open(a.input) as f:
        raw = json.load(f)
    out, notes = convert(raw)
    if a.put:
        out = {"contents": out["contents"]}
    text = json.dumps(out, indent=2)
    if a.output:
        with open(a.output, "w") as f:
            f.write(text + "\n")
    else:
        print(text)
    for n in notes:
        sys.stderr.write(f"convert-legacy-spec: {n}\n")
    sys.stderr.write("convert-legacy-spec: done — now run scripts/validate-spec.py and render the result.\n")


if __name__ == "__main__":
    main()
