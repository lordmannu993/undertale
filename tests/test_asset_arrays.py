"""Asset IDs that Undertale keeps inside instance arrays.

This checkout's decompiled events fill instance arrays with *bare* original
asset IDs and read them back through a computed index. The Snowdin shop
(``obj_shopmouth1``/``obj_shop1``) does::

    facespr[1]= 881;                        # Create
    ...
    draw_sprite(facespr[global.faceemotion], ...)   # Draw

No decompiler annotation covers those literals, so before the recovery the seven
``spr_shopkeeper1_face*`` sprites sat on synthetic IDs and every emotional line
stopped with ``Unresolved sprite ID 881`` — the shopkeeper's emotion faces never
drew, leaving the mouth floating over the default two-eye frame. The same class
covers a second, unreferenced ``facespr`` in ``obj_shop1``, the Asgore body-part
``part`` sprites, and three ``background_index`` slots. ``tools/recover_asset_arrays.py``
pairs each local literal with the asset name the pinned upstream decompilation
uses for the same statement (``port/recovered_asset_arrays.json``); these tests
pin that fix.
"""
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from conftest import ROOT
from tools import recover_asset_arrays as rec

DATA = json.loads((ROOT / "port/recovered_asset_arrays.json").read_text())


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


def local_asset_sites():
    """Every local ``var[i]= <lit>;`` site that the recovery tool treats as an
    asset array (reuses the tool's own discovery so it cannot drift)."""
    events = rec.local_events()
    categories = rec.resource_categories()
    readvar = rec.index_read_vars(events)
    for (name, key), code in sorted(events.items()):
        if not code.strip():
            continue
        for var, assigns in rec.asset_assignments(code).items():
            ok, category = rec.is_asset_array_var(var, readvar)
            if not ok:
                continue
            for subscript, value, _statement in assigns:
                yield f"{name} {key} {var}[{subscript}]", value, category


def manifest_ids():
    # Only the names map uses string keys with numeric values, so this is
    # unambiguous across the whole manifest.
    manifest = (ROOT / "generated/manifest.lua").read_text()
    return {k: int(v) for k, v in re.findall(r'\["([^"]+)"\]=(-?\d+)', manifest)}


def test_recovery_pinned_to_the_same_ref_as_the_registry():
    registry = json.loads((ROOT / "port/recovered_registry.json").read_text())
    assert DATA["upstream"] == registry["upstream"] == "kittibyte/UndertaleDecomp"
    assert DATA["ref"] == registry["ref"], "asset-array recovery must not drift off the pinned commit"


def test_recovered_pairs_are_pinned_to_the_same_ref_as_the_parts():
    parts = json.loads((ROOT / "port/recovered_parts.json").read_text())
    assert DATA["ref"] == parts["ref"] and DATA["upstream"] == parts["upstream"]


def test_every_recovered_id_is_a_local_resource():
    categories = rec.resource_categories()
    assert DATA["pairs"], "the shopkeeper face fix is missing its data"
    for name, record in DATA["pairs"].items():
        assert categories.get(name) == record["category"], f"{name} is not a local {record['category']} resource"
        assert isinstance(record["id"], int) and 0 <= record["id"] < 10000, name
        assert record["sites"], f"{name} has no evidence sites"


def test_ids_are_unique_within_their_category():
    seen = {}
    for name, record in DATA["pairs"].items():
        key = (record["category"], record["id"])
        assert key not in seen, f"ID {record['id']} ({record['category']}) claimed by both {seen[key]} and {name}"
        seen[key] = name


def test_no_array_id_was_invented_locally():
    """Every recorded ID must be this checkout's own literal at its recorded site."""
    for name, record in DATA["pairs"].items():
        for site in record["sites"]:
            code = event_code(site["object"], site["event"])
            assert re.search(rf"\b{site['variable']}\[{site['index']}\]\s*=\s*{record['id']}\s*;", code), \
                f"{name}: id {record['id']} is not a {site['variable']}[{site['index']}] literal in {site['object']} {site['event']}"
            assert site["upstream_file"].startswith(f"objects/{site['object']}/"), site


