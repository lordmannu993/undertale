from pathlib import Path
import subprocess
import sys

import pytest
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def converted():
    subprocess.run([sys.executable, str(ROOT / "tools/convert.py")], cwd=ROOT, check=True)
    return ROOT / "generated"


@pytest.fixture
def lua(converted, monkeypatch):
    monkeypatch.chdir(ROOT)
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    vm.execute('''
        Input=require("port.input")
        Runtime=require("port.runtime")
        input=Input.new()
        R=Runtime.new(require("generated.manifest"), input, {headless=true, trace=true, seed=42})
        function tick(n)
            for i=1,n do
                input:beginFrame(); R:step(); R:renderFrame(); R:finishFrame(); input:endFrame()
            end
        end
        function press(k)
            input:setSource("test",{k}); tick(1)
            input:setSource("test",{}); tick(1)
        end
        function hold(k,n)
            input:setSource("test",{k}); tick(n)
            input:setSource("test",{}); tick(1)
        end
        function dummy(id,parent)
            R.manifest.objects[id]="tests.dummy"
            R.objects[id]={name="dummy",sprite=-1,mask=-1,visible=1,solid=0,depth=0,persistent=0,parent=parent or -1,events={}}
        end
        dummy(18000);dummy(18001,18000)
        a=R:create(18000,10,20)
        b=R:create(18001,30,40)
        E=R:scope(a)
    ''')
    return vm


def run_gml(vm, source):
    from tools.gml import compile_gml
    code, _ = compile_gml(source, "test")
    vm.globals().source_code = code
    return vm.execute("return assert(loadstring(source_code))()(R,E)")
