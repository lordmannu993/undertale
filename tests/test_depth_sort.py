"""Depth / Y-sort (unified-fusion piece 2, spec section 4 and section 5).

Two systems were wrong, one per world:

* Undertale sorts its overworld by ``scr_depth`` (``depth = 50000 - y*10 +
  sprite_height*10``), but ``sprite_height`` read the *exported* (cropped)
  image size while the game's arithmetic assumes the original canvas. Every
  recovered sprite now carries its pinned canvas size (``cw``/``ch`` from
  ``port/sprite_offsets.json``) and the instance read uses it.
* Yellow Y-sorts by assigning ``depth = -y`` every step, but the renderer
  drew every room-placed (layered) instance at its *authored layer* depth and
  ignored the assignment. Assigning depth to a layered instance now moves it
  onto a managed ``Compatibility_Instances_Depth_N`` layer at that depth,
  which is what GameMaker Studio 2 itself does.

Ties keep a stable, documented rule: the layer-list slot decides across
layers (a foreground tile layer above the instance layer covers a tied
actor), otherwise creation order wins and the order never changes between
frames.

Scope: headless converted flow plus the draw log, with native rendering
evidence from CI. These tests do not claim Android GPU behaviour or
pixel-perfect parity with the original engines.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest
from lupa.luajit21 import LuaRuntime

from conftest import ROOT

LIVE = (ROOT / "yellow_src").is_dir()
live = pytest.mark.skipif(not LIVE, reason="needs the pinned Yellow source: tools/fetch_yellow.py")


def sprite_record(name):
    """The generated asset record for one Undertale sprite, as raw Lua text."""
    for path in sorted((ROOT / "generated/assets").glob("sprites_*.lua")):
        text = path.read_text()
        marker = f'["name"]="{name}",'
        at = text.find(marker)
        if at >= 0:
            # The record ends at the frame list; everything this piece adds
            # (cw/ch) is carried beside ox/oy before it.
            end = text.find('["frames"]=', at)
            return text[at:end]
    raise AssertionError(f"{name} has no generated sprite record")


def test_canvas_dimensions_reach_the_sprite_record(converted):
    """Pinned canvases reach the record; a sprite with no pin keeps its export size."""
    keeper = sprite_record("spr_shopkeeper1")
    assert '["width"]=61' in keeper and '["height"]=111' in keeper
    assert '["cw"]=64' in keeper and '["ch"]=120' in keeper, \
        "spr_shopkeeper1 lost its pinned 64x120 canvas on the way into the record"
    # Frisk's walk sprite: the canvas is pinned (20x30) but the crop offset is
    # not provable, so it carries the size and no shift (piece 6a).
    mainchara = sprite_record("spr_maincharad")
    assert '["width"]=19' in mainchara and '["height"]=29' in mainchara
    assert '["cw"]=20' in mainchara and '["ch"]=30' in mainchara, \
        "spr_maincharad lost the 20x30 canvas the pinned upstream metadata proves"
    assert '["ox"]' not in mainchara and '["oy"]' not in mainchara, \
        "spr_maincharad's unprovable crop offset must never be guessed"
    # A sprite whose pinned record disagrees about the canvas keeps its export size.
    unpinned = sprite_record("spr_6hope")
    assert '["width"]=29' in unpinned and '["height"]=11' in unpinned
    assert '["cw"]' not in unpinned and '["ch"]' not in unpinned, \
        "spr_6hope's canvas is not pinned (bbox-outside-canvas): it must not be guessed"


def test_sprite_height_reads_canvas_where_recovered(lua):
    """sprite_height is the visual bottom point's canvas height, else exported."""
    lua.execute("""
        HA = R:create(18000, 50, 100); HA.v.sprite_index = R.manifest.names["spr_shopkeeper1"]
        HB = R:create(18001, 50, 100); HB.v.sprite_index = R.manifest.names["spr_maincharad"]
        HC = R:create(18001, 50, 100); HC.v.sprite_index = R.manifest.names["spr_6hope"]
    """)
    assert lua.eval('R:instanceGet(HA, "sprite_height")') == 120
    assert lua.eval('R:instanceGet(HB, "sprite_height")') == 30   # pinned canvas, no offset proof
    assert lua.eval('R:instanceGet(HC, "sprite_height")') == 11   # no pinned canvas: exported size


