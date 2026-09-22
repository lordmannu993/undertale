"""Unified-fusion piece 5a: one *live* owner of core player progression.

This is deliberately not the whole of piece 5. Inventory/item ID adaptation,
primary equipment, the combined controller and Player+World save migration are
still pending. These tests prove that both converted global spellings address
one record immediately, that destination defaults cannot replace it, and that
real menu/reward code uses it. No Android or complete-battle claim is made.
"""
import pytest

from conftest import run_gml
from test_runtime import new_game
from test_yellow_merge import live, merged, vm, yellow_rooms  # noqa: F401 -- shared fixtures


# The names actually assigned by SCR_GAMESTART and Yellow's scr_initialize.
CORE_FIELDS = [
    ("hp", "current_hp_self", "hp", 13.5),
    ("maxhp", "max_hp_self", "maxHp", 48),
    ("lv", "player_level", "level", 8),
    ("xp", "player_exp", "exp", 709),
    ("gold", "player_gold", "gold", 317),
    ("charname", "player_name", "name", "Frisk"),
    ("at", "player_attack", "stats.attack", 24),
    ("df", "player_defense", "stats.defense", 11),
]


@live
@pytest.mark.parametrize("xp", [0, 709, 99999], ids=["LV1", "LV8", "LV20"])
@pytest.mark.parametrize("hp_offset", [-15, 0, 10], ids=["injured", "full", "overhealed"])
def test_crossing_preserves_core_progression_in_both_directions(vm, xp, hp_offset):
    """Includes Undertale's 99 max HP at LV20, not Yellow's 100-HP default."""
    vm.execute(f'''
        R:start(); crossTo(140)
        local frisk=R:select(playerOf("undertale"))[1]
        R.global.xp={xp}
        R:call("scr_levelup",R:scope(frisk))
        R.global.hp=R.global.maxhp+({hp_offset})
        R.global.gold=317
        R.global.charname="A"
        expected={{R.global.lv,R.global.xp,R.global.hp,R.global.maxhp,
                   R.global.at,R.global.df,R.global.gold,R.global.charname}}
        crossTo(R.manifest.yellow_names.rooms["rm_hotland_02"])
        local actual={{R.global.player_level,R.global.player_exp,R.global.current_hp_self,
                       R.global.max_hp_self,R.global.player_attack,R.global.player_defense,
                       R.global.player_gold,R.global.player_name}}
        for i,value in ipairs(expected) do
            assert(actual[i]==value,"crossing reset field "..i..": "..tostring(actual[i]).." ~= "..tostring(value))
        end
        -- Yellow changes the same values; no frame/crossing is needed to sync.
        R.global.current_hp_self=R.global.current_hp_self-2
        R.global.player_gold=R.global.player_gold+9
        R.global.player_exp=R.global.player_exp+1
        expected[2]=expected[2]+1; expected[3]=expected[3]-2; expected[7]=expected[7]+9
        crossTo(125)
        local actual={{R.global.lv,R.global.xp,R.global.hp,R.global.maxhp,
                       R.global.at,R.global.df,R.global.gold,R.global.charname}}
        for i,value in ipairs(expected) do
            assert(actual[i]==value,"return lost field "..i..": "..tostring(actual[i]).." ~= "..tostring(value))
        end
        -- A second entry must not restore a stale snapshot or new-game stats.
        crossTo(R.manifest.yellow_names.rooms["rm_dunes_05"])
        assert(R.global.player_exp==expected[2] and R.global.current_hp_self==expected[3])
        assert(R.global.player_gold==expected[7] and R.global.player_name=="A")
    ''')


@live
@pytest.mark.parametrize("undertale,yellow,field,value", CORE_FIELDS)
def test_each_legacy_spelling_is_a_live_view_not_a_second_value(vm, undertale, yellow, field, value):
    vm.execute("R:start()")
    vm.globals().test_value = value
    vm.execute(f'''
        R.global.{undertale}=test_value
        assert(R.global.{yellow}==test_value,"{yellow} is still independent of {undertale}")
        assert(R.player.{field}==test_value,"Player is not the owner of {field}")
        local originalPlayer=R.player
        R.global.{yellow}=0
        assert(R.player.{field}==0 and R.global.{undertale}==0,"reverse alias write was lost")
        -- Direct system-level writes use the same source of truth.
        R.player.{field}=test_value
        assert(R.global.{undertale}==test_value and R.global.{yellow}==test_value)
        assert(R.player==originalPlayer,"a write replaced the Player record")
        assert(rawget(R.global,"{undertale}")==nil and rawget(R.global,"{yellow}")==nil,
               "a second copy of {field} is still parked in global")
    ''')
    # The generated compiler's R:get / R:set / increment path, not just Lua
    # direct table assignment, must resolve to the same Player.
    vm.execute('E=R:scope(R.instances[1])')
    literal = '"Named"' if isinstance(value, str) else "0"
    source = f"global.{yellow} = {literal}; global.{undertale} = global.{yellow};"
    if not isinstance(value, str):
        source += f" global.{yellow}++; global.{undertale} -= 1;"
    run_gml(vm, source)
    expected = "Named" if isinstance(value, str) else 0
    assert vm.eval(f"R.player.{field}") == expected
    assert vm.eval(f"R.global.{undertale}") == expected
    assert vm.eval(f"R.global.{yellow}") == expected


