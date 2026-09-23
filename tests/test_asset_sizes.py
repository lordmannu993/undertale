"""One sprite-size compatibility layer (unified-fusion piece 6a, spec section 12).

Undertale's decompiled checkout exported many sprite PNGs *cropped*, so
``sprite_get_width``/``sprite_get_height`` and the ``sprite_width``/
``sprite_height`` instance reads returned the cropped pixels, while every event
that uses them -- and ``scripts/scr_depth.gml``, which turns the height into
Undertale's Y-sort key -- was written against the original canvas. Yellow's GMS2
records are not cropped, so the same calls meant the canvas there: one game meant
two different things by the same asset, which is exactly what spec section 12
asks a compatibility layer to fix.

The layer is one accessor, port/assetcompat.lua, used by the Undertale builtins
(port/graphics.lua), Yellow's builtins (port/yellow_studio.lua) and the instance
reads (port/runtime.lua). The canvas it answers with comes from the pinned
upstream metadata (port/recovered_sprite_metadata.json) through
tools/recover_sprite_offsets.py, which proves each canvas and each offset and
lists every candidate it could not prove:

  * ``port/sprite_offsets.json`` ``sprites`` -- offset proven, sprite shifted;
  * ``port/sprite_offsets.json`` ``canvas`` -- canvas pinned, offset not proven,
    sprite *never* shifted, only its reported size corrected;
  * ``port/sprite_offsets.json`` ``unresolved`` -- no canvas either; the exported
    size stays and the candidate is named with its reason.

These tests prove the wiring and the data. They do not claim pixel-perfect
parity with the original engine, Android behaviour, or a played-through scene.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_yellow_merge import merged, yellow_rooms  # noqa: F401 - session-scoped manifest fixtures

sys.path.insert(0, str(ROOT / "tools"))

import recover_sprite_offsets as recovery  # noqa: E402

OFFSETS = json.loads((ROOT / "port/sprite_offsets.json").read_text())
METADATA = json.loads((ROOT / "port/recovered_sprite_metadata.json").read_text())
LIVE = (ROOT / "yellow_src").is_dir()
live = pytest.mark.skipif(not LIVE, reason="needs the pinned Yellow source: tools/fetch_yellow.py")


def generated_record(name):
    """The generated sprite record for one Undertale sprite, as raw Lua text."""
    for path in sorted((ROOT / "generated/assets").glob("sprites_*.lua")):
        text = path.read_text()
        at = text.find(f'["name"]="{name}",')
        if at >= 0:
            return text[at:text.find('["frames"]=', at)]
    raise AssertionError(f"{name} has no generated sprite record")


# A sprite whose canvas (14x15) is bigger than the exported image (13x14): the
# recovered-canvas case that used to answer with the cropped pixels.
CROPPED_CANVAS = "spr_5_mouth2"
# A sprite whose offset is *not* provable but whose canvas is (13x10 exported
# 8x7): the case the earlier recovery could say nothing about at all.
CANVAS_ONLY = "spr_5_coffeeline"
# A candidate with no pinned upstream record: its exported size must stay.
NO_CANVAS = "spr_pressz"


def test_sprite_get_size_reports_the_recovered_canvas(lua):
    """``sprite_get_width/height`` answer in original-canvas pixels."""
    record = OFFSETS["sprites"][CROPPED_CANVAS]
    assert record["canvas"] == [14, 15] and record["png"] == [13, 14]
    assert lua.eval(f'R.builtins.sprite_get_width(nil, R.manifest.names["{CROPPED_CANVAS}"])') == 14
    assert lua.eval(f'R.builtins.sprite_get_height(nil, R.manifest.names["{CROPPED_CANVAS}"])') == 15


def test_sprite_get_size_reports_the_recovered_canvas_of_an_unshifted_sprite(lua):
    """A canvas-only sprite still reports the canvas; only its position is unknown."""
    record = OFFSETS["canvas"][CANVAS_ONLY]
    assert record["canvas"] == [13, 10] and record["png"] == [8, 7]
    assert lua.eval(f'R.builtins.sprite_get_width(nil, R.manifest.names["{CANVAS_ONLY}"])') == 13
    assert lua.eval(f'R.builtins.sprite_get_height(nil, R.manifest.names["{CANVAS_ONLY}"])') == 10


def test_instance_size_reads_use_the_canvas_and_follow_scale(lua):
    """``sprite_width``/``sprite_height`` are canvas pixels, scaled with the instance."""
    lua.execute(f"""
        CA = R:create(18000, 10, 20); CA.v.sprite_index = R.manifest.names["{CANVAS_ONLY}"]
        MA = R:create(18001, 10, 20); MA.v.sprite_index = R.manifest.names["spr_maincharad"]
        SA = R:create(18001, 10, 20); SA.v.sprite_index = R.manifest.names["{CANVAS_ONLY}"]
        SA.v.image_xscale, SA.v.image_yscale = 2, 3
    """)
    assert lua.eval('R:instanceGet(CA, "sprite_width")') == 13
    assert lua.eval('R:instanceGet(CA, "sprite_height")') == 10
    # Frisk's walk sprite: the canvas is 20x30, the export 19x29.
    assert lua.eval('R:instanceGet(MA, "sprite_width")') == 20
    assert lua.eval('R:instanceGet(MA, "sprite_height")') == 30
    assert lua.eval('R:instanceGet(SA, "sprite_width")') == 26
    assert lua.eval('R:instanceGet(SA, "sprite_height")') == 30


def test_player_walk_canvas_is_the_depth_key(lua):
    """scr_depth's Y-sort key uses the player's recovered canvas height (29 -> 30)."""
    lua.execute("""
        PA = R:create(18000, 50, 141); PA.v.sprite_index = R.manifest.names["spr_maincharad"]
        R:call("scr_depth", R:scope(PA))
    """)
    assert lua.eval("PA.v.depth") == 50000 - 141 * 10 + 30 * 10


def test_sprite_with_no_pinned_canvas_keeps_its_exported_size(lua):
    """The one candidate without upstream metadata is never given a guessed size."""
    assert f'["cw"]' not in generated_record(NO_CANVAS)
    exported = lua.eval(f'(function() local s=R.assets.sprites[R.manifest.names["{NO_CANVAS}"]]; '
                        f'return s.width*1000+s.height end)()')
    assert lua.eval(f'R.builtins.sprite_get_width(nil, R.manifest.names["{NO_CANVAS}"])*1000'
                    f'+R.builtins.sprite_get_height(nil, R.manifest.names["{NO_CANVAS}"])') == exported


def test_canvas_only_sprites_are_never_shifted(converted, lua):
    """A canvas without a proven offset keeps the exported position (no nudge)."""
    record = generated_record(CANVAS_ONLY)
    assert '["ox"]' not in record and '["oy"]' not in record
    drawn = lua.eval(f'''(function()
        local index=R.manifest.names["{CANVAS_ONLY}"]
        R.drawLog={{}}
        R.builtins.draw_sprite(E, index, 0, 130, 0)
        for _,e in ipairs(R.drawLog) do
            if e[1]=="sprite" then return {{ox=e[11],oy=e[12]}} end
        end
    end)()''')
    assert (drawn["ox"], drawn["oy"]) == (0, 0)


def test_one_accessor_backs_every_size_read(lua):
    """The builtin and the instance read agree for every recovered sprite.

    Guards the wiring, not the numbers: a regression that points one of them back
    at the exported pixels fails here even where the two happen to be equal.
    """
    lua.execute("""
        UT = {}
        for name, id in pairs(R.manifest.names) do
            local s = R.assets.sprites[id]
            if s and (s.cw or s.ch) then UT[#UT+1] = id end
        end
        MISMATCH = {}
        for _, id in ipairs(UT) do
            local s = R.assets.sprites[id]
            local inst = R:create(18000, 0, 0)
            inst.v.sprite_index = id
            if R:instanceGet(inst, "sprite_width") ~= (s.cw or s.width)
               or R:instanceGet(inst, "sprite_height") ~= (s.ch or s.height)
               or R.builtins.sprite_get_width(nil, id) ~= (s.cw or s.width)
               or R.builtins.sprite_get_height(nil, id) ~= (s.ch or s.height) then
                MISMATCH[#MISMATCH+1] = s.name
            end
            R:destroy(inst, false)
        end
    """)
    assert lua.eval("#UT") > 1000, "the recovered canvases must reach the generated records"
    assert lua.eval("#MISMATCH") == 0, \
        f"size reads disagree with the recovered canvas: {lua.eval('MISMATCH[1]')}"


@live
def test_yellow_sprite_records_stay_their_own_canvas(merged):
    """Yellow's uncropped records keep answering their own size through the layer."""
    from lupa.luajit21 import LuaRuntime

    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    lua.execute("""
        Input=require("port.input")
        Runtime=require("port.runtime")
        input=Input.new()
        R=Runtime.new(require("generated.merged.manifest"), input, {headless=true, trace=true, seed=42})
    """)
    lua.execute("""
        YELLOW = 0
        MISMATCH = {}
        for name, id in pairs(R.manifest.yellow_names.sprites) do
            local s = R.assets.sprites[id]
            if s then
                YELLOW = YELLOW + 1
                if R.builtins.sprite_get_width(nil, id) ~= s.width
                   or R.builtins.sprite_get_height(nil, id) ~= s.height
                   or R.builtins.sprite_get_xoffset(nil, id) ~= s.xorig
                   or R.builtins.sprite_get_yoffset(nil, id) ~= s.yorigin then
                    MISMATCH[#MISMATCH+1] = name
                end
            end
        end
    """)
    assert lua.eval("YELLOW") > 1000
    assert lua.eval("#MISMATCH") == 0, \
        f"Yellow sprites changed size through the layer: {lua.eval('MISMATCH[1]')}"


def test_offsets_file_separates_recovered_offsets_from_canvases():
    """Every candidate is recovered, canvas-only, or explained -- with a reason."""
    counts = OFFSETS["counts"]
    assert OFFSETS["format"] == 2
    assert counts["candidates"] == counts["recovered"] + counts["canvas"] + counts["unresolved"]
    assert counts["candidates"] == len(recovery.candidates())
    assert set(OFFSETS["sprites"]) | set(OFFSETS["canvas"]) \
        | {entry["name"] for entry in OFFSETS["unresolved"]} == set(recovery.candidates())
    assert not set(OFFSETS["sprites"]) & set(OFFSETS["canvas"])
    for name, record in OFFSETS["sprites"].items():
        assert record["offset_rule"], f"{name} has no recorded proof for its offset"
    for name, record in OFFSETS["canvas"].items():
        assert record["offset"] is None and "ox" not in record and "oy" not in record, \
            f"{name}: a canvas-only record must not carry an offset"
        proofs = record["offset_proof"]
        assert set(proofs) == {"x", "y"} and not (proofs["x"] and proofs["y"]), \
            f"{name}: a canvas-only record needs at least one unproven axis"
        assert record["reason"].startswith("offset-unproven")
    for entry in OFFSETS["unresolved"]:
        assert entry["reason"] in {"bbox-outside-canvas", "bbox-differs-from-upstream",
                                   "not-in-upstream", "fetch-failed", "missing-fields",
                                   "frame-set-differs-from-upstream", "metadata-malformed",
                                   "metadata-missing"}


def test_upstream_metadata_is_pinned_and_never_hand_typed():
    """The canvas numbers come from the pinned ref, or a candidate is refused."""
    assert (METADATA["upstream"], METADATA["ref"]) == (recovery.UPSTREAM, recovery.UPSTREAM_REF)
    assert METADATA["fields"] == list(recovery.METADATA_FIELDS)
    assert METADATA["counts"] == {"sprites": len(METADATA["sprites"]), "missing": len(METADATA["missing"])}
    assert set(METADATA["sprites"]) | set(METADATA["missing"]) == set(recovery.candidates())
    assert all(len(entry) == len(recovery.METADATA_FIELDS) for entry in METADATA["sprites"].values())
    assert METADATA["missing"]  # the candidates upstream genuinely does not carry stay named
    for name, reason in METADATA["missing"].items():
        assert reason in {entry["reason"] for entry in OFFSETS["unresolved"] if entry["name"] == name} \
            or name in OFFSETS["canvas"] or name in OFFSETS["sprites"]
    # Regression anchors: the player's own walk canvas and a sprite the recovery
    # used to leave out of the file completely.
    assert METADATA["sprites"]["spr_maincharad"] == [20, 30, 0, 19, 19, 29, 4]
    assert METADATA["sprites"]["spr_5_mouth2"] == [14, 15, 1, 0, 13, 13, 2]


def test_canvas_sizes_reach_the_generated_records(converted):
    """Every pinned canvas is carried beside the exported size, and only those."""
    for name in (CROPPED_CANVAS, CANVAS_ONLY):
        record = OFFSETS["sprites"].get(name) or OFFSETS["canvas"][name]
        text = generated_record(name)
        assert f'["cw"]={record["canvas"][0]}' in text and f'["ch"]={record["canvas"][1]}' in text, \
            f"{name} lost its pinned {record['canvas']} canvas on the way into the record"
    assert '["cw"]' not in generated_record(NO_CANVAS)


def test_check_rejects_a_tampered_canvas_and_a_shifted_canvas_only_sprite():
    """The offline gate catches both a changed canvas and a smuggled-in offset."""
    tampered = json.loads(json.dumps(OFFSETS))
    tampered["canvas"][CANVAS_ONLY]["canvas"][1] += 1
    assert any(CANVAS_ONLY in problem for problem in recovery.check(tampered))
    shifted = json.loads(json.dumps(OFFSETS))
    shifted["canvas"][CANVAS_ONLY]["ox"] = 1
    problems = recovery.check(shifted)
    assert any(CANVAS_ONLY in problem for problem in problems)


def test_recovery_tool_re_derives_everything_offline():
    """``--check`` re-derives the whole file from the pins; no network needed."""
    result = subprocess.run([sys.executable, str(ROOT / "tools/recover_sprite_offsets.py"), "--check"],
                            cwd=ROOT, capture_output=True, text=True,
                            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": ""})
    assert result.returncode == 0, result.stdout + result.stderr
