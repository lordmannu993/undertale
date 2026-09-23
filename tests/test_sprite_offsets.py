"""Canvas-offset gates for the cropped Undertale sprite export.

The checkout's sprite PNGs are cropped to their collision bbox while events keep
drawing in the original canvas coordinates, which is what doubled the Snowdin
shopkeeper's face and floated the River Person's boat cover above the water.
These tests pin the evidence file that repairs it:

  * the recovered offsets follow tools/recover_sprite_offsets.py's rule, are
    re-derivable from this checkout alone, and every candidate sprite is either
    recovered or listed with a reason (nothing is silently dropped),
  * the converter carries them into the generated sprite records,
  * the renderer hands them to the draw call, which the draw log records.

They prove the data and the wiring, not a played-through scene.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import recover_sprite_offsets as recovery  # noqa: E402

OFFSETS = json.loads((ROOT / "port/sprite_offsets.json").read_text())

# Offsets that fix visible, owner-reported defects; asserted so a regenerated
# file cannot quietly lose them.
KEY_OFFSETS = {
    "spr_shopkeeper1": (1, 9),       # Snowdin shopkeeper body: the doubled face
    "spr_shopkeeper2_body": (0, 1),
    "spr_dogboat": (3, 3),           # River Person's dog boat hull: was floating
    "spr_dogboat_cover": (7, 25),    # River Person's boat cover: the waterline
    "spr_regboat": (3, 9),
    "spr_riverman": (1, 0),
}


def test_offsets_are_recorded_with_provenance():
    # Format 2 adds the second list: a candidate whose canvas is pinned but whose
    # offset no route proves is recorded under "canvas" and never shifted.
    assert OFFSETS["format"] == 2
    assert (OFFSETS["upstream"], OFFSETS["ref"]) == (recovery.UPSTREAM, recovery.UPSTREAM_REF)
    assert "symmetric-bbox-edges" in OFFSETS["rule"] and "canvas-span" in OFFSETS["rule"]
    counts = OFFSETS["counts"]
    assert counts == {
        "candidates": len(OFFSETS["sprites"]) + len(OFFSETS["canvas"]) + len(OFFSETS["unresolved"]),
        "recovered": len(OFFSETS["sprites"]),
        "canvas": len(OFFSETS["canvas"]),
        "unresolved": len(OFFSETS["unresolved"]),
    }
    assert counts["recovered"] > 0 and counts["canvas"] > 0 and counts["unresolved"] > 0


@pytest.mark.parametrize("name,expected", sorted(KEY_OFFSETS.items()))
def test_key_offsets(name, expected):
    record = OFFSETS["sprites"][name]
    assert (record["ox"], record["oy"]) == expected
    # The canvas must be the original frame: bigger than the exported image.
    assert record["canvas"][0] >= record["png"][0] and record["canvas"][1] >= record["png"][1]
    assert record["canvas"][0] > record["png"][0] or record["canvas"][1] > record["png"][1]


def test_shopkeeper_body_offset_is_what_reunites_the_face():
    """The body art starts 9 rows below the eyes and mouth sprites it draws with.

    The eyes overlay is drawn at canvas y=40 and the mouth at y=50, and the
    body's own painted eyes and mouth live at rows 31 and 41 of the exported
    image, so the offset is what puts the overlays back on the painted features.
    """
    record = OFFSETS["sprites"]["spr_shopkeeper1"]
    assert record["oy"] - record["ox"] == 8  # (1, 9): the crop is not square
    assert record["gmx_bbox"] == [1, 9, 61, 119] == record["up_bbox"]
    assert record["art"] == [0, 0, 60, 110]


def test_dogboat_hull_offset_is_the_anchored_derivation():
    """The dog boat hull only recovers via the anchored path.

    The upstream vertical edges disagree (the export trimmed transparent rows
    below the hull art), so the original rule rejects it. The anchored path
    derives (3, 3) from this checkout's own export geometry and pins the
    canvas from the sibling records of the same draw call, both of which were
    verified upstream.
    """
    record = OFFSETS["sprites"]["spr_dogboat"]
    assert record["canvas_source"] == "sibling-pinned"
    assert record["up_bbox"] is None  # never fetched: derived locally
    siblings = sorted(record["canvas_siblings"])
    assert siblings == ["spr_dogboat_cover", "spr_regboat"]
    for name in siblings:
        sibling = OFFSETS["sprites"][name]
        assert sibling.get("canvas_source") != "sibling-pinned", \
            "a sibling-pinned canvas must rest on an upstream-verified record"
        assert sibling["canvas"] == record["canvas"]
    # The anchored rule is documented in the file's rule statement.
    assert "anchored" in OFFSETS["rule"]


def test_every_candidate_is_recovered_or_explained():
    reasons = {entry["reason"] for entry in OFFSETS["unresolved"]}
    assert reasons <= {"two-sided-disagreement", "bbox-differs-from-upstream",
                       "bbox-outside-canvas", "canvas-too-small", "not-in-upstream",
                       "fetch-failed", "missing-fields", "frame-set-differs-from-upstream"}
    for entry in OFFSETS["unresolved"]:
        assert entry["name"].startswith("spr_")
        assert entry["reason"]
    recovered = set(OFFSETS["sprites"])
    canvases = set(OFFSETS["canvas"])
    unresolved = {entry["name"] for entry in OFFSETS["unresolved"]}
    assert not (recovered & unresolved) and not (recovered & canvases) and not (canvases & unresolved)
    # A candidate that is not in the file at all would be a silent drop.
    assert recovered | canvases | unresolved == set(recovery.candidates())


def test_checked_in_offsets_still_follow_the_rule():
    problems = recovery.check(OFFSETS)
    assert not problems, "port/sprite_offsets.json drifted:\n" + "\n".join(problems)


def test_check_detects_a_tampered_offset():
    tampered = json.loads(json.dumps(OFFSETS))
    name = next(iter(tampered["sprites"]))
    tampered["sprites"][name]["ox"] += 3
    assert any(name in problem for problem in recovery.check(tampered))


def _sprite_record(name):
    """The generated asset record for one sprite, brace-matched."""
    for module in sorted((ROOT / "generated/assets").glob("sprites_*.lua")):
        text = module.read_text(errors="replace")
        marker = f'["name"]="{name}"'
        if marker not in text:
            continue
        start = text.rindex("={", 0, text.index(marker))
        depth = 0
        for index in range(start + 1, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        raise AssertionError(f"unterminated record for {name}")
    raise AssertionError(f"{name} is not in the generated sprite modules")


@pytest.mark.parametrize("name,expected", sorted(KEY_OFFSETS.items()))
def test_converter_carries_the_offsets_into_the_asset_records(converted, name, expected):
    record = _sprite_record(name)
    assert f'["ox"]={expected[0]}' in record and f'["oy"]={expected[1]}' in record


def test_uncropped_sprites_are_not_shifted(converted):
    """A sprite with no recovered offset must stay at the exported position."""
    record = _sprite_record("spr_shop1_bg")
    assert '["ox"]' not in record and '["oy"]' not in record
    assert "spr_shop1_bg" not in OFFSETS["sprites"]


def test_runtime_hands_the_offset_to_the_draw_call(converted, lua):
    """The draw log records what the renderer adds to the sprite position.

    port/graphics.lua draws with ``xorig - ox`` (and shifts draw_sprite_part
    rects by the same amount), so the log carries the offset next to the
    logical position the event passed in.
    """
    def draw(name):
        return lua.eval(f'''(function()
            local index=R.manifest.names["{name}"]
            R.drawLog={{}}
            R.builtins.draw_sprite(E, index, 0, 130, 0)
            for _,e in ipairs(R.drawLog) do
                if e[1]=="sprite" then return {{name=e[2],x=e[4],y=e[5],ox=e[11],oy=e[12]}} end
            end
        end)()''')

    body = draw("spr_shopkeeper1")
    assert (body["x"], body["y"]) == (130, 0)      # the event's canvas coordinates
    assert (body["ox"], body["oy"]) == (1, 9)      # the recovered crop offset
    eyes = draw("spr_shopkeeper1eyes")
    assert (eyes["ox"], eyes["oy"]) == (0, 0)      # uncropped companion sprite
    background = draw("spr_shop1_bg")
    assert (background["ox"], background["oy"]) == (0, 0)


def test_recovery_tool_check_mode_runs_offline():
    """`--check` is the CI-facing gate; it must not need the network."""
    result = subprocess.run([sys.executable, str(ROOT / "tools/recover_sprite_offsets.py"), "--check"],
                            cwd=ROOT, capture_output=True, text=True,
                            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": ""})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "offsets verified against the local tree" in result.stdout
