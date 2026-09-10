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


def test_flowey_battle_end_cleans_dialogue_faces_and_resumes_control(lua):
    enter_flowey(lua)
    lua.execute('''
        -- Play the tutorial battle like a player: steer the SOUL toward
        -- Flowey's demonstration pellets and advance his dialogue with Z.
        local sawFace = false
        local deadline = R.frame + 6000
        while R.roomState.name == "room_floweybattle" and R.frame < deadline do
            if #R:select(R.constants.obj_face) > 0 then sawFace = true end
            input:setSource("test", {38}); tick(2); input:setSource("test", {})
            press(90)
        end
        assert(not sawFace, "dialogue face portrait leaked into the tutorial battle")
        assert(R.roomState.name == "room_area1_2")
        assert(R.global.plot == 1 and R.global.specialbattle == 1 and R.global.interact == 1)
        assert(#R:select(R.constants.obj_face) == 0, "pre-battle Flowey face must not survive the battle")
    ''')
    lua.execute('''
        -- Toriel appears, introduces herself, then starts leading on. Before
        -- the repair, the leaked Toriel face kept obj_floweytrigger forever at
        -- conversation 3.5 (waiting for it to vanish) and the game softlocked.
        local deadline = R.frame + 3000
        local trig
        while R.frame < deadline do
            tick(10); press(90)
            trig = R:select(R.constants.obj_floweytrigger)[1]
            if trig and trig.v.conversation >= 4 and R.global.interact == 0 then break end
        end
        assert(trig and trig.v.conversation >= 4, "obj_floweytrigger stuck after the Flowey battle")
        assert(R.global.interact == 0, "player control is not restored after the battle")
        assert(#R:select(R.constants.obj_face) == 0, "Toriel dialogue face was not cleaned up")
        local tor = R:select(R.constants.obj_toroverworld1)[1]
        assert(tor and tor.v.y < 260, "Toriel should start walking toward the ruins door")
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


def test_text_skip_with_cancel_cleans_stalled_writers(lua):
    """X/Shift skipping no longer leaves a halted writer under the next bubble.

    Battle controllers (obj_sansb, obj_papdate, ...) call ``scr_textskip`` every
    step, but the old script only fast-forwarded ``stringpos``. A writer that had
    advanced to a halt state (``halt`` 1, 2 or 4) never runs its own Z-driven
    page-advance/destroy user event during a skip, so it stayed alive under the
    next bubble's writer and both texts drew at once. The fixed script branches
    on the halt state exactly like the writer's own user event does.
    """
    lua.execute('''
        R:start()
        R:gotoRoom(R.constants.room_ruins5)   -- quiet room: no dialogue of its own
        tick(3)
        assert(#R:select(782) == 0, "ambient writers would obscure the count")
        -- A battle controller polls scr_textskip while X is held, inside the tick.
        local function xskip()
            input:setSource("test", {88})
            input:beginFrame()
            R:call("scr_textskip", E)
            R:step(); R:renderFrame(); R:finishFrame()
            input:endFrame()
            input:setSource("test", {})
            tick(1)
        end
        R.global.typer = 4
        R.global.msc = 1   -- three pages: two ending "/" and a last one ending "/%"
        local stalled = R:create(R.constants.OBJ_WRITER, 40, 150)
        tick(1)
        -- Two skips per page: one completes the page, one advances to the next.
        xskip(); xskip()
        assert(stalled.alive and stalled.v.stringno == 1 and stalled.v.halt == 0,
            "the halt == 1 branch did not advance to the next page")
        xskip(); xskip()
        xskip()
        assert(stalled.alive and stalled.v.halt == 2 and stalled.v.stringno == 2,
            "the dialogue did not stall at its /% ending")
        -- The controller moves on (the battle ended) and a new bubble appears.
        local fresh = R:create(R.constants.OBJ_WRITER, 60, 250)
        tick(1)
        assert(#R:select(782) == 2, "expected the stalled writer plus the new one")
        -- The next X press must clean the stalled writer and complete the new page.
        input:setSource("test", {88})
        input:beginFrame()
        R:call("scr_textskip", E)
        local writers = R:select(782)
        assert(#writers == 1 and writers[1] == fresh,
            "the skip must leave exactly the new writer, not a stack of stalled ones")
        assert(writers[1].v.halt == 0, "the surviving writer should be mid-page, not halted")
        assert(R.global.myfight == 0 and R.global.mnfight == 1,
            "the halt == 2/4 cleanup must hand control back like the writer's own user event")
        assert(not stalled.alive, "the stalled writer was not destroyed")
        R:step(); R:renderFrame(); R:finishFrame()
        input:endFrame()
        input:setSource("test", {})
    ''')


def test_touch_pause_menu_collision_toggle_flips_testing_phasing(lua):
    """The pause menu's COLLISION button drives the game's phasing debug global.

    It is the touch equivalent of the keyboard debug toggle on obj_mainchara
    (global.phasing 0 = solid collisions, 1 = walk through walls), which is how
    the game itself gates every solid-collision pushback. It is runtime-only:
    it must not be written to the persisted touch settings.
    """
    lua.execute('''
        R:start(); tick(2)
        assert(R.global.phasing == 0)
        local Touch=require("port.touch")
        local touch=Touch.new(input,false)
        touch:resize(960,540)
        assert(touch.collision == true, "collision must default to ON")
        -- Wire it exactly like main.lua's love.load does.
        touch.onCollision=function(enabled)
            if R then R.global.phasing = enabled and 0 or 1 end
        end
        local function collisionButton()
            for _,b in ipairs(touch.menuButtons) do if b.action=="collision" then return b end end
        end
        local function fits()
            local m=touch.menu
            for _,b in ipairs(touch.menuButtons) do
                assert(b.x>=m.x and b.y>=m.y and b.x+b.w<=m.x+m.w+0.01 and b.y+b.h<=m.y+m.h+0.01,
                    "menu button escapes the panel: "..b.label)
            end
        end
        fits()
        local button=collisionButton()
        assert(button and button.label=="COLLISION: ON", "the seventh pause-menu row is missing")
        touch:setPaused(true)
        touch:pressed("finger", button.x+button.w/2, button.y+button.h/2)
        assert(touch.collision == false and R.global.phasing == 1,
            "tapping COLLISION must turn walk-through-walls on")
        assert(collisionButton().label == "COLLISION: OFF", "the button label did not refresh")
        assert(touch.settings.collision == nil, "the toggle must not persist to touch settings")
        touch:pressed("finger", button.x+button.w/2, button.y+button.h/2)
        assert(touch.collision == true and R.global.phasing == 0,
            "tapping COLLISION again must restore solid collisions")
        assert(collisionButton().label == "COLLISION: ON")
        -- The seventh row must still fit on a small phone panel.
        touch:resize(480,320)
        fits()
        assert(collisionButton().label == "COLLISION: ON")
    ''')


def test_alarm_is_one_shot_and_does_not_double_fire(lua):
    # GameMaker alarms reset to -1 when they fire; the event may re-arm them.
    # Before the fix, an alarm set to N fired twice (at 0 and at -1), which
    # double-incremented conversation counters driven by alarm[4]++.
    lua.execute('''
        R:start();tick(5)
        local fired=0
        R.objects[18000].events["2:3"] = function(R,E) fired=fired+1 end
        local d=R:create(18000,10,20)
        d.v.alarm[3]=5
        tick(20)
        assert(fired==1, "alarm fired "..fired.." times, expected exactly once")
        assert(d.v.alarm[3]==-1, "alarm did not reset to -1 after firing")
        -- Re-arming from the event works (recurring alarm).
        R.objects[18000].events["2:3"] = function(R,E) fired=fired+1; E._self.v.alarm[3]=3 end
        d.v.alarm[3]=3
        tick(10)
        assert(fired>=3, "re-armed alarm did not fire repeatedly")
    ''')


def test_papyrus4_randoblock_completes_without_softlock(lua):
    # Reported: "After I fully solve papyrus's puzzles I get softlocked and
    # papyrus's overworld sprite doesn't move." The Snowdin tile randomizer
    # (obj_papyrus4) stalled at conversation 53 with interact=1 because
    # alarm[4]=110 double-fired 51->52->53, skipping the tile wait and never
    # re-arming. Drive the scene like a player: trigger, answer Yes, wait.
    new_game(lua)
    lua.execute('''
        R.global.plot=57
        R:gotoRoom(R.constants.room_tundra_randoblock)
        tick(10)
        local p4=R:select(R.constants.obj_papyrus4)[1]
        assert(p4 and p4.v.conversation==0)
        hold(39,10)
        tick(100)
        -- Answer the intro choice (Yes) and let the tiles randomize.
        local deadline=R.frame+3000
        while R.frame<deadline do
            p4=R:select(R.constants.obj_papyrus4)[1]
            if not p4 or p4.v.conversation>=50 then break end
            if #R:select(R.constants.OBJ_WRITER)>0 then tick(40);press(90) else tick(30) end
        end
        p4=R:select(R.constants.obj_papyrus4)[1]
        assert(p4 and p4.v.conversation>=50, "papyrus4 intro did not reach the tile phase")
        -- Finish the response text so the tile phase can start.
        deadline=R.frame+2000
        while R.frame<deadline and #R:select(R.constants.OBJ_WRITER)>0 do
            tick(40);press(90)
        end
        assert(#R:select(R.constants.OBJ_WRITER)==0, "papyrus4 response text never finished")
        deadline=R.frame+3000
        while R.frame<deadline do
            p4=R:select(R.constants.obj_papyrus4)[1]
            if not p4 or not p4.alive then break end
            tick(50)
        end
        assert((not p4) or (not p4.alive), "obj_papyrus4 stuck at conversation "..tostring(p4 and p4.v.conversation))
        assert(R.global.plot==58, "plot="..tostring(R.global.plot)..", expected 58")
        assert(R.global.interact==0, "player control was not restored")
    ''')
