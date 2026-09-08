"""Recovered movement paths: provenance, coordinate semantics and playback math.

The GameMaker export this repository is built from has no ``paths`` section at all,
so every ``path_start`` call used to stop the game. ``tools/recover_paths.py`` now
pins real point data into ``port/path_data.json`` and ``port/runtime.lua`` plays it
back. These tests hold both halves to account: the data must stay traceable and the
motion must be the documented GameMaker behaviour, not an approximation we like.
"""
import json
import re
from pathlib import Path

import pytest

from conftest import run_gml
from test_regressions import enter_flowey

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "port/path_data.json").read_text())


def test_every_referenced_path_now_has_point_data(converted):
    report = json.loads((converted / "conversion-report.json").read_text())
    assert report["missing_paths"] == []
    assert len(report["recovered_paths"]) == 38
    assert {entry["name"] for entry in report["recovered_paths"]} == set(DATA["paths"])


def test_recovered_data_is_pinned_to_a_single_upstream_commit():
    assert re.fullmatch(r"[0-9a-f]{40}", DATA["ref"]), "upstream commit must be pinned, not a branch"
    assert set() == {r["source"]["ref"] for r in DATA["paths"].values()} ^ {DATA["ref"]}
    for name, record in DATA["paths"].items():
        source = record["source"]
        assert source["upstream"] == DATA["upstream"]
        assert source["file"] == f"paths/{name}/{name}.yy"
        assert len(record["points"]) >= 2


def test_no_point_was_invented_locally():
    # Integer authoring coordinates only: a fractional value would mean we interpolated
    # or scaled something, which is exactly what the recovery promises not to do.
    for name, record in DATA["paths"].items():
        for x, y in record["points"]:
            assert float(x).is_integer() and float(y).is_integer(), f"{name}: non-integer point {x},{y}"
        assert record["kind"] in (0, 1)
        assert isinstance(record["closed"], bool)


def test_absolute_coordinates_match_the_room_placement_they_were_walked_in():
    """path_torielwalk1 starts where room_ruins1 puts Toriel, so points are room-absolute.

    This is the evidence for treating ``path_start``'s fourth argument as GameMaker's
    absolute flag rather than a relative offset.
    """
    room = (ROOT / "rooms/room_ruins1.room.gmx").read_text(errors="replace")
    placed = re.search(r'<instance objName="obj_toroverworld2" x="([\d.-]+)" y="([\d.-]+)"', room)
    assert placed, "room_ruins1 no longer places obj_toroverworld2 where this was verified"
    start = DATA["paths"]["path_torielwalk1"]["points"][0]
    assert abs(start[0] - float(placed.group(1))) <= 4, "path start drifted from the room instance"
    assert abs(start[1] - float(placed.group(2))) <= 4, "path start drifted from the room instance"


def test_toriel_walk_leads_up_and_out_of_the_room():
    """Sanity on the recovered geometry: the corridor walk runs from (140,320) to (146,64)."""
    points = DATA["paths"]["path_torielwalk1"]["points"]
    assert points[0] == [140.0, 320.0]
    assert points[-1] == [146.0, 64.0]
    assert all(b[1] <= a[1] + 1e-9 for a, b in zip(points, points[1:])), "Toriel walks up: y must not descend"


def test_pixels_per_step_drive_the_position_fraction(lua):
    lua.execute('''
        R.pathData[19123]={points={{0,0},{0,-30}},closed=false,kind=0,precision=4}
        local geo=R:pathGeometry(19123)
        assert(geo._length==30)
        a.v.x=10;a.v.y=20;a.v.path_orientation=0;a.v.path_speed=0
        R:startPath(E,19123,3,0,1)
        assert(a.v.x==0 and a.v.y==0)                     -- snapped onto the path start
        for _=1,5 do R:advancePath(a) end                 -- 5 steps x 3px = half a 30px path
        assert(math.abs(a.v.path_position-0.5)<1e-9)
        assert(a.v.x==0 and a.v.y==-15)
        for _=1,6 do R:advancePath(a) end
        assert(a.v.y==-30)                                -- stop holds the final point
        assert(a.v.path_index==-1)                        -- ... and ends the path
    ''')


def test_relative_paths_offset_from_where_the_instance_stood(lua):
    lua.execute('''
        R.pathData[19124]={points={{5,0},{5,-10}},closed=false,kind=0,precision=4}
        a.v.x=100;a.v.y=200
        R:startPath(E,19124,0,0,0)                        -- relative
        assert(a.v.x==105 and a.v.y==200)
        a.v.path_speed=5
        R:advancePath(a)
        assert(a.v.x==105 and a.v.y==195)
    ''')


