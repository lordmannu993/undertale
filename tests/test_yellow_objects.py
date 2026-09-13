"""Piece 3: every Yellow object, with parents, masks, collision targets and events.

The offline half drives a miniature source tree whose objects deliberately cover
the awkward cases: a parent chain, a mask, a collision pair, two objects that
each declare a local function *with the same name*, a physics fixture, an
invisible object and the two events nothing dispatches. The live half runs the
real 3 224-object fetch and is skipped — never silently passed — when
``yellow_src/`` is absent.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from lupa.lua51 import LuaRuntime as Lua51
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import yellow_support as support  # noqa: E402
from yellow.objects import DELIVERED, ObjectConverter, delivered, delivered_reason  # noqa: E402
from yellow.registry import YELLOW_BASE, Registry  # noqa: E402
from yellow_convert import Writer, stage_objects  # noqa: E402

SOURCE = ROOT / "yellow_src"
LIVE = (SOURCE / "Undertale_Yellow.yyp").is_file() and (SOURCE / "notes/Asset_Order/Asset_Order.txt").is_file()
# CI sets PORT_REQUIRE_YELLOW=1 after fetching, so a broken fetch fails these tests
# instead of quietly skipping the only proof that the real source converts.
REQUIRED = os.environ.get("PORT_REQUIRE_YELLOW") == "1"
live = pytest.mark.skipif(not LIVE and not REQUIRED,
                          reason="yellow_src/ is not fetched; run tools/fetch_yellow.py")

PREFIX = "generated.yellow_objects_test"
OUTPUT = ROOT / "generated" / "yellow_objects_test"


@pytest.fixture()
def fixture(tmp_path):
    """A miniature Yellow project converted through piece 3."""
    source, provenance = support.build_source(tmp_path)
    registry = Registry(source, provenance)
    report = stage_objects(registry, provenance, Writer(OUTPUT), tmp_path, ROOT, prefix=PREFIX)
    return SimpleNamespace(source=source, provenance=provenance, registry=registry,
                           output=OUTPUT, report=report, prefix=PREFIX)


@pytest.fixture()
def yellow(fixture, monkeypatch):
    """A headless runtime running on the converted fixture objects."""
    monkeypatch.chdir(ROOT)
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    vm.execute(f'''
        Input=require("port.input")
        Runtime=require("port.runtime")
        input=Input.new()
        R=Runtime.new(require("{fixture.prefix}.manifest"), input, {{headless=true, trace=true, seed=42}})
        function tick(n)
            for i=1,n do
                input:beginFrame(); R:step(); R:renderFrame(); R:finishFrame(); input:endFrame()
            end
        end
    ''')
    return vm


def merged(fixture, category: str, name: str) -> int:
    return fixture.registry.merged(category, name)


# -- the converted records -------------------------------------------------
def test_every_object_converts_with_recovered_ids_and_no_depth_of_its_own(fixture):
    objects = fixture.report["objects"]
    assert objects["converted"] == objects["expected"] == len(support.OBJECTS)
    assert objects["events"] == sum(len(spec.get("events", [])) for spec in support.OBJECTS.values())
    assert objects["compile_errors"] == []
    converter = ObjectConverter(fixture.registry, fixture.source, fixture.provenance, fixture.prefix)
    for name, spec in support.OBJECTS.items():
        meta, events = converter.convert(name)
        assert meta["id"] == merged(fixture, "objects", name)
        assert meta["yellow"]["id"] == meta["id"] - YELLOW_BASE
        # Studio 2 has no per-object depth; piece 4 takes it from the room layer.
        assert meta["depth"] == 0 and meta["yellow"]["depth_source"] == "room layer (piece 4)"
        assert (OUTPUT / "objects" / f"{name}.lua").is_file()
        expected = {f"4:{merged(fixture, 'objects', entry['target'])}" if entry["kind"] == 4
                    else f"{entry['kind']}:{entry['number']}" for entry in spec.get("events", [])}
        assert set(events) == expected, name
    manifest = (fixture.output / "manifest.lua").read_text()
    for name in support.OBJECTS:
        assert f'[{merged(fixture, "objects", name)}]="{fixture.prefix}.objects.{name}"' in manifest, name


def test_sprites_masks_and_parents_are_the_pinned_ids_never_invented_ones(fixture):
    converter = ObjectConverter(fixture.registry, fixture.source, fixture.provenance, fixture.prefix)
    player, _ = converter.convert("obj_pl")
    assert player["sprite"] == merged(fixture, "sprites", "spr_pl_down")
    assert player["mask"] == merged(fixture, "sprites", "spr_a")
    assert player["parent"] == -1 and player["persistent"] == 1
    child, _ = converter.convert("obj_child")
    assert child["parent"] == merged(fixture, "objects", "obj_parent")
    parent, _ = converter.convert("obj_parent")
    assert parent["solid"] == 1 and parent["sprite"] == -1 and parent["mask"] == -1
    invisible, _ = converter.convert("obj_invisible")
    assert invisible["visible"] == 0


def test_collision_events_are_keyed_by_the_targets_merged_id(fixture):
    text = (fixture.output / "objects" / "obj_child.lua").read_text()
    target = merged(fixture, "objects", "obj_target")
    assert f'object.events["4:{target}"]' in text
    assert '"4:0"' not in text, "a collision event must never keep the raw subtype 0"
    assert fixture.report["objects"]["collision_events"] == 1
    assert text.count("object.events[") == len(support.OBJECTS["obj_child"]["events"])


def test_keyboard_and_mouse_subtypes_reach_the_manifest(fixture):
    manifest = (fixture.output / "manifest.lua").read_text()
    assert '["keys"]={27}' in manifest
    assert '["mouse_events"]={4}' in manifest
    assert fixture.report["objects"]["keyboard_keys"] == [27]
    assert fixture.report["objects"]["mouse_subtypes"] == [4]


def test_physics_objects_keep_their_box2d_record(fixture):
    converter = ObjectConverter(fixture.registry, fixture.source, fixture.provenance, fixture.prefix)
    meta, _ = converter.convert("obj_physics")
    assert meta["physics"] == 1
    assert meta["yellow"]["physics"]["shape"] == 1
    assert meta["yellow"]["physics"]["shape_points"] == [[-8.0, -8.0], [8.0, -8.0], [8.0, 8.0], [-8.0, 8.0]]
    assert fixture.report["objects"]["physics_objects"] == ["obj_physics"]


def test_events_nothing_dispatches_are_converted_and_named_not_dropped(fixture):
    text = (fixture.output / "objects" / "obj_broadcast.lua").read_text()
    assert 'object.events["7:76"]' in text and 'object.events["7:62"]' in text
    inert = fixture.report["objects"]["undispatched_events"]
    assert sorted(inert) == ["Other/Async - HTTP (7:62)", "Other/Broadcast Message (7:76)"]
    for entry in inert.values():
        assert entry["objects"] == 1 and entry["reason"]
    assert not delivered(7, 76) and not delivered(7, 62) and not delivered(6, 3)
    assert delivered(7, 10) and delivered(8, 64) and delivered(12, 0) and delivered(5, 27)
    assert delivered_reason(3, 0) is None
    assert "sprite frame events" in delivered_reason(7, 76)


# -- what the runtime does with them ---------------------------------------
def test_local_functions_stay_inside_their_own_event(yellow, fixture):
    result = yellow.execute(f'''
        local player=R:create({merged(fixture, "objects", "obj_pl")},10,10)
        local child=R:create({merged(fixture, "objects", "obj_child")},20,20)
        local target=R:create({merged(fixture, "objects", "obj_target")},30,30)
        return player.v.value .. "/" .. child.v.value .. "/" .. target.v.doubled
    ''')
    # obj_pl and obj_child each declare a function called `helper`; each keeps
    # its own. obj_target's Create calls the converted Yellow script scr_a.
    assert result == "3/7/42", result


def test_inherited_destroy_then_clean_up_runs_once_each(yellow, fixture):
    fired = yellow.execute(f'''
        local child=R:create({merged(fixture, "objects", "obj_child")},20,20)
        local order={{}}
        local parent=R:object({merged(fixture, "objects", "obj_parent")})
        local destroy,cleanup=parent.events["1:0"],parent.events["12:0"]
        parent.events["1:0"]=function(R,E) order[#order+1]="destroy" return destroy(R,E) end
        parent.events["12:0"]=function(R,E) order[#order+1]="cleanup" return cleanup(R,E) end
        R:destroy(child)
        return table.concat(order,",") .. "|" .. tostring(child.v.destroyed) .. "/" .. tostring(child.v.cleaned)
    ''')
    assert fired == "destroy,cleanup|1/1", fired


def test_a_physics_object_stops_with_its_own_name(yellow, fixture):
    message = yellow.execute(f'''
        local ok, error_message = pcall(function()
            return R:create({merged(fixture, "objects", "obj_physics")},0,0)
        end)
        return tostring(ok) .. "|" .. tostring(error_message)
    ''')
    ok, detail = message.split("|", 1)
    assert ok == "false"
    assert "obj_physics" in detail and "physics" in detail


def test_the_runtime_delivers_every_event_subtype_piece_3_claims(yellow):
    """The DELIVERED table in tools/yellow/objects.py, proved against the runtime."""
    keys = sorted({f"{kind}:{number}" for kind, allowed in DELIVERED.items() if allowed for number in allowed}
                  | {"5:27", "9:27"})
    listing = ",".join(f'"{key}"' for key in keys)
    fired = yellow.execute(f'''
        local fired={{}}
        local function mark(key) return function(R,E) fired[key]=(fired[key] or 0)+1 end end
        local keys={{ {listing} }}
        local function probe(name,persistent)
            local events={{}}
            for _,key in ipairs(keys) do events[key]=mark(key) end
            return {{name=name,sprite=999001,mask=-1,visible=1,solid=0,depth=0,parent=-1,
                    persistent=persistent and 1 or 0,events=events}}
        end
        R.assets.sprites[999001]={{name="probe",width=8,height=8,xorig=0,yorigin=0,colkind=1,coltolerance=0,
            sepmasks=0,bboxmode=0,bbox_left=0,bbox_right=7,bbox_top=0,bbox_bottom=7,
            frames={{"__probe_0.png","__probe_1.png"}}}}
        R.objects[19000]=probe("probe_kept",true)
        R.objects[19001]=probe("probe_dropped",false)
        R.manifest.objects[19000]="probe";R.manifest.objects[19001]="probe"
        R.manifest.mouse_events={{0,1,2,4,5,6,7,8,9}}
        R.manifest.keys[#R.manifest.keys+1]=27
        local room={{name="probe_room",width=320,height=240,speed=30,persistent=0,colour=0,showcolour=1,
                     enableViews=0,views={{}},backgrounds={{}},tiles={{}},
                     instances={{{{id=500001,object=19000,x=50,y=50}}}}}}
        R.rooms[1]=room;R.rooms[2]=room
        R.manifest.rooms[1]="probe";R.manifest.rooms[2]="probe"
        R.manifest.room_order={{1}}
        R:start()                                   -- Game Start and Room Start
        local kept=R.byId[500001]
        local dropped=R:create(19001,60,60)
        tick(1)                                     -- the step family and every draw pass
        for alarm=0,11 do kept.v.alarm[alarm]=1 end
        tick(1)                                     -- all twelve alarms
        for user=0,15 do R.builtins.event_user(R:scope(kept),user) end
        R.vars.mouse_x=52;R.vars.mouse_y=52
        for button=1,3 do                           -- per-instance and global mouse events
            input:mouseButton("test",button,true);tick(1)
            input:mouseButton("test",button,false);tick(1)
        end
        input:setSource("test",{{27}});tick(1)          -- escape held, pressed, then released
        input:setSource("test",{{}});tick(1)
        kept.v.x=R.vars.room_width+100;tick(1)      -- Outside Room and Intersect Boundary
        kept.v.x=50
        R:gotoRoom(2);R:applyTransitions()          -- Room End, Clean Up, Room Start
        R:destroy(kept)                             -- Destroy, then Clean Up
        local out={{}}
        for key,count in pairs(fired) do out[#out+1]=key .. "=" .. count end
        table.sort(out)
        return table.concat(out,",")
    ''')
    counts = dict(entry.split("=") for entry in fired.split(","))
    missing = [key for key in keys if key not in counts]
    assert not missing, f"the runtime never delivered {missing}; it delivered {fired}"
    # Order-sensitive facts, not just presence.
    assert int(counts["8:72"]) >= int(counts["8:0"]), "Draw Begin runs for every Draw pass"
    assert int(counts["12:0"]) >= 2, "Clean Up ran for the dropped instance and the destroyed one"


def test_an_invisible_instance_does_not_run_its_draw_event(yellow, fixture):
    """GameMaker skips every Draw event for an invisible instance, so must this."""
    fired = yellow.execute(f'''
        local room={{name="probe_room",width=320,height=240,speed=30,persistent=0,colour=0,showcolour=1,
                     enableViews=0,views={{}},backgrounds={{}},instances={{}},tiles={{}}}}
        R.rooms[1]=room;R.manifest.rooms[1]="probe";R.manifest.room_order={{1}}
        R:start()
        local invisible=R:create({merged(fixture, "objects", "obj_invisible")},10,10)
        local visible=R:create({merged(fixture, "objects", "obj_child")},20,20)
        tick(1)
        return tostring(invisible.v.invisible_draw_ran) .. "|" .. tostring(visible.v.draw_ran)
    ''')
    assert fired == "nil|1", fired


def test_a_room_change_cleans_up_the_instances_it_drops(yellow, fixture):
    fired = yellow.execute(f'''
        local room={{name="probe_room",width=320,height=240,speed=30,persistent=0,colour=0,showcolour=1,
                     enableViews=0,views={{}},backgrounds={{}},instances={{}},tiles={{}}}}
        R.rooms[1]=room;R.rooms[2]=room
        R.manifest.rooms[1]="probe";R.manifest.rooms[2]="probe"
        R.manifest.room_order={{1}}
        R:start()
        local child=R:create({merged(fixture, "objects", "obj_child")},10,10)
        local player=R:create({merged(fixture, "objects", "obj_pl")},20,20)
        R:gotoRoom(2);R:applyTransitions()
        return tostring(child.alive) .. "|" .. tostring(child.v.cleaned) .. "|"
             .. tostring(player.alive) .. "|" .. tostring(player.v.cleaned)
    ''')
    # The child is dropped and cleaned up; obj_pl is persistent and survives.
    assert fired == "false|1|true|nil", fired


# -- the real source -------------------------------------------------------
@pytest.fixture(scope="module")
def real():
    run = subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "objects"],
                         cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    report = json.loads((ROOT / "generated/yellow/conversion-report.json").read_text())
    provenance = json.loads((ROOT / "port/yellow_source.json").read_text())
    return run, report, Registry(SOURCE, provenance), provenance


@live
def test_every_yellow_object_and_event_converts(real):
    run, report, _, _ = real
    assert "Converted Yellow objects: 3224 objects, 8494 events" in run.stdout, run.stdout
    objects = report["objects"]
    assert report["stage"] == "objects"
    assert objects["converted"] == objects["expected"] == 3224
    assert objects["events"] == 8494 and objects["compile_errors"] == []
    assert (objects["with_parent"], objects["with_sprite"], objects["with_mask"]) == (1174, 2088, 62)
    assert objects["collision_events"] == 53
    assert objects["keyboard_keys"] == [27] and objects["mouse_subtypes"] == [0, 4]
    assert sorted(objects["undispatched_events"]) == ["Other/Async - HTTP (7:62)",
                                                      "Other/Broadcast Message (7:76)"]
    assert objects["undispatched_events"]["Other/Broadcast Message (7:76)"]["objects"] == 48
    assert len(list((ROOT / "generated/yellow/objects").glob("*.lua"))) == 3224


@live
def test_the_ten_physics_objects_are_the_puzzles_they_look_like(real):
    _, report, registry, provenance = real
    assert report["objects"]["physics_objects"] == [
        "obj_cutscene_hotland_03b", "obj_factory_02_seesaw_collider", "obj_factory_02_seesaw_item",
        "obj_factory_02_seesaw_wall", "obj_hotland_03_elevator", "obj_molten_rock_snowdin_19",
        "obj_puzzle_collider_snowdin_19", "obj_seesaw", "obj_snowdin_19_destroy_trigger",
        "obj_snowdin_19_piston"]
    converter = ObjectConverter(registry, SOURCE, provenance, "generated.yellow")
    for name in report["objects"]["physics_objects"]:
        meta, _ = converter.convert(name)
        assert meta["physics"] == 1 and meta["yellow"]["physics"], name


@live
def test_every_local_function_is_bound_inside_its_own_event(real):
    _, report, _, _ = real
    found = report["objects"]["local_functions"]
    # Sixteen declarations in fourteen events, two of them sharing a name.
    assert sum(len(names) for events in found.values() for names in events.values()) == 16
    assert found["obj_toy_gun_circle"] == {"3:0": ["shotFail"]}
    assert found["obj_ceroba_follower"] == {"7:10": ["multiple_lines", "update_talk_val"]}
    names = sorted(name for events in found.values() for functions in events.values() for name in functions)
    assert names.count("state_switch") == 2, "two objects declare their own state_switch"
    for name, events in found.items():
        text = (ROOT / "generated/yellow/objects" / f"{name}.lua").read_text()
        for key, functions in events.items():
            for function in functions:
                assert f'E._locals["{function}"] = function(R, E)' in text, f"{name} {key}: {function}"


@pytest.mark.parametrize("runtime", [LuaRuntime, Lua51])
@live
def test_every_generated_object_module_compiles(runtime, real):
    """Both Lua dialects the port ships with must accept all 3 224 modules."""
    _, _, _, _ = real
    vm = runtime(unpack_returned_tuples=True)
    compile = vm.eval("function(s,n) local f,e=loadstring(s,n); return f~=nil,e end")
    paths = sorted((ROOT / "generated/yellow/objects").glob("*.lua"))
    assert len(paths) == 3224
    for path in paths:
        ok, error = compile(path.read_text(), str(path))
        assert ok, f"{path}: {error}"


@live
def test_every_generated_object_loads_with_recovered_ids(real):
    _, _, _, _ = real
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    summary = vm.execute('''
        local Input=require("port.input"); local Runtime=require("port.runtime")
        local R=Runtime.new(require("generated.yellow.manifest"), Input.new(), {headless=true, seed=42})
        local objects, events, parents, masks = 0, 0, 0, 0
        for id in pairs(R.manifest.objects) do
            local object = R:object(id)
            assert(object and object.name and object.events, id)
            assert(object.depth == 0, object.name)
            assert(object.id == id, object.name)
            objects = objects + 1
            if object.parent >= 0 then
                parents = parents + 1
                assert(R.manifest.objects[object.parent], object.name .. " has an unknown parent")
            end
            if object.mask >= 0 then
                masks = masks + 1
                assert(R.assets.sprites[object.mask], object.name .. " has an unknown mask")
            end
            if object.sprite >= 0 then assert(R.assets.sprites[object.sprite], object.name) end
            for key, fn in pairs(object.events) do
                assert(type(fn) == "function", object.name .. " " .. key)
                events = events + 1
                if key:sub(1,2) == "4:" then
                    local target = tonumber(key:sub(3))
                    assert(target and target >= 1000000 and R.manifest.objects[target],
                           object.name .. " collides with an unrecovered object ID " .. tostring(target))
                end
            end
        end
        return objects .. " " .. events .. " " .. parents .. " " .. masks
    ''')
    assert summary == "3224 8494 1174 62", summary


@live
def test_a_converted_object_runs_its_own_and_its_parents_create_event(real):
    _, _, registry, _ = real
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    npc = registry.merged("objects", "obj_alphys_npc")
    base = registry.merged("objects", "obj_actor_npc_base")
    result = vm.execute(f'''
        Input=require("port.input"); Runtime=require("port.runtime")
        local R=Runtime.new(require("generated.yellow.manifest"), Input.new(), {{headless=true, seed=42}})
        local inst=R:create({npc},100,100)
        local object=R:object({npc})
        return object.name .. "|" .. tostring(object.parent == {base}) .. "|" .. object.solid .. "|"
             .. tostring(R.assets.sprites[inst.v.up_sprite] and R.assets.sprites[inst.v.up_sprite].name) .. "|"
             .. tostring(inst.v.npc_direction) .. "|" .. tostring(inst.v.actor_speed)
    ''')
    # obj_alphys_npc's Create starts with event_inherited(), so `npc_direction`
    # can only come from obj_actor_npc_base's own Create event.
    assert result == "obj_alphys_npc|true|1|spr_geno_alphys_up_talk|down|3", result


@live
def test_a_parent_chain_resolves_through_the_merged_ids(real):
    _, _, registry, _ = real
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    result = vm.execute(f'''
        Input=require("port.input"); Runtime=require("port.runtime")
        local R=Runtime.new(require("generated.yellow.manifest"), Input.new(), {{headless=true, seed=42}})
        local child={registry.merged("objects", "obj_toy_gun_circle")}
        local parent={registry.merged("objects", "obj_target_bar_battle")}
        local inst={{_instance=true,alive=true,active=true,v={{object_index=child}}}}
        return tostring(R:object(child).parent == parent) .. "|" .. tostring(R:isA(inst, parent))
             .. "|" .. tostring(R:isA(inst, {registry.merged("objects", "obj_pl")}))
    ''')
    assert result == "true|true|false", result


@live
def test_the_object_stage_is_reproducible(real):
    _, _, _, _ = real
    first = (ROOT / "generated/yellow/manifest.lua").read_bytes()
    run = subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "objects"],
                         cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert (ROOT / "generated/yellow/manifest.lua").read_bytes() == first
