#!/usr/bin/env python3
"""Recover original asset IDs that Undertale keeps inside instance arrays.

This checkout's decompiled events fill instance arrays with *bare* original
asset IDs and read them back through a computed index::

    facespr[1]= 881;                          # obj_shopmouth1 Create
    ...
    draw_sprite(facespr[global.faceemotion], ...)   # obj_shopmouth1 Draw

No decompiler annotation covers those literals, so the converter leaves the
target sprites/backgrounds on synthetic IDs and every use stops with
``Unresolved sprite ID 881``. In the Snowdin shop (room 311) that is the
shopkeeper's emotion faces: ``facespr[global.faceemotion]`` never resolves, the
face never draws, and the mouth stays floating over the default two-eye frame.
The same class covers ``obj_shop1`` (a second, unreferenced ``facespr``), the
Asgore body-part ``part`` sprites, and three ``background_index`` slots.

Rules, so this stays auditable (the same contract as ``tools/recover_parts.py``):

  * IDs come only from this repository's own numeric literals. The pinned dump
    contributes names, never numbers: its numbered asset lists are a different
    ID space and stay audit-only (see ``tools/recover_registry.py``).
  * A site is only paired when the local event and the upstream event agree
    structurally: the same variable, the same subscripts in the same statement
    order. For the GameMaker-Studio-2 ``background_index_set(slot, bg)``
    spelling of the GM1.4 ``background_index[slot]`` array, the one setter for
    the slot must line up with the one local slot assignment.
  * Every pair records the local file+event+statement and the upstream
    file+statement, so any claim can be re-checked or reverted. ``--check``
    re-verifies the checked-in file without network.

Usage::

    python3 tools/recover_asset_arrays.py            # write port/recovered_asset_arrays.json
    python3 tools/recover_asset_arrays.py --check    # verify the checked-in file only
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gml import compile_gml, walk

ROOT = Path(__file__).resolve().parents[1]

UPSTREAM = "kittibyte/UndertaleDecomp"
# Pinned deliberately: the same immutable commit already used by
# tools/recover_registry.py, tools/recover_paths.py and tools/recover_parts.py,
# so one ref backs every recovered datum in this port.
UPSTREAM_REF = "249ffa27ee7e7eee0d7ce84b736c294458b38685"
API = "https://api.github.com"

# GameMaker 1.4 event type:subtype -> GMS2 event-file name of the pinned
# upstream project. Only the kinds the asset-array pattern occurs in are
# mapped; a site in any other kind raises instead of being skipped.
UPSTREAM_EVENT = {
    "0": "Create_{n}", "1": "Destroy_{n}", "2": "Alarm_{n}",
    "3": "Step_{n}", "7": "Other_{n}", "8": "Draw_{n}", "12": "CleanUp_0",
    "5": "Keyboard_{n}", "6": "Mouse_{n}",
    "9": "KeyPress_{n}", "10": "KeyRelease_{n}",
}

# Engine-consumed arrays: their value is drawn by the engine, not by a
# draw_* call in the code, so they qualify as asset arrays without a read site.
ENGINE_ARRAYS = {"background_index": "backgrounds"}

# Calls whose first argument is an original *sprite* ID, so a variable read
# through an index in that position consumes a sprite array.
SPRITE_ARG_CALLS = ("draw_sprite", "sprite_replace", "sprite_get_width",
                    "sprite_get_height", "sprite_exists")


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "undertale-love-port-asset-array-recovery",
    })
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        request.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def numeric_lit(node):
    if node is None or not isinstance(node, tuple):
        return None
    if node[0] == "number":
        try:
            v = float(node[1])
            return int(v) if v.is_integer() else v
        except (ValueError, OverflowError):
            return None
    if node[0] == "unary" and node[1] == "-" and node[2][0] == "number":
        inner = numeric_lit(node[2])
        return -inner if inner is not None else None
    return None


def local_events() -> dict[tuple[str, str], str]:
    """Every decompiled object event of this checkout, keyed by (object, event)."""
    events: dict[tuple[str, str], str] = {}
    for path in sorted((ROOT / "objects").glob("*.object.gmx")):
        name = path.name.split(".")[0]
        for ev in ET.parse(path).findall("events/event"):
            key = ev.get("eventtype") + ":" + ev.get("enumb", ev.get("ename", "0"))
            lines = [s.text or "" for a in ev.findall("action")
                     for s in a.findall("arguments/argument/string")]
            events[(name, key)] = "\n".join(lines)
    return events


def resource_categories() -> dict[str, str]:
    project = ET.fromstring((ROOT / "projectA.project.gmx").read_text(errors="replace"))
    categories = {}
    for category, (tag, suffix) in {
        "sprites": ("sprite", ".sprite.gmx"), "objects": ("object", ".object.gmx"),
        "rooms": ("room", ".room.gmx"), "scripts": ("script", ""),
        "sounds": ("sound", ".sound.gmx"), "backgrounds": ("background", ".background.gmx"),
        "fonts": ("font", ".font.gmx")}.items():
        for e in project.findall(".//" + tag):
            p = Path(e.text.replace("\\", "/") + suffix)
            categories[p.name.split(".")[0]] = category
    return categories


def is_asset_array_var(var: str, readvar: set[str]) -> tuple[bool, str]:
    if var in ENGINE_ARRAYS:
        return True, ENGINE_ARRAYS[var]
    if var in readvar:
        return True, "sprites"
    return False, ""


def index_read_vars(events) -> set[str]:
    """Variable names index-read as the sprite argument of a draw/sprite call.

    Computed- and literal-index reads both count: the converter cannot see a
    literal value stored in the array either way.
    """
    readvar: set[str] = set()
    for code in events.values():
        if not code.strip():
            continue
        try:
            ast = compile_gml(code)[1]
        except Exception:  # noqa: BLE001 - an unparseable event is handled elsewhere
            continue
        for n in walk(ast):
            if n[0] == "call" and n[1][0] == "name" and n[1][1].startswith(SPRITE_ARG_CALLS[:1]):
                name = n[1][1]
                if any(name.startswith(c) for c in ("draw_sprite",)) or name in SPRITE_ARG_CALLS:
                    args = n[2]
                    if args and args[0][0] == "index" and args[0][1][0] == "name":
                        readvar.add(args[0][1][1])
    return readvar


def asset_assignments(code: str) -> dict[str, list[tuple[int, int, str]]]:
    """variable -> ordered [(subscript, value, statement)] for ``var[i]= <lit>;``."""
    try:
        ast = compile_gml(code)[1]
    except Exception:  # noqa: BLE001 - an unparseable event has no auditable array sites
        return {}
    out: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    for n in walk(ast):
        if n[0] != "assign" or len(n) < 4 or not isinstance(n[2], tuple) or n[2][0] != "index":
            continue
        ref = n[2]
        if ref[1][0] != "name" or len(ref[2]) != 1:
            continue
        subscript, value = numeric_lit(ref[2][0]), numeric_lit(n[3])
        if subscript is None or value is None:
            continue
        statement = _statement(n)
        out[ref[1][1]].append((subscript, int(value), statement))
    return out


def _statement(node) -> str:
    """Canonical statement text for an assign node (provenance only).

    Parsed nodes carry no source offsets, so the statement is rebuilt from the
    node; ``--check`` matches it against the raw source with a tolerant regex.
    """
    ref = node[2]
    var = ref[1][1]
    subscript = numeric_lit(ref[2][0])
    value = numeric_lit(node[3])
    return f"{var}[{subscript}]= {value};"


def upstream_event_file(name: str, event_key: str) -> str:
    kind, number = event_key.split(":", 1)
    template = UPSTREAM_EVENT.get(kind)
    if template is None:
        raise ValueError(f"{name} event {event_key}: no upstream event-file mapping for kind {kind}; extend UPSTREAM_EVENT first")
    return f"objects/{name}/" + template.format(n=number) + ".gml"


def upstream_event(name: str, event_key: str) -> str:
    entry = json.loads(fetch(f"{API}/repos/{UPSTREAM}/contents/{upstream_event_file(name, event_key)}?ref={UPSTREAM_REF}").decode("utf-8"))
    if "content" not in entry:
        raise ValueError(f"upstream {upstream_event_file(name, event_key)}: {entry.get('message', 'not found')}")
    return base64.b64decode(entry["content"]).decode("utf-8", "replace").replace("\r\n", "\n")


# Upstream (GMS2) spellings of the same statements.
UP_ARRAY_ASSIGN = re.compile(r"\b([A-Za-z_]\w*)\[(\d+)\]\s*=\s*([A-Za-z_]\w*)\s*(?=[;)\n]|//|$)")
UP_BG_SET = re.compile(r"\bbackground_index_set\s*\(\s*(\d+)\s*,\s*([A-Za-z_]\w*)\s*\)")
LOCAL_ARRAY_ASSIGN = re.compile(r"\b([A-Za-z_]\w*)\[(\d+)\]\s*=\s*(-?\d+)\s*;")
LOCAL_BG_SET = re.compile(r"\bbackground_index\[(\d+)\]\s*=\s*(-?\d+)\s*;")


def pair_site(name: str, key: str, var: str,
              local_assigns: list[tuple[int, int, str]], upstream_code: str) -> dict[int, tuple[int, str, str, str]]:
    """Pair one variable's literal array block in this event against upstream names.

    Returns {subscript: (value, local_statement, upstream_name, upstream_statement)}.
    The whole block is compared at once: every local subscript must have exactly
    one upstream counterpart at the same subscript. Any structural disagreement
    raises, so a drifted source export can never be silently paired.
    """
    local_by_index: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for subscript, value, statement in local_assigns:
        local_by_index[subscript].append((value, statement))
    result: dict[int, tuple[int, str, str, str]] = {}

    if var == "background_index":
        up_by_slot: dict[int, list[tuple[str, str]]] = defaultdict(list)
        for slot, bg in UP_BG_SET.findall(upstream_code):
            stmt = _statement_of(upstream_code, rf"\bbackground_index_set\s*\(\s*{slot}\s*,\s*[A-Za-z_]\w*\s*\)")
            up_by_slot[int(slot)].append((bg, stmt))
    else:
        up_by_slot = defaultdict(list)
        for vname, slot, uname in UP_ARRAY_ASSIGN.findall(upstream_code):
            if vname != var:
                continue
            stmt = _statement_of(upstream_code, rf"\b{re.escape(var)}\[\s*{slot}\s*\]\s*=\s*[A-Za-z_]\w*")
            up_by_slot[int(slot)].append((uname, stmt))

    for slot, local_list in local_by_index.items():
        if len(local_list) != 1:
            raise ValueError(f"{name} {key}: {var}[{slot}] assigned {len(local_list)}x locally; refusing to pair")
        up_list = up_by_slot.get(slot, [])
        if len(up_list) != 1:
            raise ValueError(f"{name} {key}: {var}[{slot}] has no single upstream counterpart "
                             f"({len(up_list)} found); refusing to pair")
        value, statement = local_list[0]
        uname, up_stmt = up_list[0]
        result[slot] = (value, statement, uname, up_stmt)
    # Upstream subscripts with no local counterpart would hide a drift.
    for slot, up_list in up_by_slot.items():
        if slot not in local_by_index and up_list:
            raise ValueError(f"{name} {key}: upstream assigns {var}[{slot}] that this checkout has "
                             f"no local counterpart for; refusing to pair")
    return result


def _statement_of(code: str, pattern: str) -> str:
    m = re.search(pattern, code)
    return m.group(0) if m else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="validate the checked-in port/recovered_asset_arrays.json instead of fetching")
    args = parser.parse_args()

    events = local_events()
    categories = resource_categories()
    readvar = index_read_vars(events)
    out = ROOT / "port" / "recovered_asset_arrays.json"

    if args.check:
        return check(out, events, categories, readvar)

    # Discover candidate sites: object events that assign a literal into an
    # asset-array variable.
    blocks: dict[tuple[str, str, str], list[dict]] = {}
    for (name, key), code in sorted(events.items()):
        if not code.strip():
            continue
        for var, assigns in asset_assignments(code).items():
            ok, category = is_asset_array_var(var, readvar)
            if not ok:
                continue
            for subscript, value, statement in assigns:
                site = {"object": name, "event": key, "variable": var, "index": subscript,
                        "value": value, "category": category}
                blocks.setdefault((name, key, var), []).append(site)

    pairs: dict[str, dict] = {}
    for (name, key, var), sites in sorted(blocks.items()):
        category = sites[0]["category"]
        try:
            upstream_code = upstream_event(name, key)
        except Exception as error:  # noqa: BLE001 - a gap must not abort the sweep silently
            print(f"error fetching upstream {name} {key}: {error}", file=sys.stderr)
            return 1
        local_assigns = asset_assignments(events[(name, key)]).get(var, [])
        try:
            matched = pair_site(name, key, var, local_assigns, upstream_code)
        except ValueError as error:
            raise SystemExit(f"refusing to pair {name} {key} {var}: {error}")
        for site in sites:
            (value, _statement, uname, up_stmt) = matched[site["index"]]
            if categories.get(uname) != category:
                raise SystemExit(f"{name} {key}: upstream names {uname} for {var}[{site['index']}], "
                                 f"which is not a local {category} resource")
            record = pairs.setdefault(uname, {"category": category, "id": value, "sites": []})
            if record["id"] != value:
                raise SystemExit(f"{uname}: sites disagree ({record['id']} vs {value})")
            entry = {"object": name, "event": key, "variable": var, "index": site["index"],
                     "file": f"objects/{name}.object.gmx",
                     "upstream_file": upstream_event_file(name, key),
                     "upstream_statement": up_stmt}
            if entry not in record["sites"]:
                record["sites"].append(entry)

    payload = {
        "schema": 1,
        "generated_by": "tools/recover_asset_arrays.py",
        "upstream": UPSTREAM,
        "ref": UPSTREAM_REF,
        "generated_on": date.today().isoformat(),
        "note": (
            "Original sprite/background IDs that the decompiler kept as bare literals inside instance "
            "arrays (var[i]= <id> read back through a computed index), which no decompiler annotation "
            "covers. Each ID is this checkout's own numeric literal; only the asset name is paired from "
            "the pinned upstream decompilation of the same game state, after both events were checked to "
            "assign the same variable at the same subscripts. The GM1.4 background_index[i] array is "
            "paired with the GMS2 background_index_set(i, ...) spelling. No number was taken from the "
            "pinned dump; its numbered lists remain audit-only in tools/recover_registry.py."
        ),
        "pairs": dict(sorted(pairs.items())),
    }
    out.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n")
    ids = {n: r["id"] for n, r in pairs.items()}
    print(f"recovered {len(pairs)} asset-array IDs across {sum(len(r['sites']) for r in pairs.values())} "
          f"sites -> {out.relative_to(ROOT)}")
    for name in sorted(pairs):
        where = ", ".join(f"{s['object']}/{s['variable']}[{s['index']}]" for s in pairs[name]["sites"][:3])
        print(f"  {pairs[name]['id']:>5} {pairs[name]['category']:<11} {name}  ({where}{'…' if len(pairs[name]['sites']) > 3 else ''})")
    return 0


def check(out: Path, events, categories, readvar) -> int:
    data = json.loads(out.read_text())
    assert data["upstream"] == UPSTREAM and data["ref"] == UPSTREAM_REF, "pinned upstream drifted"
    seen: dict[tuple[str, int], str] = {}
    for name, record in data["pairs"].items():
        category = record["category"]
        assert categories.get(name) == category, f"{name}: not a local {category} resource"
        assert isinstance(record["id"], int) and 0 <= record["id"] < 10000, name
        assert record["sites"], f"{name} has no evidence sites"
        other = seen.setdefault((category, record["id"]), name)
        assert other == name, f"ID {record['id']} ({category}) claimed by both {other} and {name}"
        for site in record["sites"]:
            code = events.get((site["object"], site["event"]))
            assert code is not None, f"site {site['object']} {site['event']} no longer exists locally"
            assert re.search(rf"\b{site['variable']}\[{site['index']}\]\s*=\s*{record['id']}\s*;", code), \
                f"{name}: id {record['id']} is not a {site['variable']}[{site['index']}] literal in {site['object']} {site['event']}"
            assert site["upstream_file"].startswith(f"objects/{site['object']}/"), site
    # Nothing left behind: every local asset-array literal site is covered.
    covered: set[tuple[str, int]] = {(r["category"], r["id"]) for r in data["pairs"].values()}
    uncovered = []
    for (name, key), code in sorted(events.items()):
        if not code.strip():
            continue
        for var, assigns in asset_assignments(code).items():
            ok, category = is_asset_array_var(var, readvar)
            if not ok:
                continue
            for subscript, value, _statement in assigns:
                if (category, value) not in covered:
                    uncovered.append(f"{name} {key} {var}[{subscript}]={value}")
    assert not uncovered, f"asset-array literal sites still unresolved but absent from the checked-in pairs: {uncovered}"
    print(f"{out.name}: {len(data['pairs'])} asset-array IDs, all "
          f"{sum(len(r['sites']) for r in data['pairs'].values())} sites resolve; pinned at {data['ref'][:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
