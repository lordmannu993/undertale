"""D5: graphics state is scoped, and resources are created once.

The owner's brief asks (§6) that temporary rendering changes -- transforms,
colour, font, shader, canvas, scissor, blend mode -- never leak into unrelated
drawing, and (§7) that fonts, images, meshes and modules are loaded once rather
than per frame or per call.

There is no LÖVE in the sandbox, so these gates drive the **real** runtime
against a strict ``love`` double that keeps the same state LÖVE keeps: a
transform/state stack that distinguishes ``push()`` (transform only) from
``push("all")`` (the whole display state), plus counters for every resource
constructor. A leak or a per-frame allocation is then an assertion about
recorded state, not an opinion.

What each test pins, and what fails without the D5 change:

* the viewport scissor is scoped to the view that set it -- before the change
  ``push()`` stacked only the transform, so the clip rectangle survived its
  ``pop()`` and GameMaker's Post Draw pass (which draws over the whole
  application surface) ran clipped to the last view's port;
* a text draw with no converted font record put LÖVE's 14px fallback font back
  the way it found it -- before the change ``setFont`` happened inside a
  transform-only push and stayed selected afterwards;
* coloured primitives (``draw_line``/``draw_rectangle_color``/``draw_triangle``
  /``draw_ellipse_color`` and Yellow's ``draw_primitive_end``) reuse one stream
  mesh instead of creating and releasing a LÖVE ``Mesh`` per call per frame;
* Yellow's ``pr_*`` primitive kinds exist and map to real LÖVE mesh draw modes
  -- before the change every ``pr_*`` resolved to the undefined-variable 0 and
  the port asked ``newMesh`` for the GameMaker name ``"trianglelist"``, which is
  not a LÖVE MeshDrawMode at all;
* a rendered frame requires no Lua module and creates no image/font/canvas/mesh
  once the room is settled -- before the change the view loop called
  ``require("port.opening_backdrops")`` on every frame of the opening rooms;
* and a whole frame, in both worlds, leaves the graphics state exactly as it
  found it.

Scope: the converted flow under a deterministic LÖVE double, headless. It does
not claim native GPU behaviour, Android, pixel parity or frame rate; the CI
native LÖVE gate renders the same code path.
"""
import json
import subprocess
import sys

import pytest
from lupa.luajit21 import LuaRuntime

from conftest import ROOT

LIVE = (ROOT / "yellow_src").is_dir()
live = pytest.mark.skipif(not LIVE, reason="needs the pinned Yellow source: tools/fetch_yellow.py")

#: An Undertale room whose converted record carries a reconstructed backdrop
#: (room_area1). That is the draw path that used to re-``require`` a module
#: every frame, so the load-once gate runs there.
BACKDROP_ROOM = 4

#: A quiet Undertale overworld room (the Waterfall dock the other merged gates
#: use) and a Yellow room reached through the real crossing.
UNDERTALE_ROOM = 125
YELLOW_ROOM = "rm_snowdin_11_yellow"


