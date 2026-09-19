"""Owner-requested Inn rule: heal to max HP + 10 at every LV, not the old table.

Exercise the converted innkeeper's real wake-up alarm and Begin Step event.
The bonus is current HP only; it must not raise maxhp or stack between stays.
"""
import pytest

from test_runtime import new_game


# scr_levelup's thresholds, including LV 20's special 99-HP maximum.
XP_BY_LV = [0, 10, 30, 70, 120, 200, 300, 500, 800, 1200,
            1700, 2500, 3500, 5000, 7000, 10000, 15000, 25000, 50000, 99999]


def wake_at_inn(lua):
    lua.execute('''
        R.global.flag[72]=2
        R.global.flag[73]=1
        R.global.entrance=2
        R:loadRoom(R.constants.room_tundra_inn)
        inn=R:select(R.constants.obj_townnpc_innlady)[1]
        assert(inn and inn.v.conversation==5)
        tick(14)
    ''')


@pytest.mark.parametrize("lv,xp", list(enumerate(XP_BY_LV, start=1)))
@pytest.mark.parametrize("offset", [-15, 0, 5, 10, 15])
def test_waking_heals_to_current_max_plus_ten_at_every_lv(lua, lv, xp, offset):
    new_game(lua)
    lua.execute(f'''
        R.global.xp={xp}
        R:call("scr_levelup", E)
        assert(R.global.lv=={lv})
        R.global.hp=R.global.maxhp+({offset})
    ''')
    maxhp = 99 if lv == 20 else 16 + 4 * lv
    assert lua.eval("R.global.maxhp") == maxhp
    wake_at_inn(lua)
    assert lua.eval("R.global.hp") == maxhp + offset, "no healing before waking"
    lua.execute("tick(2)")
    assert lua.eval("R.global.hp") == maxhp + max(10, offset)
    assert lua.eval("R.global.maxhp") == maxhp
    assert lua.eval("R.global.lv") == lv
    assert lua.eval("inn.v.conversation") == 7
    # Damage consumes temporary HP rather than silently regenerating each frame.
    lua.execute("R.global.hp=R.global.hp-3;tick(5)")
    assert lua.eval("R.global.hp") == maxhp + max(10, offset) - 3
    assert lua.eval("R.global.maxhp") == maxhp


def test_repeat_stays_do_not_stack_and_follow_changed_maximum(lua):
    new_game(lua)
    for expected in (30, 30):
        wake_at_inn(lua)
        lua.execute("tick(2)")
        assert lua.eval("R.global.hp") == expected
        assert lua.eval("R.global.maxhp") == 20
    lua.execute('R.global.xp=709;R:call("scr_levelup", E)')
    wake_at_inn(lua)
    lua.execute("tick(2)")
    assert lua.eval("R.global.hp") == 58
    assert lua.eval("R.global.maxhp") == 48
    assert lua.eval("R.global.lv") == 8


def test_visiting_without_sleep_does_not_heal(lua):
    new_game(lua)
    lua.execute('''
        R.global.hp=5
        R:loadRoom(R.constants.room_tundra_inn)
        tick(30)
        assert(R.global.hp==5 and R.global.maxhp==20)
    ''')
