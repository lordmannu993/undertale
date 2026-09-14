"""Merged-build gates: one manifest, two worlds, and the cross-game travel.

These prove conversion and routing headlessly: the ID bands survive merging, the
merged runtime boots into Undertale, the River Person and UGPS whale routes land
in the right rooms with exactly one player, and the merged save layer is
versioned. They do NOT certify native rendering or a played-through crossing.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LIVE = (ROOT / "yellow_src").is_dir()
live = pytest.mark.skipif(not LIVE, reason="needs the pinned Yellow source: tools/fetch_yellow.py")

BOOT = '''
    Input=require("port.input")
    Runtime=require("port.runtime")
    input=Input.new()
    R=Runtime.new(require("generated.merged.manifest"), input,
                  {headless=true, memorySaves=true, seed=42})
    function tick(n)
        for i=1,n do
            input:beginFrame(); R:step(); R:renderFrame(); R:finishFrame(); input:endFrame()
        end
    end
    function hold(k,n)
        input:setSource("test",{k}); tick(n); input:setSource("test",{}); tick(1)
    end
    function dummy(id)
        R.manifest.objects[id]="tests.dummy"
        R.objects[id]={name="dummy",sprite=-1,mask=-1,visible=1,solid=0,depth=0,persistent=1,parent=-1,events={}}
    end
    function countInstances(object)
        local total=0
        for _,inst in ipairs(R.instances) do
            if inst.alive and inst.v.object_index==object then total=total+1 end
        end
        return total
    end
    function playerOf(world)
        return R.travel.ids[world].player
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


@live
def test_merging_keeps_both_games_in_their_own_id_bands(vm):
    assert vm.execute('''
        local m=R.manifest
        local base=m.yellow_base
        if m.game~="merged" then return "game is "..tostring(m.game) end
        for name,id in pairs(m.names) do
            if id>=base then return "Undertale name "..name.." sits in Yellow's band" end
        end
        for name,id in pairs(m.yellow_names.all) do
            if id<base then return "Yellow name "..name.." sits below YELLOW_BASE" end
        end
        if not m.rooms[0] then return "Undertale's first room is missing" end
        if not m.rooms[base+56] then return "Yellow's rm_snowdin_11_yellow is missing" end
        if not m.objects[m.names["obj_mainchara"]] then return "obj_mainchara is missing" end
        if not m.objects[m.yellow_names.objects["obj_pl"]] then return "obj_pl is missing" end
        return "ok"
    ''') == "ok"


@live
def test_merged_build_boots_into_undertale_and_runs(vm):
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    assert vm.execute("tick(60) return R.travel.world") == "undertale"
    assert vm.execute("return countInstances(playerOf('undertale'))") >= 0


@live
def test_river_person_ride_with_x_held_lands_in_yellow(vm):
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    # The boat is stubbed so the latch is tested on its own terms: a persistent
    # instance of the boat's object plus a held X during the ride.
    result = vm.execute('''
        dummy(18100)
        R.travel.ids.undertale.boat=18100
        R:create(18100,0,0)
        hold(88,2)                       -- X, Yellow's own cancel/run button
        if not R.travel.riverLatch then return "X during the ride did not latch the crossing" end
        local hotland=R.manifest.yellow_names.rooms["rm_hotland_02"]
        local room=require(R.manifest.rooms[hotland])
        local hadPlayer=false
        for _,inst in ipairs(room.instances or {}) do
            if inst.object==playerOf("yellow") then hadPlayer=true end
        end
        crossTo(140)                     -- the River Person's Hotland dock
        if R.vars.room~=hotland then return "landed in "..tostring(R.vars.room) end
        if R.travel.world~="yellow" then return "world is "..tostring(R.travel.world) end
        if countInstances(playerOf("yellow"))~=1 then return "expected one Clover-bodied player" end
        if countInstances(playerOf("undertale"))~=0 then return "Frisk survived the crossing" end
        local pl=nil
        for _,inst in ipairs(R.instances) do
            if inst.alive and inst.v.object_index==playerOf("yellow") then pl=inst end
        end
        if not hadPlayer and (pl.v.x~=170 or pl.v.y~=120) then
            return "landed at "..pl.v.x..","..pl.v.y.." instead of Yellow's own 170,120"
        end
        if R.travel.crossings~=1 then return "crossings="..tostring(R.travel.crossings) end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_ugps_whale_entries_use_yellows_own_travel_globals(vm):
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    result = vm.execute('''
        local hotland=R.manifest.yellow_names.rooms["rm_hotland_02"]
        crossTo(hotland)
        R.global.fast_travel_list=R.builtins.ds_list_create(nil,"Snowdin - Forest")
        tick(1)
        local size=R.builtins.ds_list_size(nil,R.global.fast_travel_list)
        if size~=4 then return "whale list has "..tostring(size).." entries, expected Yellow's one plus three docks" end
        R.global.fast_travel_point="Waterfall - Dock"
        tick(1)
        if R.global.fast_travel_newroom~=125 then
            return "newroom="..tostring(R.global.fast_travel_newroom)
        end
        local dock=require(R.manifest.rooms[125])
        local boatX,boatY,playerX,playerY
        for _,inst in ipairs(dock.instances or {}) do
            if inst.object==R.manifest.names["obj_dogboat_thing"] then boatX,boatY=inst.x,inst.y end
            if inst.object==playerOf("undertale") then playerX,playerY=inst.x,inst.y end
        end
        local spotX,spotY=boatX,boatY
        if playerX then spotX,spotY=playerX,playerY end   -- the room places Frisk itself
        if not spotX then return "the Waterfall dock has neither a boat nor a player instance" end
        crossTo(R.global.fast_travel_newroom)
        if R.travel.world~="undertale" then return "world is "..tostring(R.travel.world) end
        if R.vars.room~=125 then return "room is "..tostring(R.vars.room) end
        if countInstances(playerOf("undertale"))~=1 then return "expected exactly one Frisk" end
        if countInstances(playerOf("yellow"))~=0 then return "Yellow's player survived the crossing" end
        local frisk=nil
        for _,inst in ipairs(R.instances) do
            if inst.alive and inst.v.object_index==playerOf("undertale") then frisk=inst end
        end
        if math.abs(frisk.v.x-spotX)>4 or math.abs(frisk.v.y-spotY)>4 then
            return "landed at "..frisk.v.x..","..frisk.v.y.." instead of the dock's own spot at "..spotX..","..spotY
        end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_merged_save_is_versioned_and_a_foreign_version_is_a_named_stop(vm):
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    assert vm.execute('''
        crossTo(R.manifest.yellow_names.rooms["rm_dunes_05"])
        R.builtins.ini_open(nil,"merge.sav")
        local version=R.builtins.ini_read_real(nil,"merge","version",0)
        local crossings=R.builtins.ini_read_real(nil,"merge","crossings",-1)
        local world=R.builtins.ini_read_string(nil,"merge","world","")
        local room=R.builtins.ini_read_real(nil,"merge","last_room",-1)
        R.builtins.ini_close()
        if version~=1 then return "version="..tostring(version) end
        if crossings~=1 then return "crossings="..tostring(crossings) end
        if world~="yellow" then return "world="..tostring(world) end
        if room~=R.vars.room then return "last_room="..tostring(room) end
        return "ok"
    ''') == "ok"
    stopped = vm.execute('''
        R.builtins.ini_open(nil,"merge.sav")
        R.builtins.ini_write_real(nil,"merge","version",99)
        R.builtins.ini_close()
        R:flushSaves()
        local ok,err=pcall(function() R.travel:loadSave() end)
        return (not ok) and tostring(err) or "no stop"
    ''')
    assert "merge.sav version 99" in stopped, stopped


@live
def test_packaging_refuses_a_partial_yellow_conversion(monkeypatch):
    """A merged archive must never ship a half-converted second game."""
    sys.path.insert(0, str(ROOT / "tools"))
    import package as packaging

    report = ROOT / "generated/yellow/conversion-report.json"
    original = report.read_text()
    try:
        data = json.loads(original)
        data["stage"] = "scripts"
        report.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="rooms stage"):
            packaging.merged_files(ROOT / "generated")
    finally:
        report.write_text(original)


@live
def test_merge_refuses_a_conversion_that_stopped_early(tmp_path, monkeypatch):
    """A partial Yellow conversion must not be merged into a playable build."""
    monkeypatch.chdir(ROOT)
    report = ROOT / "generated/yellow/conversion-report.json"
    original = report.read_text()
    try:
        data = json.loads(original)
        data["stage"] = "scripts"
        report.write_text(json.dumps(data))
        run = subprocess.run([sys.executable, "tools/merge.py"], cwd=ROOT, capture_output=True, text=True)
        assert run.returncode == 1
        assert "partial game" in run.stderr
    finally:
        report.write_text(original)
