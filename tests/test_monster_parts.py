"""Battles beyond the Ruins spawn monster artwork through original object IDs.

The decompiled monster events assign *bare* original object IDs to ``partN``
variables and hand them to ``instance_create`` (``part2= 255; mypart2=
instance_create(x, y, part2)``). No annotation covers those literals, so before
the recovery every such battle stopped with ``instance_create Missing original
object ID`` — the first Snowdin encounter (battlegroup 30, Snowdrake) stopped on
ID 255. ``tools/recover_parts.py`` pairs each literal with the object name the
pinned upstream decompilation uses for the same statement
(``port/recovered_parts.json``); these tests pin that fix.
"""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from test_runtime import new_game

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "port/recovered_parts.json").read_text())

PART_ASSIGN = re.compile(r"\b(part\d+)\s*=\s*(-?\d+)\s*;")
PART_CREATE = re.compile(r"instance_create\s*\([^;]*?,\s*(part\d+)\s*\)")


def event_code(name, event_key):
    tree = ET.parse(ROOT / f"objects/{name}.object.gmx")
    kind, number = event_key.split(":", 1)
    for ev in tree.findall("events/event"):
        if ev.get("eventtype") == kind and ev.get("enumb", ev.get("ename", "0")) == number:
            lines = []
            for action in ev.findall("action"):
                lines += [s.text or "" for s in action.findall("arguments/argument/string")]
            return "\n".join(lines)
    raise AssertionError(f"event {name} {event_key} not found")


def part_sites():
    """(site label, object id) for every literal part variable spawned here."""
    for path in sorted((ROOT / "objects").glob("*.object.gmx")):
        name = path.name.split(".")[0]
        for ev in ET.parse(path).findall("events/event"):
            key = ev.get("eventtype") + ":" + ev.get("enumb", ev.get("ename", "0"))
            lines = []
            for action in ev.findall("action"):
                lines += [s.text or "" for s in action.findall("arguments/argument/string")]
            code = "\n".join(lines)
            created = set(PART_CREATE.findall(code))
            for var, value in PART_ASSIGN.findall(code):
                if var in created:
                    yield f"{name} {key} {var}", int(value)


def manifest_object_ids():
    manifest = (ROOT / "generated/manifest.lua").read_text()
    return {int(i) for i in re.findall(r'\[(\d+)\]="generated\.objects\.', manifest)}


def test_every_part_variable_spawn_resolves_to_a_real_object(converted):
    """A single unresolved literal is a guaranteed battle stop on a real device."""
    known = manifest_object_ids()
    unresolved = [(site, i) for site, i in part_sites() if i not in known]
    assert not unresolved, f"part spawn targets with no original ID: {unresolved}"


def test_recovered_parts_are_pinned_to_the_same_ref_as_the_registry():
    registry = json.loads((ROOT / "port/recovered_registry.json").read_text())
    assert DATA["upstream"] == registry["upstream"] == "kittibyte/UndertaleDecomp"
    assert DATA["ref"] == registry["ref"], "part recovery must not drift off the pinned commit"


def test_no_part_id_was_invented_locally():
    """Every recorded ID must be this checkout's own literal at its recorded site."""
    assert DATA["pairs"], "the Snowdin battle crash fix is missing its data"
    for name, record in DATA["pairs"].items():
        assert isinstance(record["id"], int) and 0 <= record["id"] < 10000, name
        assert (ROOT / f"objects/{name}.object.gmx").is_file(), f"{name} is not a local object"
        assert record["sites"], f"{name} has no evidence sites"
        for site in record["sites"]:
            code = event_code(site["object"], site["event"])
            assert re.search(rf"\b{site['variable']}\s*=\s*{record['id']}\s*;", code), \
                f"{name}: id {record['id']} is not a {site['variable']} literal in {site['object']} {site['event']}"
            assert re.search(rf"instance_create\s*\([^;]*?,\s*{site['variable']}\s*\)", code), \
                f"{name}: {site['variable']} is never spawned in {site['object']} {site['event']}"
            assert site["upstream_file"].startswith(f"objects/{site['object']}/"), site


def test_snowdrake_body_id_255_is_registered(converted):
    """The reported crash: obj_snowdrake create stops on instance_create(255)."""
    known = manifest_object_ids()
    assert DATA["pairs"]["obj_drakebody"]["id"] == 255
    assert 255 in known, "ID 255 must resolve or the first Snowdin encounter stops"


SNOWDIN_BATTLES = [
    # (battlegroup, controller, parts the battle used to stop on)
    (30, "obj_snowdrake", ["obj_drakebody"]),                       # first random encounter
    (32, "obj_icecap", []),                                         # no parts: never stopped
    (35, "obj_jerry", []),                                          # Ice Cap + Jerry
    (24, "obj_lesserdoge", []),                                     # Lesser Dog (parts annotated)
    (23, "obj_movedoge", ["obj_movedogebody", "obj_movedogearms", "obj_movedogetail"]),  # Doggo
    (25, "obj_mandog", ["obj_mandogax", "obj_womandogax"]),         # Dogamy & Dogaressa
    (26, "obj_greatdog", ["obj_greatdogbody"]),                     # Greater Dog
    (27, "obj_papyrusboss", ["obj_papyrusbody"]),                   # Snowdin's boss
    (28, "obj_gyftrot", ["obj_gyftrotbody", "obj_gyftrotgift"]),    # Gyftrot
    (135, "obj_glydeb", ["obj_glyde_body"]),                        # Glyde (secret boss)
    (93, "obj_gladdummy", []),                                      # Glad Dummy
]


@pytest.mark.parametrize("group,controller,parts", SNOWDIN_BATTLES)
def test_snowdin_battle_spawns_monster_and_parts(lua, group, controller, parts):
    """Each Snowdin encounter reaches room_battle with its artwork alive."""
    new_game(lua)
    lua.execute(f"""
        R.global.battlegroup={group}
        R:create(R.constants.obj_battleblcon, 0, 0)
        tick(300)
        local wanted = {{ {", ".join(f'"{n}"' for n in [controller] + parts)} }}
        local alive = {{}}
        for _,i in ipairs(R.instances) do
            if i.alive then
                local o=R:object(i.v.object_index)
                if o then alive[o.name]=true end
            end
        end
        ALIVE_LIST, MISSING_LIST = {{}}, {{}}
        for _,want in ipairs(wanted) do
            if alive[want] then ALIVE_LIST[#ALIVE_LIST+1]=want else MISSING_LIST[#MISSING_LIST+1]=want end
        end
    """)
    assert lua.eval("R.roomState.name") == "room_battle"
    missing = [str(x) for x in lua.eval("MISSING_LIST")]
    assert not missing, f"battlegroup {group} lost its monster parts: {missing}"
    # The battle is live, not just entered: the controller survived its first
    # dialogue turn and the fight UI is up.
    assert lua.eval("R.global.inbattle") == 1


def test_waterfall_shyren_battle_spawns_its_body(lua):
    """The same recovery covers the Waterfall Shyren encounter (ID 260)."""
    new_game(lua)
    lua.execute("""
        R.global.battlegroup=44
        R:create(R.constants.obj_battleblcon, 0, 0)
        tick(300)
        local found = false
        for _,i in ipairs(R.instances) do
            if i.alive then
                local o=R:object(i.v.object_index)
                if o and o.name == "obj_shyrenbody" then found = true end
            end
        end
        SHYREN_BODY_ALIVE = found
    """)
    assert lua.eval("SHYREN_BODY_ALIVE"), "obj_shyrenbody (260) did not spawn"
    assert lua.eval("R.roomState.name") == "room_battle"
