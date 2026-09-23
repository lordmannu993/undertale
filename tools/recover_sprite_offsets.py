#!/usr/bin/env python3
"""Recover the original canvas of this checkout's cropped sprite images.

The decompiled Undertale tree in this checkout exports sprite images *cropped*:
``sprites/spr_riverman.sprite.gmx`` declares ``width`` 27 and ``bbox_left`` 1,
``bbox_right`` 27, so the PNG holds the 27x42 art while the original canvas was
29x42 with the art one pixel in. Events keep drawing with the original canvas
coordinates and origins (``draw_sprite(sprite_index, image_index, x, y)`` with
``xorig`` = 0), so every cropped sprite lands ``(bbox_left, bbox_top)`` pixels
off its intended place, and every size read (``sprite_width``,
``sprite_height`` -- which
``scripts/scr_depth.gml`` turns into the Y-sort key -- and
``sprite_get_width/height``) reports the cropped pixels instead of the original
canvas.

That misplacement is what made the Snowdin shopkeeper show a second pair of
eyes and a floating mouth (its body is cropped 9 rows above the separate eyes
and mouth sprites it is composed with) and what floats the River Person's boat
cover above the water it is meant to sit in, so the offsets are worth pinning
properly instead of nudging each room.

What counts as evidence, so this stays auditable:

  * A sprite is a candidate when its own export is self-inconsistent: the bbox
    cannot fit inside the exported image, or the art does not start at the
    bbox corner. Imported offsets are never invented for other sprites.
  * The canvas comes from the pinned upstream project's sprite metadata (same
    repository and commit as ``tools/recover_parts.py``), and only when the
    upstream bbox equals this checkout's bbox, the upstream frame count equals
    this checkout's frame count, the canvas contains every exported frame and
    the bbox -- so the canvas provably belongs to the same sprite state.
    Upstream imported no art: only numbers are read, never pixels.
  * The offset (the export's position inside that canvas) is accepted per axis
    and only where it is provable:

      - ``canvas-span``: the export spans the whole canvas on that axis, so a
        crop of that size must start at 0.
      - ``bbox-interval``: with an *automatic* bbox (``bboxmode`` 0) whose span
        equals the art's span on that axis, the art fills the bbox, so it must
        start at the bbox edge. A manual box (``bboxmode`` 2) is a collision
        rectangle and proves nothing about where the art sits, so this route
        requires the automatic mode.
      - ``symmetric-bbox-edges``: both bbox edges agree on the gap to the art
        (the rule the earlier pinned records rest on; it does not require an
        automatic bbox, and eight of those records are manual boxes kept as
        pinned baselines).
      - ``sibling-pinned`` (anchored): the art is pinned to the crop's top-left
        corner, spans the crop's full width and the crop spans the bbox width
        exactly, so both horizontal edges agree without upstream metadata; the
        vertical component uses the no-trim invariant (the export never trims
        transparent rows *above* the art, true for every upstream-verified
        record) and the canvas must be pinned by a ``CANVAS_CORROBORATION``
        sibling that was itself verified upstream.

    A sprite is only shifted when *both* axes are proven. Otherwise it keeps
    its exported position and its canvas is recorded beside the reason the
    offset is not proven -- a sprite is never nudged on a guess.
  * Every candidate that fails those checks is listed with the reason, and a
    candidate with a canvas but no provable offset is listed in ``canvas``
    (not ``sprites``), so nothing is silently dropped and a later revision can
    extend the rule deliberately.

Build model: the pinned upstream numbers live in
``port/recovered_sprite_metadata.json`` (fetched by ``--refresh``, checked in,
never hand-typed). Deriving the offset file from that metadata plus this
checkout is a pure function, so ``--check`` re-derives the whole file offline
and fails on any drift.

Usage::

    python3 tools/recover_sprite_offsets.py                 # derive from the checked-in metadata
    python3 tools/recover_sprite_offsets.py --check         # re-derive, compare, no network
    python3 tools/recover_sprite_offsets.py --refresh       # fetch upstream metadata (network + token)
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
METADATA = ROOT / "port/recovered_sprite_metadata.json"

UPSTREAM = "kittibyte/UndertaleDecomp"
# The same immutable commit already pinned by tools/recover_parts.py,
# tools/recover_paths.py and tools/recover_registry.py.
UPSTREAM_REF = "249ffa27ee7e7eee0d7ce84b736c294458b38685"
API = "https://api.github.com"

#: The per-sprite numbers the metadata file carries, in order.
METADATA_FIELDS = ("width", "height", "bbox_left", "bbox_top", "bbox_right", "bbox_bottom", "frames")

RULE = (
    "canvas = the pinned upstream sprite's width/height, accepted only when the upstream bbox "
    "equals this checkout's bbox, the upstream frame count equals this checkout's frame count, and "
    "the canvas contains every exported frame and the bbox; offset = the export's position in that "
    "canvas, accepted per axis and only where provable: canvas-span (the export spans the whole "
    "canvas on that axis, so the crop starts at 0); bbox-interval (with an automatic bbox "
    "(bboxmode 0) whose span equals the art's span on that axis the art fills the bbox, so the axis "
    "starts at the bbox edge); symmetric-bbox-edges (both bbox edges agree on the gap to the art, "
    "the rule the earlier pinned records rest on, which does not require an automatic bbox); "
    "anchored (the art is pinned to the crop's top-left corner, spans the crop's full width and the "
    "crop spans the bbox width exactly, so both horizontal edges agree without upstream metadata; "
    "the vertical component uses the no-trim invariant, i.e. the export never trims transparent "
    "rows above the art, as in every upstream-verified record) and only when a pinned sibling "
    "canvas (CANVAS_CORROBORATION) contains every frame at that offset; a sprite is shifted only "
    "when both axes are proven, never on a guess"
)

# Sibling records that pin a canvas for a sprite the anchored path derives.
# The anchored path has no upstream metadata of its own, so its canvas
# containment gate must rest on a record already verified upstream. The one
# entry below: obj_dogboat_thing draws the regular hull (spr_regboat), the
# dog boat hull (spr_dogboat) and the waterline cover (spr_dogboat_cover) at
# the same canvas origin from one draw event, and the two siblings' canvases
# were upstream-verified. Extend only with the same kind of evidence (one
# draw call site, upstream-verified siblings).
CANVAS_CORROBORATION = {
    "spr_dogboat": ("spr_regboat", "spr_dogboat_cover"),
}

GMX_FIELD = re.compile(r"<{0}>(-?\d+)</{0}>")
JSON_FIELD = re.compile(r'"{0}"\s*:\s*(-?\d+(?:\.\d+)?)')
#: ``.yy`` files are not strict JSON (GameMaker writes trailing commas), so the
#: numbers are read by name rather than by parsing the document.
SPRITE_FRAME_TAG = '"$GMSpriteFrame"'
FRAME_PATH = re.compile(r'<frame index="\d+">images\\([^<]+)</frame>')


def field(text: str, key: str) -> int | None:
    """One GMX (XML) field of this checkout's own sprite file."""
    match = GMX_FIELD = re.compile(r"<%s>(-?\d+)</%s>" % (key, key)).search(text)
    return int(match.group(1)) if match else None