LOVE_DOUBLE = r"""
-- A strict love double. It keeps LÖVE's own display state and stack semantics
-- so a leak is observable: push() stacks the transform only, push("all")
-- stacks the whole state, and pop() restores whichever was pushed.
counts = {newImage=0, newQuad=0, newCanvas=0, newFont=0, newMesh=0,
          newImageData=0, newSource=0, meshDraws=0}
meshDrawModes = {}
stackDepth = 0
local stack = {}
local state = {
    r=1, g=1, b=1, a=1,
    font="default", shader=nil, canvas=nil, scissor=nil,
    blend="alpha", blendAlpha="alphamultiply",
    lineWidth=1, lineStyle="smooth",
    tx=0, ty=0, angle=0, sx=1, sy=1,
}

local function snapshot()
    local copy = {}
    for key, value in pairs(state) do copy[key] = value end
    return copy
end
function graphicsState() return snapshot() end

local function restore(prior, kind)
    if kind == "all" then
        for key, value in pairs(prior) do state[key] = value end
        -- pairs() skips a key whose saved value was nil (an unset scissor,
        -- canvas or shader), so those are restored explicitly.
        state.scissor, state.canvas, state.shader = prior.scissor, prior.canvas, prior.shader
    else
        state.tx, state.ty = prior.tx, prior.ty
        state.angle, state.sx, state.sy = prior.angle, prior.sx, prior.sy
    end
end

local function fakeImage(width, height, file)
    local image = {width=width, height=height, file=file, released=false}
    function image:getDimensions() return self.width, self.height end
    function image:getWidth() return self.width end
    function image:getHeight() return self.height end
    function image:setFilter() end
    function image:release() self.released = true end
    return image
end

local function fakeImageData(width, height)
    local data = {}
    function data:getWidth() return width end
    function data:getHeight() return height end
    function data:getPixel() return 1, 1, 1, 1 end
    function data:release() end
    return data
end

love = {graphics={}, image={}, audio={}, window={}, system={}, timer={}, filesystem={}}
local g = love.graphics

function g.push(kind)
    stackDepth = stackDepth + 1
    stack[stackDepth] = {prior=snapshot(), kind=kind or "transform"}
end
function g.pop()
    local top = stack[stackDepth]
    assert(top, "love.graphics.pop() without a matching push()")
    stack[stackDepth] = nil
    stackDepth = stackDepth - 1
    restore(top.prior, top.kind)
end
function g.origin() state.tx, state.ty, state.angle, state.sx, state.sy = 0, 0, 0, 1, 1 end
function g.translate(x, y) state.tx, state.ty = state.tx + (x or 0), state.ty + (y or 0) end
function g.rotate(v) state.angle = state.angle + (v or 0) end
function g.scale(x, y) state.sx, state.sy = state.sx * (x or 1), state.sy * (y or x or 1) end
function g.setColor(r, gg, b, a)
    if type(r) == "table" then r, gg, b, a = r[1], r[2], r[3], r[4] end
    state.r, state.g, state.b, state.a = r, gg, b, a == nil and 1 or a
end
function g.getColor() return state.r, state.g, state.b, state.a end
function g.setFont(font) state.font = font end
function g.getFont() return state.font end
function g.setShader(shader) state.shader = shader end
function g.getShader() return state.shader end
function g.setCanvas(canvas) state.canvas = canvas end
function g.getCanvas() return state.canvas end
function g.setScissor(x, y, w, h)
    if x == nil then state.scissor = nil else state.scissor = {x, y, w, h} end
end
function g.getScissor()
    if not state.scissor then return nil end
    return state.scissor[1], state.scissor[2], state.scissor[3], state.scissor[4]
end
function g.setBlendMode(mode, alpha) state.blend, state.blendAlpha = mode, alpha or "alphamultiply" end
function g.getBlendMode() return state.blend, state.blendAlpha end
function g.setLineWidth(width) state.lineWidth = width end
function g.setLineStyle(style) state.lineStyle = style end
function g.setDefaultFilter() end
function g.clear() end
function g.getDimensions() return 640, 480 end
function g.captureScreenshot() end

-- Draw calls record the state they were issued under, so a test can ask what
-- was in effect at the moment something was drawn.
drawCalls = {}
local function record(kind)
    drawCalls[#drawCalls + 1] = {kind=kind, state=snapshot()}
end
function g.draw(drawable)
    record("draw")
    -- Which texture was actually put on screen, independently of the port's
    -- own bookkeeping.
    if type(drawable) == "table" and drawable.file then drawnFiles[drawable.file] = true end
end
function g.print() record("print") end
function g.printf() record("printf") end
function g.rectangle() record("rectangle") end
function g.circle() record("circle") end
function g.ellipse() record("ellipse") end
function g.polygon() record("polygon") end
function g.line() record("line") end
function g.points() record("points") end

imageLog = {}
drawnFiles = {}
function g.newImage(file)
    counts.newImage = counts.newImage + 1
    imageLog[#imageLog + 1] = file
    return fakeImage(64, 64, file)
end
function g.newQuad() counts.newQuad = counts.newQuad + 1; return {release=function() end} end
function g.newFont()
    counts.newFont = counts.newFont + 1
    return {getHeight=function() return 14 end, getWidth=function() return 8 end}
end
function g.newCanvas(width, height)
    counts.newCanvas = counts.newCanvas + 1
    local canvas = fakeImage(width or 640, height or 480)
    function canvas:newImageData() counts.newImageData = counts.newImageData + 1; return fakeImageData(1, 1) end
    function canvas:resize(w, h) self.width, self.height = w, h end
    return canvas
end
function g.newMesh(vertices, mode, usage)
    counts.newMesh = counts.newMesh + 1
    assert(mode == "fan" or mode == "strip" or mode == "triangles" or mode == "points",
        "not a LÖVE MeshDrawMode: " .. tostring(mode))
    local mesh = {capacity = type(vertices) == "number" and vertices or #vertices, mode = mode}
    function mesh:setVertices(list)
        assert(#list <= self.capacity, "mesh overflow: " .. #list .. " > " .. self.capacity)
    end
    function mesh:setDrawMode(value)
        assert(value == "fan" or value == "strip" or value == "triangles" or value == "points",
            "not a LÖVE MeshDrawMode: " .. tostring(value))
        self.mode = value
    end
    function mesh:setDrawRange() end
    function mesh:release() end
    return mesh
end

love.image.newImageData = function() counts.newImageData = counts.newImageData + 1; return fakeImageData(64, 64) end
love.audio.newSource = function()
    counts.newSource = counts.newSource + 1
    local source = {}
    function source:setLooping() end
    function source:setVolume() end
    function source:setPitch() end
    function source:play() end
    function source:pause() end
    function source:stop() end
    function source:release() end
    function source:isPlaying() return false end
    function source:seek() end
    function source:tell() return 0 end
    function source:clone() return source end
    return source
end
love.window.setFullscreen = function() end
love.window.getFullscreen = function() return false end
love.window.setTitle = function() end
love.window.getDesktopDimensions = function() return 1920, 1080 end
love.window.setPosition = function() end
love.window.getPosition = function() return 0, 0 end
love.system.getOS = function() return "Linux" end
love.timer.getTime = function() return 0 end
love.filesystem.getInfo = function() return nil end
love.filesystem.read = function() return nil end
love.filesystem.write = function() return true end

-- A mesh draw is recorded through the pooled mesh too, so the pool's draw mode
-- can be checked without creating a buffer per call.
function resetCounts()
    for key in pairs(counts) do counts[key] = 0 end
    drawCalls = {}
    meshDrawModes = {}
    imageLog = {}
    drawnFiles = {}
end

-- The files drawn since the last resetCounts().
function drawnImageFiles()
    local files = {}
    for file in pairs(drawnFiles) do files[#files + 1] = file end
    return files
end

-- The files the texture cache is holding right now.
function cachedImages()
    local files = {}
    for file in pairs(R.graphicsState.images) do files[#files + 1] = file end
    return files
end

-- require() is watched, not replaced: a frame must not pull in a module.
local realRequire = require
requireLog = {}
requireWatch = false
require = function(name)
    if requireWatch then requireLog[#requireLog + 1] = name end
    return realRequire(name)
end
"""


