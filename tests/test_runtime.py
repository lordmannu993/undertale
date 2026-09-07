import json

import pytest
from lupa.luajit21 import LuaError

from conftest import run_gml


def new_game(lua):
    # Actual converted title/menu code; select A through the real naming grid.
    lua.execute('''
        R:start();tick(10);press(90);tick(40);press(90)
        assert(R.roomState.name=="room_intromenu")
        press(90);press(90)
        for i=1,5 do press(39) end
        press(38);press(90);press(39);press(90);tick(200)
        assert(R.roomState.name=="room_area1")
        assert(R.global.charname=="A")
    ''')


def test_all_called_builtins_have_explicit_handlers(lua,converted):
    report=json.loads((converted/"conversion-report.json").read_text())
    for name in report["builtin_calls"]:
        assert lua.eval(f'R.builtins["{name}"] ~= nil'), name


def test_original_room_order_not_alphabetic(lua):
    assert lua.eval("R.manifest.names.room_start") == 0
    assert lua.eval("R.manifest.names.room_introimage") == 2
    assert lua.eval("R.manifest.names.room_area1") == 4
    assert lua.eval("R.manifest.names.room_ruins1") == 6
    assert lua.eval("R.manifest.names.room_tundra1") == 44
    assert lua.eval("R.manifest.names.obj_mainchara") == 1570
    assert lua.eval("R.manifest.names.spr_maincharad") == 1043


def test_opening_story_uses_inline_dialogue_and_alarms(lua):
    lua.execute("R:start();tick(120)")
    assert lua.eval("R.roomState.name") == "room_introstory"
    assert lua.eval("R.frame") == 120
    text=lua.eval('''(function() local t={} for _,v in ipairs(R.drawLog) do if v[1]=="text" then t[#t+1]=v[2] end end return table.concat(t,"") end)()''')
    assert text.startswith("Long ago, two races")
    lua.execute("press(90);tick(40)")
    assert lua.eval("R.roomState.name") == "room_introimage"


def test_title_naming_movement_menu_cancel_and_first_door(lua):
    new_game(lua)
    x=lua.eval("R:select(R.constants.obj_mainchara)[1].v.x")
    lua.execute("hold(39,20)")
    assert lua.eval("R:select(R.constants.obj_mainchara)[1].v.x") == x+60
    lua.execute("press(67)")
    assert lua.eval("R.global.interact") == 5
    lua.execute("press(88)")
    assert lua.eval("R.global.interact") == 0
    lua.execute("hold(40,10);hold(39,140);hold(38,20)")
    assert lua.eval("R.roomState.name") == "room_area1_2"


def test_draw_logic_executes_per_game_tick_not_per_present(lua):
    new_game(lua)
    lua.execute('''
        local object=R:object(R.constants.obj_overworldcontroller)
        local instance=R:select(R.constants.obj_overworldcontroller)[1]
        before=instance.v.buffer
        tick(5)
        after=instance.v.buffer
    ''')
    assert lua.eval("after-before") == 5


def test_event_inheritance_and_nested_script_arguments(lua):
    lua.execute('''
        R.objects[18000].events["7:10"]=function(R,E) E.value=3 end
        R.objects[18001].events["7:10"]=function(R,E) R:call("event_inherited",E);E.value=E.value+4 end
        R:event(b,7,10)
        assert(b.v.value==7)
        R.manifest.scripts[19000]="tests.fake"
        R.manifest.names.custom=19000
        R.scripts[19000]=function(R,E) E.value=E.argument0;return E.argument1 end
        E=R:scope(a,nil,{100,200})
        assert(R:call("custom",E,3,4)==4)
        assert(E.argument0==100 and a.v.value==3)
    ''')


def test_destroy_during_with_does_not_skip_siblings(lua):
    lua.execute("c=R:create(18001,50,60)")
    run_gml(lua,"with(18000) instance_destroy();")
    assert lua.eval("#R:select(18000)") == 0


def test_speed_direction_negative_speed_and_gravity_components(lua):
    run_gml(lua, "direction=90; speed=3;")
    assert lua.eval("a.v.vspeed") == pytest.approx(-3)
    run_gml(lua, "speed=-2;")
    assert lua.eval("E.speed") == -2
    assert lua.eval("E.direction") == 90
    assert lua.eval("E.vspeed") == pytest.approx(2)
    run_gml(lua,"hspeed=3; vspeed=4;")
    assert lua.eval("E.speed") == 5


def test_collision_queries_scaling_rotation_and_noone(lua):
    lua.execute('''
        R.assets.sprites[19000]={width=10,height=20,xorig=0,yorigin=0,bbox_left=0,bbox_top=0,bbox_right=9,bbox_bottom=19,colkind=1,frames={"test.png"}}
        a.v.sprite_index=19000
        assert(R:call("collision_point",E,15,25,18000,0,0)==a.id)
        assert(R:call("collision_point",E,15,25,18000,0,1)==-4)
        assert(R:call("collision_rectangle",E,19,39,9,19,18000,0,0)==a.id)
        assert(R:call("collision_line",E,0,30,100,30,18000,0,0)==a.id)
        assert(R:call("collision_circle",E,0,30,5,18000,0,0)==-4)
        a.v.image_xscale=-1
        assert(R:call("collision_point",E,5,25,18000,0,0)==a.id)
        a.v.image_xscale=1;a.v.image_angle=90
        assert(R:call("collision_point",E,25,15,18000,0,0)==a.id)
    ''')