def json_field(text: str, key: str) -> int | None:
    """One number of a pinned upstream ``.yy`` document, read by name."""
    match = JSON_FIELD = re.compile(r'"%s"\s*:\s*(-?\d+(?:\.\d+)?)' % key).search(text)
    if not match:
        return None
    return int(float(match.group(1)))


def frame_paths(text: str) -> list[str]:
    return [m.replace("\\", "/") for m in FRAME_PATH.findall(text)]


def local_sprite(name: str) -> dict | None:
    """Local canvas facts for one sprite: gmx fields, PNG size and art bbox."""
    path = ROOT / "sprites" / f"{name}.sprite.gmx"
    if not path.exists():
        return None
    text = path.read_text(errors="replace")
    record = {key: field(text, key) for key in
              ("width", "height", "bboxmode", "bbox_left", "bbox_right", "bbox_top", "bbox_bottom")}
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
    record["frames"] = []
    for frame in frames:
        frame_image = ROOT / "sprites" / "images" / frame
        if frame_image.exists():
            record["frames"].append(list(png_size(frame_image)))
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


def parse_upstream(text: str) -> dict | None:
    """The pinned upstream numbers of one sprite, or None when incomplete."""
    values = {key: json_field(text, key) for key in
              ("width", "height", "bbox_left", "bbox_right", "bbox_top", "bbox_bottom")}
    if values["width"] is None:
        values["width"] = json_field(text, "seqWidth")
    if values["height"] is None:
        values["height"] = json_field(text, "seqHeight")
    values["frames"] = text.count(SPRITE_FRAME_TAG)
    if any(values[key] is None for key in METADATA_FIELDS):
        return None
    return values


