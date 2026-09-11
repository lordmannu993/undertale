"""Glyde encounter timer (10x faster) and the STAT-menu "709 EXP" button.

Semantics pinned down for the button:
* +709 real EXP (global.xp, so it shows on the STAT screen and is saved),
* the EXP never raises LOVE: scr_levelup discounts global.flag[478],
* global.kills (the route-gating kill counter) is untouched, so the
  pacifist route still works.
* flag[478] (bonus EXP) rides the existing 512-flag save/load loop, so no
  save-format change.
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

    # Press it. Z works via keyboard_multicheck_pressed(13).
    lua.execute('press(90);tick(1)')
    assert lua.eval("R.global.xp") == 709
    assert lua.eval("R.global.flag[478]") == 709
    assert lua.eval("R.global.kills") == 0, "real kill counter must not move"
    assert lua.eval("R.global.lv") == 1

    # Repeatable: a second press stacks another 709.
    lua.execute('press(90);tick(1)')
    assert lua.eval("R.global.xp") == 1418
    assert lua.eval("R.global.flag[478]") == 1418

    # EXP shows the retrieved amount; no fake KILLS line gets added.
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
    assert not any(t.startswith("KILLS") for t in texts), \
        "button must not alter the KILLS display"

    # A battle's scr_levelup still ignores the button's EXP: LOVE stays 1,
    # so pacifist-route gates (global.kills == 0, LV 1) are intact.
    run_levelup(lua)
    assert lua.eval("R.global.lv") == 1
    assert lua.eval("R.global.kills") == 0
