"""Glyde encounter timer (10x faster) and the STAT-menu "Retrieve your EXP
from another life" option.

Semantics pinned down for the cheat:
* +709 real EXP (global.xp, so it shows on the STAT screen and is saved),
* the EXP never raises LOVE: scr_levelup discounts global.flag[478],
* +2 on the existing KILLS line in the STAT menu, but global.kills (the
  route-gating kill counter) is untouched, so the pacifist route still works.
* flag[478] (bonus EXP) and flag[498] (display kills) ride the existing
  512-flag save/load loop, so no save-format change.
"""
from test_runtime import new_game


def test_glyde_encounterer_uses_tentimes_faster_timers(lua, converted):
    # Conversion artifact pins the 10x values from the GMX source.
    src = (converted / "objects/obj_encounterer_glyde.lua").read_text()
    assert "101, 360, 15, 16, 203" in src, "create-event timer not reduced"
    assert "101, 84, 68, 16, 203" in src, "step-event timer not reduced"

    # Runtime check: creating the encounterer arms `steps` around 360
    # (populationfactor 1 with flag[203]==0), never near the old 3600.
    new_game(lua)
    lua.execute('''
        local g=R:create(R.constants.obj_encounterer_glyde,0,0)
        assert(g and g.v,"glyde encounterer was destroyed on create")
        assert(g.v.steps>=360 and g.v.steps<400,
               "expected steps around 360, got "..tostring(g.v.steps))
    ''')


def run_levelup(lua):
    lua.execute('local a=R:create(18000,0,0);R:call("script_execute",R:scope(a),55)')


def test_levelup_never_counts_bonus_exp(lua):
    new_game(lua)
    # Bonus EXP alone: LOVE stays 1.
    lua.execute("R.global.xp=709;R.global.flag[478]=709")
    run_levelup(lua)
    assert lua.eval("R.global.lv") == 1
    # Regular leveling still works when there is no bonus recorded.
    lua.execute("R.global.xp=709;R.global.flag[478]=0")
    run_levelup(lua)
    assert lua.eval("R.global.lv") == 8
    # Only the non-bonus part counts: 719 - 709 = 10 -> LV 2 exactly.
    lua.execute("R.global.lv=1;R.global.xp=719;R.global.flag[478]=709")
    run_levelup(lua)
    assert lua.eval("R.global.lv") == 2
    lua.execute("R.global.lv=1;R.global.xp=718")
    run_levelup(lua)
    assert lua.eval("R.global.lv") == 1


def test_stat_menu_retrieve_exp_from_another_life(lua):
    new_game(lua)
    # Open the menu like a player: menu key, down to STAT, confirm.
    lua.execute('press(17)')
    assert lua.eval("R.global.interact") == 5
    assert lua.eval("R.global.menuno") == 0
    lua.execute('press(40);press(90)')
    assert lua.eval("R.global.menuno") == 2

    # The STAT screen shows the option, the heart cursor, and EXP: 0.
    lua.execute('''R.drawLog={};tick(2)''')
    texts = lua.eval('''
        (function()
            local seen={}
            for _,e in ipairs(R.drawLog) do
                if e[1]=="text" then seen[e[2]]=true end
            end
            return seen
        end)()''')
    assert texts["RETRIEVE YOUR EXP"]
    assert texts["FROM ANOTHER LIFE"]
    assert texts["EXP: 0"]
    assert not texts["KILLS: 0"], "KILLS line must stay hidden with nothing to show"

    # Retrieve. Z works via keyboard_multicheck_pressed(13).
    lua.execute('press(90);tick(1)')
    assert lua.eval("R.global.xp") == 709
    assert lua.eval("R.global.flag[478]") == 709
    assert lua.eval("R.global.flag[498]") == 2
    assert lua.eval("R.global.kills") == 0, "real kill counter must not move"
    assert lua.eval("R.global.lv") == 1

    # The existing KILLS line now appears with the 2 other-life kills, and
    # EXP shows the retrieved 709. NEXT only counts level-eligible EXP (10).
    lua.execute('''R.drawLog={};tick(2)''')
    texts = lua.eval('''
        (function()
            local seen={}
            for _,e in ipairs(R.drawLog) do
                if e[1]=="text" then seen[e[2]]=true end
            end
            return seen
        end)()''')
    assert texts["EXP: 709"]
    assert texts["KILLS: 2"]
    assert texts["NEXT: 10"]

    # A battle's scr_levelup still ignores the bonus: LOVE stays 1,
    # so pacifist-route gates (global.kills == 0, LV 1) are intact.
    run_levelup(lua)
    assert lua.eval("R.global.lv") == 1
    assert lua.eval("R.global.kills") == 0