def fetch_upstream(name: str, attempts: int = 4) -> dict | str:
    """The pinned upstream metadata of one sprite (numbers only, never art)."""
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
                payload = json.loads(response.read().decode("utf-8"))
            text = base64.b64decode(payload["content"]).decode("utf-8", "replace")
            values = parse_upstream(text)
            if values is None:
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


def upstream_values(entry) -> dict | None:
    """A metadata entry (list of numbers) as named fields."""
    if not isinstance(entry, list) or len(entry) != len(METADATA_FIELDS):
        return None
    return dict(zip(METADATA_FIELDS, entry))


def decide(name: str, local: dict, upstream: dict) -> tuple[dict | None, str | None]:
    """The symmetric-bbox-edges route; return the record or the rejection reason."""
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
        "offset_rule": "symmetric-bbox-edges",
        "gmx_bbox": [left, top, right, bottom],
        "up_bbox": list(up_bbox),
        "png": local["png"],
        "art": art,
    }, None


def decide_anchored(name: str, local: dict, pinned: dict) -> tuple[dict | None, str | None]:
    """Anchored acceptance: the offset from this checkout's own export.

    Returns (None, None) when the sprite is not eligible for this path, so
    the caller can fall back to the upstream path and its reasons.
    """
    siblings = CANVAS_CORROBORATION.get(name)
    if not siblings:
        return None, None
    art = local["art"]
    left, right, top, bottom = (local["bbox_left"], local["bbox_right"],
                                local["bbox_top"], local["bbox_bottom"])
    if art[0] != 0 or art[1] != 0:
        return None, "anchored-art-not-pinned"
    if art[2] != local["png"][0] - 1:
        return None, "anchored-art-not-full-width"
    if local["png"][0] != right - left + 1:
        return None, "anchored-crop-wider-than-bbox"
    ox = left - art[0]
    if right - art[2] != ox:
        return None, "two-sided-disagreement"
    # No-trim invariant: the crop top equals the bbox top.
    oy = top - art[1]
    if (ox, oy) == (0, 0):
        return None, "zero-offset"
    canvases = set()
    for sibling in siblings:
        record = pinned.get(sibling)
        if not record or record.get("canvas_source") == "sibling-pinned":
            return None, "sibling-not-pinned"
        canvases.add(tuple(record["canvas"]))
    if len(canvases) != 1:
        return None, "siblings-disagree"
    canvas = list(canvases.pop())
    for width, height in local["frames"]:
        if height - 1 > bottom - top:
            return None, "frame-exceeds-bbox"
        if ox + width > canvas[0] or oy + height > canvas[1]:
            return None, "canvas-too-small"
    if right >= canvas[0] or bottom >= canvas[1]:
        return None, "bbox-outside-canvas"
    return {
        "ox": ox, "oy": oy,
        "canvas": canvas,
        "canvas_source": "sibling-pinned",
        "canvas_siblings": sorted(siblings),
        "offset_rule": "sibling-pinned",
        "gmx_bbox": [left, top, right, bottom],
        "up_bbox": None,
        "png": local["png"],
        "art": art,
        "frames": local["frames"],
    }, None


