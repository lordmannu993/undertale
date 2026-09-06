import json

import pytest

from conftest import ROOT


def test_two_fingers_and_hardware_do_not_release_each_other(lua):
    lua.execute('''
        input:setSource("touch:1",{90})
        input:setSource("touch:2",{90})
        input:keypressed("z",false)
        input:beginFrame()
        assert(input:check(90) and input:check(90,"pressed"))
        input:endFrame()
        input:setSource("touch:1",{})
        input:beginFrame()
        assert(input:check(90) and not input:check(90,"released"))
        input:endFrame()
        input:setSource("touch:2",{})
        input:beginFrame();assert(input:check(90));input:endFrame()
        input:keyreleased("z")
        input:beginFrame();assert(not input:check(90) and input:check(90,"released"))
    ''')


def test_quick_tap_lasts_one_game_tick_not_zero(lua):
    lua.execute('''
        input:setSource("touch:tap",{90});input:setSource("touch:tap",{})
        input:beginFrame()
        assert(input:check(90) and input:check(90,"pressed") and not input:check(90,"released"))
        input:endFrame();input:beginFrame()
        assert(not input:check(90) and not input:check(90,"pressed") and input:check(90,"released"))
        input:endFrame();input:beginFrame()
        assert(not input:check(90,"released"))
    ''')


def test_pressed_edges_only_once_and_auto_repeat_ignored(lua):
    lua.execute('''
        input:keypressed("z",false);input:beginFrame();assert(input:check(90,"pressed"));input:endFrame()
        input:keypressed("z",true);input:beginFrame();assert(not input:check(90,"pressed"));assert(input:check(90));input:endFrame()
        input:beginFrame();assert(input:check(90) and not input:check(90,"pressed"))
    ''')


def test_key_mapping_and_direct_check(lua):
    lua.execute('''
        input:setMap(90,13);input:setMap(88,16);input:setMap(67,17)
        input:setSource("touch:a",{90,88,67});input:beginFrame()
        assert(input:check(13) and input:check(16) and input:check(17))
        assert(not input:check(90) and input:check(90,nil,true))
        assert(input:check(1) and not input:check(0))
        input:clear(13);assert(not input:check(13))
        input:endFrame();input:beginFrame();assert(not input:check(13))
        input:endFrame();input:setSource("touch:a",{});input:beginFrame();input:endFrame()
        input:setSource("touch:a",{90});input:beginFrame();assert(input:check(13,"pressed"))
    ''')


def test_cancel_clears_pending_edges_and_synthetic_keys(lua):
    lua.execute('''
        input:setSource("touch:a",{37,90});input:setSource("gml:90",{90})
        input:cancelAll();input:beginFrame()
        assert(not input:check(1));assert(not input:check(1,"pressed"))
        assert(not input:check(1,"released"))
    ''')


def test_gamepad_diagonals_deadzone_disconnect_and_multiple_shift(lua):
    lua.execute('''
        input:gamepadaxis("one","leftx",0.1);input:beginFrame();assert(not input:check(39));input:endFrame()
        input:gamepadaxis("one","leftx",0.9);input:gamepadaxis("one","lefty",-0.8)
        input:gamepadpressed("one","a");input:beginFrame();assert(input:check(39) and input:check(38) and input:check(90));input:endFrame()
        input:gamepadaxis("one","leftx",0.35);input:beginFrame();assert(input:check(39));input:endFrame()
        input:gamepadaxis("one","leftx",0.2);input:beginFrame();assert(not input:check(39));input:endFrame()
        input:releasePrefix("gamepad:one:");input:beginFrame();assert(not input:check(1));input:endFrame()
        input:keypressed("lshift");input:keypressed("rshift");input:keyreleased("lshift")
        input:beginFrame();assert(input:check(16))
    ''')


def test_mouse_does_not_count_as_any_keyboard_key(lua):
    lua.execute('''
        input:mouseButton("pointer",1,true);input:beginFrame()
        assert(input:checkMouse(1) and input:checkMouse(1,"pressed"))
        assert(not input:check(1) and input:check(0))
    ''')


