"""Shared helpers for the Undertale Yellow merge tests.

The real Yellow source is a 580 MB fetch, so the conversion logic is tested
against a miniature source tree built here: same folder layout, same ``.yy``
shapes, same two ID records. Tests that need the real thing skip (never pass
silently) when ``yellow_src/`` has not been fetched.
"""
from __future__ import annotations

import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
YELLOW_SOURCE = ROOT / "yellow_src"
YELLOW_BASE = 1_000_000

#: name -> (folder, asset-order section), mirroring tools/yellow/registry.py
CATEGORIES = {
    "sprites": ("sprites", "sprites"),
    "objects": ("objects", "objects"),
    "rooms": ("rooms", "rooms"),
    "sounds": ("sounds", "sounds"),
    "backgrounds": ("tilesets", "backgrounds"),
    "fonts": ("fonts", "fonts"),
    "paths": ("paths", "paths"),
    "scripts": ("scripts", "scripts"),
    "shaders": ("shaders", "shaders"),
}


def write_png(path: Path, width: int, height: int, rgba: tuple[int, int, int, int] = (0, 0, 0, 0)) -> Path:
    """A real, decodable PNG of the requested size, written without an imaging library."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(rgba) * width for _ in range(height))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path


def sprite(name: str, width: int, height: int, frames: int, *, origin: int = 4,
           custom: tuple[int, int] | None = None, collision_kind: int = 1,
           speed: float = 1.0, speed_type: int = 1, nine_slice: bool = False) -> dict:
    """A GMS2 sprite record with the fields the converter depends on."""
    if origin == 9:
        custom = custom or (width // 2, height // 2)
    return {
        "resourceType": "GMSprite", "resourceVersion": "1.0", "name": name,
        "bbox_bottom": height - 1, "bbox_left": 0, "bbox_right": width - 1, "bbox_top": 0,
        "bboxMode": 0, "collisionKind": collision_kind, "collisionTolerance": 0,
        "For3D": False, "HTile": False, "VTile": False, "gridX": 0, "gridY": 0,
        "height": height, "width": width, "origin": origin,
        "frames": [{"resourceType": "GMSpriteFrame", "resourceVersion": "1.1",
                    "name": f"frame-{name}-{index}"} for index in range(frames)],
        "layers": [{"resourceType": "GMImageLayer", "resourceVersion": "1.0",
                    "name": f"layer-{name}", "blendMode": 0, "displayName": "default",
                    "isLocked": False, "opacity": 100.0, "visible": True}],
        "nineSlice": {"enabled": True} if nine_slice else None,
        "preMultiplyAlpha": False, "sequence": {
            "resourceType": "GMSequence", "resourceVersion": "1.4", "name": name,
            "length": float(frames), "playback": 1, "playbackSpeed": speed,
            "playbackSpeedType": speed_type, "timeUnits": 1,
            "xorigin": (custom or (0, 0))[0], "yorigin": (custom or (0, 0))[1],
            "tracks": [], "volume": 1.0,
        },
        "textureGroupId": {"name": "GeneralUse", "path": "texturegroups/GeneralUse"},
        "type": 0, "swfPrecision": 2.525,
    }


def sound(name: str, file_name: str, volume: float = 1.0) -> dict:
    return {"resourceType": "GMSound", "resourceVersion": "1.0", "name": name,
            "audioGroupId": {"name": "audiogroup_default", "path": "audiogroups/audiogroup_default"},
            "bitDepth": 1, "bitRate": 128, "compression": 0, "conversionMode": 0,
            "duration": 0.5, "preload": True, "sampleRate": 44100,
            "soundFile": file_name, "type": 0, "volume": volume}


def font(name: str, glyphs: dict[int, dict], size: float = 10.0) -> dict:
    return {"resourceType": "GMFont", "resourceVersion": "1.0", "name": name,
            "AntiAlias": 0, "applyKerning": 0, "ascender": 13, "ascenderOffset": 0,
            "bold": False, "canGenerateBitmap": True, "charset": 1, "first": 32,
            "fontName": "Test Mono", "glyphOperations": 0,
            "glyphs": {str(code): {"character": code, **metrics} for code, metrics in glyphs.items()},
            "hinting": 0, "includeTTF": False, "interpreter": 0, "italic": False,
            "kerningPairs": [], "last": max(glyphs), "maintainGms1Font": True,
            "pointRounding": 0, "ranges": [], "regenerateBitmap": False,
            "sampleText": "abc, } not a trailing comma", "size": size, "styleName": "Regular",
            "textureGroupId": {"name": "GeneralUse", "path": "texturegroups/GeneralUse"}, "TTFName": None}


def tileset(name: str, texture: str, *, tile: int, count: int, columns: int) -> dict:
    return {"resourceType": "GMTileSet", "resourceVersion": "1.0", "name": name,
            "autoTileSets": [], "macroPageTiles": {"SerialiseHeight": 0, "SerialiseWidth": 0, "TileSerialiseData": []},
            "out_columns": columns, "out_tilehborder": 2, "out_tilevborder": 2,
            "spriteId": {"name": texture, "path": f"sprites/{texture}/{texture}.yy"},
            "spriteNoExport": True,
            "textureGroupId": {"name": "GeneralUse", "path": "texturegroups/GeneralUse"},
            "tile_count": count,
            "tileAnimation": {"FrameData": list(range(count)), "SerialiseData": [], "SerialiseHeight": 0,
                              "SerialiseWidth": 0, "TileSerialiseData": []},
            "tileAnimationFrames": [], "tileAnimationSpeed": 15.0,
            "tileHeight": tile, "tileWidth": tile, "tilehsep": 0, "tilevsep": 0, "tilexoff": 0, "tileyoff": 0}


#: GMS2 event type -> the code file name Studio 2 uses. Mirrored here on purpose:
#: the fixture must not import the converter's own naming, or a wrong name in
#: ``tools/yellow/objects.py`` would agree with itself and pass.
EVENT_FILE_NAMES = {0: "Create", 1: "Destroy", 2: "Alarm", 3: "Step", 4: "Collision",
                    5: "Keyboard", 6: "Mouse", 7: "Other", 8: "Draw", 9: "KeyPress",
                    10: "KeyRelease", 11: "Trigger", 12: "CleanUp", 13: "Gesture", 14: "PreCreate"}


def event(kind: int, number: int, code: str, target: str | None = None) -> dict:
    """One Studio 2 event: its type/subtype, its code, and a collision target."""
    return {"kind": kind, "number": number, "code": code, "target": target}


def event_file_name(entry: dict) -> str:
    # Collision code is named after the *other* object and carries no subtype.
    if entry["kind"] == 4:
        return f"Collision_{entry['target']}.gml"
    return f"{EVENT_FILE_NAMES[entry['kind']]}_{entry['number']}.gml"


def event_entry(entry: dict) -> dict:
    target = entry["target"]
    return {"resourceType": "GMEvent", "resourceVersion": "1.0", "name": "",
            "collisionObjectId": {"name": target, "path": f"objects/{target}/{target}.yy"} if target else None,
            "eventNum": entry["number"], "eventType": entry["kind"], "isDnD": False}


def gms2_object(name: str, *, sprite: str | None = None, mask: str | None = None,
                parent: str | None = None, solid: bool = False, visible: bool = True,
                persistent: bool = False, physics: bool = False, events: list[dict] = ()) -> dict:
    """A GMS2 object record carrying every field the piece 3 converter reads."""
    reference = {"name": None, "path": None}
    return {
        "resourceType": "GMObject", "resourceVersion": "1.0", "name": name,
        "eventList": [event_entry(entry) for entry in events],
        "managed": True, "overriddenProperties": [],
        "parent": {"name": "Objects", "path": "folders/Objects.yy"},
        "parentObjectId": {"name": parent, "path": f"objects/{parent}/{parent}.yy"} if parent else None,
        "persistent": persistent,
        "physicsAngularDamping": 0.1, "physicsDensity": 0.5, "physicsFriction": 0.2,
        "physicsGroup": 0, "physicsKinematic": False, "physicsLinearDamping": 0.1,
        "physicsObject": physics, "physicsRestitution": 0.1, "physicsSensor": physics,
        "physicsShape": 1 if physics else 0,
        "physicsShapePoints": ([{"x": -8.0, "y": -8.0}, {"x": 8.0, "y": -8.0},
                                {"x": 8.0, "y": 8.0}, {"x": -8.0, "y": 8.0}] if physics else []),
        "physicsStartAwake": True, "properties": [], "solid": solid,
        "spriteId": {"name": sprite, "path": f"sprites/{sprite}/{sprite}.yy"} if sprite else None,
        "spriteMaskId": {"name": mask, "path": f"sprites/{mask}/{mask}.yy"} if mask else None,
        "visible": visible,
    }


#: The miniature object set: a parent chain, a mask, a collision pair, a physics
#: fixture, an invisible object and the two events nothing dispatches.
OBJECTS = {
    "obj_pl": {
        "sprite": "spr_pl_down", "mask": "spr_a", "persistent": True,
        "events": [
            event(0, 0, "function helper() {\n    return 3;\n}\nvalue = helper();"),
            event(3, 0, "if (keyboard_check(vk_left)) x -= 2;"),
            event(8, 64, "draw_text(4, 4, \"gui\");"),
        ],
    },
    "obj_parent": {
        "solid": True,
        "events": [
            event(0, 0, "created = 1;"),
            event(1, 0, "destroyed = 1;"),
            event(12, 0, "cleaned = 1;"),
            event(7, 10, "user_ran = 1;"),
        ],
    },
    "obj_child": {
        "parent": "obj_parent", "sprite": "spr_a",
        "events": [
            event(0, 0, "function helper() {\n    return 7;\n}\nvalue = helper();"),
            event(2, 0, "alarm_ran = 1;"),
            event(3, 1, "begin_ran = 1;"),
            event(3, 2, "end_ran = 1;"),
            event(4, 0, "hit = other.object_index;", target="obj_target"),
            event(6, 4, "clicked = 1;"),
            event(8, 72, "draw_begin_ran = 1;"),
            event(8, 0, "draw_ran = 1;"),
            event(8, 73, "draw_end_ran = 1;"),
            event(8, 74, "gui_begin_ran = 1;"),
            event(8, 75, "gui_end_ran = 1;"),
            event(8, 76, "pre_draw_ran = 1;"),
            event(8, 77, "post_draw_ran = 1;"),
            event(10, 27, "escape_ran = 1;"),
        ],
    },
    "obj_target": {
        "parent": "obj_parent", "sprite": "spr_a",
        "events": [event(0, 0, "doubled = scr_a(21);")],
    },
    "obj_physics": {
        "sprite": "spr_a", "physics": True,
        "events": [event(3, 0, "physics_step = 1;")],
    },
    "obj_broadcast": {
        "events": [
            event(7, 76, "if (ds_map_find_value(event_data, \"event_type\") == \"sprite event\") broadcast_ran = 1;"),
            event(7, 62, "live_async_http();"),
        ],
    },
    "obj_invisible": {
        "sprite": "spr_a", "visible": False,
        "events": [event(8, 0, "invisible_draw_ran = 1;")],
    },
}


def asset_order(sections: dict[str, list[str]]) -> str:
    """The decompiler's ID dump: section headers plus ``<id> - <name>`` lines."""
    out = ["Generated by test fixture", "", "Assets Found:", ""]
    for section, names in sections.items():
        out.append(f"{section.capitalize()}: {len(names)}")
    out.append("")
    for section, names in sections.items():
        out.append("")
        out.append("-" * 21 + f" {section.upper()} " + "-" * 21)
        out.extend(f"{index} - {name}" for index, name in enumerate(names))
    return "\n".join(out) + "\n"


