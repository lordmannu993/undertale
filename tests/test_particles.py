"""GameMaker particle systems (part_system_* / part_type_* / part_emitter_*).

Yellow's 33 particle objects build snow, smoke, embers, glass shards and battle
effects on these builtins; Undertale's own checkout calls none of them, so the
family must also be inert there. The unit tests drive the machinery on the
Undertale manifest (no Yellow fetch needed); the live tests land the Snowdin
boat crossing and the "Snowdin - Forest" UGPS stop that used to stop with
"Unknown GML function" in rm_snowdin_11_yellow.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LIVE = (ROOT / "yellow_src").is_dir()
live = pytest.mark.skipif(not LIVE, reason="needs the pinned Yellow source: tools/fetch_yellow.py")

# Every particle builtin Yellow's pinned source calls, in callee position.
# test_every_particle_builtin_yellow_calls_is_implemented pins this list
# against yellow_src itself, so a new call site cannot slip past the suite.
PARTICLE_BUILTINS = [
    # systems
    "part_system_create", "part_system_destroy", "part_system_exists",
    "part_system_clear", "part_system_draw_order", "part_system_depth",
    "part_system_position", "part_system_automatic_update",
    "part_system_automatic_draw", "part_system_update", "part_system_drawit",
    "part_system_create_layer",
    # types (both colour spellings: Yellow uses colour2 but color1/color3)
    "part_type_create", "part_type_destroy", "part_type_exists",
    "part_type_clear", "part_type_shape", "part_type_sprite", "part_type_size",
    "part_type_scale", "part_type_speed", "part_type_direction",
    "part_type_orientation", "part_type_gravity",
    "part_type_colour1", "part_type_color1",
    "part_type_colour2", "part_type_color2",
    "part_type_colour3", "part_type_color3",
    "part_type_colour_mix", "part_type_color_mix",
    "part_type_alpha1", "part_type_alpha2", "part_type_alpha3",
    "part_type_blend", "part_type_life", "part_type_step", "part_type_death",
    # emitters
    "part_emitter_create", "part_emitter_destroy", "part_emitter_destroy_all",
    "part_emitter_exists", "part_emitter_clear", "part_emitter_region",
    "part_emitter_burst", "part_emitter_stream",
    # direct creation
    "part_particles_create", "part_particles_create_colour",
    "part_particles_create_color", "part_particles_clear",
]

SNOW = '''
    -- part_snow's own Create event, verbatim in structure (the sprite number
    -- is Yellow's own asset ID, resolved through the merged band below).
    snowSys=R.builtins.part_system_create(nil)
    snowEm=R.builtins.part_emitter_create(nil,snowSys)
    R.builtins.part_system_depth(nil,snowSys,-9999)
    snowType=R.builtins.part_type_create(nil)
    R.builtins.part_type_sprite(nil,snowType,%s,0,0,1)
    R.builtins.part_type_size(nil,snowType,1,1,0,0)
    R.builtins.part_type_colour2(nil,snowType,16777215,16777215)
    R.builtins.part_type_alpha3(nil,snowType,0.25,0.95,0)
    R.builtins.part_type_speed(nil,snowType,0.3,1.2,0,0)
    R.builtins.part_type_direction(nil,snowType,250,290,0,0)
    R.builtins.part_type_orientation(nil,snowType,0,359,0,0.1,1)
    R.builtins.part_type_life(nil,snowType,250,2000)
    R.builtins.part_type_blend(nil,snowType,1)
    R.builtins.part_emitter_region(nil,snowSys,snowEm,0,320,0,0,3,0)
    R.builtins.part_emitter_burst(nil,snowSys,snowEm,snowType,40)
    R.builtins.part_emitter_stream(nil,snowSys,snowEm,snowType,-8)
'''


def test_the_whole_particle_family_is_registered(lua):
    missing = [name for name in PARTICLE_BUILTINS if lua.eval(f'R.builtins["{name}"]') is None]
    assert not missing, f"particle builtins with no handler: {missing}"
    assert lua.eval("R.constants.pt_shape_snow") == 13
    assert lua.eval("R.constants.ps_shape_line") == 3
    assert lua.eval("R.constants.ps_distr_invgaussian") == 2


def test_snowfall_scenario_bursts_streams_and_falls(lua):
    lua.execute("R:start();tick(5)")
    lua.execute(SNOW % lua.eval("R.manifest.names.spr_maincharad"))
    assert lua.eval("#R.particles.systems[snowSys].particles") == 40
    first = lua.eval("R.particles.systems[snowSys].particles[1].y")
    lua.execute("tick(30)")
    assert lua.eval("R.particles.systems[snowSys].particles[1].y") > first
    # The -8 stream adds about one flake every 8 steps on top of the burst.
    assert lua.eval("#R.particles.systems[snowSys].particles") > 40
    # Nothing died young: the shortest life is 250 steps.
    assert lua.eval("#R.particles.systems[snowSys].particles") < 40 + 30
    drawn = lua.eval('''(function()
        for _,entry in ipairs(R.drawLog) do
            if entry[1]=="particles" and entry[4]==-9999 and entry[3]>0 then return entry[3] end
        end
        return 0
    end)()''')
    assert drawn > 0, "snow never reached the draw log at depth -9999"
    # Undertale itself is untouched by the machinery: the opening still runs.
    assert lua.eval("R.roomState.name") == "room_introstory"


def test_emitter_regions_sample_their_own_shape(lua):
    lua.execute("R:start()")
    result = lua.eval('''
        (function()
            local B=R.builtins
            local sys=B.part_system_create(nil)
            local tp=B.part_type_create(nil)
            B.part_type_life(nil,tp,100000,100000)
            local function burst(shape,distr)
                local em=B.part_emitter_create(nil,sys)
                B.part_emitter_region(nil,sys,em,100,200,50,150,shape,distr)
                B.part_emitter_burst(nil,sys,em,tp,120)
            end
            burst(0,0); burst(1,0); burst(2,0); burst(3,0); burst(0,1); burst(0,2)
            local line,bad=0,0
            for _,p in ipairs(R.particles.systems[sys].particles) do
                if p.x<100 or p.x>200 or p.y<50 or p.y>150 then bad=bad+1 end
            end
            -- The line emitter spans (100,50)-(200,150): every one of its
            -- particles sits on the diagonal, which the box test above cannot see.
            local em=B.part_emitter_create(nil,sys)
            B.part_emitter_region(nil,sys,em,100,200,50,150,3,0)
            B.part_emitter_burst(nil,sys,em,tp,60)
            for _,p in ipairs(R.particles.systems[sys].particles) do
                if math.abs((p.y-50)-(p.x-100))<1e-6 then line=line+1 end
            end
            -- Ellipse and diamond emitters stay inside their own curve.
            local function inside(shape)
                local em2=B.part_emitter_create(nil,sys)
                B.part_emitter_clear(nil,sys,em2)
                B.part_emitter_region(nil,sys,em2,100,200,50,150,shape,0)
                for _=1,60 do
                    B.part_emitter_burst(nil,sys,em2,tp,1)
                    local q=R.particles.systems[sys].particles[#R.particles.systems[sys].particles]
                    local dx,dy=(q.x-150)/50,(q.y-100)/50
                    if shape==1 and dx*dx+dy*dy>1+1e-6 then return false end
                    if shape==2 and math.abs(dx)+math.abs(dy)>1+1e-6 then return false end
                end
                return true
            end
            if not inside(1) then return "ellipse leaked" end
            if not inside(2) then return "diamond leaked" end
            if bad>0 then return bad.." particles outside their region" end
            if line<60 then return "only "..line.." of 60 line particles on the segment" end
            return "ok"
        end)()
    ''')
    assert result == "ok", result


def test_streams_count_chance_and_off(lua):
    lua.execute("R:start()")
    result = lua.eval('''
        (function()
            local B=R.builtins
            local Vigorous=B.part_system_create(nil)
            local tp=B.part_type_create(nil)
            B.part_type_life(nil,tp,100000,100000)
            local function stream(number)
                local em=B.part_emitter_create(nil,Vigorous)
                B.part_emitter_region(nil,Vigorous,em,0,1,0,1,0,0)
                B.part_emitter_stream(nil,Vigorous,em,tp,number)
                return em
            end
            local steady,chance,off=stream(3),stream(-1),stream(0)
            R:updateParticles()
            -- 3 from the counter, exactly 1 from the 1-in-1 chance, none off.
            if #R.particles.systems[Vigorous].particles~=4 then
                return "expected 4 streamed particles, have "..#R.particles.systems[Vigorous].particles
            end
            B.part_emitter_clear(nil,Vigorous,steady)
            R:updateParticles()
            if #R.particles.systems[Vigorous].particles~=5 then
                return "clearing the stream did not stop it"
            end
            return "ok"
        end)()
    ''')
    assert result == "ok", result


def test_colour_and_alpha_interpolate_over_life(lua):
    lua.execute("R:start()")
    result = lua.eval('''
        (function()
            local B=R.builtins
            local sys=B.part_system_create(nil)
            local tp=B.part_type_create(nil)
            B.part_type_life(nil,tp,100,100)
            B.part_type_color3(nil,tp,255,65280,16711680)
            B.part_type_alpha3(nil,tp,0,1,0)
            B.part_particles_create(nil,sys,0,0,tp,1)
            local p=R.particles.systems[sys].particles[1]
            p.age=0
            local _,_,c0,a0=R:particleAppearance(R.particles.systems[sys],p)
            p.age=50
            local _,_,c1,a1=R:particleAppearance(R.particles.systems[sys],p)
            p.age=100
            local _,_,c2,a2=R:particleAppearance(R.particles.systems[sys],p)
            if c0~=255 then return "birth colour "..c0 end
            if c1~=65280 then return "mid colour "..c1 end
            if c2~=16711680 then return "death colour "..c2 end
            if math.abs(a0-0)>1e-6 or math.abs(a1-1)>1e-6 or math.abs(a2-0)>1e-6 then
                return "alpha "..a0.."/"..a1.."/"..a2
            end
            local mix=B.part_type_create(nil)
            B.part_type_colour_mix(nil,mix,0,16777215)
            B.part_particles_create(nil,sys,0,0,mix,2)
            local q1=R.particles.systems[sys].particles[2]
            local q2=R.particles.systems[sys].particles[3]
            if q1.mix==q2.mix then return "colour_mix dealt the same factor twice" end
            return "ok"
        end)()
    ''')
    assert result == "ok", result


def test_death_and_step_chains_spawn(lua):
    lua.execute("R:start()")
    result = lua.eval('''
        (function()
            local B=R.builtins
            -- obj_part_leak_complex: a droplet dies into 4 bursts.
            local sys=B.part_system_create(nil)
            local drop=B.part_type_create(nil)
            B.part_type_life(nil,drop,2,2)
            local burst=B.part_type_create(nil)
            B.part_type_life(nil,burst,100,100)
            B.part_type_death(nil,drop,4,burst)
            B.part_particles_create(nil,sys,10,10,drop,1)
            R:updateParticles()
            R:updateParticles()
            local list=R.particles.systems[sys].particles
            if #list~=4 then return "death spawned "..#list..", expected 4" end
            for _,p in ipairs(list) do
                if p.type~=burst or p.x~=10 or p.y~=10 then return "death spawn misplaced" end
            end
            local parent=B.part_type_create(nil)
            B.part_type_life(nil,parent,4,4)
            B.part_type_step(nil,parent,1,burst)
            B.part_particles_create(nil,sys,0,0,parent,1)
            R:updateParticles()
            R:updateParticles()
            return "ok"
        end)()
    ''')
    assert result == "ok", result


def test_destroy_is_lenient_and_create_is_truthy(lua):
    lua.execute("R:start()")
    result = lua.eval('''
        (function()
            local B=R.builtins
            local sys=B.part_system_create(nil)
            if sys<1 then return "system id "..sys.." is falsy in GML" end
            local tp=B.part_type_create(nil)
            if tp<1 then return "type id "..tp.." is falsy in GML" end
            if not R.truth(B.part_system_exists(nil,sys)) then return "exists() missed" end
            -- Yellow destroys shared systems from both Destroy and Room End.
            B.part_system_destroy(nil,sys)
            B.part_system_destroy(nil,sys)
            B.part_system_clear(nil,sys)
            B.part_particles_clear(nil,sys)
            if R.truth(B.part_system_exists(nil,sys)) then return "destroyed system exists" end
            -- Bursts into a gone system are ignored, visibly, like GameMaker.
            B.part_emitter_burst(nil,sys,1,tp,10)
            B.part_particles_create(nil,sys,0,0,tp,1)
            if B.part_emitter_create(nil,sys)~=-1 then return "emitter of a gone system" end
            if not R.warnings["particles-missing:part_emitter_burst"] then
                return "missing-handle burst never warned"
            end
            return "ok"
        end)()
    ''')
    assert result == "ok", result


def test_system_position_offsets_drawing_not_physics(lua):
    lua.execute("R:start()")
    result = lua.eval('''
        (function()
            local B=R.builtins
            local sys=B.part_system_create(nil)
            local tp=B.part_type_create(nil)
            B.part_type_life(nil,tp,100,100)
            B.part_type_speed(nil,tp,2,2,0,0)
            B.part_type_direction(nil,tp,0,0,0,0)
            B.part_particles_create(nil,sys,10,10,tp,1)
            B.part_system_position(nil,sys,100,50)
            local p=R.particles.systems[sys].particles[1]
            local x,y=R:particleAppearance(R.particles.systems[sys],p)
            if x~=110 or y~=60 then return "drawn at "..x..","..y end
            R:updateParticles()
            if p.x~=12 or p.y~=10 then return "physics ran in offset space" end
            local x2=R:particleAppearance(R.particles.systems[sys],p)
            if x2~=112 then return "offset lost after the step" end
            return "ok"
        end)()
    ''')
    assert result == "ok", result


def test_undertale_ids_stay_exact_outside_yellow(lua):
    # 636 is Yellow's spr_snowflake; in Undertale's world it must not band.
    lua.execute("R:start()")
    lua.execute(SNOW % 636)
    assert lua.eval("R.particles.types[snowType].sprite") == 636
    assert lua.eval('R.warnings["particle-sprite:636"]') is None


def test_layer_systems_follow_and_die_with_their_layer(lua):
    lua.execute("R:start()")
    result = lua.eval('''
        (function()
            local B=R.builtins
            R.roomState.layers={{name="fx",depth=5,visible=true,x=0,y=0,hspeed=0,vspeed=0}}
            R.roomState.tiles=R.roomState.tiles or {}
            local sys=B.part_system_create_layer(nil,"fx",0)
            if R:particleDepth(R.particles.systems[sys])~=5 then return "depth not from layer" end
            R.roomState.layers[1].depth=9
            if R:particleDepth(R.particles.systems[sys])~=9 then return "depth not following" end
            B.layer_set_visible(nil,"fx",0)
            if R:particleLayerVisible(R.particles.systems[sys]) then return "hidden layer draws" end
            B.layer_set_visible(nil,"fx",1)
            local kept=B.part_system_create_layer(nil,"fx",1)
            B.layer_destroy(nil,"fx")
            if B.part_system_exists(nil,sys)==1 then return "layer kept its system" end
            if B.part_system_exists(nil,kept)==1 then return "persistent system survived its layer" end
            return "ok"
        end)()
    ''')
    assert result == "ok", result


def test_nonpersistent_layer_systems_die_on_room_change(lua):
    lua.execute("R:start();tick(5)")
    result = lua.eval('''
        (function()
            local B=R.builtins
            R.roomState.layers={{name="fx",depth=5,visible=true,x=0,y=0,hspeed=0,vspeed=0}}
            local temp=B.part_system_create_layer(nil,"fx",0)
            local kept=B.part_system_create_layer(nil,"fx",1)
            local classic=B.part_system_create(nil)
            R:clearRoomParticleSystems()
            if B.part_system_exists(nil,temp)==1 then return "room kept a temp system" end
            if B.part_system_exists(nil,kept)==0 then return "room dropped a persistent system" end
            if B.part_system_exists(nil,classic)==0 then return "room dropped a classic system" end
            if R.particles.systems[kept].layer~=nil then return "persistent system stayed bound" end
            return "ok"
        end)()
    ''')
    assert result == "ok", result


# --- Static pins against the pinned Yellow source (no conversion needed). ---

CALL = re.compile(
    r"\b(part_system_[a-z_0-9]*|part_type_[a-z_0-9]*|part_emitter_[a-z_0-9]*"
    r"|part_particles_[a-z_0-9]*)\s*\("
)
CREATE = re.compile(r"\bpart_system_create\s*\(")


def yellow_gml():
    for path in (ROOT / "yellow_src").rglob("*.gml"):
        yield path, path.read_text(encoding="utf-8-sig", errors="replace")


@live
def test_every_particle_builtin_yellow_calls_is_implemented():
    called = set()
    for _, text in yellow_gml():
        called.update(CALL.findall(text))
    # part_type_energy/flash/ring are variable names in part_axis_ball_destroy,
    # never callee positions; the call regex must not have caught them.
    assert not (called & {"part_type_energy", "part_type_flash", "part_type_ring"})
    implemented = set(re.findall(r'reg\("(part_[a-z_0-9]*)"', (ROOT / "port/particles.lua").read_text()))
    assert called <= implemented, f"Yellow calls unimplemented particle builtins: {called - implemented}"
    assert called <= set(PARTICLE_BUILTINS), f"test list is stale: {called - set(PARTICLE_BUILTINS)}"


@live
def test_thirty_three_objects_create_particle_systems():
    owners = set()
    for path, text in yellow_gml():
        if CREATE.search(text):
            owners.add(path.parent.name)
    assert len(owners) == 33, f"{len(owners)} objects create systems: {sorted(owners)}"


# --- Live merged-build gates (need the full Yellow conversion). ---

def _boot_merged():
    machine = LuaRuntime(unpack_returned_tuples=True)
    machine.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    machine.execute('''
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
        function countInstances(object)
            local total=0
            for _,inst in ipairs(R.instances) do
                if inst.alive and inst.v.object_index==object then total=total+1 end
            end
            return total
        end
        function crossTo(room)
            R:gotoRoom(room); R:applyTransitions(); tick(1)
        end
    ''')
    return machine


@pytest.fixture(scope="module")
def merged_vm(converted):
    if not LIVE:
        pytest.skip("needs the pinned Yellow source: tools/fetch_yellow.py")
    import json as _json
    report = ROOT / "generated/yellow/conversion-report.json"
    stage = _json.loads(report.read_text())["stage"] if report.is_file() else None
    if stage != "rooms":
        subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "rooms"], cwd=ROOT, check=True)
    run = subprocess.run([sys.executable, "tools/merge.py"], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    import os
    os.chdir(ROOT)
    return _boot_merged()


@live
def test_snowdin_forest_stop_travels_and_snows(merged_vm):
    assert merged_vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    result = merged_vm.execute('''
        local forest=R.manifest.yellow_names.rooms["rm_snowdin_11_yellow"]
        local ok,err=pcall(function() crossTo(forest) end)
        if not ok then return "Snowdin - Forest still stops: "..tostring(err) end
        if R.roomState.name~="rm_snowdin_11_yellow" then
            return "landed in "..tostring(R.roomState.name)
        end
        local snow=R.manifest.yellow_names.objects["part_snow"]
        if countInstances(snow)<1 then return "part_snow never placed" end
        if not R.warnings["particle-sprite:636"] then
            return "snow sprite 636 never resolved through the merged band"
        end
        tick(30)
        local flakes=0
        for _,sys in pairs(R.particles.systems) do flakes=flakes+#sys.particles end
        if flakes<10 then return "only "..flakes.." snow particles alive" end
        for _,entry in ipairs(R.drawLog) do
            if entry[1]=="particles" and entry[4]==-9999 and entry[3]>0 then return "ok" end
        end
        return "snow never drew at depth -9999"
    ''')
    assert result == "ok", result


@live
def test_snowdin_boat_crossing_lands_in_the_forest(merged_vm):
    assert merged_vm.execute("local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)") == "ok"
    result = merged_vm.execute('''
        R.global.plot=10
        local boat=R.manifest.names["obj_dogboat_thing"]
        crossTo(70)
        if countInstances(boat)~=1 then return "no boat at the Snowdin dock" end
        hold(88,2)  -- X through the ride aims the same choice at Yellow
        if not R.travel.riverLatch then return "X during the ride did not latch" end
        local forest=R.manifest.yellow_names.rooms["rm_snowdin_11_yellow"]
        local ok,err=pcall(function() crossTo(70) end)
        if not ok then return "Snowdin crossing still stops: "..tostring(err) end
        if R.vars.room~=forest then return "landed in "..tostring(R.vars.room) end
        if R.travel.world~="yellow" then return "world is "..tostring(R.travel.world) end
        local clover=R.travel.ids.yellow.player
        if countInstances(clover)~=1 then return "expected one Yellow player" end
        local pl=nil
        for _,inst in ipairs(R.instances) do
            if inst.alive and inst.v.object_index==clover then pl=inst end
        end
        if pl.v.x~=200 or pl.v.y~=100 then
            return "landed at "..pl.v.x..","..pl.v.y.." instead of Yellow's own 200,100"
        end
        return "ok"
    ''')
    assert result == "ok", result
