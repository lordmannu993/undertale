"""Unified-fusion piece 5d: one Player + World save.

Save points in either world write merge.sav version 2. Load from either world's
script restores that document, including injured HP (Undertale's scr_load would
heal to max). Version 1 is copied to merge.sav.v1 and migrated without inventing
LV. An unknown version stops by name. Re-entering Yellow does not run
scr_initialize over story, route, NPC maps or event lists.

Not claimed: Android, audio, a played save-point menu, or pixel-perfect
original parity. Headless converted flow only.
"""
import pytest

from test_yellow_merge import live, merged, vm, yellow_rooms  # noqa: F401


def boot(vm):
    assert vm.execute(
        "local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)"
    ) == "ok"


@live
def test_reentry_does_not_reset_yellow_world_progress(vm):
    """scr_initialize is a new-game reset. A second entry must not run it.

    Without the re-entry guard this returns story=0, route=2, a new npc_map
    id, and item_stock[2]=1.
    """
    boot(vm)
    result = vm.execute('''
        local yellow=R.manifest.yellow_names.rooms["rm_hotland_02"]
        crossTo(yellow)
        assert(R.travel.yellowReady, "the first entry did not initialize Yellow")
        R.global.story=6
        R.global.route=1
        R.global.item_stock[2]=0
        R.global.saveroom="Snowdin - Resort"
        R.global.tinypuzzle=9
        local map=R.global.npc_map
        R.builtins.ds_map_add(nil, map, "dalv", 3)
        R.builtins.ds_list_add(nil, R.global.fast_travel_list, "Custom Stop")
        crossTo(140)
        crossTo(yellow)
        if R.global.story~=6 then return "story reset to "..tostring(R.global.story) end
        if R.global.route~=1 then return "route reset to "..tostring(R.global.route) end
        if R.global.item_stock[2]~=0 then return "item_stock reset to "..tostring(R.global.item_stock[2]) end
        if R.global.saveroom~="Snowdin - Resort" then
            return "saveroom reset to "..tostring(R.global.saveroom)
        end
        if R.global.tinypuzzle~=9 then return "tinypuzzle reset to "..tostring(R.global.tinypuzzle) end
        if R.global.npc_map~=map then return "npc_map was replaced on re-entry" end
        if R.builtins.ds_map_find_value(nil, map, "dalv")~=3 then return "npc entry was cleared" end
        if R.builtins.ds_list_find_index(nil, R.global.fast_travel_list, "Custom Stop")<0 then
            return "fast travel list was recreated"
        end
        if R.global.hp==nil then return "player missing" end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_either_world_save_point_round_trips_player_and_world(vm):
    """scr_save and scr_savegame write one document; the other world's load reads it.

    Without the unified load, scr_load heals HP to max and scr_savegame stops
    on ds_grid_write. A Yellow item and flag[99] would not survive the other
    world's load.
    """
    boot(vm)
    result = vm.execute('''
        local E=R:scope(R.instances[1])
        R.global.xp=709
        R:call("scr_levelup", E)
        R.global.hp=13
        R.global.gold=317
        R.global.plot=42
        R.global.flag[99]=7
        R.player.inventory[2]="Lemonade"
        R.player.equipment.ammo="Silver Ammo"
        R.player.abilities.run=1
        local saved=R:call("scr_save", E)
        if saved==nil then return "scr_save returned nil" end
        local B=R.builtins
        B.ini_open(nil, "merge.sav")
        local version=B.ini_read_real(nil, "merge", "version", 0)
        local lv=B.ini_read_string(nil, "Player", "LV", "")
        local hp=B.ini_read_string(nil, "Player", "HP", "")
        local item=B.ini_read_string(nil, "Player", "Inventory.2", "")
        local area=B.ini_read_string(nil, "World", "Current Area", "")
        local plot=B.ini_read_string(nil, "World", "Story.plot", "")
        local flag=B.ini_read_string(nil, "World", "Event.flag.99", "")
        B.ini_close()
        if version~=2 then return "version="..tostring(version) end
        if lv~="n:8" then return "LV="..lv end
        if hp~="n:13" then return "HP="..hp end
        if item~="s:Lemonade" then return "item="..item end
        if plot~="n:42" then return "plot="..plot end
        if flag~="n:7" then return "flag="..flag end
        if area=="" then return "no Current Area" end
        if B.file_exists(nil, "file0")~=1 then return "file0 projection missing" end
        if B.file_exists(nil, "Save.sav")~=1 then return "Save.sav projection missing" end
        R.global.hp=1
        R.global.gold=0
        R.global.plot=0
        R.global.flag[99]=0
        R.player.inventory[2]=0
        R.player.equipment.ammo=0
        R:call("scr_loadgame", E)
        if R.global.hp~=13 then return "load healed or dropped HP: "..tostring(R.global.hp) end
        if R.global.gold~=317 then return "gold="..tostring(R.global.gold) end
        if R.global.lv~=8 then return "lv="..tostring(R.global.lv) end
        if R.player.inventory[2]~="Lemonade" then
            return "inventory="..tostring(R.player.inventory[2])
        end
        if R.global.player_weapon_modifier~="Silver Ammo" then
            return "ammo="..tostring(R.global.player_weapon_modifier)
        end
        if R.global.plot~=42 or R.global.flag[99]~=7 then
            return "world not restored: plot "..tostring(R.global.plot)
        end
        if R.player.abilities.run~=1 then return "run ability dropped" end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_yellow_save_point_loads_from_undertale_and_keeps_the_room(vm):
    """A Yellow save point must not stop, and Undertale's scr_load must enter that room."""
    boot(vm)
    result = vm.execute('''
        local yellow=R.manifest.yellow_names.rooms["rm_hotland_02"]
        crossTo(yellow)
        R.global.story=4
        R.global.hp=11
        local pl=R:select(playerOf("yellow"))[1]
        assert(pl, "no Yellow player to save from")
        local saved=R:call("scr_savegame", R:scope(pl))
        if saved~=0 then return "scr_savegame returned "..tostring(saved) end
        local B=R.builtins
        B.ini_open(nil, "merge.sav")
        local world=B.ini_read_string(nil, "World", "World", "")
        local story=B.ini_read_string(nil, "World", "Story.story", "")
        local name=B.ini_read_string(nil, "World", "Current Area Name", "")
        B.ini_close()
        if world~="s:yellow" then return "world="..world end
        if story~="n:4" then return "story="..story end
        if name~="s:rm_hotland_02" then return "area="..name end
        if B.file_exists(nil, "file0")~=1 then return "UT continue would not see this save" end
        R.global.story=0
        R.global.hp=20
        -- Undertale's loader, called from the Yellow room. A crossing between
        -- the save point and the load would be a later travel write.
        R:call("scr_load", R:scope(pl))
        if R.global.story~=4 then return "story after UT load="..tostring(R.global.story) end
        if R.global.hp~=11 then return "HP after UT load="..tostring(R.global.hp) end
        if R.roomState.name~="rm_hotland_02" then
            return "loaded room "..tostring(R.roomState.name)
        end
        if R.travel.world~="yellow" then return "world after load="..tostring(R.travel.world) end
        -- Returning to Undertale recreates obj_time, whose Create runs
        -- SCR_GAMESTART. That reset must not become the save.
        crossTo(140)
        B.ini_open(nil, "merge.sav")
        local kept=B.ini_read_string(nil, "Player", "HP", "")
        local keptStory=B.ini_read_string(nil, "World", "Story.story", "")
        B.ini_close()
        if kept~="n:11" then return "return crossing saved reset HP "..kept end
        if keptStory~="n:4" then return "return crossing saved story "..keptStory end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_legacy_v1_is_copied_aside_and_unknown_versions_stop(vm):
    """Version 1 is not a Player save. Migrating it must not invent LV, and must keep the bytes."""
    boot(vm)
    planted = vm.execute('''
        local B=R.builtins
        B.ini_open(nil, "merge.sav")
        B.ini_write_real(nil, "merge", "version", 1)
        B.ini_write_real(nil, "merge", "crossings", 4)
        B.ini_write_real(nil, "merge", "last_room", 140)
        B.ini_write_string(nil, "merge", "world", "yellow")
        B.ini_write_string(nil, "merge", "ammo", "Silver Ammo")
        B.ini_write_string(nil, "merge", "accessory", "Steel Buckle")
        B.ini_close()
        R:flushSaves()
        return R.saveMemory["merge.sav"]
    ''')
    migrated = vm.execute('''
        R.travel:loadSave()
        local copy=R.saveMemory["merge.sav.v1"]
        local B=R.builtins
        B.ini_open(nil, "merge.sav")
        local version=B.ini_read_real(nil, "merge", "version", 0)
        local crossings=B.ini_read_real(nil, "merge", "crossings", -1)
        local ammo=B.ini_read_string(nil, "merge", "ammo", "")
        local from=B.ini_read_string(nil, "merge", "migrated_from", "")
        local lv=B.ini_read_string(nil, "Player", "LV", "")
        local area=B.ini_read_string(nil, "World", "Current Area", "")
        B.ini_close()
        if copy==nil then return "merge.sav.v1 was not preserved" end
        if version~=2 then return "version="..tostring(version) end
        if crossings~=4 then return "crossings="..tostring(crossings) end
        if ammo~="Silver Ammo" then return "ammo="..ammo end
        if from~="1" then return "migrated_from="..from end
        if lv~="" then return "invented LV "..lv end
        if area~="n:140" then return "area="..area end
        if R.saveMemory["merge.sav.v1"]==nil then return "copy deleted" end
        return "ok"
    ''')
    assert migrated == "ok", migrated
    assert "version=1" in planted and "Silver Ammo" in planted
    assert vm.execute('return R.saveMemory["merge.sav.v1"]') == planted
    stopped = vm.execute('''
        local before=R.saveMemory["merge.sav"]
        R.builtins.ini_open(nil, "merge.sav")
        R.builtins.ini_write_real(nil, "merge", "version", 99)
        R.builtins.ini_close()
        R:flushSaves()
        local marked=R.saveMemory["merge.sav"]
        local ok,err=pcall(function() R.travel:loadSave() end)
        local after=R.saveMemory["merge.sav"]
        if ok then return "no stop" end
        if after~=marked then return "unknown version was rewritten" end
        return tostring(err)
    ''')
    assert "merge.sav version 99" in stopped, stopped


@live
def test_file0_migration_preserves_the_old_file(vm):
    """An Undertale file0 with no Player record is loaded by the original script, then snapshotted.

    The file0 bytes are not deleted or rewritten. Current HP becomes max HP
    because that is what scr_load itself does; a version-2 save does not.
    """
    boot(vm)
    result = vm.execute('''
        local E=R:scope(R.instances[1])
        R.global.gold=55
        R.global.flag[99]=3
        R.global.hp=9
        R:call("scr_save", E)
        local file0=R.saveMemory.file0
        if not file0 then return "scr_save did not write file0" end
        R.builtins.file_delete(nil, "merge.sav")
        R.saveMemory["merge.sav"]=nil
        R.global.gold=0
        R.global.flag[99]=0
        R:call("scr_load", E)
        if R.saveMemory.file0~=file0 then return "file0 was rewritten during migration" end
        if R.global.gold~=55 then return "gold="..tostring(R.global.gold) end
        if R.global.flag[99]~=3 then return "flag="..tostring(R.global.flag[99]) end
        if R.global.hp~=R.global.maxhp then
            return "legacy load did not keep scr_load's heal-to-max: "..tostring(R.global.hp)
        end
        local B=R.builtins
        B.ini_open(nil, "merge.sav")
        local from=B.ini_read_string(nil, "merge", "migrated_from", "")
        local version=B.ini_read_real(nil, "merge", "version", 0)
        B.ini_close()
        if version~=2 then return "version="..tostring(version) end
        if from~="file0" then return "migrated_from="..from end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_foreign_save_sav_stops_by_name_and_is_not_deleted(vm):
    boot(vm)
    stopped = vm.execute('''
        R.builtins.file_delete(nil, "merge.sav")
        R.saveMemory["merge.sav"]=nil
        R.builtins.ini_open(nil, "Save.sav")
        R.builtins.ini_write_string(nil, "Encounters", "0", "GMFORMAT")
        R.builtins.ini_write_string(nil, "Save1", "room", "rm_hotland_02")
        R.builtins.ini_close()
        R:flushSaves()
        local before=R.saveMemory["Save.sav"]
        local E=R:scope(R.instances[1])
        local ok,err=pcall(function() R:call("scr_loadgame", E) end)
        if ok then return "no stop" end
        if R.saveMemory["Save.sav"]~=before then return "Save.sav was rewritten" end
        return tostring(err)
    ''')
    assert "Save.sav" in stopped and "Not a save string this port wrote" in stopped, stopped


@live
def test_a_fresh_runtime_loads_the_same_player(vm):
    """Quit and continue: a new runtime with the same save directory restores the document."""
    boot(vm)
    result = vm.execute('''
        local E=R:scope(R.instances[1])
        R.global.xp=709
        R:call("scr_levelup", E)
        R.global.hp=13
        R.global.gold=44
        R.global.plot=42
        R.player.inventory[1]=1
        R:call("scr_save", E)
        local Runtime=require("port.runtime")
        local Input=require("port.input")
        local input2=Input.new()
        local R2=Runtime.new(R.manifest, input2, {
            headless=true, memorySaves=true, storage=R.saveMemory, trace=true, seed=42,
        })
        R2:start()
        local scope=R2:scope(R2.instances[1])
        R2:call("scr_load", scope)
        R2:applyTransitions()
        if R2.player.hp~=13 then return "fresh HP="..tostring(R2.player.hp) end
        if R2.player.gold~=44 then return "fresh gold="..tostring(R2.player.gold) end
        if R2.player.level~=8 then return "fresh LV="..tostring(R2.player.level) end
        if R2.player.inventory[1]~=1 then return "fresh item="..tostring(R2.player.inventory[1]) end
        if R2.global.plot~=42 then return "fresh plot="..tostring(R2.global.plot) end
        if R2.saveBridge==nil then return "fresh runtime has no save bridge" end
        return "ok"
    ''')
    assert result == "ok", result


def test_single_game_runtime_has_no_unified_save(lua):
    lua.execute('''
        R:start()
        assert(R.saveBridge==nil, "a single-game runtime installed the unified save")
        assert(R.player==nil)
    ''')
