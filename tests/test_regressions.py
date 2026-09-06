"""Regression cases for the Android screenshot report (v0.1.0)."""
import json

import pytest
from lupa.luajit21 import LuaError

from test_runtime import new_game


def enter_flowey(lua):
    new_game(lua)
    # Follow the actual route/trigger/dialogue, not a direct room teleport.
    lua.execute('hold(40,10);hold(39,160);hold(38,20);hold(38,100)')
    assert lua.eval('R.roomState.name') == 'room_area1_2'
    for _ in range(40):
        lua.execute('press(90);tick(30)')
        if lua.eval('R.roomState.name') != 'room_area1_2':
            break
    assert lua.eval('R.roomState.name') == 'room_floweybattle'


def test_actual_flowey_transition_has_enemy_borders_and_dialogue(lua):
    enter_flowey(lua)
    lua.execute('''
        tick(90)
        local flow=R:select(R.constants.obj_floweybattle1)[1]
        assert(flow and flow.alive and flow.v.conversation>0)
        assert(#R:select(R.constants.obj_quickgen)==0)
        assert(R.global.idealborder[0]==237 and R.global.idealborder[1]==397)
        assert(R.global.idealborder[2]==250 and R.global.idealborder[3]==385)
        local top=R:select(R.constants.obj_uborder)[1]
        local bottom=R:select(R.constants.obj_dborder)[1]
        assert(top.v.x>0 and top.v.y>0 and top.v.image_xscale>0)
        assert(bottom.v.y>top.v.y)
        local flowDraw,borderDraw,text=false,0,false
        for _,entry in ipairs(R.drawLog) do
            if entry[1]=="sprite" and entry[2]:match("^spr_flowey") then flowDraw=true end
            if entry[1]=="sprite" and entry[2]=="spr_border" then
                assert(entry[4]>0 and entry[5]>0);borderDraw=borderDraw+1
            end
            if entry[1]=="text" and entry[3]>=350 and entry[4]<250 then text=true end
        end
        assert(flowDraw and borderDraw==4 and text)
    ''')


@pytest.mark.parametrize('name,expected', [
    ('room_fire_hotdog',158),('room_fire_sorry',160),('room_fire_apron',161),
    ('room_fire10',162),('room_fire_elevator_l2',168),('room_fire_elevator_l3',169),
    ('room_joyconfig',288),('room_battle',306),('room_floweybattle',307),
    ('room_fastbattle',308),('room_storybattle',309),('room_gameover',310),
    ('room_papdate',317),('room_adate',318),('room_afinaltest',334),
])
def test_original_room_ids_do_not_collapse_omitted_room(lua,name,expected):
    assert lua.eval(f'R.manifest.names.{name}') == expected


def test_missing_room_is_reported_and_adjacency_does_not_skip_it(lua,converted):
    report=json.loads((converted/'conversion-report.json').read_text())
    assert [r['id'] for r in report['missing_rooms']] == [159]
    assert lua.eval('#R.manifest.room_order') == 335
    assert lua.eval('R.manifest.rooms[159]') is None
    assert lua.eval('R:call("room_next",E,158)') == 159
    assert lua.eval('R:call("room_previous",E,160)') == 159
    with pytest.raises(LuaError,match='Missing original room 159'):
        lua.execute('R:gotoRoom(159)')


def test_gameover_script_targets_the_gameover_room(lua):
    new_game(lua)
    lua.execute('R:call("scr_gameoverb",R:scope(R:select(R.constants.obj_mainchara)[1]))')
    assert lua.eval('R.pendingRoom') == lua.eval('R.constants.room_gameover') == 310


def test_phone_fit_uses_available_space_and_integer_mode_is_optional(lua):
    lua.execute('''
        local P=require("port.presentation")
        local rect={x=50,y=30,w=900,h=650}
        local fit=P.fit(rect,640,480,false)
        local pixels=P.fit(rect,640,480,true)
        assert(fit.scale>1.3 and fit.h==650 and fit.w>860)
        assert(pixels.scale==1 and pixels.w==640 and pixels.h==480)
        assert(math.abs(fit.w/fit.h-4/3)<0.0001)
        local t=require("port.touch").new(input,true)
        t:resize(1440,720)
        local phone=P.fit(t.play,640,480,t.settings.pixels)
        assert(phone.w>880) -- v0.1.0 unnecessarily rounded down to 640
        assert(phone.x>=t.play.x and phone.x+phone.w<=t.play.x+t.play.w+0.001)
        for _,b in ipairs(t.controls) do assert(b.w>=44 and b.h>=44) end
        t:action({action="pixels"});assert(t.settings.pixels)
        t:action({action="pixels"});assert(not t.settings.pixels)
    ''')


def test_fit_downscales_without_cropping_even_in_integer_mode(lua):
    lua.execute('''
        local P=require("port.presentation")
        for _,integer in ipairs({true,false}) do
            local r=P.fit({x=10,y=20,w=300,h=220},640,480,integer)
            assert(r.scale<1 and r.w<=300 and r.h<=220)
            assert(r.x>=10 and r.y>=20 and r.x+r.w<=310 and r.y+r.h<=240)
        end
    ''')