@pytest.mark.parametrize("w,h,safe", [
    (640,360,(0,0,640,360)), (800,600,(0,0,800,600)),
    (960,540,(0,0,960,540)), (1280,720,(36,0,1208,692)),
    (1920,1080,(0,0,1920,1080)), (360,800,(0,28,360,744)),
    (412,915,(0,32,412,853)), (480,320,(0,0,480,320)),
])
@pytest.mark.parametrize("scale", [0.8, 1, 1.25])
@pytest.mark.parametrize("southpaw", [False, True])
def test_touch_layout_stays_in_safe_area_without_covering_game(lua,w,h,safe,scale,southpaw):
    vm=lua
    vm.globals().W=w;vm.globals().H=h;vm.globals().SCALE=scale;vm.globals().SOUTH=southpaw
    vm.globals().SAFE=vm.table_from(safe)
    vm.execute('''
        Touch=require("port.touch");touch=Touch.new(input,true)
        touch.settings.scale=SCALE;touch.settings.southpaw=SOUTH
        touch:resize(W,H,SAFE)
        local sx,sy,sw,sh=unpack(SAFE)
        local function bounds(b)
            assert(b.x>=sx-0.01 and b.y>=sy-0.01)
            assert(b.x+b.w<=sx+sw+0.01 and b.y+b.h<=sy+sh+0.01)
        end
        bounds(touch.play)
        local p=touch.pad;bounds({x=p.x-p.r,y=p.y-p.r,w=2*p.r,h=2*p.r})
        local function overlaps(a,b) return a.x<b.x+b.w and a.x+a.w>b.x and a.y<b.y+b.h and a.y+a.h>b.y end
        for i,b in ipairs(touch.controls) do
            bounds(b);assert(not overlaps(b,touch.play))
            for j,c in ipairs(touch.controls) do if i~=j then assert(not overlaps(b,c)) end end
        end
        assert(not overlaps({x=p.x-p.r,y=p.y-p.r,w=2*p.r,h=2*p.r},touch.play))
        touch.extra=true
        for page=1,3 do
            touch.page=page;touch:layoutExtras()
            for _,b in ipairs(touch.extraButtons) do bounds(b) end
        end
    ''')


def test_dpad_diagonals_slide_out_and_multitouch(lua):
    lua.execute('''
        Touch=require("port.touch");touch=Touch.new(input,true);touch:resize(960,540)
        local p=touch.pad;local z=touch.controls[1]
        assert(touch:pressed("thumb",p.x+p.r*0.7,p.y-p.r*0.7))
        assert(touch:pressed("action",z.x+z.w/2,z.y+z.h/2))
        input:beginFrame();assert(input:check(39) and input:check(38) and input:check(90));input:endFrame()
        touch:moved("thumb",p.x-p.r*0.7,p.y)
        input:beginFrame();assert(input:check(37) and not input:check(39) and not input:check(38));assert(input:check(90));input:endFrame()
        touch:moved("thumb",p.x-p.r*3,p.y)
        input:beginFrame();assert(not input:check(37) and input:check(90));input:endFrame()
        touch:released("action");input:beginFrame();assert(not input:check(90))
    ''')


def test_opening_keys_and_page_switch_preserve_other_fingers(lua):
    lua.execute('''
        Touch=require("port.touch");touch=Touch.new(input,true);touch:resize(960,540)
        local p=touch.pad;touch:pressed("thumb",p.x-p.r*0.7,p.y)
        touch:action({action="keys"})
        input:beginFrame();assert(input:check(37));input:endFrame()
        local shift
        for _,b in ipairs(touch.extraButtons) do if b.key==16 then shift=b end end
        touch:pressed("modifier",shift.x+shift.w/2,shift.y+shift.h/2)
        touch:action({action="page",page=2})
        input:beginFrame();assert(input:check(16) and input:check(37));input:endFrame()
        touch:released("modifier");touch:action({action="keys"})
        input:beginFrame();assert(not input:check(16) and input:check(37));input:endFrame()
        touch:resize(540,960);input:beginFrame();assert(not input:check(37))
    ''')


def test_every_audited_keyboard_button_has_a_touch_target(lua,converted):
    lua.execute('''
        Touch=require("port.touch");touch=Touch.new(input,true)
        touchcodes={[37]=true,[38]=true,[39]=true,[40]=true,[90]=true,[88]=true,[67]=true}
        for _,page in ipairs(Touch.pages) do for _,key in ipairs(page.keys) do touchcodes[key[2]]=true end end
    ''')
    report=json.loads((converted/"conversion-report.json").read_text())
    for key in report["input_keys"]:
        if key["code"] not in (0,1):
            assert lua.eval(f"touchcodes[{key['code']}]") is True, key
    assert lua.eval("touchcodes[1001] and touchcodes[1002]") is True
