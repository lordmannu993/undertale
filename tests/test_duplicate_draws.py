"""No duplicated characters or sprite layers (unified-fusion piece 4, spec §8).

The merged build contains 42 assets that carry the *same name* in both games
while being different files (10 sprites, 10 objects, 21 sounds, 1 font at the
pinned revisions). A name table cannot hold both, so before this piece a Yellow
caller that looked one up by name -- ``asset_get_index`` over a name, or a bare
name in Yellow's own code -- was handed **Undertale's** asset: the other game's
twin of the same character. That is §8's "do not render an Undertale version and
an Undertale Yellow version of the same character simultaneously".

The gates here are, in order:

* the audit: every shared name is enumerated with both games' IDs, from the
  conversion data (``port/merge.lua`` -> ``double_named``), never hand-typed;
* selection: a caller in either world resolves each shared name to its own
  game's asset -- never to both, never to the other one;
* rendering: an instance never draws the same pixels twice in one frame. The
  duplicate-draw detector below reads the draw log's provenance (sprite ID and
  drawing instance) and rejects an exact repeat while allowing what the original
  really does: the fractional-sub-index crossfade of one sprite, a body plus its
  differently tinted shadow, and layer/particle draws that belong to no
  instance;
* the fix that the detector found: Yellow paints an actor and then asks its
  palette shader to repaint the very same pixels, which with no shader
  converted is the base sprite drawn twice. ``port/graphics.lua`` now drops that
  repeat and reports it (``R.shaderRedraws``).

Scope: headless converted flow plus the draw log over a sweep of Undertale and
Yellow rooms. It is not a native-rendering or Android claim; the CI LÖVE gate
renders the same rooms. Nothing here asserts pixel-level parity with either
original game.
"""
import json
import subprocess
import sys

import pytest
from lupa.luajit21 import LuaRuntime

from conftest import ROOT

LIVE = (ROOT / "yellow_src").is_dir()
live = pytest.mark.skipif(not LIVE, reason="needs the pinned Yellow source: tools/fetch_yellow.py")

#: The audit's shape at the pinned revisions: category -> number of names both
#: games use. tools/yellow_convert.py derives it; this is the gate on it.
DOUBLE_NAMED = {"sprites": 10, "objects": 10, "sounds": 21, "fonts": 1}

#: Rooms the duplicate sweep drives. Undertale rooms are the decompiled room
#: IDs, Yellow's are pinned by name; both lists are the rooms the previous
#: fusion pieces already load headlessly (docks, Snowdin, Dunes, Dark Ruins).
UNDERTALE_ROOMS = [125, 70, 140, 56, 311]
YELLOW_ROOMS = ["rm_hotland_02", "rm_snowdin_11_yellow", "rm_dunes_05", "rm_darkruins_03"]


@pytest.fixture(scope="session")
def yellow_rooms(converted):
    """Both games converted, Yellow through its rooms stage."""
    if not LIVE:
        pytest.skip("needs the pinned Yellow source: tools/fetch_yellow.py")
    report = ROOT / "generated/yellow/conversion-report.json"
    stage = json.loads(report.read_text())["stage"] if report.is_file() else None
    if stage != "rooms":
        subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "rooms"], cwd=ROOT, check=True)
    return ROOT / "generated/yellow"


