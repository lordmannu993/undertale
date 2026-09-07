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