def test_scr_depth_sorts_from_the_visual_bottom_point(lua):
    """Undertale's own Y-sort key, evaluated with the canvas height."""
    lua.execute("""
        SA = R:create(18000, 50, 141); SA.v.sprite_index = R.manifest.names["spr_shopkeeper1"]
        R:call("scr_depth", R:scope(SA))
    """)
    assert lua.eval("SA.v.depth") == 50000 - 141 * 10 + 120 * 10


def test_draw_list_orders_by_visual_bottom_point(lua):
    """A pair whose order flips between cropped and canvas inputs draws canvas-ordered.

    shopkeeper (y=141, canvas 120) vs dogboat cover (y=60, canvas 40): cropped
    heights (111/15) put the shopkeeper behind; canvas heights put the cover
    behind. The draw log is painter order (first entry is furthest back).
    """
    lua.execute("""
        R:start(); tick(3)
        DA = R:create(18000, 50, 141); DA.v.sprite_index = R.manifest.names["spr_shopkeeper1"]
        DB = R:create(18001, 90, 60); DB.v.sprite_index = R.manifest.names["spr_dogboat_cover"]
        R:call("scr_depth", R:scope(DA)); R:call("scr_depth", R:scope(DB))
        R.drawLog = {}; R:renderFrame()
        IA, IB = nil, nil
        for i, e in ipairs(R.drawLog) do
            if e[1] == "sprite" and e[2] == "spr_shopkeeper1" and IA == nil then IA = i end
            if e[1] == "sprite" and e[2] == "spr_dogboat_cover" and IB == nil then IB = i end
        end
    """)
    pos_a, pos_b = lua.eval("IA"), lua.eval("IB")
    assert pos_a is not None and pos_b is not None, "both sprites must draw"
    assert pos_b < pos_a, \
        f"cover (canvas key {60 - 40}) must draw behind shopkeeper (canvas key {141 - 120})"


def test_water_statue_sorts_from_its_canvas_height(lua):
    """A live NPC (spr_statue 59px exported, 80px canvas) Y-sorts from 80."""
    lua.execute("""
        R:start(); tick(3)
        R:gotoRoom(R.constants.room_water_statue); R:applyTransitions(); tick(3)
        STATUE = nil
        for _, inst in ipairs(R.instances) do
            if inst.alive and (R:object(inst.v.object_index) or {}).name == "obj_musicstatue" then
                STATUE = inst
            end
        end
        assert(STATUE ~= nil, "obj_musicstatue is not in room_water_statue")
    """)
    depth = lua.eval("STATUE.v.depth")
    y = lua.eval("STATUE.v.y")
    assert depth == 50000 - y * 10 + 80 * 10, \
        f"statue depth {depth} is not the canvas formula at y={y}"


def test_equal_depth_ties_are_creation_ordered_and_stable(lua):
    """Same depth draws in creation order, identically every frame (no popping)."""
    lua.execute("""
        R:start(); tick(1)
        TA = R:create(18000, 50, 100); TA.v.sprite_index = R.manifest.names["spr_heart"]
        TB = R:create(18001, 90, 100); TB.v.sprite_index = R.manifest.names["spr_heart"]
        TA.v.depth, TB.v.depth = 4242, 4242
        ORDERS = {}
        for frame = 1, 3 do
            R.drawLog = {}; R:renderFrame()
            local seen = {}
            for _, e in ipairs(R.drawLog) do
                if e[1] == "sprite" and e[2] == "spr_heart" then seen[#seen + 1] = e[4] end
            end
            ORDERS[frame] = table.concat(seen, ",")
        end
    """)
    orders = [lua.eval(f"ORDERS[{i}]") for i in (1, 2, 3)]
    assert orders[0] == "50,90", f"creation order broken: {orders[0]}"
    assert orders[0] == orders[1] == orders[2], f"tie order flickers: {orders}"


# -- Yellow: managed depth layers -------------------------------------------