def test_path_end_actions_loop_and_bounce(lua):
    lua.execute('''
        R.pathData[19125]={points={{0,0},{10,0}},closed=false,kind=0,precision=4}
        a.v.x=0;a.v.y=0
        R:startPath(E,19125,6,1,1)                        -- path_action_restart
        a.v.path_position=0.9
        R:advancePath(a)                                  -- 0.9 + 0.6 -> 0.5 of the next lap
        assert(math.abs(a.v.path_position-0.5)<1e-9 and a.v.x==5)
        assert(a.v.path_index==19125)
        R:startPath(E,19125,6,3,1)                        -- path_action_reverse
        a.v.path_position=0.9
        R:advancePath(a)
        assert(a.v.path_speed==-6 and a.v.x==10)
    ''')


def test_closed_paths_measure_their_return_segment(lua):
    lua.execute('''
        R.pathData[19127]={points={{0,0},{30,0},{0,40}},closed=true,kind=0,precision=4}
        assert(R:pathGeometry(19127)._length==120)        -- 30 + 50 + 40
        R.pathData[19128]={points={{0,0},{30,0},{0,40}},closed=false,kind=0,precision=4}
        assert(R:pathGeometry(19128)._length==80)
    ''')


def test_smooth_paths_are_splined_not_straight(lua):
    lua.execute('''
        R.pathData[19126]={points={{0,0},{10,0},{20,10}},closed=false,kind=1,precision=4}
        local geo=R:pathGeometry(19126)
        assert(#geo._points==9)                           -- two spans of four samples plus the end
        local y=geo._points[3][2]
        assert(y<-0.1 and y>-1.5)                         -- the curve leaves the chord
        R.pathData[19129]={points={{0,0},{10,0},{20,10}},closed=false,kind=0,precision=4}
        assert(#R:pathGeometry(19129)._points==3)         -- a straight path is used verbatim
    ''')


def test_a_path_without_recovered_data_still_stops(lua):
    with pytest.raises(Exception, match="does not contain"):
        run_gml(lua, "path_start(19999,3,0,1);")


HANDHOLD_SCENE = """
    R:start()
    -- The lead-in (Toriel's greeting, her follow-walk and the scripted encounter
    -- at x=520) is other objects' business; this test pins the handhold scene the
    -- reported softlock happens in. obj_toroverworld6 leaves obj_torinteractable5
    -- standing at the end of path_torielwalk5, so the scene is entered exactly
    -- from there.
    R:gotoRoom(R.constants.room_ruins5)
    tick(3)
    R.global.plot = 7
    local lead = R.pathData[R.manifest.names.path_torielwalk5]
    local ia = R:create(R.constants.obj_torinteractable5,
        lead.points[#lead.points][1], lead.points[#lead.points][2])
    local mc = R:select(R.constants.obj_mainchara)[1]
    mc.v.x, mc.v.y = ia.v.x - 15, ia.v.y + 31     -- at her feet, facing right
    tick(1)
    input:setSource("test", {39}); tick(2); input:setSource("test", {}); tick(1)
    assert(R.global.facing == 1 and R.global.interact == 0)
    press(90)                                      -- talk to her (msc 217)
    for round = 1, 120 do
        if #R:select(R.constants.obj_dialoguer) == 0 then break end
        press(90)
    end
    tick(6)
    local hh = R:select(R.constants.obj_torhandhold1)[1]
    assert(hh, "talking to Toriel never spawned obj_torhandhold1")
    assert(mc.v.visible == 0 and R.global.interact == 6 and R.global.phasing == 1)
    -- The crossing must run inside the room the whole way.
    local start = R.pathData[R.manifest.names.path_torielwalk5_2].points[1]
    assert(hh.v.y == start[2] and math.abs(hh.v.x - start[1]) <= 20,
        string.format("handhold entered the maze at (%.0f,%.0f), not the path start", hh.v.x, hh.v.y))
    local peak_x, peak_y = hh.v.x, hh.v.y
    for round = 1, 700 do
        tick(1)
        if not hh.alive then break end
        if hh.v.x > peak_x then peak_x = hh.v.x end
        if hh.v.y > peak_y then peak_y = hh.v.y end
        if hh.v.conversation == 2 then break end
    end
    assert(hh.alive and hh.v.conversation == 2 and hh.v.path_position == 1,
        "the hand-in-hand crossing never reached the far side of the spikes")
    assert(hh.v.x == 1136 and hh.v.y == 60,
        string.format("crossing ended at (%.0f,%.0f) instead of (1136,60)", hh.v.x, hh.v.y))
    assert(peak_x < R.vars.room_width and peak_y < R.vars.room_height,
        string.format("Toriel and the player left the room: peak (%.0f,%.0f)", peak_x, peak_y))
    assert(R.global.phasing == 0, "phasing was not restored after the crossing")
    assert(mc.v.visible == 1, "the player was not made visible again")
    assert(mc.v.x == 1136 and mc.v.y == 60, "the player did not exit the maze with Toriel")
    assert(R:select(R.constants.obj_spiketile2)[1].v.solid == 1, "spikes stayed passable")
    local tor = R:select(R.constants.obj_toroverworld4)[1]
    assert(tor and tor.v.x == hh.v.x + 12 and tor.v.y == hh.v.y,
        "obj_toroverworld4 was not placed at the handhold's position")
    -- alarm[0] fires the farewell dialogue (msc 218); Z through it like a player.
    tick(6)
    for round = 1, 200 do
        if #R:select(R.constants.obj_dialoguer) == 0 then break end
        press(90)
    end
    tick(4)
    assert(R.global.plot == 8, "the scene did not finish with global.plot = 8")
    assert(R.global.interact == 0, "player control was not returned")
    assert(not hh.alive, "obj_torhandhold1 survived its own scene")
"""


