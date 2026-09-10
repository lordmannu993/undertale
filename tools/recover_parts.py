#!/usr/bin/env python3
"""Recover original object IDs for the monster body-part spawn variables.

Battles beyond the Ruins spawn their monster artwork through local variables
that this checkout's decompiled events fill with bare original object IDs::

    part2= 255;
    mypart2= instance_create(x, y, part2);

No decompiler annotation covers those literals, so the converter leaves the part
objects on synthetic IDs and every battle that spawns one stops with
``instance_create Missing original object ID`` — e.g. the first Snowdin
encounter (battlegroup 30, Snowdrake) stops on ID 255. The pinned upstream
decompilation of the same game state spells the same statements with object
*names* (``part2 = obj_drakebody``), so each literal can be paired with a name.

Rules, so this stays auditable:

  * IDs come only from this repository's own numeric literals. The pinned dump
    contributes names, never numbers: its numbered asset lists are a different
    ID space and stay audit-only (see ``tools/recover_registry.py``).
  * A site is only paired when the local event and the upstream event agree
    structurally: the same ``partN`` variables, assigned in the same statement
    order, and passed to ``instance_create`` in the same order.
  * Sites whose ID the converter already recovered from its own ``N/* name */``
    annotations must agree with the upstream name ("anchors"). A disagreeing
    anchor aborts the sweep instead of importing anything.
  * Every pair and anchor records the local file+event, the variable and the
    upstream file it was verified against, so any claim can be re-checked or
    reverted. ``--check`` re-verifies the checked-in file without network.

Usage::

    python3 tools/recover_parts.py            # write port/recovered_parts.json
    python3 tools/recover_parts.py --check    # verify the checked-in file only
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
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UPSTREAM = "kittibyte/UndertaleDecomp"
# Pinned deliberately: the same immutable commit already used by
# tools/recover_registry.py and tools/recover_paths.py, so one ref backs every
# recovered datum in this port.
UPSTREAM_REF = "249ffa27ee7e7eee0d7ce84b736c294458b38685"
API = "https://api.github.com"

# GameMaker 1.4 event types that the part-variable pattern appears in, mapped to
# the GMS2 event-file names of the pinned upstream project.
UPSTREAM_EVENT = {"0": "Create_{n}", "1": "Destroy_{n}", "2": "Alarm_{n}"}

LOCAL_ASSIGN = re.compile(r"\b(part\d+)\s*=\s*(-?\d+)\s*;")
LOCAL_CREATE = re.compile(r"instance_create\s*\([^;]*?,\s*(part\d+)\s*\)")
LOCAL_ASSIGN_ANY = re.compile(r"\b(part\d+)\s*=")
UP_ASSIGN_NAME = re.compile(r"\b(part\d+)\s*=\s*([A-Za-z_]\w*)\s*(?=[;)\n]|$)", re.M)
UP_ASSIGN_ANY = re.compile(r"\b(part\d+)\s*=")
UP_CREATE = re.compile(r"instance_create\s*\([^;]*?,\s*(part\d+)\s*\)")
# Same annotation passes the converter runs first; used for anchor verification.
ANNOTATION = re.compile(r"(-?\d+)\s*/\*\s*(\w+)\s*\*/")
WITH_ANNOTATION = re.compile(r"//\s*(\w+)\s*\n\s*with\((\d+)\)")


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "undertale-love-port-part-recovery",
    })
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        request.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def upstream_event(name: str, event_key: str) -> str:
    kind, number = event_key.split(":", 1)
    template = UPSTREAM_EVENT.get(kind)
    if template is None:
        raise ValueError(f"{name} event {event_key}: no upstream event-file mapping; extend UPSTREAM_EVENT first")
    path = f"objects/{name}/" + template.format(n=number) + ".gml"
    entry = json.loads(fetch(f"{API}/repos/{UPSTREAM}/contents/{path}?ref={UPSTREAM_REF}").decode("utf-8"))
    return base64.b64decode(entry["content"]).decode("utf-8", "replace").replace("\r\n", "\n")


def local_events() -> dict[tuple[str, str], str]:
    """Every decompiled object event of this checkout, keyed by (object, event)."""
    events: dict[tuple[str, str], str] = {}
    for path in sorted((ROOT / "objects").glob("*.object.gmx")):
        name = path.name.split(".")[0]
        for ev in ET.parse(path).findall("events/event"):
            key = ev.get("eventtype") + ":" + ev.get("enumb", ev.get("ename", "0"))
            lines = []
            for action in ev.findall("action"):
                lines += [s.text or "" for s in action.findall("arguments/argument/string")]
            events[(name, key)] = "\n".join(lines)
    return events


def extra_code() -> list[str]:
    """Script and room code the converter also scans for annotations."""
    chunks = [path.read_text(errors="replace") for path in sorted((ROOT / "scripts").glob("*.gml"))]
    for path in sorted((ROOT / "rooms").glob("*.room.gmx")):
        text = path.read_text(errors="replace")
        for match in re.finditer(r'<code>(.*?)</code>', text, re.S):
            chunks.append(match.group(1))
        for match in re.finditer(r'code="([^"]*)"', text):
            chunks.append(match.group(1))
    return chunks


def annotation_ids(events: dict[tuple[str, str], str]) -> dict[str, int]:
    """Object IDs the converter recovers from its own decompiler annotations."""
    names = {p.name.split(".")[0] for p in (ROOT / "objects").glob("*.object.gmx")}
    found: dict[str, int] = {}

    def add(name: str, index: int) -> None:
        if name not in names:
            return
        existing = found.get(name)
        if existing is not None and existing != index:
            raise ValueError(f"annotation conflict in checkout: {name} = {existing} and {index}")
        found[name] = index

    for (_, _), code in events.items():
        for index, name in ANNOTATION.findall(code):
            add(name, int(index))
        for name, index in WITH_ANNOTATION.findall(code):
            add(name, int(index))
    for code in extra_code():
        for index, name in ANNOTATION.findall(code):
            add(name, int(index))
        for name, index in WITH_ANNOTATION.findall(code):
            add(name, int(index))
    return found


def part_sites(events: dict[tuple[str, str], str]) -> dict[tuple[str, str], list[str]]:
    """Events that pass a literal-assigned part variable to instance_create."""
    sites: dict[tuple[str, str], list[str]] = {}
    for (name, key), code in events.items():
        assigned = {var for var, _ in LOCAL_ASSIGN.findall(code)}
        created = set(LOCAL_CREATE.findall(code))
        if assigned & created:
            sites[(name, key)] = sorted(assigned & created)
    return sites


def occurrences(code: str, pattern_any: re.Pattern, pattern_pair: re.Pattern) -> dict[str, list]:
    """Ordered assignment occurrences per variable: literal/name payloads or None."""
    spans = {m.group(1): [] for m in pattern_any.finditer(code)}
    for match in pattern_any.finditer(code):
        pair = pattern_pair.match(code, match.start())
        spans[match.group(1)].append(pair.group(2) if pair else None)
    return spans


def pair_site(name: str, key: str, local_code: str, upstream_code: str) -> list[tuple[str, int, str]]:
    """Pair this checkout's literal part IDs with the upstream names.

    Returns (variable, id, name) triples for every literal assignment. Anchors
    (IDs the converter already recovers from its own annotations) are separated
    by the caller. Any structural disagreement raises, so a drifted source
    export can never be silently paired.
    """
    local_created = LOCAL_CREATE.findall(local_code)
    upstream_created = UP_CREATE.findall(upstream_code)
    if local_created != upstream_created:
        raise ValueError(f"{name} {key}: instance_create part order differs from upstream "
                         f"({local_created} vs {upstream_created}); refusing to pair")
    local_occ = occurrences(local_code, LOCAL_ASSIGN_ANY, LOCAL_ASSIGN)
    upstream_occ = occurrences(upstream_code, UP_ASSIGN_ANY, UP_ASSIGN_NAME)
    if set(local_occ) != set(upstream_occ):
        raise ValueError(f"{name} {key}: part variables differ from upstream "
                         f"({sorted(local_occ)} vs {sorted(upstream_occ)}); refusing to pair")
    pairs = []
    for var in sorted(local_occ):
        if len(local_occ[var]) != len(upstream_occ[var]):
            raise ValueError(f"{name} {key}: {var} has {len(local_occ[var])} local assignments "
                             f"but {len(upstream_occ[var])} upstream; refusing to pair")
        for local_value, upstream_value in zip(local_occ[var], upstream_occ[var]):
            if local_value is None and upstream_value is None:
                continue  # e.g. part1= scr_marker(...) on both sides
            if local_value is None or upstream_value is None:
                raise ValueError(f"{name} {key}: {var} literal {local_value} does not line up with "
                                 f"upstream name {upstream_value}; refusing to pair")
            pairs.append((var, int(local_value), upstream_value))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="validate the checked-in port/recovered_parts.json instead of fetching")
    args = parser.parse_args()

    events = local_events()
    sites = part_sites(events)
    known = annotation_ids(events)
    out = ROOT / "port" / "recovered_parts.json"

    def local_site_object(object_name: str, event_key: str, variable: str, object_id: int) -> None:
        code = events.get((object_name, event_key))
        if code is None:
            raise ValueError(f"recorded site {object_name} {event_key} no longer exists locally")
        if not re.search(rf"\b{variable}\s*=\s*{object_id}\s*;", code):
            raise ValueError(f"{object_name} {event_key}: recorded id {object_id} for {variable} is not in the local source")
        if not re.search(rf"instance_create\s*\([^;]*?,\s*{variable}\s*\)", code):
            raise ValueError(f"{object_name} {event_key}: {variable} is never passed to instance_create")

    if args.check:
        data = json.loads(out.read_text())
        assert data["upstream"] == UPSTREAM and data["ref"] == UPSTREAM_REF, "pinned upstream drifted"
        seen_ids, seen_names = {}, {}
        for group in ("pairs", "anchors"):
            for name, record in data[group].items():
                assert (ROOT / f"objects/{name}.object.gmx").is_file(), f"{name}: not a local object"
                for site in record["sites"]:
                    local_site_object(site["object"], site["event"], site["variable"], record["id"])
                other = seen_ids.setdefault(record["id"], name)
                assert other == name, f"id {record['id']} claimed by both {other} and {name}"
                other = seen_names.setdefault(name, record["id"])
                assert other == record["id"], f"{name} claimed ids {other} and {record['id']}"
                if group == "anchors":
                    assert known.get(name) == record["id"], f"anchor {name}={record['id']} no longer matches the checkout annotations"
                else:
                    assert known.get(name) in (None, record["id"]), f"pair {name}={record['id']} conflicts with checkout annotations"
        # Nothing left behind: every literal part target resolves via annotations or a pair.
        covered = {name: record["id"] for name, record in data["pairs"].items()}
        for (name, key) in sites:
            code = events[(name, key)]
            for var, value in LOCAL_ASSIGN.findall(code):
                if var not in set(LOCAL_CREATE.findall(code)):
                    continue
                object_id = int(value)
                if object_id in covered.values() or object_id in known.values():
                    continue
                raise ValueError(f"{name} {key}: {var}={object_id} still unresolved but absent from the checked-in pairs")
        print(f"{out.name}: {len(data['pairs'])} pairs, {len(data['anchors'])} anchors, "
              f"all {len(sites)} part sites resolve; pinned at {data['ref'][:8]}")
        return 0

    recovered: dict[str, dict] = {}
    anchors: dict[str, dict] = {}
    for (name, key) in sorted(sites):
        try:
            upstream_code = upstream_event(name, key)
        except Exception as error:  # noqa: BLE001 - a gap must not abort the sweep silently
            print(f"error fetching upstream {name} {key}: {error}", file=sys.stderr)
            return 1
        for var, object_id, part_name in pair_site(name, key, events[(name, key)], upstream_code):
            if not (ROOT / f"objects/{part_name}.object.gmx").is_file():
                raise ValueError(f"{name} {key}: upstream names {part_name}, which is absent from this checkout")
            site = {"object": name, "event": key, "variable": var,
                    "file": f"objects/{name}.object.gmx",
                    "upstream_file": f"objects/{name}/{UPSTREAM_EVENT[key.split(':')[0]].format(n=key.split(':')[1])}.gml"}
            target = anchors if known.get(part_name) is not None else recovered
            record = target.setdefault(part_name, {"id": object_id, "sites": []})
            if record["id"] != object_id:
                raise ValueError(f"{part_name}: sites disagree ({record['id']} vs {object_id})")
            if known.get(part_name) not in (None, object_id):
                raise ValueError(f"{part_name}: upstream pairing says {object_id} but checkout annotations say {known[part_name]}")
            record["sites"].append(site)
    for part_name, record in anchors.items():
        if known.get(part_name) != record["id"]:
            raise ValueError(f"anchor {part_name}: pairing says {record['id']} but annotations say {known.get(part_name)}")

    payload = {
        "schema": 1,
        "generated_by": "tools/recover_parts.py",
        "upstream": UPSTREAM,
        "ref": UPSTREAM_REF,
        "generated_on": date.today().isoformat(),
        "note": (
            "Original object IDs for monster body-part spawn variables that the decompiler left as bare "
            "literals (partN= <id> before instance_create). Each ID is this checkout's own numeric literal; "
            "only the object name is paired from the pinned upstream decompilation of the same game state, "
            "after both events were checked to assign the same part variables in the same statement order. "
            "Anchors re-verify IDs the converter already recovers from its own annotations. No number was "
            "taken from the pinned dump; its numbered lists remain audit-only in tools/recover_registry.py."
        ),
        "pairs": dict(sorted(recovered.items())),
        "anchors": dict(sorted(anchors.items())),
    }
    out.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n")
    print(f"recovered {len(recovered)} part object IDs, verified {len(anchors)} anchors -> {out.relative_to(ROOT)}")
    for name, record in sorted(recovered.items()):
        where = ", ".join(f"{s['object']}/{s['variable']}" for s in record["sites"][:3])
        print(f"  {record['id']:>4} {name}  ({where}{'…' if len(record['sites']) > 3 else ''})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