def project(resources: list[tuple[str, str]]) -> str:
    """A ``.yyp`` whose resource order is the compiled asset order."""
    entries = ",\n".join(
        f'    {{"id":{{"name":"{name}","path":"{folder}/{name}/{name}.yy",}},}}' for name, folder in resources)
    return ('{\n  "resourceType": "GMProject",\n  "resourceVersion": "1.7",\n  "name": "Undertale_Yellow",\n'
            '  "resources": [\n' + entries + ",\n  ],\n}\n")


FIXTURE = {
    "sprites": {
        "spr_a": sprite("spr_a", 20, 20, 1, origin=4, collision_kind=1),
        "spr_pl_down": sprite("spr_pl_down", 20, 32, 4, origin=9, custom=(9, 17)),
        "spr_pl_run_down": sprite("spr_pl_run_down", 20, 32, 6, origin=9, custom=(9, 17)),
        "spr_fps": sprite("spr_fps", 8, 8, 3, origin=0, speed=30.0, speed_type=0),
        "spr_rotated": sprite("spr_rotated", 16, 16, 1, origin=0, collision_kind=4),
        "spr_nine": sprite("spr_nine", 24, 24, 1, origin=0, nine_slice=True),
    },
    "sounds": {"snd_a": sound("snd_a", "a_sound.ogg", 0.8), "snd_b": sound("snd_b", "b_sound")},
    "fonts": {"fnt_a": font("fnt_a", {32: {"h": 16, "offset": 0, "shift": 8, "w": 8, "x": 2, "y": 2},
                                      65: {"h": 12, "offset": 1, "shift": 9, "w": 7, "x": 12, "y": 2},
                                      9647: {"h": 12, "offset": 0, "shift": 8, "w": 6, "x": 21, "y": 2}})},
    "tilesets": {"ts_a": tileset("ts_a", "_decompiled_ts_a", tile=20, count=6, columns=3)},
    "objects": list(OBJECTS),
    "rooms": ["rm_a"],
    "paths": ["pt_a"],
    "scripts": ["scr_a"],
    "shaders": ["sh_a"],
}
TILESET_TEXTURES = {"ts_a": ("_decompiled_ts_a", sprite("_decompiled_ts_a", 60, 40, 1, origin=0))}
#: a real Undertale sprite name, used to prove the collision table keeps both games' IDs
UNDERTALE_COLLISION = "spr_flowey"


