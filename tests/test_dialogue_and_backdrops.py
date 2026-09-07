"""Content assertions for v0.1.2: text existing is not enough; it must be right."""
import json
from pathlib import Path

import pytest
from tools.gml import CompileError
from tools.source_repairs import repair_object_event, repair_script
from test_regressions import enter_flowey


@pytest.mark.parametrize('message,phrase', [
    (200,'Howdy'),(201,'This way'),(202,'Welcome to your new'),
    (666,'See that heart'),(667,'LOVE is'),(668,'Move around'),
    (669,'You idiot'),(670,'Die.'),(671,'you missed them'),
    (672,'Is this a joke'),(673,'You know what'),(674,'terrible'),
    (706,'Sit down and progress'),
])
def test_dialogue_ids_select_the_correct_scene(lua,message,phrase):
    lua.execute(f'R:call("SCR_TEXT",E,{message})')
    assert phrase in lua.eval('R.global.msg[0]')


def test_flowey_never_gets_undynes_chair_prompt_and_text_fits_bubble(lua):
    enter_flowey(lua)
    lua.execute('''
        tick(90)
        local w=R:select(R.constants.OBJ_WRITER)[1]
        assert(w and w.v.originalstring:find("See that heart",1,true))
        assert(not w.v.originalstring:find("Sit down",1,true))
        assert(w.v.myfont==R.constants.fnt_plain and w.v.spacing==9 and w.v.vspacing==20)
        local bubble=R:select(R.constants.obj_blconwdflowey)[1]
        local right=bubble.v.x+R:instanceGet(bubble,"sprite_width")
        local bottom=bubble.v.y+R:instanceGet(bubble,"sprite_height")
        local text={}
        for _,entry in ipairs(R.drawLog) do
            if entry[1]=="text" and entry[5]==w.v.myfont and entry[4]<250 then
                text[#text+1]=entry[2]
                local glyph=R.assets.fonts[w.v.myfont].glyphs[entry[2]:byte(1)]
                assert(entry[3]>=bubble.v.x and entry[3]+glyph.offset+glyph.w<=right)
                assert(entry[4]>=bubble.v.y and entry[4]+glyph.h<=bottom)
            end
        end
        assert(table.concat(text):find("See that heart",1,true))
        assert(table.concat(text):find("SOUL",1,true))
    ''')


@pytest.mark.parametrize('item,name',[(0,' '),(1,'Monster Candy'),(3,'Stick'),(11,'Butterscotch Pie')])
def test_inventory_case_labels_are_not_reversed(lua,item,name):
    lua.execute(f'E.itemid={item};E.i=0;R:call("scr_itemnamelist",E)')
    assert lua.eval('R.global.itemname[0]') == name


def test_phone_menu_case_labels_are_not_reversed(lua):
    lua.execute('R.global.phone=R:array(R.global,"phone",E);R.global.phone[0]=201;R:call("scr_phonename",E)')
    assert lua.eval('R.global.phonename[0]') == 'Say Hello'


def test_character_fonts_follow_original_callers(lua):
    lua.execute('''
        R:call("SCR_TEXTTYPE",E,17);assert(E.myfont==R.constants.fnt_comicsans)
        R:call("SCR_TEXTTYPE",E,18);assert(E.myfont==R.constants.fnt_papyrus)
        R:call("SCR_TEXTTYPE",E,34);assert(E.myfont==R.constants.fnt_wingdings)
        R:call("SCR_TEXTTYPE",E,16);assert(E.shake==1.2 and E.spacing==8 and E.vspacing==18 and E.txtsound==98)
        R:call("SCR_TEXTTYPE",E,53);assert(E.shake==1.5 and E.vspacing==18 and E.txtsound==56)
    ''')


def test_source_repairs_are_audited_and_reject_different_input(converted):
    report=json.loads((converted/'conversion-report.json').read_text())
    assert sum('switch labels' in r for r in report['repairs']) == 9
    assert any('decimal-comma' in r for r in report['repairs'])
    with pytest.raises(CompileError,match='source changed'):
        repair_script('SCR_TEXT','switch(argument0) {case 0: exit;}',{'repairs':[]})


def test_dialoguer_face_cleanup_repair_is_audited(converted):
    # The damaged export negated obj_dialoguer's obj_face cleanup guard, leaking
    # dialogue portraits (Flowey's face followed the player into and out of the
    # tutorial fight and Toriel's face then softlocked obj_floweytrigger).
    report=json.loads((converted/'conversion-report.json').read_text())
    repaired=[r for r in report['repairs'] if 'obj_face cleanup' in r]
    assert len(repaired) == 2
    assert {'1:0','3:0'} == {r.partition(' event ')[2].split(': ',1)[0] for r in repaired}
    destroy=(converted/'objects'/'obj_dialoguer.lua').read_text()
    assert 'if R.truth(R:call("instance_exists", E, 774))' in destroy
    assert 'if R.truth(R.num(not R.truth(R:call("instance_exists", E, 774))))' not in destroy
    with pytest.raises(CompileError,match='source changed'):
        repair_object_event('obj_dialoguer','1:0','instance_destroy();',{'repairs':[]})


def test_opening_backdrops_are_scoped_and_keep_original_flower_tiles(lua,converted):
    report=json.loads((converted/'conversion-report.json').read_text())
    assert {x['room'] for x in report['reconstructed_backdrops']} == {'room_area1','room_area1_2'}
    lua.execute('''
        local first=R:roomData(R.constants.room_area1)
        assert(first.port_backdrop=="room_area1" and #first.tiles==20)
        assert(R:roomData(R.constants.room_area1_2).port_backdrop=="room_area1_2")
        assert(R:roomData(R.constants.room_floweybattle).port_backdrop==nil)
        local palette=require("port.opening_backdrops").palette
        assert(palette.floor[1]==58 and palette.light[1]==200 and palette.grass[2]==177)
    ''')
