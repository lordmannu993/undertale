"""Unified-fusion piece 8 — the spec §15/§16 acceptance matrix.

Spec §15 asks for the fusion to be **tested**, not merely launched: player state
across a crossing, one inventory and equipment, movement and the animations that
match it, a rendering sweep over several rooms, and save/load from either world.
Spec §16 asks for the finished result to behave as **one unified game** and for
the code to be inspected rather than claimed — no duplicated player state, no
second inventory, no separate save structure, no separate rendering pipeline
underneath the UI.

Pieces 1–7 each proved their own slice with their own probe. This file drives
the §15 checklists as *one continuous session* — Undertale, then Undertale
Yellow, then back — with real item grants (``scr_itemget``), the game's own
equip scripts, real EXP (``scr_levelup``), Yellow's own pause menu, and the
whichever-world save points. The numbers a single scene pins stay pinned in the
tests that pinned them (pieces 3 and 7 for the boat and the shopkeeper); the
acceptance sweep here checks that the *systems* those pieces fixed hold across
the room list, and §16's audit checks there is only one of each system.

Scope: the converted flow headlessly, with the draw log as the render evidence
and the CI native LÖVE gate for pixels. Nothing here claims Android behaviour,
audio fidelity, a played-through route, or pixel-perfect parity with either
original engine.
"""
import re

from conftest import ROOT
from test_yellow_merge import live, merged, vm, yellow_rooms  # noqa: F401


def draw_order(vm):
    """Sprite *and* background names in draw order (first = furthest back).

    The docks' water draws as background calls, the actors as sprites, so the
    original layering is only visible when both are on one list.
    """
    raw = vm.eval("""(function()
        local t={}
        for _,entry in ipairs(R.drawLog) do
            if entry[1]=="sprite" or entry[1]=="background" then
                t[#t+1]=tostring(entry[2])
            end
        end
        return table.concat(t, "\\n")
    end)()""")
    return [name for name in raw.split("\n") if name]


def boot(vm):
    assert vm.execute(
        "local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)"
    ) == "ok"


def drawn(vm, prefix=""):
    """Every sprite name in the current draw log, oldest first."""
    raw = vm.eval("""(function()
        local t={}
        for _,entry in ipairs(R.drawLog) do
            if entry[1]=="sprite" then t[#t+1]=tostring(entry[2]) end
        end
        return table.concat(t, "\\n")
    end)()""")
    return [name for name in raw.split("\n") if name]


# --------------------------------------------------------------------------
# §15 Player state / Inventory: one journey through both worlds.
# --------------------------------------------------------------------------