def add_unbacked_sprite(source: Path, provenance: dict, name: str) -> dict:
    """Give a sprite an ID in both pinned records but no folder, like Yellow's ``_filter_*``.

    The converter must list it as unrecoverable instead of pointing the ID at some
    other sprite, so the fixture needs the same inconsistency the real source has.
    """
    order = source / "notes/Asset_Order/Asset_Order.txt"
    text = order.read_text()
    lines = text.splitlines()
    index = next(i for i, line in enumerate(lines) if line.startswith("--------------------- OBJECTS"))
    highest = max(int(line.split(" - ")[0]) for line in lines[:index] if " - " in line)
    lines.insert(index, f"{highest + 1} - {name}")
    lines = [f"Sprites: {highest + 2}" if line.startswith("Sprites:") else line for line in lines]
    order.write_text("\n".join(lines) + "\n")
    project_file = source / "Undertale_Yellow.yyp"
    project_text = project_file.read_text()
    entry = f'    {{"id":{{"name":"{name}","path":"sprites/{name}/{name}.yy",}},}}'
    marker = f'{{"id":{{"name":"{FIXTURE["objects"][0]}"'
    project_file.write_text(project_text.replace(marker, entry + ",\n" + marker, 1))
    provenance = json.loads(json.dumps(provenance))
    provenance["documented_counts"]["sprites"] = highest + 2
    return provenance


