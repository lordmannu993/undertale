"""D1a: Yellow callers use Yellow's own fonts, never Undertale's of the same number.

D0's harness (``docs/DEBUG_BASELINE.md`` §3, §4 symptom 1) reproduced the
owner-reported wrong-font bug: Yellow's ``obj_dialogue`` stores
``dialogue_font = 9`` and ``scr_initialize_battle`` stores
``global.font_type_text = 1`` — Yellow's own compiled font numbers (pinned
Asset_Order: 9 = ``fnt_main``, 1 = ``fnt_main_battle``). Static references
are already rewritten to merged IDs (``draw_set_font(E, 1000009)``); the
decompiler leaves a raw number wherever it could not prove an asset, and the
merged build then reads that number through Undertale's band (UT 9 =
``fnt_papyrus``, UT 1 = ``fnt_main``).

Objects already re-band those raw numbers at the consumption point
(``Runtime:resolveObjectIndex``). Fonts did not. These tests fail without
that sibling resolution at ``draw_set_font`` / ``Runtime:resolveFontIndex``.

Scope: headless converted flow + traced draw log on the merged manifest.
Not a native-rendering, Android, audio, or pixel-parity claim. Vertical
text is D1b (a different root cause: the wrap contract of ``draw_text_ext``).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LIVE = (ROOT / "yellow_src").is_dir()
live = pytest.mark.skipif(not LIVE, reason="needs the pinned Yellow source: tools/fetch_yellow.py")

BOOT = '''
    Input=require("port.input")
    Runtime=require("port.runtime")
    input=Input.new()
    R=Runtime.new(require("generated.merged.manifest"), input,
                  {headless=true, memorySaves=true, trace=true, seed=42})
    function tick(n)
        for i=1,n do
            input:beginFrame(); R:step(); R:renderFrame(); R:finishFrame(); input:endFrame()
        end
    end
    function dummy(id)
        R.manifest.objects[id]="tests.dummy"
        R.objects[id]={name="dummy",sprite=-1,mask=-1,visible=1,solid=0,depth=0,persistent=0,parent=-1,events={}}
    end
    function crossTo(room)
        R:gotoRoom(room); R:applyTransitions(); tick(1)
    end
    -- One Yellow-banded dummy and one Undertale dummy so draw_set_font can
    -- see a caller from each world without loading either game's dialogue.
    dummy(R.manifest.yellow_base + 99991)
    dummy(18101)
    yInst=R:create(R.manifest.yellow_base + 99991, 0, 0)
    uInst=R:create(18101, 0, 0)
    Ey=R:scope(yInst)
    Eu=R:scope(uInst)
    base=R.manifest.yellow_base
'''


@pytest.fixture(scope="session")
def yellow_rooms(converted):
    if not LIVE:
        pytest.skip("needs the pinned Yellow source: tools/fetch_yellow.py")
    report = ROOT / "generated/yellow/conversion-report.json"
    stage = json.loads(report.read_text())["stage"] if report.is_file() else None
    if stage != "rooms":
        subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "rooms"],
                       cwd=ROOT, check=True)
    return ROOT / "generated/yellow"


@pytest.fixture(scope="session")
def merged(yellow_rooms):
    run = subprocess.run([sys.executable, "tools/merge.py"], cwd=ROOT,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return ROOT / "generated/merged/manifest.lua"


@pytest.fixture
def vm(merged, monkeypatch):
    monkeypatch.chdir(ROOT)
    machine = LuaRuntime(unpack_returned_tuples=True)
    machine.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    machine.execute(BOOT)
    return machine


@live
def test_yellow_raw_font_nine_is_yellow_fnt_main_not_papyrus(vm):
    """The reported bug: Yellow dialogue_font=9 must select Yellow's fnt_main.

    Fails without resolveFontIndex being consumed by draw_set_font: the same
    number 9 is Undertale's fnt_papyrus in the merged font table.
    """
    assert vm.execute('''
        local ut = R.assets.fonts[9]
        local yellow = R.assets.fonts[base + 9]
        if not ut or ut.name ~= "fnt_papyrus" then
            return "Undertale font 9 is "..tostring(ut and ut.name)
        end
        if not yellow or yellow.name ~= "fnt_main" then
            return "Yellow merged font 1000009 is "..tostring(yellow and yellow.name)
        end
        R:call("draw_set_font", Ey, 9)
        local got = R.graphicsState.font
        local rec = R.assets.fonts[got]
        if got ~= base + 9 then
            return "Yellow draw_set_font(9) stored "..tostring(got).." (Undertale fnt_papyrus) instead of "..(base+9)
        end
        if not rec or rec.name ~= "fnt_main" then
            return "active font record is "..tostring(rec and rec.name)
        end
        return "ok"
    ''') == "ok"


@live
def test_yellow_raw_font_one_is_yellow_fnt_main_battle(vm):
    """The other documented raw-number path: global.font_type_text = 1."""
    assert vm.execute('''
        R:call("draw_set_font", Ey, 1)
        local got = R.graphicsState.font
        local rec = R.assets.fonts[got]
        if got ~= base + 1 then
            return "Yellow draw_set_font(1) stored "..tostring(got).." instead of "..(base+1)
        end
        if not rec or rec.name ~= "fnt_main_battle" then
            return "active font record is "..tostring(rec and rec.name)..", expected fnt_main_battle"
        end
        return "ok"
    ''') == "ok"


@live
def test_undertale_draw_set_font_still_selects_undertale_faces(vm):
    """Brief §8: Undertale's fonts stay on Undertale's band. A UT caller
    passing 9 must still get fnt_papyrus, not Yellow's fnt_main."""
    assert vm.execute('''
        R:call("draw_set_font", Eu, 9)
        if R.graphicsState.font ~= 9 then
            return "Undertale draw_set_font(9) stored "..tostring(R.graphicsState.font)
        end
        if R.assets.fonts[9].name ~= "fnt_papyrus" then
            return "Undertale font 9 was rewritten to "..tostring(R.assets.fonts[9].name)
        end
        R:call("draw_set_font", Eu, 1)
        if R.graphicsState.font ~= 1 or R.assets.fonts[1].name ~= "fnt_main" then
            return "Undertale draw_set_font(1) no longer selects fnt_main"
        end
        R:call("draw_set_font", Eu, 2)
        if R.graphicsState.font ~= 2 or R.assets.fonts[2].name ~= "fnt_maintext" then
            return "Undertale draw_set_font(2) no longer selects fnt_maintext"
        end
        return "ok"
    ''') == "ok"


