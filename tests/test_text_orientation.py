"""D1b: ``draw_text_ext`` keeps Undertale Yellow dialogue horizontal.

D0 traced Yellow's own ``obj_dialogue`` call to
``draw_text_ext(xx, yy + 10, message, line_sep, -1)``.  GameMaker defines a
non-positive wrap width as *no automatic wrapping*, but the shared renderer
compared every candidate line against ``-1``.  That made it emit one word per
line, which looks like vertically stacked text.

These tests exercise the installed shared graphics builtin with a small LÖVE
graphics double.  They deliberately test the renderer rather than copying its
word-wrap loop: reverting the ``width > 0`` guard makes the first test emit one
``print`` call per word and fail.  The double also verifies that the temporary
text transform is scoped by push/pop, so a transformed draw cannot rotate the
following Yellow dialogue.

Scope: renderer semantics and transform-stack behaviour under a deterministic
LÖVE graphics double.  Native LÖVE/Android pixels remain CI/device work; the
full port suite and CI native smoke cover the converted build path.
"""
from pathlib import Path

import pytest
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


GRAPHICS_DOUBLE = r'''
    -- Enough of love.graphics for Graphics.install's text path.  The double
    -- records the transform in effect for each fallback-font print, allowing
    -- the test to see both wrapping and transform leakage without a GPU.
    calls = {}
    local angle, tx, ty, sx, sy = 0, 0, 0, 1, 1
    local stack = {}
    pushes, pops = 0, 0
    love = {graphics = {}}
    local g = love.graphics
    function g.push()
        pushes = pushes + 1
        stack[#stack + 1] = {angle = angle, tx = tx, ty = ty, sx = sx, sy = sy}
    end
    function g.pop()
        pops = pops + 1
        local prior = assert(stack[#stack], "graphics pop without push")
        stack[#stack] = nil
        angle, tx, ty, sx, sy = prior.angle, prior.tx, prior.ty, prior.sx, prior.sy
    end
    function g.translate(x, y) tx, ty = tx + x, ty + y end
    function g.rotate(v) angle = angle + v end
    function g.scale(x, y) sx, sy = sx * x, sy * y end
    function g.setColor() end
    function g.newFont() return {} end
    function g.setFont() end
    function g.print(line, x, y)
        calls[#calls + 1] = {line = line, x = x, y = y,
                              angle = angle, tx = tx, ty = ty, sx = sx, sy = sy}
    end

    R = {
        builtins = {},
        options = {trace = true},
        assets = {fonts = {}, sprites = {}, backgrounds = {}},
        warn = function() end,
        resolveFontIndex = function(_, id) return id end,
    }
    require("port.graphics").install(R)
    B = R.builtins

    function resetCalls()
        calls = {}
        pushes, pops = 0, 0
    end
    function graphicsState()
        return {angle = angle, tx = tx, ty = ty, sx = sx, sy = sy,
                stack = #stack, pushes = pushes, pops = pops}
    end
'''


@pytest.fixture
def graphics_vm(monkeypatch):
    monkeypatch.chdir(ROOT)
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    vm.execute(GRAPHICS_DOUBLE)
    return vm


def test_non_positive_draw_text_ext_width_preserves_horizontal_words(graphics_vm):
    """Yellow dialogue's ``width=-1`` (and zero) means no auto-wrap.

    Before D1b each candidate after the first exceeded ``-1``/``0`` and was
    emitted on its own row.  The result was a tall, narrow word column.
    """
    result = graphics_vm.execute(r'''
        local message = "Hello from Undertale Yellow"
        for _, width in ipairs({-1, 0}) do
            resetCalls()
            B.draw_text_ext(nil, 37, 48, message, 18, width)
            if #calls ~= 1 then
                return "width " .. width .. " printed " .. #calls ..
                    " rows instead of one: " .. table.concat((function()
                        local rows = {}
                        for i, call in ipairs(calls) do rows[i] = call.line end
                        return rows
                    end)(), " | ")
            end
            local call = calls[1]
            if call.line ~= message then
                return "width " .. width .. " changed the horizontal line to " .. call.line
            end
            if call.angle ~= 0 or call.tx ~= 37 or call.ty ~= 48 then
                return "width " .. width .. " used a leaked transform"
            end
        end
        return "ok"
    ''')
    assert result == "ok"


def test_positive_width_still_wraps_and_explicit_newlines_are_preserved(graphics_vm):
    """D1b changes only the non-positive-width contract, not normal wrapping."""
    result = graphics_vm.execute(r'''
        resetCalls()
        B.draw_text_ext(nil, 0, 0, "A BB CCC", 18, 20)
        if #calls ~= 3 or calls[1].line ~= "A" or calls[2].line ~= "BB" or calls[3].line ~= "CCC" then
            return "positive width no longer wrapped words as expected"
        end
        if calls[1].y ~= 0 or calls[2].y ~= 18 or calls[3].y ~= 36 then
            return "positive-width line spacing changed"
        end
        resetCalls()
        B.draw_text_ext(nil, 0, 0, "First#Second", 18, -1)
        if #calls ~= 2 or calls[1].line ~= "First" or calls[2].line ~= "Second" then
            return "negative width did not retain explicit line breaks"
        end
        return "ok"
    ''')
    assert result == "ok"


def test_text_transform_is_scoped_before_following_yellow_dialogue(graphics_vm):
    """Temporary transformed text cannot rotate the next regular text draw."""
    result = graphics_vm.execute(r'''
        resetCalls()
        B.draw_text_transformed(nil, 10, 20, "tilted", 1, 1, 90)
        B.draw_text_ext(nil, 30, 40, "Yellow dialogue", 18, -1)
        local state = graphicsState()
        if #calls ~= 2 then return "expected two text prints, got " .. #calls end
        if math.abs(calls[1].angle + math.pi / 2) > 0.000001 then
            return "transformed text did not receive its requested angle"
        end
        if calls[2].angle ~= 0 or calls[2].tx ~= 30 or calls[2].ty ~= 40 then
            return "regular dialogue inherited the prior text transform"
        end
        if state.angle ~= 0 or state.tx ~= 0 or state.ty ~= 0 or state.stack ~= 0 then
            return "text transform leaked after pop"
        end
        if state.pushes ~= state.pops or state.pushes ~= 2 then
            return "text draws did not balance graphics push/pop"
        end
        return "ok"
    ''')
    assert result == "ok"
