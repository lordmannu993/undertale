"""Merged-build gates: one manifest, two worlds, and the cross-game travel.

These prove conversion and routing headlessly: the ID bands survive merging, the
merged runtime boots into Undertale, the River Person and UGPS whale routes land
in the right rooms with exactly one player, and the merged save layer is
versioned. They do NOT certify native rendering or a played-through crossing.
"""
import json
import re
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
                  {headless=true, memorySaves=true, trace=true, seed=42})
    function tick(n)
        for i=1,n do
            input:beginFrame(); R:step(); R:renderFrame(); R:finishFrame(); input:endFrame()
        end
    end
    function hold(k,n)
        input:setSource("test",{k}); tick(n); input:setSource("test",{}); tick(1)
    end
    function press(k)
        input:setSource("test",{k}); tick(1); input:setSource("test",{}); tick(1)
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
    function dialogueOpen()
        for _,i in ipairs(R.instances) do
            if i.alive and i.v.object_index==R.manifest.yellow_names.objects["obj_dialogue"] then return true end
        end
        return false
    end
    function clearDialogue()
        -- Item messages type out at their own text speed; taps advance them
        -- only once typing has reached the end, so tap and wait.
        for i=1,60 do
            if not dialogueOpen() then return true end
            press(90); tick(3)
        end
        return not dialogueOpen()
    end
    function menuOpen()
        press(67); tick(2)   -- C, Yellow's own pause cluster
        return R:select(R.manifest.yellow_names.objects["obj_pause_menu"])[1] ~= nil
    end
    function equipFromSlot(number)
        -- Drive Yellow's own pause menu: ITEM, down to the slot, USE, USE.
        assert(menuOpen(), "Yellow's pause menu did not open")
        press(90); tick(2)
        for _=2,number do press(40); tick(1) end
        press(90); tick(1)
        press(90); tick(3)
        assert(clearDialogue(), "the equip message never closed")
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
        -- The seeded entry plus every stop the merged build offers: Yellow's
        -- own seven labels and the three Undertale docks ("Snowdin - Forest"
        -- is one list, not two).
        if size~=10 then return "whale list has "..tostring(size).." entries, expected ten stops" end
        if not R.truth(R.global.player_can_travel) then return "the UGPS switch is still closed" end
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
def test_river_person_boat_and_riverman_exist_below_the_plot_gate(vm):
    """The owner's ask: the River Person is there before the game's own plot gate.

    obj_dogboat_thing deletes itself in its own Create event while global.plot is
    under 122, so every dock is empty until Undyne's chase is over. The port
    lifts that guard for the one event. global.plot itself must be untouched
    afterwards: the rest of the game reads it.
    """
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    result = vm.execute('''
        R.global.plot=10
        local boat=R.manifest.names["obj_dogboat_thing"]
        local riverman=R.manifest.names["obj_riverman"]
        if not boat or not riverman then return "the merged manifest is missing the River Person's own resources" end
        for _,room in ipairs({70,125,140}) do
            crossTo(room)
            local boats=countInstances(boat)
            if boats~=1 then return "room "..room.." placed "..tostring(boats).." boats at plot 10" end
            local men=countInstances(riverman)
            if men~=1 then return "room "..room.." has "..tostring(men).." River Person instances at plot 10" end
            if R.global.plot~=10 then return "room "..room.." left global.plot at "..tostring(R.global.plot) end
        end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_ugps_whale_lands_and_flies_a_yellow_stop_to_its_merged_room(vm):
    """Ring a bell, take Travel, and land in the far world's own room.

    Proves the three UGPS pieces together: the whale's approach reaches its own
    landing frame, Yellow's Mail/Travel choicer opens its fast-travel menu, and
    a Yellow stop travels to the merged ID of that room - not to Undertale's
    room of the same number, which is what the menu's own room numbers mean
    without the merge's ID space.
    """
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    result = vm.execute('''
        local objs=R.manifest.yellow_names.objects
        local here=R.manifest.yellow_names.rooms["rm_hotland_02"]
        crossTo(here)
        if not R.truth(R.global.player_can_travel) then return "the UGPS switch is still closed" end
        local pl
        for _,inst in ipairs(R.instances) do
            if inst.alive and inst.v.object_index==playerOf("yellow") then pl=inst end
        end
        R:create(objs["obj_mail_station_hotland"], pl.v.x+20, pl.v.y)
        tick(5)
        press(90)                        -- Z on the bell
        local whale
        local landing=R.frame+1200
        while R.frame<landing do
            whale=R:select(objs["obj_mail_whale"])[1]
            if whale and whale.v.scene==2 then break end
            tick(2)
        end
        if not whale or whale.v.scene~=2 then
            return "the whale never landed: scene="..tostring(whale and whale.v.scene)
                .." fly_speed="..tostring(whale and whale.v.fly_speed)
        end
        if whale.v.fly_speed~=0 then return "the landed whale is still moving" end
        -- Yellow's own choicer: advance until the Mail/Travel choice is up,
        -- move to Travel (p=2), then confirm with Yellow's confirm key.
        local choiceSeen=nil
        for i=1,60 do
            press(90)
            tick(4)
            local dialogue
            for _,inst in ipairs(R.instances) do
                if inst.alive and inst.v.object_index==objs["obj_dialogue"] then dialogue=inst end
            end
            if dialogue and R.truth(dialogue.v.choice) then
                tick(20)
                for _=1,12 do
                    press(39)
                    tick(3)
                    if dialogue.v.p==2 then break end
                end
                if dialogue.v.p~=2 then return "the Mail/Travel choice never reached Travel" end
                press(90)
                tick(10)
                choiceSeen=i
                break
            end
        end
        if not choiceSeen then return "the Mail/Travel choice never appeared" end
        local opening=R.frame+900
        local menu
        while R.frame<opening do
            menu=R:select(objs["obj_fast_travel_menu"])[1]
            if menu then break end
            -- "Where in the world would you like to fly?" still has to be read
            -- through Yellow's own message advance.
            press(90)
            tick(6)
        end
        if not menu then return "Travel did not open the fast-travel menu" end
        local target="Dunes - West Mines"
        for _=1,20 do
            if menu.v.point_selected==target then break end
            R.global.down_keyp=1
            if menu.alive then R:event(menu,3,0) end
            R.global.down_keyp=0
            tick(2)
        end
        if menu.v.point_selected~=target then
            return "the menu never highlighted "..target..", it stopped on "..tostring(menu.v.point_selected)
        end
        press(90)
        tick(10)
        if R.global.fast_travel_point~=target then
            return "the menu confirmed "..tostring(R.global.fast_travel_point)
        end
        local wanted=R.manifest.yellow_names.rooms["rm_dunes_05"]
        local leaving=R.vars.room
        local flight=R.frame+4000
        while R.frame<flight and R.vars.room==leaving do press(90); tick(10) end
        if R.vars.room~=wanted then
            return "flew to room "..tostring(R.vars.room).." instead of the merged "..tostring(wanted)
        end
        if R.travel.world~="yellow" then return "world="..tostring(R.travel.world) end
        if countInstances(playerOf("yellow"))~=1 then return "expected exactly one player after the flight" end
        if countInstances(playerOf("undertale"))~=0 then return "Frisk survived the whale flight" end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_yellow_travel_points_are_the_pinned_sources_own_stops():
    """Every offered Yellow stop is read back out of the pinned source.

    The four labels the Dunes-42 whale registers, the three the room creation
    codes register, and the room each one flies to - straight from
    obj_fast_travel_menu's own switch, with the room ID the merge rebases.
    """
    import json

    from tools.yellow.registry import Registry

    source = ROOT / "yellow_src"
    provenance = json.loads((ROOT / "port" / "yellow_source.json").read_text())
    registry = Registry(source, provenance)
    rooms = {number: name for name, number in registry.sections["rooms"].items()}

    registered = set()
    dunes = (source / "objects/obj_mail_whale_dunes_42/Create_0.gml").read_text()
    registered.update(re.findall(r'scr_fasttravel_add\("([^"]+)"\)', dunes))
    for room in ("rm_hotland_02", "rm_steamworks_24", "rm_steamworks_32"):
        code = (source / "rooms" / room / "RoomCreationCode.gml").read_text()
        registered.update(re.findall(r'scr_fasttravel_add\("([^"]+)"\)', code))
    assert len(registered) == 7, registered

    menu = (source / "objects/obj_fast_travel_menu/Step_0.gml").read_text()
    expected = {}
    for block in re.finditer(r'case "([^"]+)":\s*global\.fast_travel_newroom = (\d+);', menu):
        expected[block.group(1)] = rooms[int(block.group(2))]
    assert set(expected) == registered, (sorted(expected), sorted(registered))
    # The file under test offers exactly that list, in its own order.
    offered = dict(re.findall(r'\{label = "([^"]+)", room = "([^"]+)"\}',
                              (ROOT / "port" / "travel.lua").read_text()))
    assert offered == expected, offered


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


def crossToYellow(vm):
    """The native crossing path: plot 122 arms the placed dock boat, X aims
    the River Person ride at Yellow, and room 140 is the boat's own call."""
    vm.execute('''
        R.global.plot=122
        R:gotoRoom(140); R:applyTransitions(); tick(3)
        assert(R.roomState.name=="room_fire_dock", "Hotland dock did not load: "..tostring(R.roomState.name))
        hold(88,2)
        assert(R.travel.riverLatch, "holding X during the ride did not arm the crossing")
        R:gotoRoom(140); R:applyTransitions(); tick(10)
        assert(R.travel.world=="yellow" and R.roomState.name=="rm_hotland_02",
            "landed in "..tostring(R.roomState.name))
    ''')


def drawnSprites(vm):
    table = vm.eval('''
        (function()
            local t={}
            for _,entry in ipairs(R.drawLog) do
                if entry[1]=="sprite" then t[#t+1]=entry[2] end
            end
            return t
        end)()
    ''')
    return [str(name) for name in table.values()]


@live
def test_frisk_draws_the_yellow_player_and_keeps_clover_only_where_he_has_no_pose(vm):
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    crossToYellow(vm)
    assert vm.execute("R.drawLog={}; tick(2) return 'ok'") == "ok"
    names = drawnSprites(vm)
    assert any(name.startswith("spr_mainchara") for name in names), \
        f"Yellow's player was not drawn as Frisk; drew {names}"
    for name in names:
        assert name not in ("spr_pl_up", "spr_pl_down", "spr_pl_left", "spr_pl_right"), \
            f"Clover's walk sprite {name} leaked into the merged rendering"
    # The remap is pixels-only: gameplay lookups still resolve to Clover, and
    # Undertale's own sprites are never touched.
    assert vm.execute('''
        local sprites=R.manifest.yellow_names.sprites
        if R.spriteForDraw(sprites["spr_pl_down"])~=R.constants.spr_maincharad then
            return "walk sprite did not remap"
        end
        if R.spriteForDraw(sprites["spr_pl_run_down"])~=sprites["spr_pl_run_down"] then
            return "the run animation must stay Clover's"
        end
        if R.spriteForDraw(R.constants.spr_maincharad)~=R.constants.spr_maincharad then
            return "an Undertale sprite was remapped"
        end
        return "ok"
    ''') == "ok"


@live
def test_x_button_runs_with_clovers_run_sprites(vm):
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    crossToYellow(vm)
    result = vm.execute('''
        local pl
        for _,inst in ipairs(R.instances) do
            if inst.alive and inst.v.object_index==R.manifest.yellow_names.objects["obj_pl"] then pl=inst end
        end
        local function probe(withX)
            local x0,y0=pl.v.x,pl.v.y
            input:setSource("test",withX and {40,88} or {40}); tick(2)
            local moved=pl.v.y-y0
            local sprite,sprinting=pl.v.sprite_index,pl.v.is_sprinting
            input:setSource("test",{}); tick(1)
            return moved,sprite,sprinting
        end
        local runDistance,runSprite,sprinting=probe(true)
        if not R.truth(sprinting) then return "holding X did not sprint" end
        if runSprite~=R.manifest.yellow_names.sprites["spr_pl_run_down"] then
            return "sprint sprite is "..tostring(runSprite)..", not Clover's run cycle"
        end
        local walkDistance,walkSprite=probe(false)
        if walkSprite~=R.manifest.yellow_names.sprites["spr_pl_down"] then
            return "walk sprite is "..tostring(walkSprite)
        end
        -- Yellow's own rule: plspd 3 walking, plspd+2 running.
        if runDistance<=walkDistance then
            return "run distance "..runDistance.." <= walk "..walkDistance
        end
        if runDistance~=10 or walkDistance~=6 then
            return "unexpected distances: run "..runDistance..", walk "..walkDistance
        end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_pause_menu_equips_clovers_ammo_and_accessory_beside_frisks_gear(vm):
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    crossToYellow(vm)
    result = vm.execute('''
        local weapon,armor=R.global.weapon,R.global.armor
        R.global.item_slot[2]="Silver Ammo"
        R.global.item_slot[3]="Steel Buckle"
        equipFromSlot(2)
        if R.global.player_weapon_modifier~="Silver Ammo" then
            return "ammo slot is "..tostring(R.global.player_weapon_modifier)
        end
        -- Silver Ammo's own value from Yellow's scr_item_stats_weapon_mod.
        if R.global.player_weapon_modifier_attack~=3 then
            return "ammo attack is "..tostring(R.global.player_weapon_modifier_attack)
        end
        -- Equipping swaps: the slot now holds what was equipped before it.
        if R.global.item_slot[2]~="Rubber Ammo" then
            return "slot 2 holds "..tostring(R.global.item_slot[2])
        end
        equipFromSlot(3)
        if R.global.player_armor_modifier~="Steel Buckle" then
            return "accessory slot is "..tostring(R.global.player_armor_modifier)
        end
        if R.global.player_armor_modifier_defense~=7 then
            return "accessory defense is "..tostring(R.global.player_armor_modifier_defense)
        end
        -- Frisk's own equipment is untouched by Yellow's menu.
        if R.global.weapon~=weapon or R.global.armor~=armor then
            return "Undertale's weapon/armor moved: "..tostring(R.global.weapon).."/"..tostring(R.global.armor)
        end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_equipped_slots_survive_crossings_through_the_merged_save(vm):
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    crossToYellow(vm)
    vm.execute('''
        R.global.item_slot[2]="Silver Ammo"
        R.global.item_slot[3]="Steel Buckle"
        equipFromSlot(2)
        equipFromSlot(3)
    ''')
    assert vm.execute('''
        R.global.fast_travel_point="Waterfall - Dock"; tick(2)
        R:gotoRoom(125); R:applyTransitions(); tick(5)
        if R.travel.world~="undertale" or R.vars.room~=125 then
            return "the whale crossing failed: world "..tostring(R.travel.world)
        end
        R.builtins.ini_open(nil,"merge.sav")
        local ammo=R.builtins.ini_read_string(nil,"merge","ammo","")
        local accessory=R.builtins.ini_read_string(nil,"merge","accessory","")
        R.builtins.ini_close()
        if ammo~="Silver Ammo" then return "save ammo="..tostring(ammo) end
        if accessory~="Steel Buckle" then return "save accessory="..tostring(accessory) end
        return "ok"
    ''') == "ok"
    # scr_initialize resets the slots on every crossing; the merged save must
    # bring the loadout back, with Yellow's own stat scripts re-run.
    assert vm.execute('''
        hold(88,2)
        R:gotoRoom(140); R:applyTransitions(); tick(10)
        if R.travel.world~="yellow" then return "world="..tostring(R.travel.world) end
        if R.global.player_weapon_modifier~="Silver Ammo" then
            return "ammo="..tostring(R.global.player_weapon_modifier)
        end
        if R.global.player_weapon_modifier_attack~=3 then
            return "ammo attack="..tostring(R.global.player_weapon_modifier_attack)
        end
        if R.global.player_armor_modifier~="Steel Buckle" then
            return "accessory="..tostring(R.global.player_armor_modifier)
        end
        if R.global.player_armor_modifier_defense~=7 then
            return "accessory defense="..tostring(R.global.player_armor_modifier_defense)
        end
        return "ok"
    ''') == "ok"


@live
def test_merged_package_carries_every_referenced_yellow_asset():
    """The records open their assets by pinned-source path; the archive must
    carry exactly those files."""
    sys.path.insert(0, str(ROOT / "tools"))
    import package as packaging

    files = packaging.merged_files(ROOT / "generated")
    carried = {path.as_posix() for path in files if path.is_relative_to(ROOT / "yellow_src")}
    assert len(carried) > 15000, f"only {len(carried)} pinned asset files carried"
    assert all((ROOT / name).is_file() for name in carried)
    assert any("/sprites/spr_pl_down/" in name for name in carried)
    assert any("/sounds/" in name for name in carried)


@live
def test_merged_packaging_stops_when_a_referenced_asset_is_absent(tmp_path, monkeypatch):
    """A referenced pinned file that is missing stops the build instead of
    failing later on a phone with a blank, silent second world."""
    sys.path.insert(0, str(ROOT / "tools"))
    import package as packaging

    generated = tmp_path / "generated"
    (generated / "yellow/assets").mkdir(parents=True)
    (generated / "merged").mkdir(parents=True)
    (generated / "yellow/conversion-report.json").write_text(json.dumps(
        {"stage": "rooms", "scripts": {"compile_errors": []}, "objects": {"compile_errors": []},
         "rooms": {"compile_errors": []}}))
    (generated / "yellow/assets/sprites_0.lua").write_text(
        'return {[1000023]={["name"]="spr_missing_body",'
        '["frames"]={"yellow_src/sprites/spr_missing_body/no_frame.png"}}}\n')
    (generated / "merged/manifest.lua").write_text("-- test\n")
    # tools/merge.py runs against the real tree; its result is not what this
    # exercises, and the fake tree has no tools/ to run it from.
    monkeypatch.setattr(packaging.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(packaging, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="absent"):
        packaging.merged_files(generated)


def walk_poses_in_source() -> set[str]:
    """Yellow's walk-cycle poses, read from the pinned source's own folders.

    The remap table claims to be the complete walk family - the four base
    directions plus every recolour the pinned conversion carries. This derives
    that family from the folders themselves so the claim cannot quietly rot.
    """
    import re
    pattern = re.compile(r"^spr_pl_(up|down|left|right)(_(geno|water|water_geno|snowdin|snowdin_geno|roof|roof_geno))?$")
    return {p.name for p in (ROOT / "yellow_src/sprites").iterdir()
            if p.is_dir() and pattern.match(p.name)}


def run_poses_in_source() -> set[str]:
    return {p.name for p in (ROOT / "yellow_src/sprites").iterdir()
            if p.is_dir() and p.name.startswith("spr_pl_run_")}


def frisk_name_lists() -> tuple[set[str], set[str]]:
    """The two name lists port/frisk.lua checks, read straight from the module."""
    import re
    text = (ROOT / "port/frisk.lua").read_text()
    def listed(constant: str) -> set[str]:
        body = text.split(f"Frisk.{constant} = ", 1)[1].split("}", 1)[0]
        return set(re.findall(r'"(spr_pl_[a-z_]+)"', body))
    return listed("BODY_SPRITES"), listed("RUN_SPRITES")


@live
def test_the_walk_remap_is_the_whole_walk_family_and_no_run_pose_enters_it():
    """The two lists are checked against the pinned source, not against memory."""
    walks, runs = frisk_name_lists()
    assert walks == walk_poses_in_source(), \
        f"walk remap differs from the pinned source: {walks ^ walk_poses_in_source()}"
    assert runs == run_poses_in_source(), \
        f"run list differs from the pinned source: {runs ^ run_poses_in_source()}"
    assert not (walks & runs), "a run pose is listed as a walk pose"
    assert len(runs) == 24, f"expected 24 run poses, listed {len(runs)}"


@live
def test_the_frisk_report_counts_the_remap_and_promises_the_run_swap(vm):
    """The startup report must state both halves: walking is Frisk, running is Clover.

    It used to count the remap with #remap on a table keyed by Yellow's
    1,000,000-band IDs, which has no array part - so it reported "0 of
    Yellow's player body sprites" on every launch, however well the rendering
    worked.
    """
    result = vm.execute('''
        local report
        for _,line in ipairs(R.warningList) do
            if line:find("Frisk-only rendering",1,true) then report=line end
        end
        if not report then return "no Frisk remap report at startup" end
        local mapped=tonumber(report:match("(%d+) of Yellow's"))
        if mapped ~= R.friskRemap.walk or mapped ~= 28 then
            return "the report says "..tostring(mapped).." of "..tostring(R.friskRemap.walk).." walk poses"
        end
        if not report:find("running swaps to Clover",1,true) then
            return "the report does not mention the run swap: "..report
        end
        -- Both halves of the contract, as the renderer will apply them.
        local Frisk=require("port.frisk")
        local sprites=R.manifest.yellow_names.sprites
        for _,name in ipairs(Frisk.RUN_SPRITES) do
            local id=sprites[name]
            if not id then return "run pose "..name.." is missing from the merged manifest" end
            if R.spriteForDraw(id)~=id then return "run pose "..name.." was remapped to Frisk" end
        end
        for _,name in ipairs(Frisk.BODY_SPRITES) do
            local id=sprites[name]
            if not id then return "walk pose "..name.." is missing from the merged manifest" end
            if R.spriteForDraw(id)==id then return "walk pose "..name.." was not remapped to Frisk" end
        end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_every_run_family_the_game_selects_stays_clover(vm):
    """Sprinting selects Clover's run sprite in every family the source can pick.

    scr_determine_player_sprites is the game's own selector: it is called here
    directly, so route (base/genocide) and global.player_sprites (the water
    recolours) are both covered without needing a room that happens to be
    water or a genocide save.
    """
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    crossToYellow(vm)
    result = vm.execute('''
        local sprites=R.manifest.yellow_names.sprites
        local pl
        for _,inst in ipairs(R.instances) do
            if inst.alive and inst.v.object_index==R.manifest.yellow_names.objects["obj_pl"] then pl=inst end
        end
        if not pl then return "no player instance in Yellow's world" end
        local function determine()
            R:script("scr_determine_player_sprites", R:scope(pl))
            return {right=pl.v.rsprite,up=pl.v.usprite,left=pl.v.lsprite,down=pl.v.dsprite}
        end
        local function check(label, route, playerSprites, walk, run)
            local routeBefore,spritesBefore=R.global.route,R.global.player_sprites
            R.global.route,R.global.player_sprites=route,playerSprites
            -- GML's true/false are the numbers 1/0 here, exactly as the game's
            -- own scr_normal_state writes them; a Lua boolean would not match
            -- the script's own "is_sprinting == true" test.
            pl.v.is_sprinting=0
            local walked=determine()
            pl.v.is_sprinting=1
            local ran=determine()
            R.global.route,R.global.player_sprites=routeBefore,spritesBefore
            for direction,name in pairs(walk) do
                if walked[direction]~=sprites[name] then
                    return label.." walk "..direction.." selected "..tostring(walked[direction])..", expected "..name
                end
                if R.spriteForDraw(sprites[name])==sprites[name] then
                    return label.." walk pose "..name.." was not drawn as Frisk"
                end
            end
            for direction,name in pairs(run) do
                if ran[direction]~=sprites[name] then
                    return label.." run "..direction.." selected "..tostring(ran[direction])..", expected "..name
                end
                if R.spriteForDraw(sprites[name])~=sprites[name] then
                    return label.." run pose "..name.." was remapped to Frisk"
                end
            end
            return nil
        end
        local base={right="spr_pl_right",up="spr_pl_up",left="spr_pl_left",down="spr_pl_down"}
        local baseRun={right="spr_pl_run_right",up="spr_pl_run_up",left="spr_pl_run_left",down="spr_pl_run_down"}
        local geno={right="spr_pl_right_geno",up="spr_pl_up",left="spr_pl_left_geno",down="spr_pl_down_geno"}
        local genoRun={right="spr_pl_run_right_geno",up="spr_pl_run_up_geno",
                       left="spr_pl_run_left_geno",down="spr_pl_run_down_geno"}
        local water={right="spr_pl_right_water",up="spr_pl_up_water",left="spr_pl_left_water",down="spr_pl_down_water"}
        local waterRun={right="spr_pl_run_right_water",up="spr_pl_run_up_water",
                        left="spr_pl_run_left_water",down="spr_pl_run_down_water"}
        local waterGeno={right="spr_pl_right_water_geno",up="spr_pl_up_water",
                         left="spr_pl_left_water_geno",down="spr_pl_down_water_geno"}
        local waterGenoRun={right="spr_pl_run_right_water_geno",up="spr_pl_run_up_water_geno",
                            left="spr_pl_run_left_water_geno",down="spr_pl_run_down_water_geno"}
        local cases={
            {"base",check("base",2,"normal",base,baseRun)},
            {"genocide",check("genocide",3,"normal",geno,genoRun)},
            {"water",check("water",2,"water",water,waterRun)},
            {"water+genocide",check("water+genocide",3,"water",waterGeno,waterGenoRun)},
        }
        for _,case in ipairs(cases) do if case[2] then return case[2] end end
        -- And a real sprint in the room, so the selector is not the only proof.
        pl.v.x,pl.v.y=170,120
        input:setSource("test",{39,88}); tick(3)
        if pl.v.sprite_index~=sprites["spr_pl_run_right"] then
            return "a real right-hand sprint drew "..tostring(pl.v.sprite_index)
        end
        input:setSource("test",{})
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_autorun_runs_while_walking_and_x_walks_instead(vm):
    """AUTO RUN is Yellow's own option, driven from the port's pause menu.

    With it on, moving runs - which is also the fastest way to see Clover's run
    animation - and the run cluster becomes the walk key, exactly as Yellow's
    own scr_normal_state decides it. It has to survive a crossing, because
    scr_initialize resets Yellow's globals on the way in.
    """
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    crossToYellow(vm)
    result = vm.execute('''
        local sprites=R.manifest.yellow_names.sprites
        local pl
        -- Crossing destroys the other world's persistent instances, so the
        -- player is looked up again after every crossing instead of kept.
        local function player()
            for _,inst in ipairs(R.instances) do
                if inst.alive and inst.v.object_index==R.manifest.yellow_names.objects["obj_pl"] then pl=inst end
            end
            assert(pl and pl.alive, "no live player instance in Yellow's world")
            return pl
        end
        player()
        local function probe(keys)
            player()
            pl.v.x,pl.v.y=170,120
            local y0=pl.v.y
            input:setSource("test",keys); tick(4)
            local moved=pl.v.y-y0
            local sprite,sprinting=pl.v.sprite_index,pl.v.is_sprinting
            input:setSource("test",{}); tick(1)
            return moved,sprite,sprinting
        end
        if R.global.option_autorun~=0 then return "AUTO RUN must start off" end
        R:setAutorun(true)
        if R.global.option_autorun~=1 then
            return "AUTO RUN did not reach Yellow's own option: "..tostring(R.global.option_autorun)
        end
        local runDistance,runSprite,sprinting=probe({40})
        if not R.truth(sprinting) or runSprite~=sprites["spr_pl_run_down"] then
            return "AUTO RUN did not run while walking: sprite "..tostring(runSprite)
                ..", is_sprinting "..tostring(sprinting)
        end
        local walkDistance,walkSprite,walkSprinting=probe({40,88})
        if R.truth(walkSprinting) or walkSprite~=sprites["spr_pl_down"] then
            return "holding the run button must walk with AUTO RUN on: sprite "..tostring(walkSprite)
                ..", is_sprinting "..tostring(walkSprinting)
        end
        if runDistance<=walkDistance then
            return "AUTO RUN run distance "..runDistance.." is not faster than walking "..walkDistance
        end
        -- The port's setting is written where the game itself keeps it.
        local B=R.builtins
        B.ini_open(nil,"Controls.sav")
        local saved=B.ini_read_real(nil,"Controls","autorun",0)
        B.ini_close()
        if saved~=1 then return "Controls.sav autorun is "..tostring(saved) end
        -- ...and it survives leaving and re-entering Yellow's world.
        R:gotoRoom(70); R:applyTransitions(); tick(2)
        R.global.plot=122
        R:gotoRoom(140); R:applyTransitions(); tick(3)
        input:setSource("test",{88}); tick(2); input:setSource("test",{})
        R:gotoRoom(140); R:applyTransitions(); tick(10)
        if R.global.option_autorun~=1 then
            return "AUTO RUN was lost across a crossing: "..tostring(R.global.option_autorun)
        end
        player()
        R:setAutorun(false)
        local offDistance,offSprite,offSprinting=probe({40})
        if R.truth(offSprinting) or offSprite~=sprites["spr_pl_down"] then
            return "AUTO RUN off must walk again: sprite "..tostring(offSprite)
        end
        local xDistance,xSprite,xSprinting=probe({40,88})
        if not R.truth(xSprinting) or xSprite~=sprites["spr_pl_run_down"] then
            return "with AUTO RUN off the run button must run again: sprite "..tostring(xSprite)
        end
        return "ok"
    ''')
    assert result == "ok", result
