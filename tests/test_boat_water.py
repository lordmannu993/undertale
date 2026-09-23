"""River Person's boat and water (unified-fusion piece 3, spec section 6).

The original-game layering, pinned here from the draw log:

    water background (backmost)  <  boat hull  <  waterline cover
        <  riverman  <  player,

and during the ride the water pillar (depth -1) is in front of everything.
The room instance depths are the original room data (49330 hull / 49320
riverman in the water and fire docks, 950000 boat in the tundra dock); the
player is placed with no authored depth and takes scr_depth's key, which
piece 6a moved onto the recovered canvas height (49310 in the dock at y=100,
was 49300 with the 29px cropped export). This piece does not move anything to
a different global render layer, it repairs two pixel defects inside that
layering:

* ``spr_dogboat`` was the one boat sprite whose crop offset never recovered
  (the upstream vertical edges disagree: the export trimmed transparent
  rows below the hull art). The hull therefore drew 3 px up and left of its
  canvas place, floating above the waterline its cover sits in. The anchored
  recovery path in tools/recover_sprite_offsets.py now pins (3, 3),
  corroborated by the sibling hull and cover, whose canvases are the
  upstream-verified 91x40 of the same draw call.
* The cover animates with a fractional sub-index (``cc += 0.1`` per draw);
  the renderer floored it, snapping the ripple to hard steps. It now
  crossfades the two frames (base frame, then next frame at the fractional
  amount), and the draw log records the blend.

Scope: headless converted flow plus the draw log, with native rendering
evidence from CI. No Android GPU or pixel-perfect parity claim.
"""
import json
import subprocess
import sys

import pytest
from lupa.luajit21 import LuaRuntime

from conftest import ROOT

LIVE = (ROOT / "yellow_src").is_dir()
live = pytest.mark.skipif(not LIVE, reason="needs the pinned Yellow source: tools/fetch_yellow.py")

# Original room data (decompiled rooms), pinned as the layering reference.
# The boat and riverman depths are authored room data. The player's is the key
# scripts/scr_depth.gml computes from y and sprite_height: 50000 - 10y + 10h,
# with h the *canvas* height piece 6a pinned (spr_maincharad 19x29 exported,
# 20x30 canvas). Before that piece the cropped 29 read as 49300 / 48280 here.
DOCK_DEPTH = {"boat": 49330, "riverman": 49320, "player": 49310}
TUNDRA_DEPTH = {"boat": 950000, "riverman": 49320, "player": 48290}


@pytest.fixture(scope="session")
def yellow_rooms(converted):
    """Both games converted, Yellow through its rooms stage."""
    if not LIVE:
        pytest.skip("needs the pinned Yellow source: tools/fetch_yellow.py")
    report = ROOT / "generated/yellow/conversion-report.json"
    stage = json.loads(report.read_text())["stage"] if report.is_file() else None
    if stage != "rooms":
        subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "rooms"], cwd=ROOT, check=True)
    return ROOT / "generated/yellow"


