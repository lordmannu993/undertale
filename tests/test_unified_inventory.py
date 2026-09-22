"""Unified inventory and four-slot equipment: one item list, both spellings.

These pin piece 5b of the unified fusion (spec §1): the shared item catalog
extracted from the recovered item scripts, global.item and global.item_slot as
live views of the same eight slots with working numeric/string adapters, the
common item actions that make every item usable in either content set, and one
four-slot equipment set whose gear-stat globals are derived from the equipped
tokens.  Native behaviour of items each game already understands is left to the
native scripts; the wrappers only carry what the native switches cannot match.
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
    function playerOf(world)
        return R.travel.ids[world].player
    end
    function dialogueOpen()
        for _,i in ipairs(R.instances) do
            if i.alive and i.v.object_index==R.manifest.yellow_names.objects["obj_dialogue"] then return true end
        end
        return false
    end
    function clearDialogue()
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
        assert(menuOpen(), "Yellow's pause menu did not open")
        press(90); tick(2)
        for _=2,number do press(40); tick(1) end
        press(90); tick(1)
        press(90); tick(3)
        assert(clearDialogue(), "the equip message never closed")
    end
    function crossToYellow()
        R.global.plot=122
        R:gotoRoom(140); R:applyTransitions(); tick(3)
        hold(88,2)
        R:gotoRoom(140); R:applyTransitions(); tick(10)
    end
    function crossToUndertale()
        R.global.fast_travel_point="Waterfall - Dock"; tick(2)
        R:gotoRoom(125); R:applyTransitions(); tick(5)
    end
'''


@pytest.fixture(scope="session")
def yellow_rooms(converted):
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


def booted(vm):
    assert vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"


def test_the_catalog_comes_out_of_the_item_scripts_with_no_invented_rows(merged):
    machine = LuaRuntime(unpack_returned_tuples=True)
    machine.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    catalog = machine.execute("return require('generated.merged.items')")
    ut, yellow, pairs = catalog["ut"], catalog["yellow"], catalog["pairs"]
    assert ut[13]["name"] == "Toy Knife" and ut[3]["name"] == "Stick"
    assert ut[13]["weapon_strength"] == 3 and not ut[13]["heal"]
    assert ut[3]["weapon_strength"] == 0           # the Stick adds nothing
    assert ut[14]["weapon_strength"] == 5          # Tough Glove, from scr_weaponeq
    assert ut[1]["kind"] == "consume" and ut[1]["heal"] == 10   # Monster Candy
    assert ut[1]["messages"][1] == "* You ate the Monster Candy."
    assert ut[2]["name"] == "Croquet Roll" and ut[2]["heal"] == 15
    assert ut[4]["armor_defense"] == 0
    assert ut[64]["armor_defense"] == 20 and ut[64]["armor_weapon_bonus"] == 10
    assert ut[13]["value"] == 100 and ut[3]["value"] == 150   # scr_itemvalue
    assert yellow["Sea Tea"]["heal"] == 10 and yellow["Sea Tea"]["kind"] == "consume"
    assert yellow["Toy Gun"]["weapon_strength"] == 0   # Yellow's own table
    assert yellow["Silver Ammo"]["weapon_mod_strength"] == 3
    assert yellow["Steel Buckle"]["armor_mod_defense"] == 7
    assert yellow["Gunpowder"]["heal"] == "max"
    paired = dict(pairs)
    assert paired == {1: "Monster Candy", 7: "Spider Donut", 13: "Toy Knife",
                      41: "Sea Tea", 58: "Popato Chisps"}
    # Nothing is committed or hand-typed: the file must regenerate bit-for-bit
    # from the recovered scripts it was extracted from.
    run = subprocess.run([sys.executable, "tools/item_catalog.py", "--check"],
                         cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr + run.stdout


@live
def test_both_inventory_spellings_are_live_views_of_the_same_eight_slots(vm):
    booted(vm)
    assert vm.execute('''
        R.global.item[2]=13
        -- Yellow's view projects the paired id as its own name.
        if R.global.item_slot[3]~="Toy Knife" then
            return "item_slot[3] reads "..tostring(R.global.item_slot[3]).." for item[2]=13"
        end
        R.global.item_slot[3]="Nothing"
        if R.global.item[2]~=0 then
            return "clearing through item_slot left item[2]="..tostring(R.global.item[2])
        end
        R.global.item_slot[5]="Lemonade"
        if R.global.item[4]~="Lemonade" then
            return "item[4] reads "..tostring(R.global.item[4]).." for the Yellow token"
        end
        if R.player.inventory[5]~="Lemonade" then
            return "the shared slot 5 is "..tostring(R.player.inventory[5])
        end
        -- index 8 is Undertale's keep-full scratch and stays out of both views.
        R.global.item[8]=999
        if R.global.item[8]~=999 or R.global.item_slot[9]==999 or R.global.item[9]==999 then
            return "the item[8] scratch leaked out of its unguarded storage"
        end
        return "ok"
    ''') == "ok"


@live
def test_numeric_and_string_item_adapters_each_read_the_others_tokens(vm):
    booted(vm)
    assert vm.execute('''
        R.global.item_slot[1]="Toy Knife"       -- paired name, Yellow's spelling
        if R.global.item[0]~=13 then
            return "the paired name read as "..tostring(R.global.item[0])..", not its UT id 13"
        end
        R.global.item[0]=13
        if R.global.item_slot[1]~="Toy Knife" then
            return "the paired id read back as "..tostring(R.global.item_slot[1])
        end
        R.global.item[0]=52                      -- Real Knife: no Yellow name
        if R.global.item_slot[1]~="Real Knife" then
            return "a UT-only id projected as "..tostring(R.global.item_slot[1])
        end
        R.global.item[0]="Sea Tea"
        if R.global.item[0]~=41 then
            return "a paired name written to item[] read as "..tostring(R.global.item[0])
        end
        R.global.item[0]="Honeydew Pin"          -- Yellow-only name
        if R.global.item[0]~="Honeydew Pin" or R.global.item_slot[1]~="Honeydew Pin" then
            return "a Yellow-only name must ride both views as its string"
        end
        return "ok"
    ''') == "ok"


@live
def test_the_item_name_and_value_scripts_carry_foreign_items(vm):
    booted(vm)
    assert vm.execute('''
        R.global.item[0]=13                 -- Toy Knife, native for the switch
        R.global.item[1]="Lemonade"         -- Yellow-only name
        R.global.item[3]="Sea Tea"          -- paired: resolves to its UT id 41
        R:call("scr_itemname", R:scope(R.instances[1]))
        local names=R.global.itemname
        if names[0]~="Toy Knife" then return "native slot renamed: "..tostring(names[0]) end
        if names[1]~="Lemonade" then return "foreign slot renamed: "..tostring(names[1]) end
        if names[3]~="Sea Tea" then return "paired slot renamed: "..tostring(names[3]) end
        R:call("scr_itemnameb", R:scope(R.instances[1]))
        local short=R.global.itemnameb
        if short[0]~="Toy Knife" then return "native short name: "..tostring(short[0]) end
        if short[1]~="Lemonade" then return "foreign short name: "..tostring(short[1]) end
        -- scr_itemvalue fills the caller-scope array `value`, like the
        -- original (the item menu reads it back from its own scope).
        local E=R:scope(R.instances[1])
        R:call("scr_itemvalue", E)
        local value=R:array(E, "value", E)
        if value[0]~=100 then return "Toy Knife value: "..tostring(value[0]) end
        if value[1]~=0 then return "foreign items must not invent a sell value: "..tostring(value[1]) end
        return "ok"
    ''') == "ok"


@live
def test_storage_box_names_read_the_shared_inventory_spelling(vm):
    booted(vm)
    assert vm.execute('''
        -- The box contents live in flags either way (see scr_storageget).
        R.global.flag[300]=4
        R.global.flag[301]="Steel Buckle"
        R.global.flag[310]=999
        R:call("scr_storagename", R:scope(R.instances[1]), 300)
        local names=R.global.itemname
        if names[0]~="Bandage" then
            return "native box entry: "..tostring(names[0])
        end
        if names[1]~="Steel Buckle" then
            return "foreign box entry: "..tostring(names[1])
        end
        return "ok"
    ''') == "ok"


@live
def test_undertale_menus_can_use_yellow_items(vm):
    booted(vm)
    assert vm.execute('''
        R.global.item[1]="Lemonade"         -- Yellow's heal 7 consume
        R.global.hp=5
        R:call("scr_itemuseb", R:scope(R.instances[1]), 1, R.global.item[1])
        if R.global.hp~=12 then return "hp "..tostring(R.global.hp).." after Lemonade" end
        if R.global.item[1]~=0 then return "the consumed item stayed: "..tostring(R.global.item[1]) end
        if R.global.msg[0]~="* (You drink the Lemonade.)" then
            return "message: "..tostring(R.global.msg[0])
        end
        -- max heal through the common action (Yellow's Gunpowder).
        R.global.item[0]="Gunpowder"
        R.global.hp=5
        R:call("scr_itemuseb", R:scope(R.instances[1]), 0, R.global.item[0])
        if R.global.hp~=R.global.maxhp then
            return "max heal left hp at "..tostring(R.global.hp)
        end
        return "ok"
    ''') == "ok"


@live
def test_yellow_menus_can_use_undertale_items(vm):
    booted(vm)
    assert vm.execute('''
        R.global.item_slot[1]="Faded Ribbon"    -- Undertale armor
        R:call("scr_item_use", R:scope(R.instances[1]), "Faded Ribbon", 1)
        if R.global.player_armor~="Faded Ribbon" then
            return "armor slot is "..tostring(R.global.player_armor)
        end
        if R.global.adef~=3 then return "armor defense "..tostring(R.global.adef) end
        -- Equipping swaps: the slot holds whatever was equipped there before
        -- -- the starter Bandage (id 4) Undertale's boot put in the armor slot.
        if R.global.item_slot[1]~="Bandage" then
            return "slot 1 holds "..tostring(R.global.item_slot[1])
        end
        -- Undertale's consume, in Yellow's own use entry.
        R.global.item_slot[2]="Nice Cream"
        R.global.hp=5
        R:call("scr_item_use", R:scope(R.instances[1]), "Nice Cream", 2)
        if R.global.hp~=20 then return "hp "..tostring(R.global.hp).." after Nice Cream" end
        if R.global.item_slot[2]~="Nothing" then
            return "the consumed slot holds "..tostring(R.global.item_slot[2])
        end
        return "ok"
    ''') == "ok"


@live
def test_paired_items_run_the_native_handling_of_the_world_they_are_used_in(vm):
    booted(vm)
    assert vm.execute('''
        -- Sea Tea heals 10 in both games' own scripts (Yellow also gives +1
        -- SOUL speed); the native handling of each world agrees.
        R.global.item_slot[1]="Sea Tea"
        R.global.hp=5
        R:call("scr_item_use", R:scope(R.instances[1]), "Sea Tea", 1)
        local yellowHp=R.global.hp
        R.global.item[1]=41
        R.global.hp=5
        R:call("scr_itemuseb", R:scope(R.instances[1]), 1, 41)
        if yellowHp~=15 or R.global.hp~=15 then
            return "Sea Tea healed "..tostring(yellowHp).." / "..tostring(R.global.hp)..", not 15 / 15"
        end
        -- Toy Knife has Yellow stats but no Yellow use case: equipping it is
        -- the catalog's action in Yellow, and its attack matches both tables.
        R.global.item_slot[1]="Toy Knife"
        R:call("scr_item_use", R:scope(R.instances[1]), "Toy Knife", 1)
        if R.global.player_weapon~="Toy Knife" then
            return "weapon slot is "..tostring(R.global.player_weapon)
        end
        if R.global.wstrength~=3 then return "Toy Knife attack "..tostring(R.global.wstrength) end
        return "ok"
    ''') == "ok"


@live
def test_equipment_has_four_slots_in_both_spellings_with_one_shared_state(vm):
    booted(vm)
    assert vm.execute('''
        R.global.weapon=52                  -- Real Knife
        R.global.armor=53                   -- The Locket
        R.global.player_weapon_modifier="Silver Ammo"
        R.global.player_armor_modifier="Steel Buckle"
        if R.player.equipment.weapon~=52 or R.player.equipment.armor~=53 then
            return "shared equipment: "..tostring(R.player.equipment.weapon).."/"..tostring(R.player.equipment.armor)
        end
        if R.player.equipment.ammo~="Silver Ammo" or R.player.equipment.accessory~="Steel Buckle" then
            return "shared modifiers: "..tostring(R.player.equipment.ammo).."/"..tostring(R.player.equipment.accessory)
        end
        -- The Yellow spellings read the same four slots as names.
        if R.global.player_weapon~="Real Knife" or R.global.player_armor~="The Locket" then
            return "Yellow spellings: "..tostring(R.global.player_weapon).."/"..tostring(R.global.player_armor)
        end
        if R.global.player_weapon_modifier~="Silver Ammo" or R.global.player_armor_modifier~="Steel Buckle" then
            return "modifier spellings drifted"
        end
        return "ok"
    ''') == "ok"


@live
def test_derived_gear_stats_track_the_equipped_tokens(vm):
    booted(vm)
    assert vm.execute('''
        R.global.weapon=52                  -- Real Knife: 99
        R.global.armor=53                   -- The Locket: 99
        if R.global.wstrength~=99 then return "Real Knife wstrength "..tostring(R.global.wstrength) end
        if R.global.player_weapon_attack~=99 then return "weapon attack "..tostring(R.global.player_weapon_attack) end
        if R.global.adef~=99 or R.global.player_armor_defense~=99 then
            return "Locket defense "..tostring(R.global.adef).."/"..tostring(R.global.player_armor_defense)
        end
        -- wstrength = weapon attack + the armor's own weapon bonus:
        -- Real Knife 99 plus temy armor's +10 is 109.
        R.global.weapon=52
        R.global.armor=64
        if R.global.wstrength~=109 then return "temy wstrength "..tostring(R.global.wstrength) end
        if R.global.player_weapon_attack~=99 then return "temy attack "..tostring(R.global.player_weapon_attack) end
        if R.global.adef~=20 then return "temy defense "..tostring(R.global.adef) end
        -- The modifier slots are Yellow's own determine scripts' values.
        R.global.player_weapon_modifier="Silver Ammo"
        R.global.player_armor_modifier="Steel Buckle"
        if R.global.player_weapon_modifier_attack~=3 then return "ammo attack "..tostring(R.global.player_weapon_modifier_attack) end
        if R.global.player_armor_modifier_defense~=7 then return "accessory defense "..tostring(R.global.player_armor_modifier_defense) end
        return "ok"
    ''') == "ok"


@live
def test_the_equipment_stat_scripts_resolve_tokens_from_both_games(vm):
    booted(vm)
    assert vm.execute('''
        local E=R:scope(R.instances[1])
        -- Foreign tokens (no native case) read the catalog tables.
        if R:call("scr_item_stats_weapon", E, "Tough Glove")~=5 then return "Tough Glove" end
        if R:call("scr_item_stats_armor", E, "The Locket")~=99 then return "The Locket" end
        if R:call("scr_item_stats_weapon", E, "Toy Knife")~=3 then return "Toy Knife" end
        -- Yellow's own names keep the native tables verbatim.
        if R:call("scr_item_stats_weapon", E, "Wild Revolver")~=0 then return "Wild Revolver" end
        if R:call("scr_item_stats_weapon_mod", E, "Silver Ammo")~=3 then return "Silver Ammo" end
        if R:call("scr_item_stats_armor_mod", E, "Steel Buckle")~=7 then return "Steel Buckle" end
        -- Unknown names read zero instead of inventing a value.
        if R:call("scr_item_stats_armor_mod", E, "Faded Ribbon")~=0 then return "non-accessory" end
        return "ok"
    ''') == "ok"


@live
def test_item_descriptions_carry_foreign_items(vm):
    booted(vm)
    assert vm.execute('''
        local E=R:scope(R.instances[1])
        -- Foreign descriptions carry the item's own extracted text (Yellow
        -- has no separate desc script; the use messages are its own words).
        R:call("scr_itemdesc", E, "Gunpowder")
        if string.find(R.global.msg[0], "* (You put the gunpowder", 1, true)~=1 then
            return "catalog description: "..tostring(R.global.msg[0])
        end
        R:call("scr_itemdesc", E, "Honeydew Pin")
        if string.find(R.global.msg[0], "* (You pin the Honeydew", 1, true)~=1 then
            return "second description: "..tostring(R.global.msg[0])
        end
        return "ok"
    ''') == "ok"


@live
def test_the_shared_inventory_survives_crossings_with_no_snapshot_to_restore(vm):
    booted(vm)
    vm.execute("crossToYellow()")
    assert vm.execute('''
        R.global.item_slot[2]="Silver Ammo"
        R.global.item_slot[3]="Steel Buckle"
        equipFromSlot(2)
        equipFromSlot(3)
        if R.global.player_weapon_modifier~="Silver Ammo" then return "setup ammo" end
        return "ok"
    ''') == "ok"
    assert vm.execute('''
        crossToUndertale()
        if R.travel.world~="undertale" then return "world "..tostring(R.travel.world) end
        if R.global.player_weapon_modifier~="Silver Ammo" then
            return "live ammo after crossing to Undertale: "..tostring(R.global.player_weapon_modifier)
        end
        if R.global.player_armor_modifier~="Steel Buckle" then
            return "live accessory after crossing to Undertale: "..tostring(R.global.player_armor_modifier)
        end
        -- Enter Yellow again: its initializer runs every time and must still
        -- be unable to reset the shared equipment (no snapshot is applied).
        crossToYellow()
        if R.travel.world~="yellow" then return "world "..tostring(R.travel.world) end
        if R.global.player_weapon_modifier~="Silver Ammo" then
            return "ammo after re-entering Yellow: "..tostring(R.global.player_weapon_modifier)
        end
        if R.global.player_weapon_modifier_attack~=3 then
            return "ammo attack "..tostring(R.global.player_weapon_modifier_attack)
        end
        if R.global.player_armor_modifier~="Steel Buckle" then
            return "accessory after re-entering Yellow: "..tostring(R.global.player_armor_modifier)
        end
        if R.global.player_armor_modifier_defense~=7 then
            return "accessory defense "..tostring(R.global.player_armor_modifier_defense)
        end
        -- The items put in the inventory survive the same initializer.
        if R.global.item_slot[2]~="Rubber Ammo" then
            return "slot 2 should hold the swapped-out Rubber Ammo: "..tostring(R.global.item_slot[2])
        end
        return "ok"
    ''') == "ok"