@live
def test_already_banded_yellow_font_ids_and_named_lookups_pass_through(vm):
    """Static rewritten references (draw_set_font(E, 1000009)) and the
    double_named fnt_main split must keep working; the re-band must not
    double-add YELLOW_BASE or hand Yellow Undertale's fnt_main."""
    assert vm.execute('''
        R:call("draw_set_font", Ey, base + 9)
        if R.graphicsState.font ~= base + 9 then
            return "banded 1000009 was rewritten to "..tostring(R.graphicsState.font)
        end
        local yellowName = R:assetName("fnt_main", Ey)
        local utName = R:assetName("fnt_main", Eu)
        if yellowName ~= base + 9 then
            return "Yellow assetName(fnt_main) is "..tostring(yellowName)
        end
        if utName ~= 1 then
            return "Undertale assetName(fnt_main) is "..tostring(utName).." (expected 1)"
        end
        return "ok"
    ''') == "ok"


@live
def test_yellow_text_draw_log_uses_the_yellow_font_record(vm):
    """The renderer, not just state.font, must consume the Yellow record.
    string_width / a traced draw_text with raw 9 from a Yellow caller have
    to match Yellow's fnt_main, not Undertale's fnt_papyrus of the same number.
    """
    assert vm.execute('''
        local sample = "Hello"
        R:call("draw_set_font", Eu, 9)
        local papyrusWidth = R:call("string_width", Eu, sample)
        R:call("draw_set_font", Ey, base + 9)
        local intendedWidth = R:call("string_width", Ey, sample)
        R:call("draw_set_font", Ey, 9)
        local rawWidth = R:call("string_width", Ey, sample)
        if rawWidth ~= intendedWidth then
            return "raw 9 measured "..tostring(rawWidth).." px, Yellow fnt_main measures "..tostring(intendedWidth)
        end
        if rawWidth == papyrusWidth then
            return "Yellow raw 9 still measures as Undertale fnt_papyrus ("..tostring(papyrusWidth).." px)"
        end
        R.drawLog = {}
        R:call("draw_text", Ey, 10, 20, sample)
        local fontId = nil
        for _, entry in ipairs(R.drawLog) do
            if entry[1] == "text" and entry[2] == sample then fontId = entry[5] end
        end
        if fontId ~= base + 9 then
            return "draw_text logged font "..tostring(fontId).." instead of Yellow fnt_main "..(base+9)
        end
        return "ok"
    ''') == "ok"