@live
def test_crossing_clears_shared_scratch_flags_not_player_or_other_story_fields(vm):
    vm.execute('''
        R:start(); crossTo(140)
        R.global.hp=7; R.global.gold=61; R.global.plot=122
        local yellow=R.manifest.yellow_names.rooms["rm_hotland_02"]
        for _,room in ipairs({yellow,125,yellow}) do
            for i=0,29 do R.global.flag[i]=100+i end
            R.global.flag[40]=9
            crossTo(room)
            for i=0,29 do assert(R.global.flag[i]==0,"cross-world scratch flag survived: "..i) end
            assert(R.global.flag[40]==9 and R.global.plot==122,"unrelated story data was cleared")
            assert(R.global.hp==7 and R.global.gold==61,"progression was parked in scratch flags")
        end
    ''')


@live
def test_naming_and_yellow_pause_header_show_the_shared_player(vm):
    new_game(vm)
    vm.execute('''
        local frisk=R:select(playerOf("undertale"))[1]
        R.global.xp=709; R:call("scr_levelup",R:scope(frisk))
        R.global.hp=13; R.global.gold=317
        local player=R.player
        crossTo(R.manifest.yellow_names.rooms["rm_hotland_02"])
        assert(R.player==player,"room transition replaced the authoritative Player")
        assert(menuOpen(),"Yellow's pause menu did not open")
        R.drawLog={}; tick(2)
        local text={}
        for _,entry in ipairs(R.drawLog) do if entry[1]=="text" then text[entry[2]]=true end end
        assert(text["A"],"the pause header did not use the name chosen in Undertale")
        assert(text["LV 8"] and text["HP 13/48"] and text["G   317"],"the pause header drew new-game progression")
    ''')


@live
def test_yellow_reward_event_updates_the_same_exp_gold_level_and_stats(vm):
    """The real converted reward/level-up event, not a claimed full battle."""
    vm.execute('''
        R:start(); crossTo(140)
        R.global.xp=9; R.global.gold=5; R.global.hp=13
        crossTo(R.manifest.yellow_names.rooms["rm_hotland_02"])
        local objects=R.manifest.yellow_names.objects
        -- Instantiate only the event's real prerequisites; drive the actual
        -- fade-out alarm which awards EXP/gold and evaluates the LV table.
        local dialogue=R:create(objects.obj_dialogue_battle_flee,0,0)
        local fade=R:create(objects.obj_battle_fade_out_screen,0,0)
        R.global.enemy_count=1; R.global.enemy_dead=1
        R.global.enemy_exp=1; R.global.enemy_gold=7
        R.global.current_room_overworld="rm_hotland_02"
        R:event(fade,2,0)
        assert(R.global.player_exp==10 and R.global.xp==10,"Yellow's earned EXP was not shared")
        assert(R.global.player_gold==12 and R.global.gold==12,"Yellow's earned gold was not shared")
        assert(R.global.player_level==2 and R.global.lv==2,"Yellow's LV rise was not shared")
        local hp,at,df=R.global.max_hp_self,R.global.player_attack,R.global.player_defense
        assert(R.global.maxhp==hp and R.global.at==at and R.global.df==df,"base stats have separate owners")
        R:applyTransitions(); tick(2)
        crossTo(125)
        assert(R.global.lv==2 and R.global.xp==10 and R.global.gold==12)
        assert(R.global.maxhp==hp and R.global.at==at and R.global.df==df)
        assert(R.global.hp==13,"a crossing healed or clamped HP")
    ''')


@live
def test_world_defaults_seed_only_absent_fields_and_release_the_guard_on_error(vm):
    vm.execute('''
        R:start(); crossTo(140)
        local frisk=R:select(playerOf("undertale"))[1]
        local original=R.scripts.scr_initialize
        R.global.hp=0 -- zero is an existing value, not a missing default
        R.player.gold=nil
        R.scripts.scr_initialize=function(runtime)
            runtime.global.current_hp_self=20
            assert(runtime.global.hp==0 and runtime.global.current_hp_self==0,
                   "nested initialization saw a temporary fresh player")
            runtime.global.player_gold=123
            runtime.global.some_world_default=456
            error("injected initializer failure",0)
        end
        local ok,err=pcall(function() R.travel:initialize("yellow",frisk) end)
        R.scripts.scr_initialize=original
        assert(not ok and tostring(err):find("injected initializer failure",1,true))
        assert(R.global.hp==0,"content defaults replaced existing zero HP")
        assert(R.player.gold==123,"a genuinely absent field did not receive its source default")
        assert(R.global.some_world_default==456,"non-player initialization was suppressed")
        R.global.current_hp_self=-0.5
        assert(R.global.hp==-0.5,"the failed initializer left the player write-protected")
    ''')


@live
def test_explicit_new_game_initialization_is_not_blocked_by_travel_protection(vm):
    vm.execute('''
        R:start(); crossTo(140)
        local frisk=R:select(playerOf("undertale"))[1]
        local player=R.player
        R.global.xp=709; R.global.gold=317; R.global.hp=1
        R:call("SCR_GAMESTART",R:scope(frisk))
        assert(R.player==player,"new-game initialization replaced the Player table")
        assert(R.global.xp==0 and R.global.player_exp==0 and R.player.exp==0)
        assert(R.global.gold==0 and R.global.player_gold==0 and R.player.gold==0)
        assert(R.global.hp==20 and R.global.current_hp_self==20 and R.player.hp==20)
        assert(R.global.lv==1 and R.global.player_level==1)
    ''')


def test_single_game_runtime_keeps_its_existing_global_semantics(lua):
    lua.execute('''
        R:start()
        assert(R.player==nil and R.playerBridge==nil,"a single-game runtime installed the fusion bridge")
        R.global.hp=7; R.global.current_hp_self=13
        assert(R.global.hp==7 and R.global.current_hp_self==13)
        assert(rawget(R.global,"hp")==7 and rawget(R.global,"current_hp_self")==13)
    ''')