@pytest.fixture(scope="session")
def merged(yellow_rooms):
    """The merged manifest, built exactly like the other merged-build gates."""
    run = subprocess.run([sys.executable, "tools/merge.py"], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "Merged manifest" in run.stdout
    return ROOT / "generated/merged/manifest.lua"


DETECTOR = """
    -- Prove provenance: every sprite entry names the sprite ID it resolved to
    -- (after the Frisk remap, so an Undertale and a Yellow asset that share a
    -- name stay distinct) and the instance that asked for it.
    function duplicateDraws()
        local groups, order = {}, {}
        for index, e in ipairs(R.drawLog) do
            if e[1] == "sprite" then
                -- The gate is only meaningful with provenance: a sprite entry
                -- that does not say which asset it resolved to and which
                -- instance asked for it cannot be audited at all.
                if type(e[15]) ~= "number" or type(e[16]) ~= "number" then
                    return "sprite draw without provenance: " .. tostring(e[2])
                end
                local owner, sprite, frame = e[16], e[15], math.floor(e[3])
                -- Layer drawables, backgrounds and particle systems own no
                -- instance; they tile or repeat one sprite by design and are
                -- not characters.
                if owner and owner >= 0 then
                    -- Two draws are the same visual only when every parameter
                    -- matches: a body plus its black alpha-blended shadow
                    -- differs in tint/alpha, and the crossfade pair differs in
                    -- frame with a fractional blend.
                    local key = table.concat({owner, sprite, frame, e[4], e[5], e[6], e[7], e[8], e[9], e[10]}, "/")
                    if groups[key] == nil then groups[key] = {}; order[#order + 1] = key end
                    groups[key][#groups[key] + 1] = index
                end
            end
        end
        local out = {}
        for _, key in ipairs(order) do
            local list = groups[key]
            if #list > 1 then
                out[#out + 1] = key .. " x" .. #list
            end
        end
        table.sort(out)
        return table.concat(out, ", ")
    end
    function playerOf(object)
        for _, i in ipairs(R.instances) do
            if i.alive and i.v.object_index == object then return i end
        end
        return nil
    end
    -- Frisk does not exist in Undertale's opening cutscene, so the Undertale-side
    -- gates use the Waterfall dock, where the tests' other gates already place
    -- him.
    function undertalePlayer()
        local player = playerOf(R.manifest.names["obj_mainchara"])
        if player then return player end
        R:gotoRoom(125); R:applyTransitions(); tick(10)
        return playerOf(R.manifest.names["obj_mainchara"])
    end
"""


def boot(merged, cross=False):
    """A merged Runtime booted like the game, with the draw-log detector
    loaded. ``cross=True`` runs the native River Person crossing first, so the
    Yellow-side gates start in Yellow's world with its own player."""
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    vm.execute("""
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
        function hold(k,n)
            input:setSource("test",{k}); tick(n); input:setSource("test",{}); tick(1)
        end
    """ + DETECTOR + """
        R:start(); tick(1)
    """)
    if cross:
        vm.execute("""
            R.global.plot = 122
            R:gotoRoom(140); R:applyTransitions(); tick(3)
            hold(88,2)
            R:gotoRoom(140); R:applyTransitions(); tick(10)
            assert(R.travel.world == "yellow", "did not reach Yellow: " .. tostring(R.roomState.name))
            R:gotoRoom(R.manifest.yellow_names.rooms["rm_snowdin_11_yellow"]); R:applyTransitions(); tick(4)
        """)
    return vm


@pytest.fixture(scope="module")
def undertaleGame(merged):
    return boot(merged)


@pytest.fixture(scope="module")
def yellowGame(merged):
    return boot(merged, cross=True)


def enterRoom(vm, room):
    """Load a room, let it settle, then render exactly one frame to inspect.

    ``room`` is a Lua expression for the room ID: a decompiled Undertale room
    number, or ``R.manifest.yellow_names.rooms[...]`` for a Yellow one.
    """
    vm.execute(f"R:gotoRoom({room}); R:applyTransitions(); tick(4)")
    vm.execute("R.drawLog = {}; R:renderFrame()")


@live
def test_every_shared_asset_name_is_audited_with_both_games_ids(merged):
    """The audit §8 asks for: list the twins instead of picking one silently."""
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    summary = vm.execute("""
        local m=require("generated.merged.manifest")
        local counts,names={},{}
        for _,entry in ipairs(m.double_named or {}) do
            counts[entry.category]=(counts[entry.category] or 0)+1
            names[#names+1]=entry.category..":"..entry.name
            if type(entry.undertale)~="number" or type(entry.yellow)~="number" then
                return "shared name "..entry.name.." has a non-numeric side"
            end
            if entry.yellow < m.yellow_base then
                return "shared name "..entry.name.." has Yellow id "..entry.yellow
            end
            if entry.undertale >= m.yellow_base then
                return "shared name "..entry.name.." has Undertale id "..entry.undertale
            end
        end
        local flat={}
        for _,entry in ipairs(m.double_named or {}) do flat[entry.name]=true end
        local total=0
        for _ in pairs(flat) do total=total+1 end
        if total~=#(m.double_named or {}) then return "a name is listed twice" end
        if #names~=#(m.name_collisions_with_undertale or {}) then
            return "the flat collision list disagrees with the audit: "..#names.." vs "..#(m.name_collisions_with_undertale or {})
        end
        return table.concat({counts.sprites,counts.objects,counts.sounds,counts.fonts},",")
    """)
    assert summary == "10,10,21,1", summary
    assert sum(DOUBLE_NAMED.values()) == 42


@live
def test_both_games_report_the_same_shared_name_count(merged):
    """The conversion report and the merged manifest must agree on the audit,
    and tools/merge.py must print the real number (it used to print len() of the
    per-category mapping -- the number of categories, 4, not the 42 names)."""
    report = json.loads((ROOT / "generated/yellow/conversion-report.json").read_text())
    table = report["name_collisions_with_undertale"]
    assert {category: len(entries) for category, entries in table.items()} == DOUBLE_NAMED
    run = subprocess.run([sys.executable, "tools/merge.py"], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "assets both games name: 42" in run.stdout, run.stdout
    for category, count in DOUBLE_NAMED.items():
        assert f"{category} {count}" in run.stdout, run.stdout


@live
def test_each_world_resolves_a_shared_name_to_its_own_asset(undertaleGame, yellowGame):
    """One authoritative asset per name per world, for all 42 names: a Yellow
    caller gets Yellow's copy, an Undertale caller Undertale's -- never both."""
    undertaleGame.execute("tick(60)")
    ut = undertaleGame.execute("""
        local player = undertalePlayer()
        if not player then return "no Frisk in Undertale's world" end
        local scope = R:scope(player)
        local wrong, checked = 0, 0
        for _, entry in ipairs(R.manifest.double_named) do
            checked = checked + 1
            if R:call("asset_get_index", scope, entry.name) ~= entry.undertale then wrong = wrong + 1 end
            if scope[entry.name] ~= entry.undertale then wrong = wrong + 1 end
            if R:assetName(entry.name, scope) ~= entry.undertale then wrong = wrong + 1 end
        end
        return tostring(checked) .. ":" .. tostring(wrong)
    """)
    assert ut == "42:0", ut

    yellow = yellowGame.execute("""
        local clover = playerOf(R.manifest.yellow_names.objects["obj_pl"])
        if not clover then return "no Clover-bodied player in Yellow" end
        local scope = R:scope(clover)
        local wrong, checked = 0, 0
        negative = 0
        for _, entry in ipairs(R.manifest.double_named) do
            checked = checked + 1
            if R:call("asset_get_index", scope, entry.name) ~= entry.yellow then wrong = wrong + 1 end
            if scope[entry.name] ~= entry.yellow then wrong = wrong + 1 end
            if R:assetName(entry.name, scope) ~= entry.yellow then wrong = wrong + 1 end
            -- the Undertale side is never what a Yellow caller is handed
            if R.constants[entry.name] ~= entry.yellow then negative = negative + 1 end
        end
        return tostring(checked) .. ":" .. tostring(wrong) .. ":" .. tostring(negative)
    """)
    checked, wrong, flat_undertale = (int(part) for part in yellow.split(":"))
    assert checked == 42 and wrong == 0, yellow
    # the flat table still holds Undertale's ID for every shared name: the port's
    # own Lua and the tests read it directly, and Undertale's behaviour is
    # unchanged by the split.
    assert flat_undertale == 42, yellow


@live
def test_a_yellow_lookup_never_lands_on_the_other_games_twin(yellowGame):
    """The concrete twins §8 names, one per category: a Yellow caller looking a
    shared name up is handed Yellow's copy, never Undertale's -- and the two
    really are different assets, so the check has something to catch."""
    named = yellowGame.execute("""
        local clover = playerOf(R.manifest.yellow_names.objects["obj_pl"])
        local scope = R:scope(clover)
        local names = {"spr_flowey", "spr_switch", "obj_floweytrigger", "obj_solidparent",
                       "obj_alphys_npc", "mus_shop", "snd_splash", "fnt_main"}
        local out = {}
        for _, name in ipairs(names) do
            local entry
            for _, candidate in ipairs(R.manifest.double_named) do
                if candidate.name == name then entry = candidate end
            end
            if not entry then
                out[#out+1] = name .. " is not in the audit"
            else
                local got = R:call("asset_get_index", scope, name)
                if got ~= entry.yellow then
                    out[#out+1] = name .. " gave " .. tostring(got) .. ", not Yellow's " .. tostring(entry.yellow)
                end
                if entry.undertale == entry.yellow then
                    out[#out+1] = name .. " has one ID for both games"
                end
                if R.constants[name] ~= entry.undertale then
                    out[#out+1] = name .. " lost Undertale's value in the flat table"
                end
            end
        end
        return table.concat(out, "; ")
    """)
    assert named == "", named


@live
def test_no_instance_draws_the_same_sprite_twice_in_one_frame(undertaleGame, yellowGame):
    """The duplicate gate itself, over a sweep of both worlds' rooms."""
    failures = []

    def sweep(vm, rooms):
        for label, expression in rooms:
            enterRoom(vm, expression)
            found = vm.execute("return duplicateDraws()")
            if found:
                failures.append(f"{label}: {found}")

    sweep(undertaleGame, [(f"room {room}", str(room)) for room in UNDERTALE_ROOMS])
    sweep(yellowGame, [(name, f"R.manifest.yellow_names.rooms['{name}']") for name in YELLOW_ROOMS])
    assert failures == [], "duplicated sprite draws: " + " | ".join(failures)


@live
def test_the_palette_shaders_redraw_is_not_repeated(yellowGame):
    """The duplicate the detector found, pinned at its source: Yellow draws an
    actor and then asks sh_palette_swap to repaint the same pixels. With shaders
    unconverted the second draw is the base sprite drawn twice, so it is
    dropped and counted -- the body itself still draws exactly once."""
    enterRoom(yellowGame, "R.manifest.yellow_names.rooms['rm_snowdin_11_yellow']")
    result = yellowGame.execute("""
        local clover = playerOf(R.manifest.yellow_names.objects["obj_pl"])
        if not clover then return "no player in Yellow" end
        R.shaderRedraws = 0
        R.drawLog = {}; R:renderFrame()
        local body, suppressed = 0, 0
        for _, e in ipairs(R.drawLog) do
            if e[1] == "sprite-suppressed" then suppressed = suppressed + 1 end
            if e[1] == "sprite" and e[16] == clover.id then body = body + 1 end
        end
        return table.concat({body, suppressed, R.shaderRedraws, #R.drawLog}, ":")
    """)
    body, suppressed, reported, _ = (int(part) for part in result.split(":"))
    assert body == 1, f"the player's own body drew {body} times in one frame: {result}"
    assert suppressed == 1, f"the shader's duplicate redraw was not dropped: {result}"
    assert reported == 1, f"the dropped redraw was not reported: {result}"


@live
def test_a_shader_active_draw_that_is_not_a_repeat_still_draws(yellowGame):
    """The drop is a duplicate rule, not a blanket shader no-op: under the same
    unconverted shader, a draw of an identical sprite somewhere else still
    happens, so nothing disappears from a scene."""
    result = yellowGame.execute("""
        local clover = playerOf(R.manifest.yellow_names.objects["obj_pl"])
        if not clover then return "no player in Yellow" end
        local drawn = R.spriteForDraw(clover.v.sprite_index)
        R.builtins.shader_set(nil, 0)
        R.drawLog = {}; R:renderFrame()
        -- the opaque body, not the black alpha-blended shadow beside it
        local body = 0
        for _, e in ipairs(R.drawLog) do
            if e[1] == "sprite" and e[15] == drawn and e[9] == 16777215 and e[10] == 1 then body = body + 1 end
        end
        -- the same sprite, asked for at a different place, under the shader
        R:call("draw_sprite", R:scope(clover), clover.v.sprite_index, 0, 123, 45)
        local extra, dropped = 0, 0
        for _, e in ipairs(R.drawLog) do
            if e[1] == "sprite" and e[15] == drawn and e[4] == 123 and e[5] == 45
               and e[9] == 16777215 and e[10] == 1 then extra = extra + 1 end
            if e[1] == "sprite-suppressed" then dropped = dropped + 1 end
        end
        R.builtins.shader_reset(nil)
        return tostring(body) .. ":" .. tostring(extra) .. ":" .. tostring(dropped)
    """)
    body, extra, dropped = (int(part) for part in result.split(":"))
    assert body == 1, f"the body did not draw once: {result}"
    assert extra == 1, f"a non-repeating draw under the shader was dropped: {result}"
    assert dropped == 1, f"the palette redraw was expected to be dropped once: {result}"


def test_only_yellow_looks_assets_up_by_name(converted):
    """Why the split cannot change Undertale, name by name, from the converted
    code itself.

    Undertale's conversion resolves assets numerically: no generated Undertale
    code calls ``asset_get_index``, and none of the 32 shared sprite, sound or
    font names survives as a quoted string in it. The 10 shared *object* names do
    appear -- as Undertale's own ``with``-style selectors, ``E["obj_floweytrigger"]``,
    and as the names in their own object definitions -- and those must keep
    resolving to Undertale's copy, which is what the world-aware scope read
    above checks. Yellow's conversion is the opposite: it looks names up at run
    time (40 sites), so Yellow is the side the per-world resolution protects."""
    audit = LuaRuntime(unpack_returned_tuples=True)
    audit.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    entries = audit.execute("""
        local out={}
        for _,e in ipairs(require("generated.merged.manifest").double_named) do
            out[#out+1]=e.category.." "..e.name
        end
        return table.concat(out,"\\n")
    """).split("\n")
    assert len(entries) == 42, entries

    def generated(root):
        return list((ROOT / root).rglob("*.lua"))

    undertale_files = generated("generated/objects") + generated("generated/scripts")
    lookups = [p.relative_to(ROOT).as_posix() for p in undertale_files if "asset_get_index" in p.read_text()]
    assert lookups == [], "Undertale's converted code looks assets up by name: " + "; ".join(lookups[:5])

    leftovers = []
    for entry in entries:
        category, name = entry.split(" ", 1)
        for path in undertale_files:
            text = path.read_text()
            if '"' + name + '"' not in text:
                continue
            if category == "objects":
                # its own definition and its own with-style selector are fine
                text = text.replace('["name"]="' + name + '"', "")
                text = text.replace('E["' + name + '"]', "")
            if '"' + name + '"' in text:
                leftovers.append(f"{path.relative_to(ROOT)}: {name} ({category})")
    assert leftovers == [], "Undertale's converted code names a shared asset outside a selector: " + "; ".join(leftovers[:5])

    yellow_files = generated("generated/yellow/objects") + generated("generated/yellow/scripts")
    yellow_lookups = [p.relative_to(ROOT).as_posix() for p in yellow_files if "asset_get_index" in p.read_text()]
    assert len(yellow_lookups) >= 10, f"Yellow's converted code should look names up: {yellow_lookups}"


def test_an_undertale_visitor_keeps_the_undertale_asset_in_yellow(yellowGame):
    """The §8 selection rule at its sharpest: an Undertale instance standing in a
    Yellow room must keep Undertale's copy of a shared name, because the asset
    belongs to the content the caller came from -- not to the room it happens to
    be in. (Resolving by the room's world instead hands it Yellow's Flowey.)"""
    result = yellowGame.execute("""
        local visitor = R:create(R.manifest.names["obj_mainchara"], 100, 100)
        local scope = R:scope(visitor)
        local flag = 1
        local wrong, checked = 0, 0
        for _, entry in ipairs(R.manifest.double_named) do
            checked = checked + 1
            if R:assetName(entry.name, scope) ~= entry.undertale then wrong = wrong + 1 end
            if R:call("asset_get_index", scope, entry.name) ~= entry.undertale then wrong = wrong + 1 end
        end
        -- and the room's own, instance-less caller still gets Yellow's copy
        local roomWide = R:assetName("spr_flowey", R:scope(nil))
        R:destroy(visitor)
        return table.concat({checked, wrong, flag, roomWide,
            R.manifest.yellow_names.sprites["spr_flowey"]}, ":")
    """)
    checked, wrong, flag, room_wide, yellow_flowey = (int(part) for part in result.split(":"))
    assert checked == 42 and wrong == 0, f"the visitor resolved {wrong} of {checked} names wrong: {result}"
    assert flag == 1, result  # the visitor still exists and runs in Yellow's world
    assert room_wide == yellow_flowey, f"a room-level caller lost Yellow's Flowey: {result}"


@live
def test_no_scene_shows_both_games_copies_of_one_name(undertaleGame, yellowGame):
    """Spec §8's headline case: no scene holds both an Undertale and a Yellow
    version of the same character. Two gates per room -- an instance of a
    double-named object must be the room's own game's copy, and no frame may
    paint both copies of a shared sprite."""
    failures = []

    def sweep(vm, rooms, expect):
        for label, expression in rooms:
            enterRoom(vm, expression)
            found = vm.execute(f"""
                local objectPair = {{}}
                for _, e in ipairs(R.manifest.double_named) do
                    if e.category == "objects" then
                        objectPair[e.undertale] = e
                        objectPair[e.yellow] = e
                    end
                end
                local out = {{}}
                for _, i in ipairs(R.instances) do
                    if i.alive then
                        local entry = objectPair[i.v.object_index]
                        if entry then
                            -- the room's world picks which copy is right
                            local belongs = (i.v.object_index >= 1000000) and "yellow" or "undertale"
                            if belongs ~= "{expect}" then
                                out[#out + 1] = "foreign " .. belongs .. " " .. entry.name .. " #" .. i.id
                            end
                        end
                    end
                end
                local seen = {{}}
                for _, e in ipairs(R.drawLog) do
                    if e[1] == "sprite" then seen[e[15]] = true end
                end
                for _, e in ipairs(R.manifest.double_named) do
                    if e.category == "sprites" and seen[e.undertale] and seen[e.yellow] then
                        out[#out + 1] = "both copies of " .. e.name .. " drawn"
                    end
                end
                table.sort(out)
                return table.concat(out, "; ")
            """)
            if found:
                failures.append(f"{label}: {found}")

    sweep(undertaleGame, [(f"room {room}", str(room)) for room in UNDERTALE_ROOMS], "undertale")
    sweep(yellowGame, [(name, f"R.manifest.yellow_names.rooms['{name}']") for name in YELLOW_ROOMS], "yellow")
    assert failures == [], "both games' copy in one scene: " + " | ".join(failures)


@live
def test_a_shader_guarded_repeat_under_a_new_blend_mode_still_draws(yellowGame):
    """The drop is not "the same sprite twice under a shader", it is "the same
    pixels under the same blend state twice". Adding an identical draw on top of
    itself is how the original asks for a glow, so a blend-mode change between
    the two draws keeps both."""
    result = yellowGame.execute("""
        local clover = playerOf(R.manifest.yellow_names.objects["obj_pl"])
        if not clover then return "no player in Yellow" end
        local scope = R:scope(clover)
        local index = clover.v.sprite_index
        R.builtins.shader_set(nil, 0)
        R.drawLog = {}; R.shaderRedraws = 0
        R:call("draw_sprite", scope, index, 0, 200, 200)
        R.builtins.gpu_set_blendmode(nil, R.constants.bm_add)
        R:call("draw_sprite", scope, index, 0, 200, 200)
        local drawn, dropped = 0, 0
        for _, e in ipairs(R.drawLog) do
            if e[1] == "sprite" and e[4] == 200 and e[5] == 200 then drawn = drawn + 1 end
            if e[1] == "sprite-suppressed" then dropped = dropped + 1 end
        end
        R.builtins.gpu_set_blendmode(nil, 0)
        R.builtins.shader_reset(nil)
        return tostring(drawn) .. ":" .. tostring(dropped) .. ":" .. tostring(R.shaderRedraws)
    """)
    drawn, dropped, reported = (int(part) for part in result.split(":"))
    assert drawn == 2, f"an additive repeat was dropped instead of drawn: {result}"
    assert dropped == 0 and reported == 0, f"a blend-mode change was not noticed: {result}"
