"""Piece 2's GMS2 compiler and runtime namespace checks."""
from __future__ import annotations

import pytest

from tools.gml import CompileError
from tools.gml2 import compile_gml2, compile_gml2_functions


def run_gms2(lua, source, args=()):
    code, _ = compile_gml2(source, "test.gml")
    lua.globals().source_code = code
    lua.globals().script_args = lua.table_from(args)
    return lua.execute("return assert(loadstring(source_code))()(R, R:scope(a, nil, script_args))")


def test_named_gms2_functions_bind_arguments_and_defaults(lua):
    assert run_gms2(lua, "function add(left, right = 2) { return left + right; }", (5,)) == 7
    assert run_gms2(lua, "function add(left, right = 2) { return left + right; }", (5, 4)) == 9


def test_gms2_arrays_loop_declarations_and_enums_compile_with_shared_semantics(lua):
    source = """
        enum Mode { Idle, Ready = 4, Done }
        function choose() {
            var values = [Mode.Idle, Mode.Ready, Mode.Done];
            for (var i = 0; i < 3; i++) values[i] += 1;
            return values[0] * 100 + values[1] * 10 + values[2];
        }
    """
    records, metadata = compile_gml2_functions(source, "enum.gml")
    assert [name for name, _, _ in records] == ["choose"]
    assert metadata["enums"] == {"Mode.Idle": 0, "Mode.Ready": 4, "Mode.Done": 5}
    code = records[0][1]
    lua.globals().source_code = code
    assert lua.execute("return assert(loadstring(source_code))()(R, R:scope(a))") == 156


def test_yellow_name_resolver_keeps_scripts_as_names_not_asset_ids():
    resolver = {"spr_collision": 1_000_007, "scr_next": "scr_next"}
    code, _ = compile_gml2(
        "function call_next() { value = spr_collision; script_execute(scr_next); return value; }",
        "names.gml", resolver=resolver)
    assert "1000007" in code
    assert '"scr_next"' in code
    assert "1000000 +" not in code


def test_malformed_gms2_structure_stops_during_conversion():
    with pytest.raises(CompileError, match="has no body"):
        compile_gml2("function broken(value) value;", "broken.gml")


def test_yellow_runtime_namespace_and_builtin_adapter_do_not_rebind_undertale_names(lua):
    lua.execute("""
        local manifest={
            game="undertale-yellow", names={spr_collision=17},
            yellow_names={sprites={spr_collision=1000007, spr_yellow=1000008}},
            objects={}, rooms={},
            scripts={keyboard_multicheck_pressed={module="unused", export="keyboard_multicheck_pressed"}},
            room_order={}, asset_modules={}
        }
        local yellow=Runtime.new(manifest, Input.new(), {headless=true, seed=42})
        assert(yellow.constants.spr_collision==17)
        assert(yellow.constants.spr_yellow==1000008)
        assert(yellow.builtins.array_length_1d~=nil)
        assert(yellow.builtins.is_undefined~=nil)
        assert(yellow.builtins.keyboard_multicheck_pressed==nil)
        -- layer_create is a real layer now; a facility this port genuinely
        -- lacks (cross-room layer editing) still stops with its own name.
        local ok, error_message=pcall(function()
            yellow:call("layer_set_target_room", yellow:scope(nil))
        end)
        assert(not ok and string.find(error_message, "Compatibility stop: layer_set_target_room", 1, true))
    """)


def test_undertale_script_names_are_not_shadowed_by_yellow_aliases(lua):
    lua.execute("""
        assert(R.manifest.scripts[R.manifest.names.keyboard_multicheck_pressed]~=nil)
        assert(R.builtins.keyboard_multicheck_pressed==nil)
    """)
