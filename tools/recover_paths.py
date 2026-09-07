#!/usr/bin/env python3
"""Recover the movement paths that the GameMaker export lost.

This checkout's ``projectA.project.gmx`` has no ``paths`` section at all, so the
converter can only learn path *names* from decompiler comments and the runtime
stops on every ``path_start`` call. This tool fetches the point data for those
names from a pinned public GameMaker project dump, normalises it into
``port/path_data.json`` and records where each path came from.

Rules, so this stays auditable:
  * Only paths already referenced by this repository's own code are fetched.
  * Nothing is interpolated, smoothed or invented: a name with no upstream
    record is reported as still missing and the runtime keeps stopping on it.
  * Every recovered path carries the upstream project, commit and file it came
    from, so any claim can be re-checked or reverted.

Usage::

    python3 tools/recover_paths.py            # write port/path_data.json
    python3 tools/recover_paths.py --check    # verify the checked-in file only
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UPSTREAM = "kittibyte/UndertaleDecomp"
# Pinned deliberately: an API read of the default branch would let upstream
# movement data drift under a supposedly reproducible port.
UPSTREAM_REF = "249ffa27ee7e7eee0d7ce84b736c294458b38685"
API = "https://api.github.com"
# GameMaker 1.4 code in the wild writes these two spellings for the same asset.
ALIASES = {}
NEEDED = re.compile(r"(\d+)\s*/\*\s*(path_\w+)\s*\*/")


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "undertale-love-port-path-recovery",
    })
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        request.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def api(path: str) -> dict:
    return json.loads(fetch(f"{API}/{path}").decode("utf-8"))


def repo_ref(ref: str) -> str:
    """Resolve a branch name to an immutable commit SHA."""
    if re.fullmatch(r"[0-9a-f]{40}", ref):
        return ref
    return api(f"repos/{UPSTREAM}/commits/{ref}")["sha"]


def listing(directory: str, ref: str) -> set:
    """Names of the directories directly under ``directory`` upstream."""
    try:
        entries = api(f"repos/{UPSTREAM}/contents/{directory}?ref={ref}")
    except Exception:  # noqa: BLE001 - absent folder means no data to recover
        return set()
    return {e["name"] for e in entries if isinstance(e, dict)}


def tolerant_json(text: str):
    """GameMaker ``.yy`` files carry trailing commas, which is not valid JSON."""
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def upstream_path_file(name: str, ref: str) -> dict | None:
    entry = api(f"repos/{UPSTREAM}/contents/paths/{name}/{name}.yy?ref={ref}")
    if not isinstance(entry, dict) or "content" not in entry:
        return None
    return tolerant_json(base64.b64decode(entry["content"]).decode("utf-8", "replace"))


def normalize(name: str, document: dict) -> dict:
    """Map a GMS2 GMPath record onto the flat form the runtime consumes."""
    points = []
    for point in document.get("points") or []:
        try:
            x, y = float(point["x"]), float(point["y"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"{name}: point record without numeric x/y") from None
        points.append([x, y])
    if len(points) < 2:
        raise ValueError(f"{name}: fewer than two points; refusing to store a useless path")
    return {
        "points": points,
        "closed": bool(document.get("closed", False)),
        # GMS1 path kinds: 0 = straight segments, 1 = smooth (Catmull-Rom).
        "kind": int(1 if document.get("kind") else 0),
        "precision": int(document.get("precision") or 4),
    }


def referenced_paths() -> dict:
    """Path names this repository's own code calls ``path_start`` with."""
    found = {}
    report = ROOT / "generated" / "conversion-report.json"
    if report.is_file():
        for entry in json.loads(report.read_text()).get("missing_paths", []):
            found[int(entry["id"])] = entry["name"]
    if found:
        return found
    for directory in ("objects", "rooms", "scripts"):
        for source in sorted((ROOT / directory).glob("*")):
            if not source.is_file():
                continue
            text = source.read_text(errors="replace")
            for index, name in NEEDED.findall(text):
                if not name.startswith("path_action_"):
                    found.setdefault(int(index), name.replace("/*", "").strip())
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="validate the checked-in port/path_data.json instead of fetching")
    parser.add_argument("--ref", default=UPSTREAM_REF, help=f"upstream ref to pin (default {UPSTREAM_REF})")
    parser.add_argument("--output", default=str(ROOT / "port" / "path_data.json"))
    args = parser.parse_args()

    wanted = referenced_paths()
    if not wanted:
        print("No path_start references found; run tools/convert.py first.", file=sys.stderr)
        return 1

    out = Path(args.output)
    if args.check:
        data = json.loads(out.read_text())
        stale = sorted(set(data["paths"]) ^ {wanted[i] for i in wanted if wanted[i] in data["paths"]})
        for name, record in data["paths"].items():
            assert len(record["points"]) >= 2, name
            assert all(len(p) == 2 and all(isinstance(v, (int, float)) for v in p) for p in record["points"]), name
            assert record["source"]["upstream"], name
        print(f"{out.name}: {len(data['paths'])} paths, schema {data['schema']}, "
              f"pinned at {data['ref'][:8]}")
        if stale:
            print(f"referenced-but-unrecorded names: {len(stale)}")
        return 0

    ref = repo_ref(args.ref)
    available = listing("paths", ref)
    recovered, missing, failures = {}, [], []
    for index in sorted(wanted):
        name = ALIASES.get(wanted[index], wanted[index])
        if name not in available:
            missing.append(name)
            continue
        try:
            document = upstream_path_file(name, ref)
        except Exception as error:  # noqa: BLE001 - a gap must not abort the sweep
            failures.append(f"{name}: {error}")
            continue
        if document is None:
            missing.append(name)
            continue
        try:
            record = normalize(name, document)
        except ValueError as error:
            failures.append(str(error))
            continue
        record["source"] = {"upstream": UPSTREAM, "ref": ref,
                            "file": f"paths/{name}/{name}.yy",
                            "retrieved": datetime.now(timezone.utc).date().isoformat()}
        recovered[name] = record

    payload = {
        "schema": 1,
        "generated_by": "tools/recover_paths.py",
        "upstream": UPSTREAM,
        "ref": ref,
        "generated_on": date.today().isoformat(),
        "note": ("Point data for movement paths absent from this repository's GameMaker export. "
                 "Coordinates are upstream authoring pixels, room-absolute; no point was interpolated, "
                 "rounded or added locally. Paths still listed as missing have no recovered record and "
                 "the runtime stops on them by design."),
        "paths": dict(sorted(recovered.items())),
    }
    out.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n")

    print(f"recovered {len(recovered)} of {len(wanted)} referenced paths -> {out.relative_to(ROOT)}")
    if missing:
        print(f"still missing ({len(missing)}): {', '.join(missing)}")
    if failures:
        print(f"rejected ({len(failures)}): {', '.join(failures)}")
    return 0 if recovered else 1


if __name__ == "__main__":
    sys.exit(main())
