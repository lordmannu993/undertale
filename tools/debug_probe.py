#!/usr/bin/env python3
"""D0 reproduction harness — the headless baseline for the debug & repair plan.

The owner's brief (``docs/DEBUG_SPEC.md``) reports five symptoms on the merged
build: wrong fonts and vertical text on the Undertale Yellow side, heavy lag
there, a duplicated Player at the River Person crossing, and a wrong boat
destination. This probe boots the *converted* merged game exactly the way the
tests do (headless LÖVE-less runtime, traced draw log, in-memory saves, fixed
seed) and prints, section by section, the observable evidence for each symptom:

* ``[opening]``        — (full mode only) the played Undertale opening up to
                         Flowey's corridor, which also yields the Undertale
                         text baseline the Yellow side is compared against;
* ``[font-text]``      — every ``draw_set_font`` a Yellow room makes, the font
                         each Yellow text draw actually uses, the font Yellow's
                         own numbers mean, and the layout the shared text
                         renderer produces for Yellow's ``draw_text_ext`` call;
* ``[performance]``    — per-tick cost (CPU time, allocations, event
                         dispatches, draw-log entries, instance counts) for an
                         Undertale room and two Yellow rooms on the same run;
* ``[player-identity]``— Player/controller instance counts across repeated
                         Undertale <-> Yellow crossings;
* ``[boat-destination]``— where the River Person's own disembark code and the
                         packaged crossings actually land for every choice,
                         recorded by wrapping ``R:gotoRoom`` in this probe's VM
                         only (no repository code is changed).

The probe is a *measurement*: it exits 0 when it ran to completion, and its
output is quoted in ``docs/DEBUG_BASELINE.md``. It fixes nothing; the fixes
belong to pieces D1-D5, each of which must fail a test without its change.
Run ``python3 tools/debug_probe.py --help`` for options; ``--quick`` is the
reduced budget the regression test uses.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Everything the probe observes runs in this Lua program. It follows the boot
#: recipe of tests/conftest.py and port/smoke.lua: merged manifest, headless,
#: traced draw log, in-memory saves, fixed seed, so two runs agree.
PROBE_LUA = r"""
local PHASE = os.getenv("DEBUG_PROBE_PHASES") or "all"
local QUICK = os.getenv("DEBUG_PROBE_QUICK") == "1"
local PERF_TICKS = tonumber(os.getenv("DEBUG_PROBE_PERF_TICKS") or (QUICK and "120" or "300"))

