"""One movement speed for both worlds (unified-fusion piece 6c, spec section 12).

Spec section 12 lists "movement speed" among the things one compatibility layer
normalises, and spec section 3 asks for Clover's running to be the unified
player's. Both games walk 3px a step -- Undertale's ``obj_mainchara`` Step
(``x+= 3``) and Yellow's ``obj_pl`` Create (``plspd = 3``) -- and Yellow runs
``pl_spd = plspd + 2`` (``scr_normal_state``). Piece 5c ran Undertale at an
extra 3px lattice step (6px a step), a different speed from the same button in
the other world. Piece 6c makes the run one rule: 5px a step in both worlds,
Undertale's +2 bonus colliding through Undertale's own collision events.

The numbers are re-read from both pinned sources here, so the controller's
constants cannot silently drift from either game. These tests prove distances
headlessly; they do not claim a played-through route, Android, or input latency.
"""
import html
import re

import pytest

from conftest import ROOT
from test_yellow_merge import LIVE, live, merged, vm, yellow_rooms  # noqa: F401


def undertale_step_source():
    text = (ROOT / "objects/obj_mainchara.object.gmx").read_text()
    step = re.search(r'<event eventtype="3" enumb="0">(.*?)</event>', text, re.S).group(1)
    return "\n".join(html.unescape(chunk) for chunk in re.findall(r"<string>(.*?)</string>", step, re.S))


def test_both_speeds_come_from_the_pinned_sources(lua):
    """WALK_STEP is Undertale's own step and Yellow's plspd; RUN_BONUS is Yellow's +2."""
    step = undertale_step_source()
    assert re.search(r"\by-= 3;", step) and re.search(r"\by\+= 3;", step), \
        "obj_mainchara no longer walks 3px vertically"
    constants = lua.eval('(function() local C=require("port.controller"); '
                         'return C.WALK_STEP..","..C.RUN_BONUS end)()')
    walk, bonus = (int(float(n)) for n in constants.split(","))
    assert walk == 3
    if LIVE:
        create = (ROOT / "yellow_src/objects/obj_pl/Create_0.gml").read_text()
        assert re.search(r"^plspd = (\d+);", create, re.M).group(1) == str(walk), \
            "Yellow's obj_pl walk speed is not the shared WALK_STEP"
        normal = (ROOT / "yellow_src/scripts/scr_normal_state/scr_normal_state.gml").read_text()
        assert re.search(r"pl_spd = plspd \+ (\d+);", normal).group(1) == str(bonus), \
            "Yellow's sprint bonus is not the shared RUN_BONUS"
    else:
        assert bonus == 2


@live
def test_running_is_five_pixels_a_step_in_both_worlds(vm):
    """The same button runs the same speed on either side of a crossing.

    Undertale: 5px a step in all four directions (it was 6 with piece 5c's
    lattice step). Yellow: its own compiled 3+2, unchanged.
    """
    result = vm.execute('''
        R:start(); crossTo(4)
        local frisk=R:select(playerOf("undertale"))[1]
        R.global.interact=0
        frisk.v.movement=1
        local function steps(keys, x, y, n)
            frisk.v.x, frisk.v.y=x, y
            frisk.v.xprevious, frisk.v.yprevious=x, y
            local out={}
            input:setSource("test", keys)
            for _=1,n do
                local x0, y0=frisk.v.x, frisk.v.y
                tick(1)
                out[#out+1]=(frisk.v.x-x0)..":"..(frisk.v.y-y0)
            end
            input:setSource("test", {}); tick(1)
            return table.concat(out, " ")
        end
        local right=steps({39, 88}, 140, 120, 4)
        if right~="5:0 5:0 5:0 5:0" then return "Undertale run right: "..right end
        local left=steps({37, 88}, 240, 120, 4)
        if left~="-5:0 -5:0 -5:0 -5:0" then return "Undertale run left: "..left end
        local up=steps({38, 88}, 150, 200, 4)
        if up~="0:-5 0:-5 0:-5 0:-5" then return "Undertale run up: "..up end
        local walk=steps({39}, 140, 120, 4)
        if walk~="3:0 3:0 3:0 3:0" then return "Undertale walk changed: "..walk end
        R:gotoRoom(140); R:applyTransitions(); tick(1)
        R:gotoRoom(R.manifest.yellow_names.rooms["rm_hotland_02"]); R:applyTransitions(); tick(1)
        local pl=R:select(playerOf("yellow"))[1]
        R.global.player_can_run=1
        pl.v.x, pl.v.y=170, 120
        local y0=pl.v.y
        input:setSource("test", {40, 88}); tick(1)
        local first=pl.v.y-y0
        y0=pl.v.y; tick(1)
        local second=pl.v.y-y0
        input:setSource("test", {}); tick(1)
        -- Yellow's first sprint step is plspd+2 as well: scr_normal_state
        -- applies it before it moves.
        if first~=5 or second~=5 then return "Yellow run steps: "..first..", "..second end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_a_run_into_a_wall_never_enters_it_from_any_phase(vm):
    """The +2 bonus collides: from every 5px phase, the run rests flush-ish, never inside.

    room_area1's east wall (``obj_solidsmall``) starts at x=280, and Frisk's
    mask is 20px wide, so any x above 260 overlaps it. Starting at x=230..234
    covers all five phases of a 5px step. With the bonus collided through
    Undertale's own collision events the player never overlaps the wall and
    rests within one step of flush (258-260, the same band the 3px walk rests
    in). Without that collision, phases 231 and 232 end inside the wall
    (x=261, 262): the next walk step's own collision reverts to the spot the
    unchecked bonus left.
    """
    result = vm.execute('''
        R:start(); crossTo(4)
        local frisk=R:select(playerOf("undertale"))[1]
        R.global.interact=0
        frisk.v.movement=1
        local wall
        for _,inst in ipairs(R.instances) do
            if inst.alive and inst.v.object_index==R.constants.obj_solidsmall then
                local l,t,r,b=R:bbox(inst)
                if l==280 and t==120 then wall=inst end
            end
        end
        if not wall then return "room_area1's east wall at x=280 is missing" end
        local wl=R:bbox(wall)
        local rests={}
        for x0=230,234 do
            frisk.v.x, frisk.v.y=x0, 120
            frisk.v.xprevious, frisk.v.yprevious=x0, 120
            input:setSource("test", {39, 88})
            for _=1,14 do
                tick(1)
                local _, _, r=R:bbox(frisk)
                if r>=wl then
                    input:setSource("test", {})
                    return "from x="..x0.." the run entered the wall: x="..frisk.v.x
                end
            end
            input:setSource("test", {}); tick(1)
            if frisk.v.x<258 then return "from x="..x0.." the run stopped short at x="..frisk.v.x end
            rests[#rests+1]=frisk.v.x
        end
        return "ok "..table.concat(rests, ",")
    ''')
    assert result.startswith("ok"), result