def decide_canvas(name: str, local: dict, upstream: dict) -> tuple[dict | None, str | None]:
    """Pin the canvas and prove each axis' offset independently.

    Returns the record (``sprites`` shape when both axes are proven, ``canvas``
    shape otherwise) or a rejection reason.
    """
    left, right, top, bottom = (local["bbox_left"], local["bbox_right"],
                                local["bbox_top"], local["bbox_bottom"])
    up_bbox = (upstream["bbox_left"], upstream["bbox_top"], upstream["bbox_right"], upstream["bbox_bottom"])
    if (left, top, right, bottom) != up_bbox:
        return None, "bbox-differs-from-upstream"
    if len(local["frames"]) != upstream["frames"]:
        return None, "frame-set-differs-from-upstream"
    canvas = [upstream["width"], upstream["height"]]
    png = local["png"]
    art = local["art"]
    if upstream["bbox_right"] >= canvas[0] or upstream["bbox_bottom"] >= canvas[1]:
        return None, "bbox-outside-canvas"
    for frame in local["frames"]:
        if frame[0] > canvas[0] or frame[1] > canvas[1]:
            return None, "frame-exceeds-canvas"
    if png[0] > canvas[0] or png[1] > canvas[1]:
        return None, "export-exceeds-canvas"
    proofs, offsets = {}, {}
    for axis, (lo, hi, length) in (("x", (left, right, png[0])), ("y", (top, bottom, png[1]))):
        routes = []
        if length == canvas[0 if axis == "x" else 1]:
            routes.append(("canvas-span", 0))
        if local["bboxmode"] == 0 and length == hi - lo + 1 \
                and art[0 if axis == "x" else 1] == 0 and art[2 if axis == "x" else 3] == length - 1:
            routes.append(("bbox-interval", lo))
        values = {value for _, value in routes}
        if len(values) == 1:
            proofs[axis], offsets[axis] = routes[0][0], values.pop()
        else:
            proofs[axis], offsets[axis] = None, None
    if proofs["x"] and proofs["y"]:
        return {
            "ox": offsets["x"], "oy": offsets["y"],
            "canvas": canvas,
            "offset_rule": f"x: {proofs['x']}, y: {proofs['y']}",
            "gmx_bbox": [left, top, right, bottom],
            "up_bbox": list(up_bbox),
            "png": png,
            "art": art,
            "frames": local["frames"],
        }, None
    unproven = "".join(axis for axis in "xy" if not proofs[axis])
    return {
        "canvas": canvas,
        "offset_proof": {"x": proofs["x"], "y": proofs["y"]},
        "offset": None,
        "reason": f"offset-unproven-on-{'x' if unproven == 'x' else 'y' if unproven == 'y' else 'both-axes'}",
        "gmx_bbox": [left, top, right, bottom],
        "up_bbox": list(up_bbox),
        "png": png,
        "art": art,
        "frames": local["frames"],
    }, None


def fetch_reason(metadata: object) -> str:
    """Normalise the fetch layer's wording into stable reason names."""
    reason = str(metadata or "metadata-missing")
    reason = {"missing": "not-in-upstream", "not-in-upstream": "not-in-upstream"}.get(reason, reason)
    if reason.startswith("error") or reason.startswith("http") or reason == "fetch-failed":
        reason = "fetch-failed"
    return reason


def read_metadata(path: Path = METADATA) -> dict:
    """The checked-in pinned upstream numbers, or an empty document."""
    if not path.exists():
        return {"sprites": {}, "missing": {}}
    document = json.loads(path.read_text())
    return {"sprites": document.get("sprites", {}), "missing": document.get("missing", {})}


def write_metadata(path: Path, fetched: dict) -> None:
    sprites, missing = {}, {}
    for name, entry in sorted(fetched.items()):
        if isinstance(entry, dict) and all(entry.get(key) is not None for key in METADATA_FIELDS):
            sprites[name] = [int(entry[key]) for key in METADATA_FIELDS]
        else:
            missing[name] = fetch_reason(entry)
    document = {
        "format": 1,
        "upstream": UPSTREAM,
        "ref": UPSTREAM_REF,
        "source": ("repos/%s/contents/sprites/<name>/<name>.yy at ref %s (GameMaker Studio 2 sprite "
                   "metadata: width/height, bbox, frame count); fetched by tools/recover_sprite_offsets.py "
                   "--refresh. No art is imported or used." % (UPSTREAM, UPSTREAM_REF)),
        "fields": list(METADATA_FIELDS),
        "counts": {"sprites": len(sprites), "missing": len(missing)},
        "sprites": sprites,
        "missing": missing,
    }
    path.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")