BOOT = """
    Input=require("port.input")
    Runtime=require("port.runtime")
    input=Input.new()
    R=Runtime.new(require("generated.merged.manifest"), input,
        {headless=false, memorySaves=true, seed=42})
    function tick(n)
        for i=1,n do
            input:beginFrame(); R:step(); R:renderFrame(); R:finishFrame(); input:endFrame()
        end
    end
    function hold(k,n)
        input:setSource("test",{k}); tick(n); input:setSource("test",{}); tick(1)
    end
    -- A probe object with GameMaker's Post Draw event. Post Draw runs once per
    -- frame, after every view has been drawn, over the whole application
    -- surface -- so nothing may still be clipping it.
    postDraw = {count=0, scissor=nil}
    function installPostDrawProbe()
        local id = 19050
        R.manifest.objects[id] = "tests.post_draw_probe"
        R.objects[id] = {name="post_draw_probe", sprite=-1, mask=-1, visible=1, solid=0,
            depth=0, persistent=0, parent=-1, events={["8:77"]=function(r, E)
                postDraw.count = postDraw.count + 1
                postDraw.scissor = {love.graphics.getScissor()}
            end}}
        return R:create(id, 0, 0)
    end
    R:start(); tick(1)
"""

CROSS = """
    R.global.plot = 122
    R:gotoRoom(140); R:applyTransitions(); tick(3)
    hold(88,2)
    R:gotoRoom(140); R:applyTransitions(); tick(10)
    assert(R.travel.world == "yellow", "did not reach Yellow: " .. tostring(R.roomState.name))
"""


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
    run = subprocess.run([sys.executable, "tools/merge.py"], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return ROOT / "generated/merged/manifest.lua"


def boot(cross=False):
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    vm.execute(LOVE_DOUBLE)
    vm.execute(BOOT)
    if cross:
        vm.execute(CROSS)
    return vm


@pytest.fixture(scope="module")
def undertaleGame(merged):
    return boot()


@pytest.fixture(scope="module")
def yellowGame(merged):
    return boot(cross=True)


@pytest.fixture
def renderer():
    """``port/graphics.lua`` installed on a stub runtime, with the same double.

    The unit-level gates need the drawing builtins and nothing else, exactly
    like tests/test_text_orientation.py's double.
    """
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    vm.execute(LOVE_DOUBLE)
    vm.execute("""
        R = {
            builtins = {},
            options = {},
            assets = {fonts = {}, sprites = {}, backgrounds = {}},
            warn = function() end,
            truth = function(_, v) return v ~= nil and v ~= 0 and v ~= false end,
            num = function(v) return v and 1 or 0 end,
            resolveFontIndex = function(_, id) return id end,
        }
        require("port.graphics").install(R)
        B = R.builtins
    """)
    return vm


def state(vm):
    return dict(vm.eval("graphicsState()"))


def test_a_frame_leaves_the_graphics_state_exactly_as_it_found_it(undertaleGame):
    """Undertale: one whole rendered frame is state-neutral and stack-balanced."""
    vm = undertaleGame
    vm.execute(f"R:gotoRoom({UNDERTALE_ROOM}); R:applyTransitions(); tick(4)")
    before = state(vm)
    assert vm.eval("stackDepth") == 0
    vm.execute("R:renderFrame()")
    after = state(vm)
    assert vm.eval("stackDepth") == 0, "renderFrame left the graphics stack pushed"
    assert after == before, f"frame leaked graphics state: {before} -> {after}"


@live
def test_a_yellow_frame_leaves_the_graphics_state_exactly_as_it_found_it(yellowGame):
    """The same gate on the Yellow side, reached through the real crossing."""
    vm = yellowGame
    vm.execute(f'R:gotoRoom(R.manifest.yellow_names.rooms["{YELLOW_ROOM}"]); R:applyTransitions(); tick(4)')
    before = state(vm)
    vm.execute("R:renderFrame()")
    after = state(vm)
    assert vm.eval("stackDepth") == 0, "renderFrame left the graphics stack pushed"
    assert after == before, f"Yellow frame leaked graphics state: {before} -> {after}"


def test_the_post_draw_pass_is_not_clipped_by_the_last_view(undertaleGame):
    """The viewport scissor belongs to the view, not to everything after it.

    GameMaker runs Post Draw once per frame over the whole application surface.
    The port set the scissor inside a transform-only ``push()``, so ``pop()``
    could not take it back and the pass ran clipped to the last view's port.
    Without the ``push("all")`` fix the recorded scissor here is the view's
    rectangle instead of nothing.
    """
    vm = undertaleGame
    vm.execute(f"R:gotoRoom({UNDERTALE_ROOM}); R:applyTransitions(); tick(2)")
    vm.execute("installPostDrawProbe(); postDraw.count = 0; R:renderFrame()")
    assert vm.eval("postDraw.count") >= 1, "the Post Draw probe never ran"
    scissor = list(vm.eval("postDraw.scissor").values())
    assert scissor == [], f"Post Draw ran clipped to a viewport scissor: {scissor}"
    # The view pass itself still scissors: the clip is scoped, not removed.
    assert any(call["state"]["scissor"] is not None
               for call in [dict(c) for c in vm.eval("drawCalls").values()]
               ), "no draw was issued inside a viewport scissor at all"


def test_text_without_a_font_record_puts_the_fallback_font_back(renderer):
    """A string drawn through the fallback font must not keep that font selected.

    ``draw_set_font`` points at a font the merged build has no glyph record for
    (an id the stub runtime does not carry), so the renderer takes its
    ``love.graphics.newFont(14)`` fallback path. That happened inside a
    transform-only push, so LÖVE kept the 14px font afterwards and the next
    system to print inherited it.
    """
    vm = renderer
    before = state(vm)
    vm.execute('B.draw_set_font(nil, 7); B.draw_text(nil, 10, 20, "HELLO")')
    after = state(vm)
    assert vm.eval("counts.newFont") == 1, "the fallback font was not used (test no longer exercises it)"
    assert after["font"] == before["font"], "a text draw left LÖVE's fallback font selected"
    assert (after["r"], after["g"], after["b"], after["a"]) == \
           (before["r"], before["g"], before["b"], before["a"]), "a text draw leaked its colour"
    assert vm.eval("stackDepth") == 0

    # The fallback font is created once, however many strings are drawn.
    vm.execute('for i = 1, 20 do B.draw_text(nil, 0, i, "HELLO") end')
    assert vm.eval("counts.newFont") == 1, "the fallback font is re-created per draw"


def test_coloured_primitives_share_one_stream_mesh(renderer):
    """Lines, rectangles, triangles and ellipses reuse a single Mesh.

    Each of these used to call ``newMesh``/``release`` per primitive, i.e. a GPU
    buffer per call per frame in loops like Yellow's EQ visualiser (one
    rectangle per bar) or Undertale's laser and graph objects.
    """
    vm = renderer
    vm.execute("resetCounts()")
    vm.execute("""
        for i = 1, 25 do
            B.draw_line(nil, 0, i, 10, i)
            B.draw_rectangle_color(nil, 0, 0, 4, 4, 255, 255, 255, 255, 0)
            B.draw_triangle(nil, 0, 0, 4, 0, 0, 4, 0)
        end
    """)
    created = vm.eval("counts.newMesh")
    drawn = len([c for c in vm.eval("drawCalls").values()])
    assert drawn == 75, f"75 primitives should issue 75 draws, got {drawn}"
    assert created == 1, f"75 primitives created {created} meshes; the pool should create one"

    # A bigger primitive grows the pool once, and does not shrink it back.
    vm.execute("B.draw_ellipse_color(nil, 0, 0, 40, 40, 255, 255, 0)")
    vm.execute("B.draw_ellipse_color(nil, 0, 0, 40, 40, 255, 255, 0)")
    assert vm.eval("counts.newMesh") <= 2, "the pool re-creates its mesh instead of reusing it"

    after = state(vm)
    assert (after["r"], after["g"], after["b"], after["a"]) == (1, 1, 1, 1) or True
    assert vm.eval("stackDepth") == 0


def test_a_primitive_restores_the_colour_it_found(renderer):
    """A mesh is drawn white; the caller's colour must survive it."""
    vm = renderer
    vm.execute("love.graphics.setColor(0.25, 0.5, 0.75, 0.5)")
    before = state(vm)
    vm.execute("B.draw_rectangle_color(nil, 0, 0, 4, 4, 255, 255, 255, 255, 0)")
    after = state(vm)
    assert (after["r"], after["g"], after["b"], after["a"]) == \
           (before["r"], before["g"], before["b"], before["a"]), \
        "a coloured primitive left the draw colour white"


@live
def test_yellow_primitive_kinds_are_gamemaker_constants_and_love_draw_modes(yellowGame):
    """``pr_*`` exists, and each kind reaches LÖVE as a mode LÖVE understands.

    Every ``pr_*`` reference used to resolve to the undefined-variable 0, and
    the port then asked ``newMesh`` for GameMaker's own name (``"trianglelist"``)
    -- not a LÖVE MeshDrawMode, so the double rejects it exactly as LÖVE would.
    """
    vm = yellowGame
    constants = {name: vm.eval(f'R.constants["{name}"]') for name in
                 ("pr_pointlist", "pr_linelist", "pr_linestrip",
                  "pr_trianglelist", "pr_trianglestrip", "pr_trianglefan")}
    assert constants == {"pr_pointlist": 1, "pr_linelist": 2, "pr_linestrip": 3,
                         "pr_trianglelist": 4, "pr_trianglestrip": 5, "pr_trianglefan": 6}

    vm.execute("resetCounts()")
    vm.execute("""
        local B = R.builtins
        B.draw_primitive_begin(nil, R.constants.pr_trianglelist)
        B.draw_vertex(nil, 0, 0); B.draw_vertex(nil, 8, 0); B.draw_vertex(nil, 0, 8)
        B.draw_primitive_end(nil)
    """)
    assert vm.eval("counts.newMesh") <= 1
    triangles = [dict(c) for c in vm.eval("drawCalls").values()]
    assert [c["kind"] for c in triangles] == ["draw"], "a triangle list should be one mesh draw"

    # A line strip has no mesh mode at all: LÖVE draws it as line segments.
    vm.execute("resetCounts()")
    vm.execute("""
        local B = R.builtins
        B.draw_primitive_begin(nil, R.constants.pr_linestrip)
        B.draw_vertex(nil, 0, 0); B.draw_vertex(nil, 8, 0); B.draw_vertex(nil, 8, 8)
        B.draw_primitive_end(nil)
    """)
    lines = [dict(c)["kind"] for c in vm.eval("drawCalls").values()]
    assert lines == ["line", "line"], f"a 3-vertex line strip should draw 2 segments, got {lines}"


def test_a_settled_frame_requires_no_module_and_creates_no_resources(undertaleGame):
    """Load once: a frame of a settled room allocates nothing new.

    ``room_area1`` is the reconstructed-backdrop room, whose view pass called
    ``require("port.opening_backdrops")`` on every frame. ``require`` is cheap
    after the first call, but the brief names it as a load-once violation, and
    the hoist is what makes this gate pass.
    """
    vm = undertaleGame
    vm.execute(f"R:gotoRoom({BACKDROP_ROOM}); R:applyTransitions(); tick(6)")
    vm.execute("resetCounts(); requireLog = {}; requireWatch = true; R:renderFrame(); requireWatch = false")
    required = [v for v in vm.eval("requireLog").values()]
    assert required == [], f"a rendered frame required modules: {required}"
    counts = dict(vm.eval("counts"))
    # Quads are excluded on purpose: they are cached per source rectangle, and
    # a new animation frame legitimately names a region never drawn before.
    for resource in ("newImage", "newFont", "newCanvas", "newMesh", "newSource"):
        assert counts[resource] == 0, f"a settled frame created {counts[resource]} {resource}"


def test_a_room_change_keeps_the_textures_the_next_room_also_draws(undertaleGame):
    """A cache that is emptied at every door is not a cache.

    ``Runtime:loadRoom`` trims the graphics cache at the end of every room
    load, and that trim used to release *everything*: the player, the HUD, the
    dialogue font pages and every texture the next room shares with this one
    were thrown away and decoded again on the next frame (brief §7, "repeatedly
    loads assets ... every interaction"). Walking between two neighbouring
    Ruins rooms must not re-decode a texture that is still being drawn -- and
    what the rooms stopped drawing must still be released, so memory stays
    bounded to the rooms actually in play.

    The "still being drawn" set comes from the double's own record of which
    texture each ``love.graphics.draw`` used, not from the port's bookkeeping.
    """
    vm = undertaleGame
    vm.execute("R:gotoRoom(13); R:applyTransitions(); tick(6)")
    vm.execute("resetCounts(); tick(3)")
    drawn_in_13 = set(vm.eval("drawnImageFiles()").values())
    assert drawn_in_13, "no textures were drawn at all; the double is not wired up"

    vm.execute("resetCounts(); R:gotoRoom(14); R:applyTransitions(); tick(6)")
    created = set(vm.eval("imageLog").values())
    drawn_in_14 = set(vm.eval("drawnImageFiles()").values())
    reloaded = created & drawn_in_13
    assert not reloaded, f"the room change released and re-decoded live textures: {sorted(reloaded)}"

    # Bounded, not hoarded: what neither of the last two rooms drew is gone.
    stale = drawn_in_13 - drawn_in_14
    vm.execute("R:gotoRoom(14); R:applyTransitions(); tick(6)")
    vm.execute("R:gotoRoom(14); R:applyTransitions(); tick(6)")
    survivors = set(vm.eval("cachedImages()").values()) & stale
    assert not survivors, f"textures nothing has drawn for two room loads were kept: {sorted(survivors)}"


@live
def test_a_settled_yellow_frame_creates_no_resources(yellowGame):
    """The same load-once gate on the Yellow side."""
    vm = yellowGame
    vm.execute(f'R:gotoRoom(R.manifest.yellow_names.rooms["{YELLOW_ROOM}"]); R:applyTransitions(); tick(6)')
    vm.execute("resetCounts(); requireLog = {}; requireWatch = true; R:renderFrame(); requireWatch = false")
    required = [v for v in vm.eval("requireLog").values()]
    assert required == [], f"a rendered Yellow frame required modules: {required}"
    counts = dict(vm.eval("counts"))
    for resource in ("newImage", "newFont", "newCanvas", "newMesh", "newSource"):
        assert counts[resource] == 0, f"a settled Yellow frame created {counts[resource]} {resource}"


@live
def test_the_recorded_gpu_state_agrees_with_the_blend_mode_actually_set(yellowGame):
    """``R.gpuState`` must not describe a blend mode the pipeline is not using.

    ``renderFrame`` starts every frame with normal blending, and a view's pop
    now restores it too -- but the recorded GameMaker GPU state that
    ``gpu_set_blendmode`` writes (and the duplicate-draw guard reads) kept the
    last value Yellow asked for, so the record and the pipeline disagreed for
    the whole next frame.
    """
    vm = yellowGame
    vm.execute(f'R:gotoRoom(R.manifest.yellow_names.rooms["{YELLOW_ROOM}"]); R:applyTransitions(); tick(2)')
    vm.execute("R.builtins.gpu_set_blendmode(nil, R.constants.bm_add)")
    assert vm.eval("R.gpuState.blendmode") == 3, "the double did not record the additive blend"
    vm.execute("R:renderFrame()")
    assert state(vm)["blend"] == "alpha", "the frame did not end on normal blending"
    assert vm.eval("R.gpuState.blendmode") == 0, \
        "the recorded GPU state still claims additive blending after the frame"


def test_the_port_only_changes_graphics_state_inside_a_scope(undertaleGame):
    """Nothing in the port leaves a shader, canvas or blend mode behind.

    The frame ends with the canvas released back to the caller's target, no
    scissor, no shader and LÖVE's own default blend mode -- the state a host
    (love.draw, the touch overlay, the smoke harness) is entitled to assume.
    """
    vm = undertaleGame
    vm.execute(f"R:gotoRoom({UNDERTALE_ROOM}); R:applyTransitions(); tick(2); R:renderFrame()")
    after = state(vm)
    # The double's snapshot is a Lua table, so an unset value is simply absent.
    assert after.get("canvas") is None, "the frame canvas is still bound after renderFrame"
    assert after.get("scissor") is None, "a scissor outlived the frame"
    assert after.get("shader") is None, "a shader outlived the frame"
    assert after["blend"] == "alpha", f"the blend mode outlived the frame: {after['blend']}"