local function section(name) print(""); print("== [" .. name .. "] ==") end
local function say(...)
    local parts = {}
    for _, value in ipairs({...}) do parts[#parts + 1] = tostring(value) end
    print(table.concat(parts, " "))
end
local function fmt(n) if n == math.floor(n) then return tostring(math.floor(n)) end return string.format("%.2f", n) end

---------------------------------------------------------------- boot -------
Input = require("port.input")
Runtime = require("port.runtime")
local input = Input.new()
local R = Runtime.new(require("generated.merged.manifest"), input,
    {headless = true, trace = true, memorySaves = true, seed = 42})
R:start()
local base = R.manifest.yellow_base or 1000000
local YN = R.manifest.yellow_names
local UN = R.manifest.names

local OBJ = {
    frisk = UN["obj_mainchara"],
    clover = YN.objects["obj_pl"],
    controller = YN.objects["obj_controller"],
    boat = UN["obj_dogboat_thing"],
    dialogue = YN.objects["obj_dialogue"],
    writer = UN["OBJ_WRITER"],
}
local ROOM = {
    hotland = YN.rooms["rm_hotland_02"],
    snowdin = YN.rooms["rm_snowdin_11_yellow"],
    dunes = YN.rooms["rm_dunes_05"],
}

local function tick(n)
    for _ = 1, n do
        input:beginFrame(); R:step(); R:renderFrame(); R:finishFrame(); input:endFrame()
    end
end
local function hold(k, n)
    input:setSource("test", {k}); tick(n); input:setSource("test", {}); tick(1)
end
local function tap(k) hold(k, 1) end
local function countInstances(object)
    local total = 0
    for _, inst in ipairs(R.instances) do
        if inst.alive and inst.v.object_index == object then total = total + 1 end
    end
    return total
end
local function roomName() return R.roomState and R.roomState.name or "?" end

-- Instrumentation, installed only in this probe's VM. The wrap points are the
-- same ones the runtime itself uses (R.gotoRoom is already the travel-wrapped
-- function, so requests are recorded before travel:resolve sees them).
local gotoLog = {}
local wrappedGoto = R.gotoRoom
function R:gotoRoom(index)
    local travel = R.travel
    gotoLog[#gotoLog + 1] = {
        req = index,
        world = travel and travel.world,
        latch = travel and travel.riverLatch or false,
        dest = travel and travel.riverDestination and travel.riverDestination.label or nil,
        from = R.vars.room,
    }
    return wrappedGoto(self, index)
end

local fontSets = {}
local dfs = R.builtins.draw_set_font
R.builtins.draw_set_font = function(E, v)
    fontSets[#fontSets + 1] = {v = v, room = R.vars.room}
    return dfs(E, v)
end

local eventCount = 0
local rawEvent = R.event
function R:event(inst, kind, number, ...)
    eventCount = eventCount + 1
    return rawEvent(self, inst, kind, number, ...)
end

local drawCounts = {}
local rawRender = R.renderFrame
function R:renderFrame()
    local result = rawRender(self)
    drawCounts[#drawCounts + 1] = #self.drawLog
    return result
end

local function fontInfo(id)
    if type(id) ~= "number" then return {id = id, present = false} end
    local rec = R.assets.fonts[id]
    return {
        id = id, present = rec ~= nil, name = rec and rec.name or nil,
        world = id >= base and "yellow" or "undertale",
        height = rec and rec.height or nil,
    }
end
local function describeFont(id)
    local info = fontInfo(id)
    if not info.present then
        return tostring(id) .. " -> NO FONT RECORD (text falls back to the generic renderer)"
    end
    return ("%d -> %s (%s side)"):format(info.id, info.name, info.world)
end
-- Yellow's compiled font numbers, from the merged manifest (which reads them
-- from the pinned Asset_Order dump): raw N means yellow_names.fonts at base+N.
local function yellowFontByRaw(raw)
    for name, id in pairs(YN.fonts) do
        if id == base + raw then return name end
    end
    return nil
end

local function wants(phase) return PHASE == "all" or PHASE:find(phase, 1, true) ~= nil end

-- Per-tick cost of one room: CPU microseconds, garbage growth, event
-- dispatches and draw-log entries. Defined early so any section can measure.
local function measure(label, ticks)
    collectgarbage("collect")
    local mem0 = collectgarbage("count")
    local ev0 = eventCount
    local frames0 = #drawCounts
    local t0 = os.clock()
    tick(ticks)
    local dt = os.clock() - t0
    local frames = #drawCounts - frames0
    local draws = 0
    for i = frames0 + 1, #drawCounts do draws = draws + drawCounts[i] end
    local players = countInstances(OBJ.frisk) + countInstances(OBJ.clover)
    say(("%-26s world=%-9s instances=%-5d players=%d us/tick=%-9s KB/tick=%-8s events/tick=%-7s draws/frame=%s")
        :format(label, tostring(R.travel.world), #R.instances, players, fmt(dt / ticks * 1e6),
            fmt((collectgarbage("count") - mem0) / ticks),
            fmt((eventCount - ev0) / ticks), frames > 0 and fmt(draws / frames) or "n/a"))
    return dt / ticks * 1e6
end

section("boot")
say("manifest:", R.manifest.game, "yellow_base:", base, "first room:",
    roomName(), "world:", R.travel and R.travel.world)
tick(2)
say("boot stable: room=" .. roomName() .. " instances=" .. #R.instances)

-------------------------------------------------------------- opening ------
-- The scripted opening from port/smoke.lua: title -> menu -> naming -> the
-- corridor, then Flowey's greeting in room_area1_2. This is the Undertale
-- baseline: how UT text is drawn, and the cost of a plain Undertale room.
local utTextSamples = {}
local openingPlayed = false
if wants("opening") and not QUICK then
    section("opening")
    tick(10); tap(90); tick(40); tap(90)
    assert(roomName() == "room_intromenu", "title -> menu failed: " .. roomName())
    tap(90); tap(90)
    for _ = 1, 5 do tap(39) end
    tap(38); tap(90); tap(39); tap(90); tick(200)
    assert(roomName() == "room_area1" and R.global.charname == "A",
        "naming -> first room failed: " .. roomName())
    hold(40, 10); hold(39, 160); hold(38, 20); hold(38, 100)
    assert(roomName() == "room_area1_2", "first doorway failed: " .. roomName())
    openingPlayed = true
    tick(90) -- let OBJ_WRITER type Flowey's greeting
    local writer = R:select(OBJ.writer)[1]
    for _, entry in ipairs(R.drawLog) do
        if entry[1] == "text" and #utTextSamples < 6 then
            utTextSamples[#utTextSamples + 1] = {text = tostring(entry[2]):sub(1, 24), font = entry[5]}
        end
    end
    say("Undertale played to", roomName(), "| writer present:", writer ~= nil,
        "| UT text draws in current frame:", #utTextSamples)
    local seen = {}
    for _, sample in ipairs(utTextSamples) do
        local key = describeFont(sample.font)
        if not seen[key] then seen[key] = true; say("  UT font in use:", key, "e.g. \"" .. sample.text .. "\"") end
    end
    utCorridor = measure("UT " .. roomName(), PERF_TICKS) -- the Undertale baseline room
end

------------------------------------------------------------- font-text -----
-- Cross into Yellow the packaged way (dock 140 with X held, exactly as
-- port/smoke.lua does it) and open Yellow's own dialogue object the way
-- Yellow's NPCs do: instance_create(obj_dialogue) + message[...] .
if wants("font-text") then
    section("font-text")
    R.global.plot = 122
    R:gotoRoom(140); R:applyTransitions(); tick(5)
    assert(roomName() == "room_fire_dock", "Hotland dock did not load: " .. roomName())
    hold(88, 2)
    R:gotoRoom(140); R:applyTransitions(); tick(10)
    assert(R.travel.world == "yellow", "crossing into Yellow failed")
    say("crossed to", roomName(), "| world:", R.travel.world)

    fontSets = {} -- measure only what Yellow's world draws
    local dlg = R:create(OBJ.dialogue, 100, 100)
    local marker = "* Hello! Welcome to#  the Hotland crossing."
    dlg.v.message = {[0] = marker}
    dlg.v.talker = {[0] = -4}
    dlg.v.portrait = 0
    local deadline, sawText = 0, false
    R.drawLog = {}
    while deadline < 240 and not sawText do
        tick(1); deadline = deadline + 1
        for _, entry in ipairs(R.drawLog) do
            if entry[1] == "text" and tostring(entry[2]):find("Hotland crossing", 1, true) then sawText = true end
        end
    end
    say("obj_dialogue alive after", deadline, "ticks:", dlg.alive, "| marker drawn:", sawText)

    local textDraws, drawnFonts = {}, {}
    for _, entry in ipairs(R.drawLog) do
        if entry[1] == "text" then
            textDraws[#textDraws + 1] = entry
            drawnFonts[entry[5]] = (drawnFonts[entry[5]] or 0) + 1
        end
    end
    say("Yellow text draws captured:", #textDraws)
    local setSeen = {}
    for _, set in ipairs(fontSets) do
        local key = describeFont(set.v)
        if not setSeen[key] then
            setSeen[key] = true
            local raw = type(set.v) == "number" and set.v < base and set.v or nil
            local intended = raw and yellowFontByRaw(raw) or nil
            if intended then
                say("  draw_set_font:", key, "| raw Yellow number", raw,
                    "means Yellow's own font", intended, "(merged id", base + raw .. ")")
            else
                say("  draw_set_font:", key)
            end
        end
    end
    for id, count in pairs(drawnFonts) do
        say(("  text drawn with font %s x%d"):format(describeFont(id), count))
    end

    -- The layout the shared renderer gives Yellow's own call:
    -- draw_text_ext(xx, yy+10, message, line_sep=18, width=-1).
    local state = R.graphicsState
    local activeFont = state.font
    local B = R.builtins
    local function wrapLines(str, width)
        -- Port of port/graphics.lua's draw_text_ext wrap, verbatim semantics.
        local linesOut = {}
        for line in (str .. "\n"):gmatch("([^\n]*)\n") do
            line = line:gsub("\\#", "\1"):gsub("#", "\n")
            for sub in (line .. "\n"):gmatch("([^\n]*)\n") do
                local current = ""
                for word in sub:gmatch("%S+") do
                    local next = current == "" and word or current .. " " .. word
                    if current ~= "" and B.string_width(nil, next) > width then
                        linesOut[#linesOut + 1] = current; current = word
                    else current = next end
                end
                linesOut[#linesOut + 1] = current
            end
        end
        return linesOut
    end
    local plain = (marker:gsub("#", " "))
    local linesWrapped = wrapLines(marker, -1)          -- Yellow's width argument
    local linesSensible = wrapLines(marker, 320)        -- a sane wrap width
    local longest = 0
    for _, line in ipairs(linesWrapped) do longest = math.max(longest, B.string_width(nil, line)) end
    local f = R.assets.fonts[activeFont]
    local spacing = 18
    local boxW, boxH = longest, #linesWrapped * spacing
    say(("layout of the marker under active font %s: %d lines from %d words, box %sx%s px -> %s")
        :format(describeFont(activeFont), #linesWrapped, select(2, plain:gsub("%S+", "")),
            fmt(boxW), fmt(boxH), (boxH > boxW and #linesWrapped > 2) and "VERTICAL COLUMN" or "horizontal"))
    say(("layout under a 320px wrap width for comparison: %d lines"):format(#linesSensible))
    local function coverage(str, fontId)
        local rec = R.assets.fonts[fontId]; if not rec then return -1 end
        local hits, total = 0, 0
        for i = 1, #str do
            local ch = str:byte(i)
            if ch ~= 32 then total = total + 1; if rec.glyphs[ch] then hits = hits + 1 end end
        end
        return total == 0 and 1 or hits / total
    end
    say(("glyph coverage of the marker: active font %.0f%% | Yellow's own fnt_main (merged %d) %.0f%%")
        :format(coverage(plain, activeFont) * 100, base + 9, coverage(plain, base + 9) * 100))
    local active = fontInfo(activeFont)
    if active.present and active.world == "undertale" then
        say("SYMPTOM FONT: Yellow dialogue is drawn with an UNDERTALE font (" ..
            tostring(active.name) .. "); Yellow's dialogue_font=9 is Yellow's own raw font number " ..
            "(fnt_main), which the merged build reads through Undertale's ID band.")
    elseif not active.present then
        say("SYMPTOM FONT: Yellow dialogue is drawn with NO converted font record (id " ..
            tostring(activeFont) .. "); the generic fallback face renders it.")
    end
    if boxH > boxW and #linesWrapped > 2 then
        say("SYMPTOM VERTICAL: draw_text_ext(..., width=-1) wraps at every word, " ..
            "so the box is taller than it is wide: text stacks as a column. " ..
            "GameMaker treats a negative width as 'no wrapping'; the shared renderer does not.")
    end
    -- Cleanup of this probe's dialogue so later sections start clean.
    if dlg.alive then R:destroy(dlg, false) end
    R.global.dialogue_open = false
    tick(2)
end

----------------------------------------------------------- performance -----
-- Per-tick cost of one Undertale room vs two Yellow rooms, same run, same
-- measurement. The numbers are CPU microseconds/tick, garbage growth, event
-- dispatches and draw-log entries per tick/frame - the quantities piece D2
-- must beat after its fix. The Undertale baseline is always an Undertale
-- room (the corridor in full mode, the Hotland dock in quick mode).
if wants("performance") then
    section("performance")
    say("tick budget per room:", PERF_TICKS, "(quick=" .. tostring(QUICK) .. ")")
    local ut
    if openingPlayed then
        -- Already measured in the opening section, at Flowey's corridor.
        ut = nil
    else
        if R.travel.world ~= "undertale" then
            R:gotoRoom(140); R:applyTransitions(); tick(5)
        end
        R.global.plot = 122
        ut = measure("UT " .. roomName(), PERF_TICKS)
    end
    R.global.plot = 122
    if R.travel.world ~= "yellow" then
        hold(88, 2)
        R:gotoRoom(140); R:applyTransitions(); tick(10)
    end
    local y1 = measure("Y " .. roomName(), PERF_TICKS)
    R:gotoRoom(ROOM.snowdin); R:applyTransitions(); tick(10)
    local y2 = measure("Y " .. roomName(), PERF_TICKS)
    if ut then
        say(("Yellow/Undertale tick-cost ratio: %.2fx (hotland), %.2fx (snowdin)")
            :format(y1 / ut, y2 / ut))
    else
        say(("Yellow/Undertale tick-cost ratio vs the corridor baseline above: " ..
             "%.2fx (hotland), %.2fx (snowdin)"):format(y1 / utCorridor, y2 / utCorridor))
    end
end

-------------------------------------------------------- player-identity ----
-- Exactly one Player, ever: count both worlds' player objects and Yellow's
-- controllers across repeated crossings, on both packaged directions.
local function census(label)
    local frisk, clover = countInstances(OBJ.frisk), countInstances(OBJ.clover)
    local controllers = countInstances(OBJ.controller)
    say(("%-38s world=%-9s room=%-26s frisk=%d clover=%d controllers=%d total=%d")
        :format(label, tostring(R.travel.world), roomName(), frisk, clover, controllers, #R.instances))
    return frisk, clover
end
if wants("player-identity") then
    section("player-identity")
    if R.travel.world ~= "undertale" then
        R:gotoRoom(140); R:applyTransitions(); tick(5)
    end
    census("start (Undertale dock)")
    local worst = 0
    for round = 1, (QUICK and 2 or 3) do
        hold(88, 2)
        R:gotoRoom(140); R:applyTransitions(); tick(10)
        local f, c = census("round " .. round .. " -> Yellow")
        worst = math.max(worst, f + c)
        R:gotoRoom(140); R:applyTransitions(); tick(10)
        f, c = census("round " .. round .. " -> back to Undertale")
        worst = math.max(worst, f + c)
    end
    say("max simultaneous player instances across all crossings:", worst)
    if worst > 1 then
        say("SYMPTOM DUPLICATE-PLAYER: more than one Player instance alive at once.")
    else
        say("scripted packaged crossings keep exactly one Player; the owner's " ..
            "duplicate must come from the interactive boat flow - checked next.")
    end
end

-------------------------------------------------------- boat-destination ---
-- The River Person's own code decides the destination: flag[459] chooses the
-- dock in obj_dogboat_thing's Step (con==18), and travel:resolve may redirect
-- that dock through the fused crossing. Each case seeds only state, then lets
-- the game's own events call room_goto; the wrapper above records the
-- request and the outcome is whatever room actually loaded.
local function toHotlandDock()
    if R.travel.world ~= "undertale" then
        R:gotoRoom(140); R:applyTransitions(); tick(5)
    end
    R.global.plot = 122
    R:gotoRoom(140); R:applyTransitions(); tick(5)
    assert(roomName() == "room_fire_dock", "dock did not load: " .. roomName())
    local boat
    for _, inst in ipairs(R.instances) do
        if inst.alive and inst.v.object_index == OBJ.boat then boat = inst end
    end
    assert(boat, "dock has no boat")
    return boat
end
-- The expected room name comes from the manifest itself, so the probe never
-- hard-codes a name the conversion could legitimately change.
local function nameOfRoom(id) return R:roomData(id).name end
local function runDisembark(case, boat, expectRoomId)
    local dockName = roomName()
    local before = #gotoLog
    boat.v.con = 18 -- the boat's own disembark state: flag[459] -> room_goto
    local deadline = 0
    while deadline < 60 and roomName() == dockName do tick(1); deadline = deadline + 1 end
    local landed = roomName()
    local request = nil
    for i = before + 1, #gotoLog do request = gotoLog[i] end
    local expect = nameOfRoom(expectRoomId)
    local ok = expect == landed
    say(("%-46s requested=%-9s latch=%-5s landed=%-26s expected=%-26s %s")
        :format(case, tostring(request and request.req), tostring(request and request.latch),
            landed, expect, ok and "OK" or "MISMATCH"))
    local frisk, clover = countInstances(OBJ.frisk), countInstances(OBJ.clover)
    if frisk + clover ~= 1 then
        say("  players after this case: frisk=" .. frisk .. " clover=" .. clover)
    end
    return ok
end
if wants("boat-destination") then
    section("boat-destination")
    local results = {}
    -- A: native disembark, Snowdin dock, nothing held -> Undertale's own dock.
    local boat = toHotlandDock()
    R.global.flag[459] = 1
    results[#results + 1] = runDisembark("native flag=1 (Snowdin), no X", boat, 70)
    -- B: the Waterfall dock.
    boat = toHotlandDock()
    R.global.flag[459] = 2
    results[#results + 1] = runDisembark("native flag=2 (Waterfall), no X", boat, 125)
    -- C: the Hotland dock (flag 3) - the boat stays in its own dock room.
    boat = toHotlandDock()
    R.global.flag[459] = 3
    results[#results + 1] = runDisembark("native flag=3 (Hotland), no X", boat, 140)
    -- D: holding X through the disembark aims the native dock at Yellow.
    boat = toHotlandDock()
    R.global.flag[459] = 1
    input:setSource("test", {88}); tick(2)
    results[#results + 1] = runDisembark("X held, flag=1 -> Yellow stop", boat, ROOM.snowdin)
    input:setSource("test", {}); tick(1)
    -- E: the pager: an explicit Yellow selection with its own landing spot.
    boat = toHotlandDock()
    local points = R.travel.YELLOW_TRAVEL_POINTS
    R.travel:finishRiverChoice(1, points[2]) -- Dunes - West Mines
    boat = nil
    for _, inst in ipairs(R.instances) do
        if inst.alive and inst.v.object_index == OBJ.boat then boat = inst end
    end
    if boat then
        results[#results + 1] = runDisembark("pager -> Dunes - West Mines", boat, ROOM.dunes)
    else
        say("pager -> Dunes: boat missing after finishRiverChoice; recording latch only")
        results[#results + 1] = R.travel.riverLatch == true
    end
    -- G: the pager selection, then the boat's own ride from the state
    -- finishRiverChoice leaves it in (con=0.1) - no states forced. This is
    -- the interactive flow the owner plays: does the ride animation run,
    -- and where does the first room_goto land?
    boat = toHotlandDock()
    R.travel:finishRiverChoice(1, points[1]) -- Snowdin - Forest
    boat = nil
    for _, inst in ipairs(R.instances) do
        if inst.alive and inst.v.object_index == OBJ.boat then boat = inst end
    end
    if boat then
        local before = #gotoLog
        local deadline = 0
        while deadline < 900 and R.travel.world == "undertale" and boat.alive do
            tick(1); deadline = deadline + 1
        end
        say(("full ride after pager: %d ticks, landed=%s world=%s goto sequence:")
            :format(deadline, roomName(), tostring(R.travel.world)))
        for i = before + 1, #gotoLog do
            local entry = gotoLog[i]
            say(("    room_goto(%s) from %s latch=%s dest=%s")
                :format(tostring(entry.req), tostring(entry.from), tostring(entry.latch),
                    tostring(entry.dest)))
        end
        local frisk, clover = countInstances(OBJ.frisk), countInstances(OBJ.clover)
        say("  players after full ride: frisk=" .. frisk .. " clover=" .. clover ..
            " (total instances " .. #R.instances .. ")")
    else
        say("full ride: boat missing after finishRiverChoice")
    end
    -- F: the return trip through Yellow's own whale globals.
    if R.travel.world ~= "yellow" then
        hold(88, 2); R:gotoRoom(140); R:applyTransitions(); tick(5)
    end
    R.global.fast_travel_point = "Waterfall - Dock"
    R:gotoRoom(125); R:applyTransitions(); tick(5)
    local ok = roomName() == nameOfRoom(125) and R.travel.world == "undertale"
    say(("%-46s requested=%-9s landed=%-26s expected=%-26s %s")
        :format("whale return fast_travel_point=Waterfall", "125",
            roomName(), nameOfRoom(125), ok and "OK" or "MISMATCH"))
    results[#results + 1] = ok
    local mismatches = 0
    for _, okk in ipairs(results) do if not okk then mismatches = mismatches + 1 end end
    say("boat destination cases:", #results, "mismatches:", mismatches)
    if mismatches > 0 then
        say("SYMPTOM BOAT-DESTINATION: at least one packaged choice lands somewhere else.")
    end
end

--------------------------------------------------------------- summary -----
section("summary")
say("probe completed: phases=" .. PHASE .. " quick=" .. tostring(QUICK) ..
    " perf_ticks=" .. PERF_TICKS .. " frames=" .. R.frame .. " crossings=" ..
    tostring(R.travel and R.travel.crossings))
say("Evidence above feeds docs/DEBUG_BASELINE.md; pieces D1-D5 own the fixes.")
"""


def run_probe(phases: str, quick: bool, perf_ticks: int | None) -> int:
    """Run the probe in a Lua VM via lupa, mirroring the test-suite boot."""
    import os

    from lupa.luajit21 import LuaRuntime

    env_patch = {
        "DEBUG_PROBE_PHASES": phases,
        "DEBUG_PROBE_QUICK": "1" if quick else "",
    }
    if perf_ticks is not None:
        env_patch["DEBUG_PROBE_PERF_TICKS"] = str(perf_ticks)
    old = {key: os.environ.get(key) for key in env_patch}
    os.environ.update(env_patch)
    try:
        vm = LuaRuntime(unpack_returned_tuples=True)
        vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
        vm.execute(PROBE_LUA)
        return 0
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true",
                        help="reduced tick budget and no played opening (the regression test's mode)")
    parser.add_argument("--phases", default="all",
                        help="comma/substring filter of phases to run (default: all)")
    parser.add_argument("--perf-ticks", type=int, default=None,
                        help="override the per-room performance tick budget")
    parser.add_argument("--check-pipeline", action="store_true",
                        help="run tools/convert.py etc. first if generated/ is missing")
    args = parser.parse_args()

    if args.check_pipeline and not (ROOT / "generated/merged/manifest.lua").is_file():
        for tool in ("tools/convert.py", "tools/yellow_convert.py --stage rooms", "tools/merge.py"):
            subprocess.run([sys.executable, *tool.split()], cwd=ROOT, check=True)

    if not (ROOT / "generated/merged/manifest.lua").is_file():
        print("generated/merged/manifest.lua is missing; run the conversion pipeline first "
              "(docs/DEBUG_QUEUE.md section 4) or pass --check-pipeline.", file=sys.stderr)
        return 2
    # The suite's own tests re-run earlier conversion stages on generated/yellow/,
    # so the rooms stage must be re-asserted before the probe measures anything.
    report = ROOT / "generated/yellow/conversion-report.json"
    import json
    stage = json.loads(report.read_text()).get("stage") if report.is_file() else None
    if stage != "rooms":
        print(f"generated/yellow/ is at stage {stage!r}, not 'rooms'; re-run the pipeline "
              "(python3 tools/yellow_convert.py --stage rooms && python3 tools/merge.py).",
              file=sys.stderr)
        return 2
    import os
    os.chdir(ROOT)
    return run_probe(args.phases, args.quick, args.perf_ticks)


if __name__ == "__main__":
    sys.exit(main())
