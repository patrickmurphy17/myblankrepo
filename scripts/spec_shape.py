"""Shared workbook-spec shape helpers (imported by validate-spec.py, workbook-manifest.py,
convert-legacy-spec.py).

The Sigma workbook API changed shape (verified 2026-09-29):

  current   POST /v2/workbooks               {name, folderId, contents:{schemaVersion, kind, pages, elements, layout, settings}}
            PUT  /v2/workbooks/{id}/contents {contents:{...}, documentVersion?}
  legacy-ep POST /v2/workbooks/spec          {name, folderId, document:{...same inner shape...}}
  old flat  (pre-2026-09) {name, folderId, schemaVersion, pages:[{id,name,elements:[...]}], layout, themeOverrides}

In the current shape `elements` is ONE flat list, `pages[]` is metadata only, and placement on
pages/containers is determined solely by the layout XML (<Page>, <Container>, <Element>).

`normalize()` returns a *view* shaped like the old flat format (pages[].elements populated from the
layout) so per-element checks can run unchanged on any shape.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET

LEGACY_LAYOUT_TAGS = ("LayoutElement", "GridContainer")
CONTAINER_TAGS = ("Container", "GridContainer")


def detect_shape(spec: dict) -> str:
    """'contents' | 'document' | 'legacy'."""
    if isinstance(spec.get("contents"), dict):
        return "contents"
    if isinstance(spec.get("document"), dict):
        return "document"
    return "legacy"


def inner_body(spec: dict) -> dict:
    shape = detect_shape(spec)
    if shape == "contents":
        return spec["contents"]
    if shape == "document":
        return spec["document"]
    return spec


def parse_layout(layout: str, warn: bool = True) -> ET.Element | None:
    if not layout:
        return None
    cleaned = re.sub(r"<\?xml[^?]*\?>", "", layout).strip()
    try:
        return ET.fromstring(f"<root>{cleaned}</root>")
    except ET.ParseError as e:
        if warn:
            sys.stderr.write(f"spec_shape: layout XML failed to parse: {e}\n")
        return None


def placed_ids(root: ET.Element | None) -> set[str]:
    if root is None:
        return set()
    return {e.get("elementId") for e in root.iter() if e.get("elementId")}


def element_page_map(root: ET.Element | None) -> dict[str, str]:
    """elementId -> <Page id> for every element placed under a <Page>."""
    out: dict[str, str] = {}
    if root is None:
        return out
    for page in root.findall("Page"):
        pid = page.get("id")
        for e in page.iter():
            eid = e.get("elementId")
            if eid and eid not in out:
                out[eid] = pid
    return out


def normalize(spec: dict) -> tuple[dict, str]:
    """Return (view, shape). `view` looks like the old flat format:
    top-level name/folderId/layout/settings + pages[].elements. Extra keys:
      _flat            flat element list (current shapes) or None
      _unplaced        flat elements not referenced anywhere in the layout
      _illegal_page_elements   page ids that carry a forbidden pages[].elements
    """
    shape = detect_shape(spec)
    body = inner_body(spec)
    if shape == "legacy":
        view = dict(body)
        view["_flat"] = None
        view["_unplaced"] = []
        view["_illegal_page_elements"] = []
        return view, shape

    view = {k: v for k, v in body.items() if k != "pages"}
    view["name"] = spec.get("name")
    view["folderId"] = spec.get("folderId")
    root = parse_layout(body.get("layout", ""), warn=False)
    page_of = element_page_map(root)
    everywhere = placed_ids(root)

    pages = []
    illegal = []
    for p in body.get("pages", []) or []:
        q = dict(p)
        if "elements" in q:
            illegal.append(p.get("id"))
        q["elements"] = []
        pages.append(q)
    by_id = {p.get("id"): p for p in pages}

    flat = body.get("elements", []) or []
    unplaced, offpage = [], []
    for e in flat:
        eid = e.get("id")
        pid = page_of.get(eid)
        if pid in by_id:
            by_id[pid]["elements"].append(e)
        elif eid in everywhere:
            offpage.append(e)  # placed in a <Panel>/overlay, not on a page
        else:
            unplaced.append(e)
    if offpage:
        pages.append({"id": "_offpage", "name": "(panels/overlays)", "elements": offpage})

    view["pages"] = pages
    view["_flat"] = flat
    view["_unplaced"] = unplaced
    view["_illegal_page_elements"] = illegal
    return view, shape