def refresh(pool: dict, cache_path: Path | None = None, all_names: bool = False,
            workers: int = 8, metadata_path: Path = METADATA) -> dict:
    """Fetch the pinned upstream metadata and write the checked-in file."""
    current = read_metadata(metadata_path)
    fetched = {name: entry for name, entry in current["sprites"].items() if isinstance(entry, list)}
    fetched.update({name: reason for name, reason in current["missing"].items()})
    cache = {}
    if cache_path and cache_path.exists():
        cache = json.loads(cache_path.read_text())
    done = set(fetched) if all_names else {name for name, entry in fetched.items() if isinstance(entry, list)}
    todo = sorted(name for name in pool if name not in done)
    if todo:
        def work(name):
            entry = cache.get(name)
            if isinstance(entry, dict) and all(entry.get(key) is not None for key in METADATA_FIELDS):
                return name, entry
            return name, fetch_upstream(name)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for name, entry in executor.map(work, todo):
                fetched[name] = entry
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(fetched, indent=0, sort_keys=True) + "\n")
    write_metadata(metadata_path, fetched)
    return read_metadata(metadata_path)


def derive(pool: dict, metadata: dict) -> dict:
    """The offset file's contents from this checkout plus the pinned metadata.

    Three passes, so the anchored route still sees the sibling canvases the
    upstream routes verified: (1) upstream routes -- the symmetric-bbox-edges
    rule and the per-axis proofs; (2) anchored, for the one sprite whose canvas
    is pinned by siblings; (3) whatever is left is a canvas-only record or an
    explained refusal.
    """
    derived: dict[str, tuple[str, object]] = {}
    pending: list[tuple[str, dict]] = []
    for name in sorted(pool):
        entry = metadata["sprites"].get(name)
        upstream = upstream_values(entry) if entry is not None else None
        if upstream is None:
            reason = "metadata-malformed" if entry is not None \
                else fetch_reason(metadata["missing"].get(name))
            derived[name] = ("unresolved", reason)
        else:
            pending.append((name, upstream))
    for name, upstream in pending:
        local = pool[name]
        record, reason = decide(name, local, upstream)
        if not record:
            record, reason = decide_canvas(name, local, upstream)
            if record and "ox" not in record:
                # A canvas with at least one axis unproven: never shifted.
                derived[name] = ("canvas", record)
                continue
        derived[name] = ("offset", record) if record else ("unresolved", reason or "fetch-failed")
    verified = {name: record for name, (kind, record) in derived.items() if kind == "offset"}
    for name, _ in pending:
        kind, value = derived[name]
        if kind != "canvas":
            continue
        anchored, _ = decide_anchored(name, pool[name], verified)
        if anchored:
            derived[name] = ("offset", anchored)
    sprites = {name: record for name, (kind, record) in derived.items() if kind == "offset"}
    canvas = {name: record for name, (kind, record) in derived.items() if kind == "canvas"}
    unresolved = [{"name": name, "reason": str(record)}
                  for name, (kind, record) in sorted(derived.items()) if kind == "unresolved"]
    return {
        "format": 2,
        "upstream": UPSTREAM,
        "ref": UPSTREAM_REF,
        "source": ("sprites/<name>/<name>.yy metadata (numbers only, no art) checked in as "
                   "port/recovered_sprite_metadata.json, plus this checkout's own .sprite.gmx and PNGs"),
        "rule": RULE,
        "counts": {
            "candidates": len(pool),
            "recovered": len(sprites),
            "canvas": len(canvas),
            "unresolved": len(unresolved),
        },
        "sprites": sprites,
        "canvas": canvas,
        "unresolved": unresolved,
    }