def test_missing_path_stops_explicitly_not_silent_noop(lua):
    with pytest.raises(LuaError,match="repository does not contain"):
        run_gml(lua,"path_start(0,3,0,0);")


def test_missing_external_sprite_stops_explicitly(lua):
    with pytest.raises(LuaError,match="Missing external image"):
        run_gml(lua,'sprite_replace(2000,"external/missing.gif",0,1,0,0,0);')


def test_ini_and_text_save_round_trip_and_traversal(lua):
    lua.execute('''
        local B=R.builtins
        B.ini_open(E,"roundtrip.ini")
        assert(B.ini_read_real(E,"General","LV",1)==1)
        B.ini_write_real(E,"General","LV",12.5)
        B.ini_write_string(E,"General","Name","A")
        B.ini_close()
        B.ini_open(E,"roundtrip.ini")
        assert(B.ini_section_exists(E,"General")==1)
        assert(B.ini_read_real(E,"General","LV",0)==12.5)
        assert(B.ini_read_string(E,"General","Name","")=="A")
        B.ini_close()
        local id=B.file_text_open_write(E,"file-test")
        B.file_text_write_string(E,id,"name");B.file_text_writeln(E,id)
        B.file_text_write_real(E,id,-12.5);B.file_text_writeln(E,id)
        B.file_text_close(E,id)
        id=B.file_text_open_read(E,"file-test")
        assert(B.file_text_read_string(E,id)=="name");B.file_text_readln(E,id)
        assert(B.file_text_read_real(E,id)==-12.5);B.file_text_readln(E,id)
        assert(B.file_text_eof(E,id)==1);B.file_text_close(E,id)
    ''')
    with pytest.raises(LuaError,match="traversal"):
        run_gml(lua,'file_text_open_write("../outside");')
    with pytest.raises(LuaError,match="Unsafe save path"):
        run_gml(lua,'file_text_open_write("/etc/forbidden");')


def test_original_save_load_scripts_keep_state(lua):
    new_game(lua)
    lua.execute('''
        local player=R:select(R.constants.obj_mainchara)[1]
        local E=R:scope(player)
        R.global.hp=17;R.global.gold=123;R.global.flag[99]=7;R.global.item[0]=5
        R:call("scr_save",E)
        assert(R.saveMemory.file0~=nil)
        R.global.hp=1;R.global.gold=0;R.global.flag[99]=0;R.global.item[0]=0
        R:call("scr_load",E)
        assert(R.global.hp==R.global.maxhp and R.global.gold==123 and R.global.flag[99]==7 and R.global.item[0]==5)
    ''')


def test_audio_asset_versus_instance_ids_and_fade(lua):
    lua.execute('''
        local B=R.builtins
        local sound=R.constants.mus_story
        local a=B.audio_play_sound(E,sound,100,1)
        local b=B.audio_play_sound(E,sound,100,1)
        assert(a~=b and a~=sound)
        B.audio_sound_pitch(E,a,0.5)
        assert(B.audio_sound_get_pitch(E,a)==0.5 and B.audio_sound_get_pitch(E,b)==1)
        B.audio_sound_gain(E,a,0,1000);R:updateAudio(0.5)
        assert(math.abs(B.audio_sound_get_gain(E,a)-0.5)<0.001)
        B.audio_pause_sound(E,a);assert(B.audio_is_playing(E,a)==0 and B.audio_is_playing(E,b)==1)
        R:suspendAudio();R:resumeAudio()
        assert(B.audio_is_playing(E,a)==0 and B.audio_is_playing(E,b)==1)
        B.audio_stop_sound(E,sound)
        assert(B.audio_is_playing(E,a)==0 and B.audio_is_playing(E,b)==0)
    ''')


def test_persistent_rooms_restore_state_and_discard_it_when_disabled(lua):
    lua.execute('''
        for n=19001,19002 do
            R.manifest.rooms[n]="tests.room"
            R.rooms[n]={id=n,name="test-room",width=320,height=240,speed=30,persistent=0,colour=0,showcolour=1,
                enableViews=0,backgrounds={},views={},tiles={},instances={{object=18000,x=10,y=20,id=100000+n}}}
        end
        R:loadRoom(19001)
        local saved=R:select(18000)[1];saved.v.value=17;saved.v.x=70
        R.vars.background_x[0]=123
        R:call("room_set_persistent",R:scope(saved),19001,1)
        R:loadRoom(19002);R:loadRoom(19001)
        assert(R:select(18000)[1]==saved and saved.v.value==17 and saved.v.x==70)
        assert(R.vars.background_x[0]==123)
        R.vars.room_persistent=0
        R:loadRoom(19002);R:loadRoom(19001)
        assert(R:select(18000)[1]~=saved)
        assert(R:instanceGet(R:select(18000)[1],"value")==0)
    ''')


def test_runtime_sprite_mutations_do_not_leak_through_require_on_restart(lua):
    lua.execute('''
        local original=R.assets.sprites[1043].bbox_left
        R.assets.sprites[1043].bbox_left=500
        local other=Runtime.new(require("generated.manifest"),Input.new(),{headless=true})
        assert(other.assets.sprites[1043].bbox_left==original)
    ''')