@pytest.fixture(scope="session")
def merged(yellow_rooms):
    """The merged manifest, built exactly like the other merged-build gates
    do — the CI pipeline never runs tools/merge.py itself."""
    run = subprocess.run([sys.executable, "tools/merge.py"], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "Merged manifest" in run.stdout
    return ROOT / "generated/merged/manifest.lua"


@pytest.fixture(scope="module")
def boat(merged):
    """Merged Runtime booted like the game, before the waterfall plot point."""
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    vm.execute("""
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
        function dummy(id,parent)
            R.manifest.objects[id]="tests.dummy"
            R.objects[id]={name="dummy",sprite=-1,mask=-1,visible=1,solid=0,depth=0,persistent=0,parent=parent or -1,events={}}
        end
        dummy(18000);dummy(18001,18000)
        a=R:create(18000,10,20)
        E=R:scope(a)
        R:start(); tick(1)
    """)
    return vm


def set_boatable(vm, reg):
    """Plot past the waterfall; flag 461 picks the hull variant (1 = dog boat)."""
    vm.execute(f"""
        R.global.plot = 200
        R.global.flag[461] = {1 if reg == 0 else 0}
        R.global.entrance = 0
    """)


def dock(vm, reg=0, room=125, ticks=20):
    set_boatable(vm, reg)
    vm.execute(f"R:gotoRoom({room}); R:applyTransitions(); tick({ticks})")
    vm.execute("R.drawLog = {}; R:renderFrame()")


def draw_entries(vm, name):
    """Every sprite entry for one name in the current R.drawLog, oldest first.

    Field layout of a sprite entry: kind,name,frame,x,y,sx,sy,angle,tint,alpha,
    ox,oy[,blendFrame,blendT]. The helper serializes on the Lua side because
    lupa hands back Lua tables, not Python lists.
    """
    raw = vm.eval(f"""(function()
        local out = {{}}
        for _, e in ipairs(R.drawLog) do
            if e[1] == "sprite" and e[2] == "{name}" then
                out[#out+1] = e[3] .. "," .. e[4] .. "," .. e[5] .. "," .. e[11]
                          .. "," .. e[12] .. "," .. tostring(e[13]) .. "," .. tostring(e[14])
            end
        end
        return table.concat(out, "\\n")
    end)()""")
    entries = []
    for line in raw.split("\n"):
        if not line:
            continue
        f = line.split(",")
        entries.append({
            "frame": int(float(f[0])), "x": float(f[1]), "y": float(f[2]),
            "ox": int(float(f[3])), "oy": int(float(f[4])),
            "blend": None if f[5] == "nil" else int(float(f[5])),
            "t": None if f[6] == "nil" else float(f[6]),
        })
    return entries


def draw_order(vm):
    """Sprite names and background names in draw order (first = furthest back)."""
    raw = vm.eval("""(function()
        local out = {}
        for _, e in ipairs(R.drawLog) do
            if e[1] == "sprite" or e[1] == "background" then out[#out+1] = e[2] end
        end
        return table.concat(out, "\\n")
    end)()""")
    return raw.split("\n") if raw else []


def layer_depth(vm, object_name):
    """The depth the renderer sorts an instance by.

    Studio 2 (Yellow) room instances sort by their layer depth; GM 1.4
    (Undertale) room instances carry their own ``depth`` variable, which is
    the original room data.
    """
    return vm.eval(f"""(function()
        for _, inst in ipairs(R.instances) do
            if not inst.alive then goto continue end
            local name = (R:object(inst.v.object_index) or {{}}).name
            if name == "{object_name}" then
                local layer = inst.layer and R.roomState.layers[inst.layer]
                return (layer and layer.depth) or inst.v.depth
            end
            ::continue::
        end
    end)()""")


@live
def test_dock_drawing_order_is_the_original_layering(boat):
    """Water behind the boat, cover over the hull, riverman and player in front."""
    dock(boat, reg=0)
    order = draw_order(boat)
    hulls = [i for i, n in enumerate(order) if n == "spr_dogboat"]
    covers = [i for i, n in enumerate(order) if n == "spr_dogboat_cover"]
    rman = [i for i, n in enumerate(order) if n == "spr_riverman"]
    player = [i for i, n in enumerate(order) if n == "spr_maincharad"]
    water = [i for i, n in enumerate(order) if n.startswith("bg_watertiles")]
    assert hulls and covers and rman and player and water, f"missing actors: {order}"
    assert max(water) < hulls[0], "water background must be behind the boat hull"
    assert hulls[0] < covers[0] < rman[0] < player[0], \
        f"expected hull < cover < riverman < player in {order}"


@live
def test_dock_depths_are_the_original_room_data(boat):
    assert layer_depth(boat, "obj_dogboat_thing") == DOCK_DEPTH["boat"]
    assert layer_depth(boat, "obj_riverman") == DOCK_DEPTH["riverman"]
    assert layer_depth(boat, "obj_mainchara") == DOCK_DEPTH["player"]


@live
def test_fire_dock_matches_the_water_dock(boat):
    dock(boat, reg=0, room=140)
    order = draw_order(boat)
    assert order.index("spr_dogboat") < order.index("spr_dogboat_cover") \
        < order.index("spr_riverman") < order.index("spr_maincharad")
    assert layer_depth(boat, "obj_dogboat_thing") == DOCK_DEPTH["boat"]


@live
def test_tundra_dock_pins_the_tundra_depths(boat):
    dock(boat, reg=0, room=70)
    order = draw_order(boat)
    assert order.index("spr_dogboat") < order.index("spr_dogboat_cover")
    assert layer_depth(boat, "obj_dogboat_thing") == TUNDRA_DEPTH["boat"]
    assert layer_depth(boat, "obj_riverman") == TUNDRA_DEPTH["riverman"]
    assert layer_depth(boat, "obj_mainchara") == TUNDRA_DEPTH["player"]


@live
def test_regulated_boat_shares_the_same_layering(boat):
    """flag 461 = 0 switches the hull to spr_regboat; everything else holds."""
    dock(boat, reg=1)
    order = draw_order(boat)
    assert order.index("spr_regboat") < order.index("spr_dogboat_cover") \
        < order.index("spr_riverman")
    hull = draw_entries(boat, "spr_regboat")[0]
    assert (hull["ox"], hull["oy"]) == (3, 9)


@live
def test_dogboat_hull_sits_at_its_canvas_place(boat):
    """The recovered (3, 3) crop offset reaches the draw call.

    Before the anchored recovery, spr_dogboat had no record and the hull drew
    at (0, 0), floating 3 px up and left of the waterline.
    """
    dock(boat, reg=0)
    hull = draw_entries(boat, "spr_dogboat")
    assert hull, "the dog boat hull is not drawn in the water dock"
    assert (hull[0]["ox"], hull[0]["oy"]) == (3, 3)
    cover = draw_entries(boat, "spr_dogboat_cover")[0]
    assert (cover["ox"], cover["oy"]) == (7, 25), "the waterline cover regressed"


@live
def test_dogboat_generated_record_carries_offset_and_canvas(converted, boat):
    for path in sorted((ROOT / "generated/assets").glob("sprites_*.lua")):
        text = path.read_text()
        at = text.find('["name"]="spr_dogboat",')
        if at >= 0:
            end = text.find('["frames"]=', at)
            record = text[at:end]
            break
    else:
        raise AssertionError("spr_dogboat has no generated sprite record")
    assert '["ox"]=3' in record and '["oy"]=3' in record, \
        "spr_dogboat lost its recovered (3, 3) crop offset"
    assert '["cw"]=91' in record and '["ch"]=40' in record, \
        "spr_dogboat lost its 91x40 canvas (sibling-pinned, same draw call)"


def cover_blend_state(vm):
    """The cover's logged blend next to the expectation computed from the
    boat's own cc, exactly as the renderer derives it.

    The cover (spr_dogboat_cover, 2 frames) is drawn with sub-index cc, and
    the boat's draw event advances cc by 0.1 on every draw. GameMaker
    interpolates the fractional part between the two frames; the expected
    values are computed here with the same operations on the same cc, so a
    floored renderer (frame only, no blend) cannot satisfy this.
    """
    return vm.eval("""(function()
        local boat
        for _, inst in ipairs(R.instances) do
            if not inst.alive then goto c end
            local name = (R:object(inst.v.object_index) or {}).name
            if name == "obj_dogboat_thing" then boat = inst end
            ::c::
        end
        if not boat then return nil end
        local cc = boat.v.cc
        local n = 2  -- spr_dogboat_cover's frame count
        local base = math.floor(cc) % n
        local frac = cc - math.floor(cc)
        local blend = frac > 0 and (base + 1) % n or nil
        local entry
        for i = #R.drawLog, 1, -1 do
            local e = R.drawLog[i]
            if e[1] == "sprite" and e[2] == "spr_dogboat_cover" then entry = e break end
        end
        if not entry then return nil end
        return entry[3], entry[14], entry[13], base, frac, blend
    end)()""")


@live
def test_cover_ripple_interpolates_between_frames(boat):
    """cc += 0.1 per draw must blend the two frames, not floor to a hard step."""
    dock(boat, reg=0, ticks=11)
    logged_frame, logged_t, logged_blend, base, frac, expected_blend = cover_blend_state(boat)
    assert logged_frame is not None, "the waterline cover is not drawn in the dock"
    assert logged_frame == base, "the cover must draw the floor frame of cc"
    if expected_blend is None:
        assert logged_t in (None, 0) and logged_blend is None, \
            "an integral cc must not carry a blend"
    else:
        assert logged_t is not None, "fractional cc was not blended (renderer floored it)"
        assert abs(logged_t - frac) < 1e-9, "the blend amount must be cc's fraction"
        assert logged_blend == expected_blend
        assert 0 < logged_t < 1

    # One more draw advances cc by 0.1 and the renderer must follow it.
    vm = boat
    vm.execute("R.drawLog = {}; R:renderFrame()")
    _, t2, blend2, base2, frac2, expected2 = cover_blend_state(vm)
    assert base2 is not None
    value1 = (logged_frame or 0) + (logged_t or 0)
    value2 = base2 + (t2 or 0)
    delta = (value2 - value1) % 2
    assert abs(delta - 0.1) < 1e-6, f"cover sub-index advanced by {delta}, want 0.1"
    if expected2 is None:
        assert blend2 is None
    else:
        assert blend2 == expected2


@live
def test_integer_subindex_draws_unblended(boat):
    """Integer draws must log exactly as before (no blend fields)."""
    boat.execute("""
        R.drawLog = {}
        R.builtins.draw_sprite(E, R.manifest.names["spr_riverman"], 1, 100, 100)
        R.builtins.draw_sprite(E, R.manifest.names["spr_riverman"], 0, 100, 100)
    """)
    entries = draw_entries(boat, "spr_riverman")
    assert [e["frame"] for e in entries] == [1, 0]
    for entry in entries:
        assert entry["blend"] is None and entry["t"] is None


def boat_pose(vm):
    """(x, y, depth) of the ride boat in room 316, or None."""
    return vm.eval("""(function()
        for _, inst in ipairs(R.instances) do
            if not inst.alive then goto continue end
            local name = (R:object(inst.v.object_index) or {}).name
            if name == "obj_dogboat_thing" then
                return inst.v.x, inst.v.y, inst.v.depth
            end
            ::continue::
        end
    end)()""")


@live
def test_ride_moves_the_boat_and_puts_the_pillar_in_front(boat):
    """Room 316: the boat slides left at 2 px/tick to x = 118, pillar in front."""
    vm = boat
    set_boatable(vm, reg=0)
    vm.execute("R.global.entrance = 24")
    vm.execute("R:gotoRoom(316); R:applyTransitions(); tick(1)")
    start = boat_pose(vm)
    assert start is not None, "the ride boat is missing from room 316"
    assert start[0] == 340, f"boat starts at x={start[0]}, want 340 (room 355, first step -15)"
    assert start[2] == 900000, f"ride boat depth is {start[2]}, want 900000"

    vm.execute("tick(5)")
    assert boat_pose(vm)[0] == 330, "the boat must slide left at 2 px per tick"

    vm.execute("tick(124)")  # tick 130 total
    assert boat_pose(vm)[0] == 118, "the boat must stop at x = 118 (the player's side)"

    vm.execute("R.drawLog = {}; R:renderFrame()")
    order = draw_order(vm)
    assert "spr_waterpillar" in order, "the water pillar is not drawn during the ride"
    assert order.index("spr_waterpillar") > order.index("spr_maincharal"), \
        "the pillar (depth -1) must draw in front of the player and the boat"