def check(document: dict, pool: dict | None = None, metadata: dict | None = None) -> list[str]:
    """Re-derive every recorded canvas and offset from the local tree; no network."""
    problems: list[str] = []
    if document.get("upstream") != UPSTREAM or document.get("ref") != UPSTREAM_REF:
        problems.append("provenance changed: upstream/ref do not match this tool's pins")
    pool = candidates() if pool is None else pool
    metadata = read_metadata() if metadata is None else metadata
    if not metadata["sprites"] and not metadata["missing"]:
        problems.append(f"{METADATA.name} is missing: run --refresh to fetch the pinned upstream metadata")
        return problems
    expected = derive(pool, metadata)
    for section in ("sprites", "canvas"):
        recorded, rebuilt = document.get(section, {}), expected[section]
        for name in sorted(set(recorded) | set(rebuilt)):
            if name not in rebuilt:
                problems.append(f"{name}: recorded in {section} but the rule no longer derives it")
            elif name not in recorded:
                problems.append(f"{name}: the rule derives a {section} record that is not in the file")
            elif recorded[name] != rebuilt[name]:
                if section == "sprites" and (recorded[name].get("ox"), recorded[name].get("oy")) \
                        != (rebuilt[name].get("ox"), rebuilt[name].get("oy")):
                    problems.append(f"{name}: offset no longer follows the rule "
                                    f"({recorded[name].get('ox')}, {recorded[name].get('oy')}) -> "
                                    f"({rebuilt[name].get('ox')}, {rebuilt[name].get('oy')})")
                else:
                    problems.append(f"{name}: {section} record no longer follows the rule")
    for name, record in sorted(document.get("canvas", {}).items()):
        if "ox" in record or "oy" in record:
            problems.append(f"{name}: a canvas-only record must never carry an offset")
    recorded_unresolved = {entry["name"]: entry.get("reason") for entry in document.get("unresolved", [])}
    rebuilt_unresolved = {entry["name"]: entry["reason"] for entry in expected["unresolved"]}
    for name in sorted(set(recorded_unresolved) | set(rebuilt_unresolved)):
        if name not in rebuilt_unresolved:
            problems.append(f"{name}: listed unresolved but the rule now derives a record")
        elif name not in recorded_unresolved:
            problems.append(f"{name}: the rule cannot recover it but it is not listed as unresolved")
        elif recorded_unresolved[name] != rebuilt_unresolved[name]:
            problems.append(f"{name}: unresolved reason {recorded_unresolved[name]!r} is no longer "
                            f"{rebuilt_unresolved[name]!r}")
    if document.get("counts") != expected["counts"]:
        problems.append(f"counts do not match: {document.get('counts')} vs {expected['counts']}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify the checked-in file without network")
    parser.add_argument("--refresh", action="store_true",
                        help="fetch the pinned upstream metadata (needs GITHUB_TOKEN), then derive")
    parser.add_argument("--all", action="store_true", help="with --refresh: refetch every candidate")
    parser.add_argument("--cache", type=Path, default=None,
                        help="with --refresh: reuse/renew fetched upstream metadata in this file")
    parser.add_argument("--workers", type=int, default=8, help="with --refresh: parallel fetches")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--metadata", type=Path, default=METADATA)
    arguments = parser.parse_args()
    pool = candidates()
    if arguments.check:
        if not arguments.output.exists():
            print(f"{arguments.output} is missing; run the recovery first")
            return 2
        problems = check(json.loads(arguments.output.read_text()), pool)
        for problem in problems:
            print("FAIL " + problem)
        if problems:
            return 1
        document = json.loads(arguments.output.read_text())
        counts = document["counts"]
        print(f"OK {arguments.output.name}: {counts['recovered']} offsets "
              f"verified against the local tree ({counts['canvas']} more canvases, "
              f"{counts['unresolved']} candidates explained without one)")
        return 0
    if arguments.refresh:
        refresh(pool, arguments.cache, arguments.all, arguments.workers, arguments.metadata)
    metadata = read_metadata(arguments.metadata)
    if not metadata["sprites"] and not metadata["missing"] and not arguments.refresh:
        print(f"{arguments.metadata} is missing; run --refresh to fetch the pinned upstream metadata")
        return 2
    document = derive(pool, metadata)
    arguments.output.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
    counts = document["counts"]
    print(f"wrote {arguments.output.relative_to(ROOT)}: {counts['recovered']} offsets, "
          f"{counts['canvas']} canvases, {counts['candidates']} candidates, "
          f"{counts['unresolved']} unresolved")
    for name, record in sorted(document["sprites"].items()):
        if name in ("spr_shopkeeper1", "spr_dogboat", "spr_dogboat_cover",
                    "spr_regboat", "spr_riverman", "spr_shopkeeper2_body"):
            source = "" if record.get("offset_rule") == "symmetric-bbox-edges" else " " + record["offset_rule"]
            print(f"   {name}: offset ({record['ox']}, {record['oy']}) of canvas {record['canvas']}{source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