BOOT = '''
    Input=require("port.input")
    Runtime=require("port.runtime")
    input=Input.new()
    R=Runtime.new(require("generated.merged.manifest"), input,
                  {headless=true, memorySaves=true, trace=true, seed=42})
    function tick(n)
        for i=1,n do
            input:beginFrame(); R:step(); R:renderFrame(); R:finishFrame(); input:endFrame()
        end
    end
    function crossTo(room)
        R:gotoRoom(room); R:applyTransitions(); tick(1)
    end
'''


@pytest.fixture(scope="session")
def yellow_rooms(converted):
    """Both games converted, Yellow through its rooms stage."""
    if not LIVE:
        pytest.skip("needs the pinned Yellow source: tools/fetch_yellow.py")
    import json
    report = ROOT / "generated/yellow/conversion-report.json"
    stage = json.loads(report.read_text())["stage"] if report.is_file() else None
    if stage != "rooms":
        subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "rooms"], cwd=ROOT, check=True)
    return ROOT / "generated/yellow"


@pytest.fixture(scope="session")
def merged(yellow_rooms):
    run = subprocess.run([sys.executable, "tools/merge.py"], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "Merged manifest" in run.stdout
    return ROOT / "generated/merged/manifest.lua"


@pytest.fixture
def vm(merged, monkeypatch):
    monkeypatch.chdir(ROOT)
    machine = LuaRuntime(unpack_returned_tuples=True)
    machine.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    machine.execute(BOOT)
    return machine


def layer_of(machine, expression):
    return machine.eval(f"R.roomState.layers[{expression}].name")


@live
def test_depth_assignment_moves_layered_instances_to_managed_layers(vm):
    """Yellow's Step-level `depth = -y` moves actors off their authored layer.

    In Dalv's room the chest (y=148) and gramophone (y=169) assign their depth
    every step; each must end up on its own Compatibility layer at -y while the
    static diary stays on the authored instance layer.
    """
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    result = vm.execute('''
        crossTo(R.manifest.yellow_names.rooms["rm_dalvsroom"]); tick(3)
        local found = {}
        for _, inst in ipairs(R.instances) do
            if not inst.alive then goto continue end
            local name = (R:object(inst.v.object_index) or {}).name
            if name == "obj_dalvsroom_chest" or name == "obj_dalvsroom_gramophone"
               or name == "obj_dalv_diary" then
                found[name] = inst
            end
            ::continue::
        end
        if not found.obj_dalvsroom_chest then return "no chest in rm_dalvsroom" end
        if not found.obj_dalvsroom_gramophone then return "no gramophone in rm_dalvsroom" end
        if not found.obj_dalv_diary then return "no diary in rm_dalvsroom" end
        local function checkManaged(inst, wantDepth)
            if inst.v.depth ~= wantDepth then
                return "v.depth is " .. tostring(inst.v.depth) .. ", want " .. wantDepth
            end
            local layer = R.roomState.layers[inst.layer]
            if not layer then return "instance has no layer" end
            if layer.depth ~= wantDepth then
                return "layer depth is " .. tostring(layer.depth) .. ", want " .. wantDepth
            end
            if layer.name ~= "Compatibility_Instances_Depth_" .. tostring(wantDepth) then
                return "unexpected managed layer " .. tostring(layer.name)
            end
            if not inst._homeLayer then return "managed move lost the home layer" end
            if not inst.element or inst.element.layer ~= inst.layer then
                return "the layer element did not follow the managed move"
            end
            return nil
        end
        local bad = checkManaged(found.obj_dalvsroom_chest, -148)
            or checkManaged(found.obj_dalvsroom_gramophone, -169)
        if bad then return bad end
        local diary = found.obj_dalv_diary
        local home = R.roomState.layers[diary.layer]
        if not home or home.name ~= "Compatibility_Instances_Depth_0" then
            return "the static diary left its authored layer: " .. tostring(home and home.name)
        end
        -- One step re-assigns the same depth: the managed layer must be reused,
        -- not duplicated, and nothing else in the room may have moved.
        local managed = 0
        for _, layer in ipairs(R.roomState.layers) do
            if layer.name == "Compatibility_Instances_Depth_-148" then managed = managed + 1 end
        end
        if managed ~= 1 then return "depth -148 owns " .. managed .. " layers, want 1" end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_dalvsroom_draws_y_sorted(vm):
    """Behind-to-front: diary (static, depth 0), player (-140), chest (-148),
    gramophone (-169). Before the fix the chest drew first (stuck at its authored
    layer depth 0) and the player drew last."""
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    result = vm.execute('''
        crossTo(R.manifest.yellow_names.rooms["rm_dalvsroom"]); tick(3)
        local player = nil
        for _, inst in ipairs(R.instances) do
            if inst.alive and (R:object(inst.v.object_index) or {}).name == "obj_pl" then
                player = inst
            end
        end
        if not player then return "no obj_pl after the crossing" end
        if player.v.depth ~= -player.v.y then
            return "player depth " .. tostring(player.v.depth) .. " is not -y (" .. tostring(player.v.y) .. ")"
        end
        R.drawLog = {}; R:renderFrame()
        local at = {}
        for i, e in ipairs(R.drawLog) do
            if e[1] == "sprite" then
                if e[2] == "spr_dalv_journal" and not at.diary then at.diary = i end
                if e[2] == "spr_dalvsroom_chest" and not at.chest then at.chest = i end
                if e[2] == "spr_dalvsroom_gramophone" and not at.gramophone then at.gramophone = i end
                if e[4] == player.v.x and e[5] == player.v.y and not at.player then at.player = i end
            end
        end
        if not (at.diary and at.player and at.chest and at.gramophone) then
            return "missing draw: diary=" .. tostring(at.diary) .. " player=" .. tostring(at.player)
                .. " chest=" .. tostring(at.chest) .. " gramophone=" .. tostring(at.gramophone)
        end
        if not (at.diary < at.player and at.player < at.chest and at.chest < at.gramophone) then
            return "wrong Y order: diary=" .. at.diary .. " player=" .. at.player
                .. " chest=" .. at.chest .. " gramophone=" .. at.gramophone
        end
        return "ok"
    ''')
    assert result == "ok", result


SYNTHETIC_LAYERS = """
    R:start(); tick(1)
    -- A foreground tile layer above the actor layer in list order, exactly
    -- like a canopy: same shape as the converted Yellow records.
    R.roomState.layers[1] = {name="fg_tiles", kind="GMRAssetLayer", depth=-100,
        visible=true, x=0, y=0, hspeed=0, vspeed=0}
    R.roomState.layers[2] = {name="actors", kind="GMRInstanceLayer", depth=0,
        visible=true, x=0, y=0, hspeed=0, vspeed=0}
    R.roomState.tiles[#R.roomState.tiles + 1] = {yellow=true, layer=1,
        sprite=R.manifest.names["spr_heart"], resourceType="GMRSpriteGraphic",
        x=100, y=100, scaleX=1, scaleY=1, rotation=0, colour=4294967295}
    -- The renderer caches the room's tile list on first render; a tile added
    -- afterwards (as here) needs the same fresh-room rebuild a load would do.
    R.roomState.staticTileDrawList = nil
    dummy(18000)
    R.objects[18000].sprite = R.manifest.names["spr_maincharad"]
"""


def test_foreground_tiles_cover_a_tied_actor_and_yield_below_it(lua):
    """Cross-layer ties resolve by layer-list slot; distinct depths interleave.

    The actor assigns `depth = -y` through compiled GML, the way Yellow's Step
    events do. At y=100 it ties the foreground tile layer (-100) and the tiles
    cover it; at y=101 it is below the plane and draws in front (this leg fails
    while layered instances ignore their assigned depth).
    """
    lua.execute(SYNTHETIC_LAYERS + """
        ACTOR = R:create(18000, 200, 100, {yellow=true, layer=2, depth=0,
            imageIndex=0, imageSpeed=1, colour=4294967295})
    """)
    # The assignment runs through the GML compiler, not around it.
    from tools.gml import compile_gml
    code, _ = compile_gml("depth = -y;", "test")
    lua.globals().GML_DEPTH_ASSIGN = code
    lua.execute("""
        local AE = R:scope(ACTOR)
        local function orderAt(y)
            ACTOR.v.y = y
            local fn = assert(loadstring(GML_DEPTH_ASSIGN))()
            fn(R, AE)
            R.drawLog = {}; R:renderFrame()
            local tile, actor = nil, nil
            for i, e in ipairs(R.drawLog) do
                if e[1] == "sprite" and e[2] == "spr_heart" and not tile then tile = i end
                if e[1] == "sprite" and e[2] == "spr_maincharad" and not actor then actor = i end
            end
            return tile, actor
        end
        T_TIE, A_TIE = orderAt(100)
        T_BELOW, A_BELOW = orderAt(101)
        T_ABOVE, A_ABOVE = orderAt(99)
    """)
    tie = (lua.eval("T_TIE"), lua.eval("A_TIE"))
    below = (lua.eval("T_BELOW"), lua.eval("A_BELOW"))
    above = (lua.eval("T_ABOVE"), lua.eval("A_ABOVE"))
    assert None not in tie + below + above, f"both must draw every time: {tie} {below} {above}"
    assert tie[1] < tie[0], f"tied actor must be covered by the foreground tiles: {tie}"
    assert below[0] < below[1], f"actor below the plane must draw in front: {below}"
    assert above[1] < above[0], f"actor above the plane must be covered: {above}"


def test_layer_depth_moves_unmanaged_members_but_not_managed_ones(lua):
    """layer_depth follows GMS2: members mirror it, managed actors stay detached."""
    lua.execute(SYNTHETIC_LAYERS + """
        A = R:create(18000, 200, 100, {yellow=true, layer=2, depth=0,
            imageIndex=0, imageSpeed=1, colour=4294967295})
        B = R:create(18000, 210, 50, {yellow=true, layer=2, depth=0,
            imageIndex=0, imageSpeed=1, colour=4294967295})
        R:instanceSet(B, "depth", -50)
        R.builtins.layer_depth(nil, 2, 500)
        R.drawLog = {}; R:renderFrame()
        IA, IB = nil, nil
        for i, e in ipairs(R.drawLog) do
            if e[1] == "sprite" and e[2] == "spr_maincharad" then
                if e[4] == 200 and not IA then IA = i end
                if e[4] == 210 and not IB then IB = i end
            end
        end
    """)
    assert lua.eval("A.v.depth") == 500, "unmanaged member must mirror layer_depth"
    assert lua.eval("B.v.depth") == -50, "managed actor must stay detached"
    pos = (lua.eval("IA"), lua.eval("IB"))
    assert None not in pos, "both actors must draw"
    assert pos[0] < pos[1], f"moved layer (500) draws behind the managed actor (-50): {pos}"


def test_repeated_depth_assignment_reuses_one_managed_layer(lua):
    """Every Step re-assigns the same depth: one layer per depth value, no growth."""
    lua.execute(SYNTHETIC_LAYERS + """
        M = R:create(18000, 200, 100, {yellow=true, layer=2, depth=0,
            imageIndex=0, imageSpeed=1, colour=4294967295})
        for _ = 1, 3 do R:instanceSet(M, "depth", -50) end
        local count50, count60 = 0, 0
        for _, layer in ipairs(R.roomState.layers) do
            if layer.name == "Compatibility_Instances_Depth_-50" then count50 = count50 + 1 end
            if layer.name == "Compatibility_Instances_Depth_-60" then count60 = count60 + 1 end
        end
        FIRST50, FIRST60 = count50, count60
        R:instanceSet(M, "depth", -60)
        count50, count60 = 0, 0
        for _, layer in ipairs(R.roomState.layers) do
            if layer.name == "Compatibility_Instances_Depth_-50" then count50 = count50 + 1 end
            if layer.name == "Compatibility_Instances_Depth_-60" then count60 = count60 + 1 end
        end
        SECOND50, SECOND60 = count50, count60
        HOME = M._homeLayer
        LAYERDEPTH = R.roomState.layers[M.layer].depth
    """)
    assert (lua.eval("FIRST50"), lua.eval("FIRST60")) == (1, 0)
    assert (lua.eval("SECOND50"), lua.eval("SECOND60")) == (1, 1)
    assert lua.eval("HOME") == 2, "the managed move must remember the authored layer"
    assert lua.eval("LAYERDEPTH") == -60
