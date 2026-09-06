import json
from pathlib import Path

import pytest
from lupa.lua51 import LuaRuntime as Lua51
from lupa.luajit21 import LuaRuntime

from tools.gml import CompileError, Parser, compile_gml, decode_string
from conftest import ROOT, run_gml


def test_every_unit_converted_and_manifest_counts(converted):
    r = json.loads((converted / "conversion-report.json").read_text())
    assert r["compile_errors"] == []
    assert r["code_units"] == r["converted_code_units"] == 20285
    assert r["resources"]["objects"] == 1703
    assert r["resources"]["rooms"] == 334
    assert r["resources"]["scripts"] == 173
    assert not r["missing_asset_files"]
    assert len(r["missing_paths"]) == 38
    assert r["unresolved_numeric_references"]  # not disguised as complete compatibility


@pytest.mark.parametrize("runtime", [LuaRuntime, Lua51])
def test_every_generated_chunk_compiles(converted, runtime):
    vm = runtime(unpack_returned_tuples=True)
    compile = vm.eval("function(s,n) local f,e=loadstring(s,n); return f~=nil,e end")
    paths = list(converted.rglob("*.lua")) + list((ROOT / "port").glob("*.lua")) + [ROOT / "main.lua", ROOT / "conf.lua"]
    assert len(paths) > 2200
    for path in paths:
        ok, error = compile(path.read_text(), str(path))
        assert ok, f"{path}: {error}"


@pytest.mark.parametrize("source,expected", [
    ("x=2+3*4; return x;", 14),
    ("x=0; if (0) x=1; if (!0) x+=2; return x;", 2),
    ("return (2<3)+(2>3)+(3==3);", 2),
    ("x=0; if 2 = 2 { x=4; } return x;", 4),
    ('a="hello"; a+=" // not a comment"; return a;', "hello // not a comment"),
    ('return "with (other) { if } /* still a string */";', "with (other) { if } /* still a string */"),
    ("return -7 % 3;", -1),
    ("return -7 div 3;", -2),
    ("return (5&3) | (1<<3);", 9),
    ("a=1; b=a++; c=++a; return a*100+b*10+c;", 313),
    ("if (1) exit; x=100;", 0),
    ("return 0 ? 12 : 24;", 24),
    ("return 1 ? 0 : 24;", 0),
    ("return 0 && (1/0);", 0),
    ("return 1 || (1/0);", 1),
])
def test_gml_semantics(lua, source, expected):
    assert run_gml(lua, source) == expected


def test_arrays_are_zero_based_and_indices_evaluated_once(lua):
    assert run_gml(lua, "i=0; values[0]=10; values[i++]+=2; grid[2,3]=values[0]; return i*100+grid[2,3];") == 112
    assert run_gml(lua, "global.flag[0]=5; return global.flag[1]+global.flag[0];") == 5


def test_loops_break_and_continue(lua):
    assert run_gml(lua, "i=0; total=0; while(i<10) { i++; if(i==2) continue; if(i==5) break; total+=i; } return total;") == 8
    assert run_gml(lua, "sum=0; for(i=0;i<5;i++) { if(i==2) continue; sum+=i; } return sum;") == 8
    assert run_gml(lua, "i=0; do { i++; } until i=3; repeat(2) i++; return i;") == 5


def test_switch_fallthrough_default_and_nested_break(lua):
    source = "x=0; switch(argument0) { default: x=3; case 1: x+=1; break; case 2: repeat(3) { x++; break; } x+=6; } return x;"
    for val, expected in [(9, 4), (1, 1), (2, 7)]:
        lua.execute(f"E=R:scope(a,nil,{{{val}}})")
        assert run_gml(lua, source) == expected


def test_large_switch_keeps_return_and_fallthrough(lua):
    cases = [f'case {i}: text="{"x"*300}"; break;' for i in range(800)]
    cases += ['case 1000: x=7;', 'case 1001: return x+2;', 'default: return 99;']
    source = 'switch(argument0) {' + "\n".join(cases) + '}'
    code, _ = compile_gml(source)
    assert "partitioned switch" in code
    lua.execute("E=R:scope(a,nil,{1000})")
    assert run_gml(lua, source) == 9
    lua.execute("E=R:scope(a,nil,{-20})")
    assert run_gml(lua, source) == 99


def test_with_context_and_local_scope(lua):
    # All descendants selected, `other` is the caller; locals are shared with
    # the with scope but do not become instance variables.
    result = run_gml(lua, "var localnum=5; with(18001) { x=other.x+localnum; other.result=self; localnum++; } return localnum;")
    assert result == 6
    assert lua.eval("b.v.x") == 15
    assert lua.eval("a.v.result") == lua.eval("b.id")
    assert lua.eval("a.v.localnum") is None
    run_gml(lua, "(18000).y=99;")
    assert lua.eval("a.v.y") == lua.eval("b.v.y") == 99


def test_glyph_and_dialogue_repairs_are_reported(converted):
    r = json.loads((converted / "conversion-report.json").read_text())
    assert sum("malformed backslash" in x for x in r["repairs"]) == 5
    assert sum("glyph labels" in x for x in r["repairs"]) == 11
    assert any("testlines.txt" in x for x in r["repairs"])
    assert decode_string(r'''"hello\'s \\E1"''') == "hello's \\E1"


def test_strict_parser_rejects_unknown_syntax():
    with pytest.raises(CompileError):
        Parser("x = @not_gml;").program()
    with pytest.raises(CompileError):
        Parser("if (1) { x=2;").program()