def build_source(root: Path, *, swap_sprite_order: bool = False,
                 collide_with_undertale: bool = False) -> tuple[Path, dict]:
    """Write a miniature Yellow project tree; return (source dir, provenance)."""
    source = root / "yellow_src"
    for folder in {folder for folder, _ in CATEGORIES.values()} | {"sequences", "options/main"}:
        (source / folder).mkdir(parents=True, exist_ok=True)

    sprites = dict(FIXTURE["sprites"])
    if collide_with_undertale:
        # Undertale already owns this sprite name; the merged manifest must keep both.
        record = sprites.pop("spr_a")
        record["name"] = UNDERTALE_COLLISION
        record["sequence"]["name"] = UNDERTALE_COLLISION
        sprites = {UNDERTALE_COLLISION: record, **sprites}
    sprite_names = list(sprites)
    project_names = list(sprite_names)
    if swap_sprite_order:
        # Only the decompiler's ID dump is reordered, so the two pinned records
        # genuinely disagree and the registry has to refuse both.
        sprite_names[0], sprite_names[1] = sprite_names[1], sprite_names[0]
    sections = {
        "sprites": sprite_names,
        "objects": FIXTURE["objects"],
        "rooms": FIXTURE["rooms"],
        "sounds": list(FIXTURE["sounds"]),
        "backgrounds": list(FIXTURE["tilesets"]),
        "shaders": FIXTURE["shaders"],
        "fonts": list(FIXTURE["fonts"]),
        "paths": FIXTURE["paths"],
        "scripts": FIXTURE["scripts"],
        "timelines": [],
        "extensions": [],
    }
    (source / "notes" / "Asset_Order").mkdir(parents=True, exist_ok=True)
    (source / "notes/Asset_Order/Asset_Order.txt").write_text(asset_order(sections))

    resources: list[tuple[str, str]] = []
    for name, record in sprites.items():
        folder = source / "sprites" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.yy").write_text(json.dumps(record, indent=2))
        for frame in record["frames"]:
            write_png(folder / f"{frame['name']}.png", record["width"], record["height"])
        resources.append((name, "sprites"))
    for tileset_name, (texture, record) in TILESET_TEXTURES.items():
        folder = source / "sprites" / texture
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{texture}.yy").write_text(json.dumps(record, indent=2))
        for frame in record["frames"]:
            write_png(folder / f"{frame['name']}.png", record["width"], record["height"])
    for name, record in FIXTURE["sounds"].items():
        folder = source / "sounds" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.yy").write_text(json.dumps(record, indent=2))
        declared = record["soundFile"]
        (folder / (declared if "." in declared else declared + ".ogg")).write_bytes(b"OggS test audio")
        resources.append((name, "sounds"))
    for name, record in FIXTURE["fonts"].items():
        folder = source / "fonts" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.yy").write_text(json.dumps(record, indent=2))
        write_png(folder / f"{name}.png", 64, 32)
        resources.append((name, "fonts"))
    for name, record in FIXTURE["tilesets"].items():
        folder = source / "tilesets" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}.yy").write_text(json.dumps(record, indent=2))
        resources.append((name, "tilesets"))
    for name, spec in OBJECTS.items():
        folder = source / "objects" / name
        folder.mkdir(parents=True, exist_ok=True)
        events = spec.get("events", [])
        record = gms2_object(name, events=events, **{k: v for k, v in spec.items() if k != "events"})
        (folder / f"{name}.yy").write_text(json.dumps(record, indent=2))
        for entry in events:
            (folder / event_file_name(entry)).write_text(entry["code"] + "\n")
        resources.append((name, "objects"))
    for folder_name, names in (("rooms", FIXTURE["rooms"]), ("paths", FIXTURE["paths"]),
                               ("scripts", FIXTURE["scripts"]), ("shaders", FIXTURE["shaders"])):
        for name in names:
            (source / folder_name / name).mkdir(parents=True, exist_ok=True)
            (source / folder_name / name / f"{name}.yy").write_text(json.dumps({"name": name}))
            resources.append((name, folder_name))
    # Piece 2 and 3 need the script's own GML, not just its .yy placeholder.
    (source / "scripts" / "scr_a" / "scr_a.gml").write_text(
        "function scr_a(value) {\n    return value * 2;\n}\n")

    # The project file's resource order has to agree with the ID dump, category by category.
    project_sections = dict(sections, sprites=project_names)
    ordered: list[tuple[str, str]] = []
    for section, names in project_sections.items():
        folder = next((f for f, s in CATEGORIES.values() if s == section), None)
        ordered += [(name, folder) for name in names if folder]
    (source / "Undertale_Yellow.yyp").write_text(project(ordered))
    (source / "options/main/options_main.yy").write_text(json.dumps({"option_game_speed": 30}))
    provenance = {
        "upstream": "fixture/UnderTale-Yellow", "ref": "0" * 40,
        "extract_to": "yellow_src",
        "documented_counts": {
            "sprites": len(sections["sprites"]), "objects": len(sections["objects"]),
            "rooms": len(sections["rooms"]), "sounds": len(sections["sounds"]),
            "backgrounds": len(sections["backgrounds"]), "fonts": len(sections["fonts"]),
            "paths": len(sections["paths"]), "scripts": len(sections["scripts"]),
            "shaders": len(sections["shaders"]), "game_speed": 30,
            "sprite_folders_on_disk": len(FIXTURE["sprites"]) + len(TILESET_TEXTURES),
            "script_folders_on_disk": len(FIXTURE["scripts"]),
        },
    }
    return source, provenance