@live
def test_spec15_one_journey_keeps_inventory_equipment_and_progression(vm):
    """§15's state and inventory checklists, in one continuous session.

    Undertale grants a weapon (``scr_itemget``) and equips it through
    ``scr_weaponeq``; a consumable stays in a slot. The crossing into Yellow
    must keep the slots, the equipped weapon, LV/EXP/HP/stats/gold/name and the
    shared abilities; Yellow's own pause menu then equips Yellow-only gear and
    puts a Yellow-only item in a slot; the crossing home must keep all of it —
    including the Yellow item, which Undertale's own ``global.item`` spelling
    has to read as the same slot.
    """
    boot(vm)
    result = vm.execute('''
        R:start(); crossTo(4)
        local player=R.player
        local frisk=R:select(playerOf("undertale"))[1]
        assert(frisk, "no Undertale player")
        local E=R:scope(frisk)

        -- Undertale's own grant and equip paths, not direct writes.
        R:call("scr_itemget", E, 13)                    -- Toy Knife
        R:call("scr_weaponeq", E, 0, 13)                -- equip it (swaps the Stick back)
        R:call("scr_itemget", E, 1)                     -- Monster Candy, carried
        if R.player.inventory[1]~=3 then
            return "slot 1 is "..tostring(R.player.inventory[1])..", not the swapped-out Stick"
        end
        if R.player.inventory[2]~=1 then
            return "slot 2 is "..tostring(R.player.inventory[2])..", not the Monster Candy"
        end
        if R.global.weapon~=13 or R.global.wstrength~=3 then
            return "weapon="..tostring(R.global.weapon).." wstrength="..tostring(R.global.wstrength)
        end
        R.global.xp=709; R:call("scr_levelup", E)
        R.global.hp=13; R.global.gold=317; R.global.charname="Frisk"
        if R.global.lv~=8 or R.global.maxhp~=48 or R.global.at~=24 or R.global.df~=11 then
            return "level up: "..R.global.lv.."/"..R.global.maxhp.."/"..R.global.at.."/"..R.global.df
        end

        -- Cross into Yellow with that state.
        crossTo(R.manifest.yellow_names.rooms["rm_hotland_02"])
        if R.travel.world~="yellow" then return "crossing failed: "..tostring(R.travel.world) end
        if R.player~=player then return "the crossing replaced the Player record" end
        if countInstances(playerOf("yellow"))~=1 then return "not exactly one player in Yellow" end
        if countInstances(playerOf("undertale"))~=0 then return "Frisk survived the crossing" end
        if R.player.inventory[1]~=3 or R.player.inventory[2]~=1 then
            return "inventory after crossing: "..tostring(R.player.inventory[1])..","..tostring(R.player.inventory[2])
        end
        if R.global.item_slot[2]~="Monster Candy" then
            return "Yellow's spelling reads "..tostring(R.global.item_slot[2])
        end
        if R.player.equipment.weapon~=13 then return "shared weapon="..tostring(R.player.equipment.weapon) end
        if R.global.player_weapon~="Toy Knife" then
            return "Yellow's equipment spelling reads "..tostring(R.global.player_weapon)
        end
        if R.global.player_level~=8 or R.global.player_exp~=709 then return "LV/EXP lost" end
        if R.global.current_hp_self~=13 or R.global.max_hp_self~=48 then return "HP lost" end
        if R.global.player_attack~=24 or R.global.player_defense~=11 then return "stats lost" end
        if R.global.player_gold~=317 or R.global.player_name~="Frisk" then return "money/name lost" end
        if R.player.abilities.run~=1 or R.player.abilities.menu~=1 or R.player.abilities.interact~=1 then
            return "abilities lost"
        end

        -- Yellow content: its own pause menu equips Yellow-only gear, and a
        -- Yellow-only item rides in a shared slot.
        R.global.item_slot[4]="Lemonade"
        R.global.item_slot[3]="Silver Ammo"
        equipFromSlot(3)
        if R.global.player_weapon_modifier~="Silver Ammo" then
            return "ammo="..tostring(R.global.player_weapon_modifier)
        end
        if R.global.player_weapon_modifier_attack~=3 then
            return "ammo attack="..tostring(R.global.player_weapon_modifier_attack)
        end
        if R.global.item_slot[3]~="Rubber Ammo" then
            return "the equipped ammo did not swap back into its slot: "..tostring(R.global.item_slot[3])
        end

        -- And home through the whale.
        R.global.fast_travel_point="Waterfall - Dock"; tick(2)
        R:gotoRoom(125); R:applyTransitions(); tick(5)
        if R.travel.world~="undertale" then return "return crossing failed: "..tostring(R.travel.world) end
        if R.player~=player then return "the return replaced the Player record" end
        if countInstances(playerOf("undertale"))~=1 then return "no single Frisk after the return" end
        if countInstances(playerOf("yellow"))~=0 then return "Clover survived the return" end
        if R.player.inventory[1]~=3 or R.player.inventory[2]~=1 then
            return "the Undertale items did not survive: "..tostring(R.player.inventory[1])..","..tostring(R.player.inventory[2])
        end
        if R.player.inventory[4]~="Lemonade" or R.global.item[3]~="Lemonade" then
            return "the Yellow item did not survive: "..tostring(R.player.inventory[4]).."/"..tostring(R.global.item[3])
        end
        if R.global.weapon~=13 or R.global.wstrength~=3 then
            return "weapon after the return: "..tostring(R.global.weapon).."/"..tostring(R.global.wstrength)
        end
        if R.global.player_weapon_modifier~="Silver Ammo" then
            return "the equipped ammo did not survive: "..tostring(R.global.player_weapon_modifier)
        end
        if R.global.lv~=8 or R.global.xp~=709 or R.global.hp~=13 then return "progression lost" end
        if R.global.at~=24 or R.global.df~=11 or R.global.gold~=317 or R.global.charname~="Frisk" then
            return "stats/money/name lost"
        end
        if R.player.abilities.run~=1 then return "the shared run ability did not survive" end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_spec15_both_worlds_save_points_write_and_load_the_one_document(vm):
    """§15's save/load checklist: save in each world, load from the other.

    Both save scripts write ``merge.sav`` version 2, and both loaders read it —
    including Undertale's ``scr_load`` while standing in a Yellow room, which
    must restore that room and the injured HP rather than healing to max.
    """
    boot(vm)
    result = vm.execute('''
        R:start(); crossTo(4)
        local frisk=R:select(playerOf("undertale"))[1]
        R.global.xp=709; R:call("scr_levelup", R:scope(frisk))
        R.global.hp=13; R.global.flag[99]=7
        R.player.inventory[2]="Lemonade"
        if R:call("scr_save", R:scope(frisk))==nil then return "scr_save returned nil" end

        -- Undertale save, mangled, loaded back.
        R.global.hp=1; R.global.flag[99]=0; R.player.inventory[2]=0
        R:call("scr_load", R:scope(R.instances[1]))
        if R.global.hp~=13 or R.global.flag[99]~=7 then
            return "Undertale load: hp="..tostring(R.global.hp).." flag="..tostring(R.global.flag[99])
        end
        if R.player.inventory[2]~="Lemonade" then
            return "Undertale load dropped the Yellow item: "..tostring(R.player.inventory[2])
        end
        if R.global.lv~=8 or R.roomState.name~="room_area1" then
            return "Undertale load: lv="..tostring(R.global.lv).." room="..tostring(R.roomState.name)
        end

        -- Yellow save point, mangled, loaded with Undertale's own loader.
        crossTo(R.manifest.yellow_names.rooms["rm_hotland_02"])
        R.global.story=4; R.global.hp=11
        local pl=R:select(playerOf("yellow"))[1]
        assert(pl, "no Yellow player to save from")
        if R:call("scr_savegame", R:scope(pl))~=0 then return "scr_savegame did not return 0" end
        R.global.hp=20; R.global.story=0; R.global.flag[99]=0
        R:call("scr_load", R:scope(pl))
        if R.global.hp~=11 or R.global.story~=4 or R.global.flag[99]~=7 then
            return "cross-world load: hp="..tostring(R.global.hp).." story="..tostring(R.global.story)
                .." flag="..tostring(R.global.flag[99])
        end
        if R.roomState.name~="rm_hotland_02" or R.travel.world~="yellow" then
            return "cross-world load landed in "..tostring(R.roomState.name).."/"..tostring(R.travel.world)
        end

        -- One document, version 2, written by both worlds' save scripts.
        local B=R.builtins
        B.ini_open(nil, "merge.sav")
        local version=B.ini_read_real(nil, "merge", "version", 0)
        local lv=B.ini_read_string(nil, "Player", "LV", "")
        local item=B.ini_read_string(nil, "Player", "Inventory.2", "")
        B.ini_close()
        if version~=2 then return "merge.sav version="..tostring(version) end
        if lv~="n:8" then return "merge.sav LV="..lv end
        if item~="s:Lemonade" then return "merge.sav Inventory.2="..item end
        local keys={}
        for key in pairs(R.saveMemory) do keys[#keys+1]=key end
        table.sort(keys)
        local documents={}
        for _,key in ipairs(keys) do
            if key:sub(-4)==".sav" and key~="merge.sav.v1" then documents[#documents+1]=key end
        end
        if #documents~=2 or documents[1]~="Save.sav" or documents[2]~="merge.sav" then
            return "the save store holds "..table.concat(documents, ",")
        end
        return "ok"
    ''')
    assert result == "ok", result


# --------------------------------------------------------------------------
# §15 Movement: one rule, and the animation that matches it.
# --------------------------------------------------------------------------

@live
def test_spec15_movement_and_its_animations_match_in_both_worlds(vm):
    """Walk everywhere, run in Undertale, and draw the pose the state means.

    Undertale's walk is its own 3px step; holding X adds Yellow's collided +2
    bonus and the renderer swaps the pose to Clover's run cycle (spec §3), so
    the run animation does not disappear in Undertale content. Yellow walks 3px
    and runs 5px on the same rule, drawing Frisk's art while walking and
    Clover's own run cycle while running.

    The draw log is one frame long (``renderFrame`` starts a new one), so the
    sprite names are collected inside the move, frame by frame.
    """
    boot(vm)
    result = vm.execute('''
        R:start(); crossTo(4)
        local frisk=R:select(playerOf("undertale"))[1]
        R.global.interact=0
        frisk.v.movement=1
        local function steps(entity, keys, n)
            entity.v.x, entity.v.y=140, 120
            entity.v.xprevious, entity.v.yprevious=140, 120
            local deltas, names={}, {}
            input:setSource("test", keys)
            for _=1,n do
                local x0=entity.v.x
                tick(1)
                deltas[#deltas+1]=entity.v.x-x0
                for _,e in ipairs(R.drawLog) do
                    if e[1]=="sprite" and e[16] and e[16]>0 then
                        local name=tostring(e[2])
                        if name:find("mainchara",1,true) or name:find("spr_pl_run",1,true) then
                            names[name]=true
                        end
                    end
                end
            end
            input:setSource("test", {}); tick(1)
            local list={}
            for name in pairs(names) do list[#list+1]=name end
            table.sort(list)
            return table.concat(deltas, ","), list
        end
        local function has(list, want)
            for _,name in ipairs(list) do if name==want then return true end end
            return false
        end
        local function allRun(names)
            for _,name in ipairs(names) do
                if name:sub(1,10)~="spr_pl_run" then return false end
            end
            return #names>0
        end
        local function allWalk(names)
            for _,name in ipairs(names) do
                if name:sub(1,13)~="spr_mainchara" then return false end
            end
            return #names>0
        end

        local deltas, names=steps(frisk, {39}, 4)
        if deltas~="3,3,3,3" then return "Undertale walk distance: "..deltas end
        if not allWalk(names) or not has(names, "spr_maincharar") then
            return "Undertale walk drew "..table.concat(names, ",")
        end
        deltas, names=steps(frisk, {39, 88}, 4)
        if deltas~="5,5,5,5" then return "Undertale run distance: "..deltas end
        if not allRun(names) or not has(names, "spr_pl_run_right") then
            return "Undertale run drew "..table.concat(names, ",")
        end

        R:gotoRoom(R.manifest.yellow_names.rooms["rm_hotland_02"]); R:applyTransitions(); tick(3)
        local pl=R:select(playerOf("yellow"))[1]
        R.global.player_can_run=1
        deltas, names=steps(pl, {39}, 4)
        if deltas~="3,3,3,3" then return "Yellow walk distance: "..deltas end
        if not allWalk(names) or not has(names, "spr_maincharar") then
            return "Yellow walk drew "..table.concat(names, ",")
        end
        deltas, names=steps(pl, {39, 88}, 4)
        if deltas~="5,5,5,5" then return "Yellow run distance: "..deltas end
        if not allRun(names) or not has(names, "spr_pl_run_right") then
            return "Yellow run drew "..table.concat(names, ",")
        end
        return "ok"
    ''')
    assert result == "ok", result


# --------------------------------------------------------------------------
# §15 Rendering: a sweep over both worlds.
# --------------------------------------------------------------------------

@live
def test_spec15_rendering_sweep_keeps_every_scene_coherent(vm):
    """The §15 room sweep: the same systems hold in ten rooms of both worlds.

    Every room renders; no instance draws the same sprite twice in one frame
    (spec §8's duplicate rule, checked on the whole scene rather than one
    object); every sprite draw with an owner belongs to a live instance; and
    the sweep as a whole covers the list §15 asks about — the player in both
    worlds, NPCs beside the player, the docks' water backgrounds, particle
    systems, and a multi-layer composite (the shopkeeper's body + eyes + mouth).
    """
    undertale = """sweep({ {4, "room_area1"}, {311, "room_shop1"}, {140, "room_fire_dock"},
        {125, "room_water_dock"}, {70, "room_tundra_dock"} }, "undertale")"""
    yellow = """{ {R.manifest.yellow_names.rooms["rm_hotland_02"], "rm_hotland_02"},
        {R.manifest.yellow_names.rooms["rm_dalvsroom"], "rm_dalvsroom"},
        {R.manifest.yellow_names.rooms["rm_dunes_42"], "rm_dunes_42"},
        {R.manifest.yellow_names.rooms["rm_steamworks_32"], "rm_steamworks_32"},
        {R.manifest.yellow_names.rooms["rm_snowdin_11_yellow"], "rm_snowdin_11_yellow"} }"""
    script = """(function()
        local out={}
        local function sweep(list, world)
            for _,entry in ipairs(list) do
                local id, expected=entry[1], entry[2]
                local ok, err=pcall(function() R:gotoRoom(id); R:applyTransitions(); tick(3) end)
                if not ok then return "room "..expected.." stopped: "..tostring(err) end
                if R.roomState.name~=expected then
                    return "expected "..expected..", loaded "..tostring(R.roomState.name)
                end
                R.drawLog={}
                R:renderFrame()
                local draws, owned, repeats, particles, backgrounds, multi, player=0,0,0,0,0,0,0
                local seen, owners={}, {}
                for _,e in ipairs(R.drawLog) do
                    if e[1]=="sprite" then
                        draws=draws+1
                        local name=tostring(e[2])
                        local oid=e[16]
                        if oid and oid>0 then
                            owned=owned+1
                            if not R.byId[oid] then
                                return "an owner in "..expected.." is not a live instance: "..oid
                            end
                            owners[oid]=owners[oid] or {}
                            owners[oid][name]=true
                            local key=oid..":"..name
                            if seen[key] then repeats=repeats+1 end
                            seen[key]=true
                            if name:find("mainchar",1,true) or name:find("spr_pl_",1,true) then
                                player=player+1
                            end
                        else
                            particles=particles+1
                        end
                    elseif e[1]=="background" then
                        backgrounds=backgrounds+1
                    end
                end
                for _,set in pairs(owners) do
                    local count=0
                    for _ in pairs(set) do count=count+1 end
                    if count>1 then multi=multi+1 end
                end
                out[#out+1]=string.format("%s %s %d %d %d %d %d %d %d", world, tostring(expected), draws,
                    owned, repeats, particles, backgrounds, multi, player)
            end
            return nil
        end
        R:start(); crossTo(4)
        local stop=UNDERTALE_ROOMS
        if stop then return stop end
        stop=sweep(YELLOW_ROOMS, "yellow")
        if stop then return stop end
        return table.concat(out, "\\n")
    end)()"""
    script = script.replace("UNDERTALE_ROOMS", undertale).replace("YELLOW_ROOMS", yellow)
    vm.globals()  # keep lupa from reusing the module-level pattern
    result = vm.execute("return " + script)
    lines = [line for line in result.split("\n") if line]
    assert len(lines) == 10, result
    rows = {}
    for line in lines:
        world, name, draws, owned, repeats, particles, backgrounds, multi, player = line.split()
        rows[name] = dict(world=world, draws=int(draws), owned=int(owned), repeats=int(repeats),
                          particles=int(particles), backgrounds=int(backgrounds),
                          multi=int(multi), player=int(player))
    # No instance draws the same sprite twice in a frame, in any swept room.
    assert sum(row["repeats"] for row in rows.values()) == 0, rows
    # The sweep is not vacuous: both worlds' scenes are in it, and §15's list
    # of things to look at is actually covered.
    assert {row["world"] for row in rows.values()} == {"undertale", "yellow"}
    assert sum(row["draws"] for row in rows.values()) > 3000, rows
    assert sum(row["owned"] for row in rows.values()) > 25, rows
    assert sum(row["backgrounds"] for row in rows.values()) > 400, \
        "the docks' water/background layers never drew"
    assert sum(row["particles"] for row in rows.values()) > 500, \
        "no particle system drew in the sweep"
    assert sum(row["multi"] for row in rows.values()) > 0, \
        "no multi-layer composite (the shopkeeper's face) was in the sweep"
    # The player draws in every swept room except the shop interior: entering
    # room 311 with gotoRoom skips the shop's own entry scene, which is why the
    # counter scene below asserts the shopkeeper's composition instead. Both
    # worlds must show the player somewhere in the sweep.
    assert sum(1 for row in rows.values() if row["player"] > 0) >= 8, rows
    assert any(row["world"] == "undertale" and row["player"] > 0 for row in rows.values())
    assert any(row["world"] == "yellow" and row["player"] > 0 for row in rows.values())


@live
def test_spec15_named_scenes_keep_their_original_layering(vm):
    """The three scenes §15 names, in the acceptance suite's own run.

    Water behind the hull < hull < waterline cover < River Person < player in
    the dock; the shopkeeper's three face layers exactly once each, body first;
    and the Snowdin forest drawing the visiting Frisk (never Clover's walk
    sprites) with its snow particles.
    """
    boot(vm)
    vm.execute('''
        R:start()
        R.global.plot=200
        R.global.flag[461]=1
        R.global.entrance=0
        R:gotoRoom(140); R:applyTransitions(); tick(20)
        R.drawLog={}; R:renderFrame()
    ''')
    dock = draw_order(vm)
    assert "spr_dogboat" in dock and "spr_dogboat_cover" in dock, dock
    assert "spr_riverman" in dock and "spr_maincharad" in dock, dock
    hull = dock.index("spr_dogboat")
    water = [i for i, name in enumerate(dock) if name.startswith("bg_watertiles")]
    assert water, "the dock drew no water background"
    assert max(water) < hull, dock
    assert hull < dock.index("spr_dogboat_cover") < dock.index("spr_riverman") \
        < dock.index("spr_maincharad"), dock

    vm.execute('''
        R:gotoRoom(R.constants.room_shop1); R:applyTransitions(); tick(3)
        R.global.faceemotion=0
        R.drawLog={}; R:renderFrame()
    ''')
    faces = [name for name in drawn(vm) if "shopkeeper1" in name]
    assert faces == ["spr_shopkeeper1", "spr_shopkeeper1eyes", "spr_shopkeeper1mouth"], faces

    vm.execute('''
        R:gotoRoom(R.manifest.yellow_names.rooms["rm_snowdin_11_yellow"])
        R:applyTransitions(); tick(3)
        R.drawLog={}
        for _=1,2 do tick(1) end
    ''')
    forest = drawn(vm)
    assert any(name.startswith("spr_mainchara") for name in forest), \
        "Yellow's forest did not draw the player as Frisk"
    assert not ({"spr_pl_up", "spr_pl_down", "spr_pl_left", "spr_pl_right"} & set(forest)), \
        "Clover's walk sprites leaked into the merged rendering"
    assert sum(1 for name in forest if "snow" in name.lower()) > 0, \
        "the forest drew no snow particles"


# --------------------------------------------------------------------------
# §16: one unified game — inspect the code, do not just claim it.
# --------------------------------------------------------------------------

#: The separate-state spellings spec §9 forbids by name, plus the mode/launcher
#: shapes spec §16 rules out ("not a launcher, selector, or transition between
#: two independently functioning games").
FORBIDDEN_STATE = (
    "cloverInventory", "friskInventory", "undertaleInventory", "yellowInventory",
    "undertaleLV", "yellowLV", "undertaleEXP", "yellowEXP",
    "undertaleHP", "yellowHP", "undertaleGold", "yellowGold",
    "yellowMode", "undertaleMode", "gameMode",
)


@live
def test_spec16_no_duplicated_player_state_exists_in_the_port(merged):
    """§9/§16: the shared systems are the implementation, not a UI layer.

    The whole port and both conversions are scanned for the separate-state
    spellings the spec forbids. A hit fails by name, so a future piece cannot
    reintroduce a second inventory or a mode switch while the UI still looks
    unified.
    """
    hits = []
    for path in sorted((ROOT / "port").glob("*.lua")):
        text = path.read_text()
        for token in FORBIDDEN_STATE:
            if token in text:
                hits.append(f"{path.relative_to(ROOT)}: {token}")
    generated = merged.parents[1]  # generated/
    for path in sorted(generated.rglob("*.lua")):
        if path.parent.name == "merged":
            continue
        text = path.read_text()
        for token in FORBIDDEN_STATE:
            if token in text:
                hits.append(f"{path.relative_to(ROOT)}: {token}")
    assert not hits, "separate player state in the shared tree: " + ", ".join(hits)

    # One implementation of each shared system: a second one would be the
    # "two games in one" architecture the spec rejects, however it is named.
    owners = {}
    for path in sorted((ROOT / "port").glob("*.lua")):
        for name in re.findall(r"function (\w+)\.install\(", path.read_text()):
            owners.setdefault(name, []).append(path.name)
    for system in ("Player", "Inventory", "Controller", "Save", "Travel", "Frisk"):
        assert owners.get(system) == [f"{system.lower()}.lua"], \
            f"{system} is installed by {owners.get(system)}"
    # The boot path picks a *room*, never which game to run.
    for name in ("runtime.lua", "travel.lua"):
        text = (ROOT / "port" / name).read_text()
        assert not re.search(r"\bmode\s*==", text), f"{name} has a mode switch"


@live
def test_spec16_one_player_one_inventory_one_controller_one_save(vm):
    """§16's "one continuous player" as identities, not as values.

    One ``R.player`` table is the owner of every progression spelling, one
    inventory/equipment table backs both games' spellings, one controller
    object drives both adapters, and a crossing does not recreate any of them —
    it changes the world. Every progression global must be a live view: a write
    through either game's spelling has to land in (and read back from) the one
    record, which is what "shared rather than duplicated" means.
    """
    boot(vm)
    result = vm.execute('''
        R:start(); crossTo(4)
        local player=R.player
        local controller=R.playerController
        if not controller or controller~=R.player.controller then return "no single controller" end
        if R.playerBridge.state~=player then return "the player bridge owns a second record" end
        if R.inventoryBridge.state~=player then return "the inventory bridge owns a second record" end
        if R.player.inventory==nil or R.player.equipment==nil then return "no shared inventory tables" end

        -- Every spelling is the same field: write through one, read the other.
        local pairsToCheck={
            {"hp", "current_hp_self"}, {"maxhp", "max_hp_self"}, {"lv", "player_level"},
            {"xp", "player_exp"}, {"gold", "player_gold"}, {"at", "player_attack"},
            {"df", "player_defense"},
        }
        for _,pair in ipairs(pairsToCheck) do
            local before=R.global[pair[1]]
            R.global[pair[1]]=before+1
            if R.global[pair[2]]~=before+1 then
                return pair[1].." and "..pair[2].." are separate values"
            end
            R.global[pair[2]]=before
            if R.global[pair[1]]~=before then
                return pair[2].." did not write back to "..pair[1]
            end
        end
        R.global.charname="Frisk"
        if R.global.player_name~="Frisk" or R.player.name~="Frisk" then
            return "charname and player_name are separate values"
        end
        R.global.player_name="Acceptance"
        if R.global.charname~="Acceptance" then return "player_name did not write back" end
        R.global.charname="Frisk"
        R.global.item[1]=1
        if R.player.inventory[2]~=1 or R.global.item_slot[2]~="Monster Candy" then
            return "the numeric and string inventories are separate"
        end
        R.player.inventory[2]=0
        if R.global.item[1]~=0 then return "the inventory is not a live view" end

        -- A crossing changes the world, not the record or any of its tables.
        local inventory, equipment=R.player.inventory, R.player.equipment
        crossTo(R.manifest.yellow_names.rooms["rm_hotland_02"])
        if R.player~=player then return "the crossing replaced the Player" end
        if R.playerController~=controller or R.player.controller~=controller then
            return "the crossing replaced the controller"
        end
        if R.player.inventory~=inventory or R.player.equipment~=equipment then
            return "the crossing replaced the inventory/equipment tables"
        end
        if countInstances(playerOf("yellow"))~=1 or countInstances(playerOf("undertale"))~=0 then
            return "the crossing left the wrong number of bodies"
        end
        crossTo(140)
        if R.player~=player or R.playerController~=controller then
            return "the return replaced the Player or the controller"
        end

        -- One save document, written by whichever world saved last.
        local B=R.builtins
        B.ini_open(nil, "merge.sav")
        local version=B.ini_read_real(nil, "merge", "version", 0)
        B.ini_close()
        if version~=2 then return "merge.sav version="..tostring(version) end
        return "ok"
    ''')
    assert result == "ok", result
