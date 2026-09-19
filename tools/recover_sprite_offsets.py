#!/usr/bin/env python3
"""Recover the original canvas offsets of this checkout's cropped sprite images.

The decompiled Undertale tree in this checkout exports every sprite image
*cropped to its collision bounding box*: ``sprites/spr_riverman.sprite.gmx``
declares ``width`` 27 and ``bbox_left`` 1, ``bbox_right`` 27, so the PNG holds
the 27x42 art while the original canvas was 29x42 with the art one pixel in.
Events keep drawing with the original canvas coordinates and origins
(``draw_sprite(sprite_index, image_index, x, y)`` with ``xorig`` = 0), so every
cropped sprite lands ``(bbox_left, bbox_top)`` pixels off its intended place.

That misplacement is what made the Snowdin shopkeeper show a second pair of
eyes and a floating mouth (its body is cropped 9 rows above the separate eyes
and mouth sprites it is composed with) and what floats the River Person's boat
cover above the water it is meant to sit in, so the offsets are worth pinning
properly instead of nudging each room.

What counts as evidence, so this stays auditable:

  * A sprite is a candidate when its own export is self-inconsistent: the bbox
    cannot fit inside the exported image, or the art does not start at the
    bbox corner. Imported offsets are never invented for sprites that are not
    candidates.
  * The offset comes from the pinned upstream project's frame metadata (same
    repository and commit as ``tools/recover_parts.py``), and only when the
    upstream bbox equals this checkout's bbox *and* both edges agree:
    ``bbox_left - art_left == bbox_right - art_right`` (and the same for the
    vertical axis), with the canvas large enough to contain the image.
  * Every candidate that fails those checks is listed in the file's
    ``unresolved`` list with the reason, so nothing is silently dropped and a
    later revision can extend the rule deliberately.

Usage::

    python3 tools/recover_sprite_offsets.py                 # write port/sprite_offsets.json
    python3 tools/recover_sprite_offsets.py --check         # verify the checked-in file, no network
    python3 tools/recover_sprite_offsets.py --cache FILE    # reuse/renew fetched upstream metadata
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pngalpha import alpha_bbox, png_size  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "port/sprite_offsets.json"

UPSTREAM = "kittibyte/UndertaleDecomp"
# The same immutable commit already pinned by tools/recover_parts.py,
# tools/recover_paths.py and tools/recover_registry.py.
UPSTREAM_REF = "249ffa27ee7e7eee0d7ce84b736c294458b38685"
API = "https://api.github.com"

RULE = (
    "offset = (bbox_left - art_left, bbox_top - art_top) from the original canvas, "
    "accepted only when this checkout's bbox equals the pinned upstream frame bbox, "
    "both canvas edges agree on the offset, and the canvas contains the exported image"
)

GMX_FIELD = re.compile(r"<{0}>(-?\d+)</{0}>")


def field(text: str, key: str) -> int | None:
    match = GMX_FIELD = re.compile(r"<%s>(-?\d+)</%s>" % (key, key)).search(text)
    return int(match.group(1)) if match else None


def frame_paths(text: str) -> list[str]:
    return [m.replace("\\", "/") for m in re.findall(r'<frame index="\d+">images\\([^<]+)</frame>', text)]


def local_sprite(name: str) -> dict | None:
    """Local canvas facts for one sprite: gmx fields, PNG size and art bbox."""
    path = ROOT / "sprites" / f"{name}.sprite.gmx"
    if not path.exists():
        return None
    text = path.read_text(errors="replace")
    record = {key: field(text, key) for key in
              ("width", "height", "bbox_left", "bbox_right", "bbox_top", "bbox_bottom")}
    if any(record[key] is None for key in record):
        return None
    frames = frame_paths(text)
    if not frames:
        return None
    image = ROOT / "sprites" / "images" / frames[0]
    if not image.exists():
        return None
    record["png"] = list(png_size(image))
    record["art"] = list(alpha_bbox(image)) if alpha_bbox(image) else None
    record["file"] = frames[0]
    return record


def candidates() -> dict[str, dict]:
    """Sprites whose export cannot be the canvas their bbox describes."""
    found: dict[str, dict] = {}
    for path in sorted((ROOT / "sprites").glob("*.sprite.gmx")):
        name = path.name[: -len(".sprite.gmx")]
        record = local_sprite(name)
        if not record or record["art"] is None:
            continue
        width, height = record["width"], record["height"]
        left, right, top, bottom = (record["bbox_left"], record["bbox_right"],
                                    record["bbox_top"], record["bbox_bottom"])
        art = record["art"]
        clipped = right >= width or bottom >= height
        shifted = left != art[0] or top != art[1]
        if clipped or shifted:
            found[name] = record
    return found


def fetch_upstream(name: str, attempts: int = 4) -> dict | str:
    """Frame metadata of the pinned upstream project for one sprite."""
    url = f"{API}/repos/{UPSTREAM}/contents/sprites/{name}/{name}.yy?ref={UPSTREAM_REF}"
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "undertale-love-port-sprite-offset-recovery",
    })
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        request.add_header("Authorization", f"token {token}")
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                text = base64.b64decode(json.loads(response.read().decode("utf-8"))["content"]).decode("utf-8", "replace")
            values = {key: field(text, key) for key in
                      ("width", "height", "bbox_left", "bbox_right", "bbox_top", "bbox_bottom")}
            if any(values[key] is None for key in values):
                return "missing-fields"
            return values
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return "not-in-upstream"
            if error.code in (403, 429):
                time.sleep(5 * (attempt + 1))
                continue
            return f"http-{error.code}"
        except Exception:  # noqa: BLE001 - reported as a reason, never guessed
            time.sleep(2 * (attempt + 1))
    return "fetch-failed"


def decide(name: str, local: dict, upstream: dict) -> tuple[dict | None, str | None]:
    """Apply the acceptance gates; return the record or the rejection reason."""
    width, height = local["width"], local["height"]
    left, right, top, bottom = (local["bbox_left"], local["bbox_right"],
                                local["bbox_top"], local["bbox_bottom"])
    art = local["art"]
    canvas = (upstream["width"], upstream["height"])
    up_bbox = (upstream["bbox_left"], upstream["bbox_top"], upstream["bbox_right"], upstream["bbox_bottom"])
    if (left, top, right, bottom) != up_bbox:
        return None, "bbox-differs-from-upstream"
    horizontal = {upstream["bbox_left"] - art[0], upstream["bbox_right"] - art[2]}
    vertical = {upstream["bbox_top"] - art[1], upstream["bbox_bottom"] - art[3]}
    if len(horizontal) != 1 or len(vertical) != 1:
        return None, "two-sided-disagreement"
    ox, oy = horizontal.pop(), vertical.pop()
    if canvas[0] < ox + width or canvas[1] < oy + height:
        return None, "canvas-too-small"
    if upstream["bbox_right"] >= canvas[0] or upstream["bbox_bottom"] >= canvas[1]:
        return None, "bbox-outside-canvas"
    if (ox, oy) == (0, 0):
        return None, "zero-offset"
    return {
        "ox": ox, "oy": oy,
        "canvas": [canvas[0], canvas[1]],
        "gmx_bbox": [left, top, right, bottom],
        "up_bbox": list(up_bbox),
        "png": local["png"],
        "art": art,
    }, None


def build(cache_path: Path | None) -> dict:
    pool = candidates()
    cache: dict[str, dict | str] = {}
    if cache_path and cache_path.exists():
        for name, entry in json.loads(cache_path.read_text()).items():
            if isinstance(entry, dict) and "bbox" in entry:
                box = entry["bbox"]
                entry = {"width": entry["width"], "height": entry["height"],
                         "bbox_left": box[0], "bbox_top": box[1],
                         "bbox_right": box[2], "bbox_bottom": box[3]}
            cache[name] = entry
    todo = sorted(name for name in pool if name not in cache)
    if todo:
        with ThreadPoolExecutor(max_workers=8) as executor:
            for name, metadata in zip(todo, executor.map(fetch_upstream, todo)):
                cache[name] = metadata
        if cache_path:
            cache_path.write_text(json.dumps(cache, indent=0, sort_keys=True))
    sprites, unresolved = {}, []
    for name in sorted(pool):
        metadata = cache.get(name)
        if not isinstance(metadata, dict):
            reason = str(metadata or "no-upstream-record")
            # Normalise the fetch layer's wording into stable reason names.
            reason = {"missing": "not-in-upstream", "not-in-upstream": "not-in-upstream"}.get(reason, reason)
            if reason.startswith("error") or reason.startswith("http") or reason == "fetch-failed":
                reason = "fetch-failed"
            unresolved.append({"name": name, "reason": reason})
            continue
        record, reason = decide(name, pool[name], metadata)
        if record:
            sprites[name] = record
        else:
            unresolved.append({"name": name, "reason": reason})
    return {
        "format": 1,
        "upstream": UPSTREAM,
        "ref": UPSTREAM_REF,
        "source": "sprites/<name>/<name>.yy frame metadata (no art is imported; offsets only)",
        "rule": RULE,
        "counts": {"candidates": len(pool), "recovered": len(sprites), "unresolved": len(unresolved)},
        "sprites": sprites,
        "unresolved": unresolved,
    }


def check(document: dict) -> list[str]:
    """Re-derive every recorded offset from the local tree; no network."""
    problems: list[str] = []
    if document.get("upstream") != UPSTREAM or document.get("ref") != UPSTREAM_REF:
        problems.append("provenance changed: upstream/ref do not match this tool's pins")
    pool = candidates()
    recorded = document.get("sprites", {})
    unresolved = {entry["name"]: entry["reason"] for entry in document.get("unresolved", [])}
    for name, record in sorted(recorded.items()):
        local = pool.get(name)
        if not local:
            problems.append(f"{name}: recorded offset but the sprite is no longer a candidate")
            continue
        if local["png"] != record["png"] or local["art"] != record["art"]:
            problems.append(f"{name}: exported image changed (png {local['png']} art {local['art']})")
            continue
        gmx_bbox = [local["bbox_left"], local["bbox_top"], local["bbox_right"], local["bbox_bottom"]]
        if gmx_bbox != record["gmx_bbox"]:
            problems.append(f"{name}: gmx bbox changed to {gmx_bbox}")
            continue
        rebuilt, reason = decide(name, local, {
            "width": record["canvas"][0], "height": record["canvas"][1],
            "bbox_left": record["up_bbox"][0], "bbox_top": record["up_bbox"][1],
            "bbox_right": record["up_bbox"][2], "bbox_bottom": record["up_bbox"][3],
        })
        if not rebuilt or (rebuilt["ox"], rebuilt["oy"]) != (record["ox"], record["oy"]):
            problems.append(f"{name}: offset no longer follows the rule ({reason})")
    for name, reason in sorted(unresolved.items()):
        local = pool.get(name)
        if not local:
            problems.append(f"{name}: listed unresolved but is no longer a candidate")
            continue
        if name in recorded:
            problems.append(f"{name}: listed both recovered and unresolved")
        if not reason:
            problems.append(f"{name}: unresolved without a reason")
    missing = sorted(set(pool) - set(recorded) - set(unresolved))
    if missing:
        problems.append(f"candidates neither recovered nor explained: {missing[:8]}{'...' if len(missing) > 8 else ''}")
    if document.get("counts") != {"candidates": len(pool), "recovered": len(recorded), "unresolved": len(unresolved)}:
        problems.append("counts do not match the recorded lists")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify the checked-in file without network")
    parser.add_argument("--cache", type=Path, default=None, help="reuse/renew fetched upstream metadata")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    if arguments.check:
        if not arguments.output.exists():
            print(f"{arguments.output} is missing; run the recovery first")
            return 2
        problems = check(json.loads(arguments.output.read_text()))
        for problem in problems:
            print("FAIL " + problem)
        if problems:
            return 1
        document = json.loads(arguments.output.read_text())
        print(f"OK {arguments.output.name}: {document['counts']['recovered']} offsets verified against the local tree")
        return 0
    document = build(arguments.cache)
    arguments.output.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    counts = document["counts"]
    print(f"wrote {arguments.output.relative_to(ROOT)}: {counts['recovered']} offsets, "
          f"{counts['candidates']} candidates, {counts['unresolved']} unresolved")
    for name, record in sorted(document["sprites"].items()):
        if name in ("spr_shopkeeper1", "spr_dogboat_cover", "spr_regboat", "spr_riverman", "spr_shopkeeper2_body"):
            print(f"   {name}: offset ({record['ox']}, {record['oy']}) of canvas {record['canvas']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
