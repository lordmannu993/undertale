"""Glyde encounter timer (20x faster) and the STAT-menu "709 EXP" button.

Semantics pinned down for the button:
* +709 real EXP on global.xp, and it levels you up exactly like battle
  EXP: the button runs the game's own scr_levelup, so LOVE and stats rise
  the moment it is pressed (and again at every battle end, as always).
* Nothing else moves: global.kills and every route flag stay untouched,
  so pacifist stays pacifist and neutral stays neutral.
* Sans's Last Corridor judgment notices a bloodless LV rise (LV > 1 with
  kills == 0 can only happen via the button): he questions it seriously,
  then lets it go and keeps rooting for you - without ever saying how he
  knows you didn't hurt anyone.
"""
from test_runtime import new_game


def test_glyde_encounterer_uses_20x_faster_timers(lua, converted):
    # Conversion artifact pins the /20 values from the GMX source.
    src = (converted / "objects/obj_encounterer_glyde.lua").read_text()
    assert "101, 180, 7.5, 16, 203" in src, "create-event timer not reduced"
    assert "101, 42, 34, 16, 203" in src, "step-event timer not reduced"

    # Runtime check: creating the encounterer arms `steps` around 180
    # (populationfactor 1 with flag[203]==0), never near the old 3600.
    new_game(lua)
    lua.execute('''
        local g=R:create(R.constants.obj_encounterer_glyde,0,0)
        assert(g and g.v,"glyde encounterer was destroyed on create")
        assert(g.v.steps>=180 and g.v.steps<200,
               "expected steps around 180, got "..tostring(g.v.steps))
    ''')


def run_levelup(lua):
    lua.execute('local a=R:create(18000,0,0);R:call("script_execute",R:scope(a),55)')


def test_button_exp_levels_normally_like_battle_exp(lua):
    new_game(lua)
    lua.execute("R.global.xp=709")
    run_levelup(lua)
    assert lua.eval("R.global.lv") == 8
    assert lua.eval("R.global.maxhp") == 48
    assert lua.eval("R.global.at") == 24
    assert lua.eval("R.global.df") == 11
    assert lua.eval("R.global.kills") == 0, "kill counter must not move"
    assert lua.eval("R.global.flag[27]") == 0, "genocide flag must not move"


def test_stat_menu_709_exp_button(lua):
    new_game(lua)
    # Open the menu like a player: menu key, down to STAT, confirm.
    lua.execute('press(17)')
    assert lua.eval("R.global.interact") == 5
    assert lua.eval("R.global.menuno") == 0
    lua.execute('press(40);press(90)')
    assert lua.eval("R.global.menuno") == 2

    # The STAT screen shows the "709 EXP" button and EXP: 0.
    lua.execute('''R.drawLog={};tick(2)''')
    texts = lua.eval('''
        (function()
            local seen={}
            for _,e in ipairs(R.drawLog) do
                if e[1]=="text" then seen[e[2]]=true end
            end
            return seen
        end)()''')
    assert texts["709 EXP"]
    assert texts["EXP: 0"]
    assert not texts["KILLS: 0"], "KILLS line must stay hidden with nothing to show"

    # Press it. Z works via keyboard_multicheck_pressed(13). LOVE rises
    # immediately through the game's own scr_levelup, like battle EXP.
    lua.execute('press(90);tick(1)')
    assert lua.eval("R.global.xp") == 709
    assert lua.eval("R.global.lv") == 8
    assert lua.eval("R.global.maxhp") == 48
    assert lua.eval("R.global.at") == 24
    assert lua.eval("R.global.df") == 11
    assert lua.eval("R.global.hp") == 20, "scr_levelup does not heal - stock quirk"
    assert lua.eval("R.global.kills") == 0, "real kill counter must not move"
    assert lua.eval("R.global.flag[478]") == 0, "no hidden EXP accounting"

    # Repeatable: a second press stacks another 709 and levels again.
    lua.execute('press(90);tick(1)')
    assert lua.eval("R.global.xp") == 1418
    assert lua.eval("R.global.lv") == 10

    # EXP/LV show the new values; no fake KILLS line gets added.
    lua.execute('''R.drawLog={};tick(2)''')
    texts = lua.eval('''
        (function()
            local seen={}
            for _,e in ipairs(R.drawLog) do
                if e[1]=="text" then seen[e[2]]=true end
            end
            return seen
        end)()''')
    assert texts["EXP: 1418"]
    assert texts["LV  10"]
    assert not any(t.startswith("KILLS") for t in texts), \
        "button must not alter the KILLS display"


def test_sans_judgment_questions_bloodless_lv_rise(lua, converted):
    # Conversion artifact pins the custom judgment speech.
    src = (converted / "objects/obj_lastsans_trigger.lua").read_text()
    assert "some other life" in src, "Sans bloodless-LV speech was not converted"
    assert "hurt anyone" in src

    new_game(lua)
    got = lua.execute('''
        local function clear_dialogue()
            for _,i in ipairs(R:select(R.constants.obj_dialoguer)) do i.alive=false end
            for _,i in ipairs(R:select(R.constants.OBJ_WRITER)) do i.alive=false end
        end
        local out={}
        -- Stock pacifist at LV 1: the classic "you never gained any LOVE" speech.
        R.global.lv=1;R.global.kills=0
        local t=R:create(R.constants.obj_lastsans_trigger,0,0)
        t.v.con=6
        tick(2)
        out.classic1=tostring(R.global.msg[1])
        clear_dialogue()
        -- Button-grown LV with zero kills: Sans questions it, then lets it go,
        -- without saying how he knows nobody got hurt.
        R.global.msg[0]="?";R.global.msg[1]="?"
        local t2=R:create(R.constants.obj_lastsans_trigger,0,0)
        t2.v.con=6
        R.global.lv=8
        tick(2)
        out.custom9=tostring(R.global.msg[9])
        out.custom12=tostring(R.global.msg[12])
        out.custom14=tostring(R.global.msg[14])
        out.custom20=tostring(R.global.msg[20])
        return out
    ''')
    assert "never gained" in got["classic1"], "stock pacifist speech changed!"
    assert "but you didn" in got["custom9"]
    assert "some other life" in got["custom12"]
    assert "really matter" in got["custom14"]
    assert "still rooting" in got["custom20"]