@live
def test_obj_dialogue_draws_with_yellow_fnt_main(vm):
    """The D0 reproduction, now a gate: Yellow's own obj_dialogue (Create
    sets dialogue_font = 9, Draw calls draw_set_font(dialogue_font)) must
    paint its marker with Yellow's fnt_main. Fails if draw_set_font still
    looks 9 up in Undertale's band."""
    assert vm.execute('''
        R:start()
        local hotland = R.manifest.yellow_names.rooms["rm_hotland_02"]
        crossTo(hotland)
        if R.travel.world ~= "yellow" then
            return "crossing failed, world="..tostring(R.travel.world)
        end
        local dlg = R:create(R.manifest.yellow_names.objects["obj_dialogue"], 100, 100)
        if dlg.v.dialogue_font ~= 9 then
            return "obj_dialogue Create no longer stores raw 9; got "..tostring(dlg.v.dialogue_font)
        end
        local marker = "* Hello! Welcome to#  the Hotland crossing."
        dlg.v.message = {[0] = marker}
        dlg.v.talker = {[0] = -4}
        dlg.v.portrait = 0
        local saw, fontId = false, nil
        for _ = 1, 120 do
            R.drawLog = {}
            tick(1)
            for _, entry in ipairs(R.drawLog) do
                if entry[1] == "text" and tostring(entry[2]):find("Hotland crossing", 1, true) then
                    saw, fontId = true, entry[5]
                end
            end
            if saw then break end
        end
        if not saw then return "obj_dialogue never drew the marker" end
        local rec = R.assets.fonts[fontId]
        if fontId ~= base + 9 or not rec or rec.name ~= "fnt_main" then
            return "marker drawn with font "..tostring(fontId).." ("..tostring(rec and rec.name)..", "..
                (fontId and fontId >= base and "yellow" or "undertale").." side)"
        end
        if dlg.alive then R:destroy(dlg, false) end
        R.global.dialogue_open = false
        return "ok"
    ''') == "ok"


@live
def test_every_yellow_raw_font_number_has_a_merged_record(vm):
    """The re-band is only as good as the converted font table. Yellow's
    eleven fonts occupy raw 0..10; each must exist at YELLOW_BASE + n so a
    Yellow caller never falls through to the colliding Undertale face."""
    assert vm.execute('''
        local names = {
            [0]="fnt_chem_computer_screen", [1]="fnt_main_battle", [2]="fnt_battle",
            [3]="fnt_mars_needs_cunnilingus", [4]="fnt_mainb", [5]="fnt_dotumche",
            [6]="fnt_hachicro", [7]="fnt_stats", [8]="fnt_sans", [9]="fnt_main",
            [10]="fnt_arcade",
        }
        for raw, name in pairs(names) do
            local rec = R.assets.fonts[base + raw]
            if not rec or rec.name ~= name then
                return "raw "..raw.." expected "..name.." at "..(base+raw)..
                    ", got "..tostring(rec and rec.name)
            end
            R:call("draw_set_font", Ey, raw)
            if R.graphicsState.font ~= base + raw then
                return "Yellow draw_set_font("..raw..") stored "..tostring(R.graphicsState.font)
            end
        end
        return "ok"
    ''') == "ok"