def test_every_asset_array_site_is_covered():
    """Nothing left behind: every local asset-array literal resolves to a recorded ID."""
    covered = {(r["category"], r["id"]) for r in DATA["pairs"].values()}
    uncovered = [f"{site}={value}" for site, value, category in local_asset_sites()
                 if (category, value) not in covered]
    assert not uncovered, f"asset-array literal sites still unresolved: {uncovered}"


def test_shopkeeper_face_ids_are_registered(converted):
    """The reported bug: facespr[1]= 881 resolved to nothing, so emotion faces never drew."""
    names = manifest_ids()
    expected = {"spr_shopkeeper1_face0": 876, "spr_shopkeeper1_face1": 881,
                "spr_shopkeeper1_face2": 880, "spr_shopkeeper1_face3": 882,
                "spr_shopkeeper1_face4": 879, "spr_shopkeeper1_face5": 878,
                "spr_shopkeeper1_face6": 877}
    for name, asset_id in expected.items():
        assert names.get(name) == asset_id, f"{name} must be original ID {asset_id}, got {names.get(name)}"
        assert DATA["pairs"][name]["id"] == asset_id


def test_recovered_array_assets_resolve_in_the_runtime(lua):
    """Each recovered ID must now index a real asset record; the Unresolved stop is gone."""
    for name, record in DATA["pairs"].items():
        asset_id = record["id"]
        table = "sprites" if record["category"] == "sprites" else "backgrounds"
        lua.execute(f'''
            assert(R.assets.{table}[{asset_id}], "missing {table} id {asset_id} for {name}")
            assert(R.assets.{table}[{asset_id}].name == "{name}", "wrong asset at id {asset_id}")
        ''')
    # Drawing each recovered sprite through the real builtin must log the sprite
    # and must not emit the "Unresolved sprite ID" stop that shipped before.
    for name, record in DATA["pairs"].items():
        if record["category"] != "sprites":
            continue
        asset_id = record["id"]
        lua.execute(f'''
            R.drawLog={{}}; R.warningList={{}}
            R.builtins.draw_sprite(E, {asset_id}, 0, 10, 10)
            local ok=false
            for _,e in ipairs(R.drawLog) do if e[1]=="sprite" and e[2]=="{name}" then ok=true end end
            DRAWN_{asset_id} = ok
        ''')
        assert lua.eval(f"DRAWN_{asset_id}"), f"{name} (id {asset_id}) did not draw"
        assert not any("Unresolved sprite ID" in str(w) for w in lua.eval("R.warningList")), \
            f"{name} still stopped as an unresolved sprite"


def test_shopkeeper_emotion_faces_draw_in_the_shop(lua):
    """§7: in room 311 the shopkeeper's emotion faces (faceemotion 1-6) must draw.

    In the real game the shop's OBJ_WRITER drives global.faceemotion from the
    dialogue text each step; here we set it directly and render a single frame so
    the mouth's Draw event is observed in isolation. Before the recovery the same
    draw stopped with ``Unresolved sprite ID 881`` and no face reached the log.
    """
    lua.execute('''
        R:start(); tick(5)
        R:gotoRoom(R.constants.room_shop1); R:applyTransitions(); tick(3)
        assert(R.roomState.name == "room_shop1")
        FACES = {}
        for emo=1,6 do
            R.global.faceemotion=emo
            R.drawLog={}
            R:renderFrame()
            local want = "spr_shopkeeper1_face" .. emo
            for _,e in ipairs(R.drawLog) do
                if e[1]=="sprite" and e[2]==want then
                    FACES[emo]=e[2]
                end
            end
        end
    ''')
    faces = lua.eval("FACES")
    for emo in range(1, 7):
        got = faces[emo]
        assert got == f"spr_shopkeeper1_face{emo}", \
            f"emotion {emo} did not draw spr_shopkeeper1_face{emo}: got {got}"
    unresolved = [str(w) for w in lua.eval("R.warningList") if "Unresolved sprite ID" in str(w)]
    assert not unresolved, f"shop face draw still unresolved: {unresolved}"


def test_recovery_check_mode_runs_offline():
    """`--check` is the CI-facing offline re-derivation gate; it must not need the network."""
    result = subprocess.run([sys.executable, str(ROOT / "tools/recover_asset_arrays.py"), "--check"],
                            cwd=ROOT, capture_output=True, text=True,
                            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": ""})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "sites resolve" in result.stdout
