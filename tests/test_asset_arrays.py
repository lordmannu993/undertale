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


def test_shopkeeper_default_face_layers_seat_exactly(lua):
    """§7 visual sweep, emotion 0: three layers, one pair of eyes, a seated mouth.

    ``obj_shop1``'s Draw paints the body at ``(shx, 0)`` -- a cropped 61x111
    export whose recovered canvas offset is ``(1, 9)`` -- and the shop adds the
    blinking eyes at ``(18 + shx, 40)`` (Create) and the mouth at
    ``(shx + 27, 50)`` (obj_shopmouth1 Create). Those positions were authored
    against the *original canvas*, so the layers only show one face when the
    body's exported pixels land at their canvas position ``(shx + 1, 9)``:
    eyes 17 columns and 31 rows into the body's bitmap, mouth at (26, 41).
    Without the crop carriage the body's painted eyes and mouth ride 9 rows up
    and 1 column left of the overlays -- four eyes and a floating mouth, the
    owner's original screenshot.
    """
    lua.execute('''
        R:start(); tick(5)
        R:gotoRoom(R.constants.room_shop1); R:applyTransitions(); tick(3)
        assert(R.roomState.name == "room_shop1")
        R.global.faceemotion=0
        R.drawLog={}
        R:renderFrame()
        LAYERS={}
        local n=0
        for _,e in ipairs(R.drawLog) do
            if e[1]=="sprite" and tostring(e[2]):find("shopkeeper1") then
                n=n+1
                LAYERS[n]={name=tostring(e[2]),x=e[4],y=e[5],ox=e[11],oy=e[12]}
            end
        end
        LAYERS.n=n
    ''')
    count = lua.eval("LAYERS.n")
    layers = [{k: lua.eval(f"LAYERS[{i}].{k}")
               for k in ("name", "x", "y", "ox", "oy")} for i in range(1, count + 1)]
    names = [layer["name"] for layer in layers]
    assert names == ["spr_shopkeeper1", "spr_shopkeeper1eyes", "spr_shopkeeper1mouth"], \
        f"room 311 must draw body, eyes and mouth exactly once each: {names}"
    body, eyes, mouth = layers[0], layers[1], layers[2]
    assert (body["x"], body["y"]) == (130, 0), "obj_shop1 draws the body at (shx, 0), shx=130"
    assert (body["ox"], body["oy"]) == (1, 9), \
        "the cropped export must carry its recovered canvas offset (port/sprite_offsets.json)"
    assert (eyes["x"], eyes["y"]) == (148, 40), "the eyes blink at (18 + shx, 40)"
    assert (mouth["x"], mouth["y"]) == (157, 50), "the mouth sits at (shx + 27, 50)"
    bx, by = body["x"] + body["ox"], body["y"] + body["oy"]
    assert (eyes["x"] - bx, eyes["y"] - by) == (17, 31), \
        "the eyes strip must sit on the body's painted eye band, not beside it"
    assert (mouth["x"] - bx, mouth["y"] - by) == (26, 41), \
        "the mouth must sit on the body's muzzle, not float above it"


def test_shopkeeper_emotion_faces_cover_the_default_face_and_swap_out_the_mouth(lua):
    """§7 visual sweep, emotions 1-6: one face, drawn once, over the default.

    ``obj_shopmouth1``'s Draw swaps the mouth for ``facespr[faceemotion]`` at
    ``(shx + 20, 36)`` -- so the separate mouth must not draw -- and the face
    sprites carry origin ``(1, 4)``, putting the 25x25 bitmap at
    ``(shx + 19, 32)``: 18 columns and 23 rows into the body's bitmap, which
    covers the body's painted eyes (bitmap rows 31-36), the blinking strip's
    band (rows 31-37, dark pixels from column 18) and the body's own mouth
    (rows 42-45). One pair of eyes, the painted mouth seated on the muzzle.
    """
    lua.execute('''
        R:start(); tick(5)
        R:gotoRoom(R.constants.room_shop1); R:applyTransitions(); tick(3)
        assert(R.roomState.name == "room_shop1")
        ROWS={}
        for emo=1,6 do
            R.global.faceemotion=emo
            R.drawLog={}
            R:renderFrame()
            local t={}
            for _,e in ipairs(R.drawLog) do
                if e[1]=="sprite" and tostring(e[2]):find("shopkeeper1") then
                    t[#t+1]={name=tostring(e[2]),x=e[4],y=e[5],ox=e[11],oy=e[12],oX=e[17],oY=e[18]}
                end
            end
            ROWS[emo]=t
        end
    ''')
    for emo in range(1, 7):
        count = lua.eval(f"#ROWS[{emo}]")
        layers = [{k: lua.eval(f"ROWS[{emo}][{i}].{k}")
                   for k in ("name", "x", "y", "ox", "oy", "oX", "oY")}
                  for i in range(1, count + 1)]
        layers = {layer["name"]: layer for layer in layers}
        names = list(layers)
        face = f"spr_shopkeeper1_face{emo}"
        assert names == ["spr_shopkeeper1", "spr_shopkeeper1eyes", face], \
            f"emotion {emo}: body, blinking eyes and exactly one face: {names}"
        assert "spr_shopkeeper1mouth" not in layers, \
            f"emotion {emo}: the face replaces the mouth layer"
        body, face_row = layers["spr_shopkeeper1"], layers[face]
        assert (face_row["x"], face_row["y"]) == (150, 36), \
            f"emotion {emo}: the face draws at (shx + 20, 36)"
        assert (face_row["oX"], face_row["oY"]) == (1, 4), \
            f"emotion {emo}: the face sprites' origin is (1, 4)"
        bx, by = body["x"] + body["ox"], body["y"] + body["oy"]
        assert (face_row["x"] - face_row["oX"] - bx, face_row["y"] - face_row["oY"] - by) == (18, 23), \
            f"emotion {emo}: the face bitmap must cover the body's painted face"
        left, top = face_row["x"] - face_row["oX"], face_row["y"] - face_row["oY"]
        assert left <= layers["spr_shopkeeper1eyes"]["x"] + 2, \
            f"emotion {emo}: the face must cover the strip's dark eye pixels (they start 2 columns in)"
        strip = layers["spr_shopkeeper1eyes"]
        assert top <= strip["y"] and top + 25 >= strip["y"] + 7, \
            f"emotion {emo}: the face must cover the blinking strip's whole band"
    unresolved = [str(w) for w in lua.eval("R.warningList") if "Unresolved sprite ID" in str(w)]
    assert not unresolved, f"shop face draw still unresolved: {unresolved}"


def test_recovery_check_mode_runs_offline():
    """`--check` is the CI-facing offline re-derivation gate; it must not need the network."""
    result = subprocess.run([sys.executable, str(ROOT / "tools/recover_asset_arrays.py"), "--check"],
                            cwd=ROOT, capture_output=True, text=True,
                            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": ""})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "sites resolve" in result.stdout