def test_toriel_handhold_completes_scene_instead_of_walking_off_room(lua):
    """The Ruins water-spike handhold crossing plays out inside room_ruins5.

    ``obj_torhandhold1`` started ``path_torielwalk5_2`` with GameMaker's
    *relative* flag, but the recovered points are room-absolute coordinates that
    zig-zag through the spike maze. Read as offsets from the walk-in position
    (768,110) the path dumped Toriel and the invisible player around (1540,210)
    to (1904,170) — outside the 1200x240 room — so the whole crossing, its
    follow-up dialogue and the hand-back of control happened off-camera: on a
    phone that reads as Toriel and the player vanishing at the spike bridge.
    The fix starts the maze path absolutely, exactly like sibling
    ``obj_toroverworld6`` already did for ``path_torielwalk5`` in the same room.
    """
    lua.execute(HANDHOLD_SCENE)


ROUTE_DRIVE = """
    local deadline = R.frame + 6000
    while R.roomState.name == "room_floweybattle" and R.frame < deadline do
        input:setSource("test", {38}); tick(2); input:setSource("test", {})
        press(90)
    end
    assert(R.roomState.name == "room_area1_2", "tutorial battle did not return to the corridor")
    deadline = R.frame + 3000
    local trigger
    while R.frame < deadline do
        tick(10); press(90)
        trigger = R:select(R.constants.obj_floweytrigger)[1]
        if trigger and trigger.v.conversation >= 4 and R.global.interact == 0 then break end
    end
    assert(trigger and trigger.v.conversation >= 4, "obj_floweytrigger stuck after the Flowey battle")

    local function walker()
        for _, id in ipairs({R.constants.obj_toroverworld2, R.constants.obj_toroverworld1}) do
            local instance = R:select(id)[1]
            if instance and instance.v.path_index >= 0 then return instance end
        end
        return R:select(R.constants.obj_toroverworld2)[1] or R:select(R.constants.obj_toroverworld1)[1]
    end
    for round = 1, 700 do
        if R.roomState.name ~= "room_area1_2" then break end
        input:setSource("test", {38}); tick(6); input:setSource("test", {})
        if round % 20 == 0 then press(90) end
    end
    assert(R.roomState.name == "room_ruins1",
        "following Toriel never reached room_ruins1: " .. R.roomState.name)

    local tor
    for round = 1, 60 do
        input:setSource("test", {38}); tick(4); input:setSource("test", {})
        tor = walker()
        if tor and tor.v.path_index >= 0 then break end
    end
    assert(tor and tor.v.path_index == R.manifest.names.path_torielwalk1,
        "Toriel is not walking path_torielwalk1 in room_ruins1")
    local started_y, furthest = tor.v.y, 0
    for round = 1, 400 do
        input:setSource("test", {38}); tick(4); input:setSource("test", {})
        if round % 20 == 0 then press(90) end
        if tor.v.path_position > furthest then furthest = tor.v.path_position end
        if tor.v.path_position >= 1 or tor.v.path_index < 0 then break end
    end
    assert(furthest > 0.02, "Toriel never advanced along the recovered path")
    assert(tor.v.y < started_y - 20, "Toriel did not walk up the corridor")
"""


def test_the_reported_scene_now_walks_instead_of_stopping(lua):
    """Reproduces the reported phone screen: the ruins-entry corridor walk plays out.

    Before the recovered path data this raised the compatibility stop inside
    ``path_start``; the assertion is the route itself, driven through the real
    scripted battle, dialogue and triggers rather than a teleported room.
    """
    enter_flowey(lua)
    lua.execute(ROUTE_DRIVE)
