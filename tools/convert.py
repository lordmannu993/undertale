#!/usr/bin/env python3
"""Convert every GMX event, room creation action and GML script to Lua.

Run from any directory: python3 tools/convert.py
Only Python's standard library is required. Output is reproducible and ignored
by Git; packaging regenerates it. See docs/PORTING.md for fidelity limitations.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gml import CompileError, compile_gml, quote, walk
from source_repairs import repair_object_event, repair_script

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {"sprites": ("sprite", ".sprite.gmx"), "objects": ("object", ".object.gmx"),
              "rooms": ("room", ".room.gmx"), "scripts": ("script", ""),
              "sounds": ("sound", ".sound.gmx"), "backgrounds": ("background", ".background.gmx"),
              "fonts": ("font", ".font.gmx")}


def lua(value):
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return quote(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "{" + ",".join(lua(v) for v in value) + "}"
    if isinstance(value, dict):
        return "{" + ",".join(f"[{lua(k)}]={lua(v)}" for k, v in value.items()) + "}"
    raise TypeError(type(value))


def value(s):
    try:
        n = float(s)
        return int(n) if n.is_integer() else n
    except (ValueError, TypeError):
        return s


BOOL_FIELDS = {"visible", "solid", "persistent", "enableViews", "showcolour", "foreground", "htiled", "vtiled", "stretch"}


def meta_value(key, text):
    v = value(text)
    return int(v != 0) if key in BOOL_FIELDS and isinstance(v, (int, float)) else v


def fields(element):
    return {k: meta_value(k, v) for k, v in element.attrib.items()}


def child_fields(element, tags):
    return {k: meta_value(k, element.findtext(k, "0")) for k in tags.split()}


def numeric(node):
    if node[0] == "number":
        v = node[1]
        return int(v[1:], 16) if v.startswith("$") else value(v)
    if node[0] == "unary" and node[1] == "-" and node[2][0] == "number":
        return -numeric(node[2])
    if node[0] == "call" and node[1] == ("name", "ord") and len(node[2]) == 1 and node[2][0][0] == "string":
        s = node[2][0][1]
        return ord(s[0]) if s else 0
    return None


class Converter:
    def __init__(self, root, output):
        self.root, self.output = root, output
        self.resources = {c: {} for c in CATEGORIES}
        self.category = {}
        self.codes = []
        self.ids = {c: {} for c in CATEGORIES}
        self.evidence = {}
        self.errors, self.missing = [], []
        self.calls, self.keys = Counter(), defaultdict(set)
        self.references = []
        self.external_files = defaultdict(set)
        self.digest = hashlib.sha256()
        self.written = []
        self.report = {"format": 1, "status": "experimental; source translation is not a full-game certification",
                       "repairs": [], "limitations": []}

    def read(self, path):
        data = path.read_bytes()
        self.digest.update(str(path.relative_to(self.root)).encode())
        self.digest.update(data)
        return data.decode("utf-8-sig")

    def collect(self):
        project = ET.fromstring(self.read(self.root / "projectA.project.gmx"))
        for category, (tag, suffix) in CATEGORIES.items():
            for e in project.findall(".//" + tag):
                p = self.root / (e.text.replace("\\", "/") + suffix)
                name = p.name.split(".")[0]
                raw = self.read(p)
                self.resources[category][name] = (p, raw if category == "scripts" else ET.fromstring(raw))
                self.category[name] = category
        for name, (path, text) in self.resources["scripts"].items():
            self.codes.append((f"scripts/{name}", path.relative_to(self.root).as_posix(), text))
        for name, (path, obj) in self.resources["objects"].items():
            for event in obj.findall("events/event"):
                key = event.get("eventtype") + ":" + event.get("enumb", event.get("ename", "0"))
                lines = []
                for action in event.findall("action"):
                    args = [a.text or "" for a in action.findall("arguments/argument/string")]
                    if action.findtext("whoName") != "self":
                        raise CompileError(f"{path}: non-self D&D action requires explicit support")
                    if action.findtext("id") == "603" and action.findtext("exetype") == "2":
                        lines.extend(args)
                    elif action.findtext("exetype") == "1" and action.findtext("functionname") in ("action_move_to", "action_set_hspeed"):
                        if action.findtext("relative") != "0":
                            raise CompileError(f"{path}: unsupported relative D&D action")
                        lines.append(action.findtext("functionname") + "(" + ",".join(args) + ");")
                    else:
                        raise CompileError(f"{path}: unsupported action id {action.findtext('id')}")
                self.codes.append((f"objects/{name}/{key}", f"{path.relative_to(self.root)} event {key}", "\n".join(lines)))
                if event.get("eventtype") in ("5", "9", "10"):
                    self.keys[int(event.get("enumb"))].add(f"{name} event {key}")
        for name, (path, room) in self.resources["rooms"].items():
            self.codes.append((f"rooms/{name}/create", f"{path.relative_to(self.root)} creation", room.findtext("code", "")))
            for inst in room.findall("instances/instance"):
                self.codes.append((f"rooms/{name}/{inst.get('name')}", f"{path.relative_to(self.root)} {inst.get('name')}", inst.get("code", "")))

    def add_id(self, name, index, why):
        if name not in self.category:
            return
        category = self.category[name]
        existing = self.ids[category].get(name)
        other = next((n for n, i in self.ids[category].items() if i == index and n != name), None)
        if (existing is not None and existing != index) or other:
            raise CompileError(f"conflicting ID evidence: {name}={index}, existing={existing}, other={other}")
        self.ids[category][name] = index
        self.evidence[name] = why

    def recover_ids(self):
        # The GMX tree is alphabetized, but decompiler numeric IDs are NOT.
        # Recover annotated IDs rather than assigning the GMX tree's indices.
        for _, origin, code in self.codes:
            for index, name in re.findall(r"(-?\d+)\s*/\*\s*(\w+)\s*\*/", code):
                self.add_id(name, int(index), "decompiler annotation")
            for name, index in re.findall(r"//\s*(\w+)\s*\n\s*with\((\d+)\)", code):
                self.add_id(name, int(index), "decompiler with annotation")
        overrides_file = self.root / "port/resource_overrides.json"
        overrides = json.loads(self.read(overrides_file)) if overrides_file.exists() else {}
        # Instance IDs establish RELATIVE order, not contiguous resource IDs.
        # The omitted Hotland room occupies original slot 159; compacting this
        # hole routed Flowey into a test room and broke every later raw room ID.
        gaps = overrides.get("room_id_gaps", [])
        missing = {g["id"]: g for g in gaps}
        if len(missing) != len(gaps) or any(type(i) is not int or i < 0 for i in missing):
            raise CompileError("invalid or duplicate room ID gaps")
        if any(g["name"] in self.resources["rooms"] for g in gaps):
            raise CompileError("a declared missing room now exists; review its original ID before converting")
        self.missing_rooms = {i: g["name"] for i, g in missing.items()}
        self.report["missing_rooms"] = gaps
        recovered_room = self.root / "port/recovered_rooms/manifest.json"
        if recovered_room.exists():
            source = json.loads(self.read(recovered_room))
            self.report["recovered_room_sources"] = [source]
            self.report["limitations"].append(
                "Room source for the original slot 159 is recovered and shipped with provenance, "
                "but its GMS2 room format still needs an explicit GMX adapter before it can replace "
                "the visible compatibility stop.")
        # Keep the non-overlapping editor order, constrained by the documented
        # gaps and independent original-ID anchors in resource_overrides.json.
        ordered = []
        for name, (_, room) in self.resources["rooms"].items():
            numbers = []
            for inst in room.findall("instances/instance"):
                m = re.fullmatch(r"inst_(\d+)", inst.get("name", ""))
                if not m:
                    raise CompileError(f"{name}: original room order cannot be recovered from this instance ID")
                numbers.append(int(m[1]))
            if not numbers:
                raise CompileError(f"{name}: no instance IDs; supply an explicit original room order")
            ordered.append((min(numbers), max(numbers), name))
        ordered.sort()
        self.room_order = []
        slot, used_gaps = 0, set()
        for i, (lo, hi, name) in enumerate(ordered):
            if i and ordered[i - 1][1] >= lo:
                raise CompileError("overlapping room instance ranges: cannot infer room order safely")
            while slot in missing:
                self.room_order.append(slot)  # next/previous must not silently skip missing rooms
                used_gaps.add(slot)
                slot += 1
            self.add_id(name, slot, "relative instance order with documented original-ID gaps")
            self.room_order.append(slot)
            slot += 1
        if used_gaps != set(missing):
            raise CompileError("room ID gap is outside the reconstructed room sequence")
        self.report["repairs"].append("Reconstructed room IDs from relative instance order, preserving missing slot 159 and checking independent room-call anchors; no contiguous-ID assumption.")
        # The stream adapter explicitly identifies most of the remaining music.
        music = self.resources["scripts"]["scr_getmusindex"][1]
        unresolved_music = []
        for filename, index in re.findall(r'if\(argument0 == "([^"]+)"\) song_index= (\d+);', music):
            stem = Path(filename).stem
            candidates = ["mus_" + stem, "snd_" + stem, stem]
            if "/drum/" in filename:
                candidates.insert(0, "mus_drum" + stem)
            match = next((n for n in candidates if n in self.resources["sounds"]), None)
            if match:
                self.add_id(match, int(index), f"scr_getmusindex: {filename}")
            else:
                unresolved_music.append({"file": filename, "id": int(index)})
        self.report["unresolved_music_aliases"] = unresolved_music
        for category, entries in overrides.get("ids", {}).items():
            for name, index in entries.items():
                if self.category.get(name) != category:
                    raise CompileError(f"invalid resource override {category}/{name}")
                self.add_id(name, index, "documented resource override")
        # Import only exact names from the pinned upstream registry audit.  Local
        # overrides and decompiler annotations win: the two exports are known to
        # have different ordering in places, so a conflict is evidence, not a
        # reason to silently replace an established ID.
        registry_file = self.root / "port/recovered_registry.json"
        if registry_file.exists():
            registry = json.loads(self.read(registry_file))
            conflicts = []
            for category, entries in registry.get("recovered", {}).items():
                for name, evidence in entries.items():
                    if name not in self.category or name in self.ids[category]:
                        if name in self.ids[category] and self.ids[category][name] != evidence["id"]:
                            conflicts.append((category, name, self.ids[category][name], evidence["id"]))
                        continue
                    other = next((n for n, i in self.ids[category].items() if i == evidence["id"]), None)
                    if other is not None:
                        conflicts.append((category, name, None, evidence["id"]))
                        continue
                    self.add_id(name, evidence["id"], "pinned upstream registry list")
            self.report["registry_conflicts"] = [dict(category=c, name=n, local=local, upstream=upstream)
                                                  for c, n, local, upstream in conflicts]
            self.report["registry_source"] = {"upstream": registry.get("upstream"), "ref": registry.get("ref")}
        recovered_sound_ids = set(self.ids["sounds"].values())
        self.report["unresolved_music_aliases"] = [entry for entry in unresolved_music if entry["id"] not in recovered_sound_ids]
        self.report["synthetic_ids"] = {}
        for category, resources in self.resources.items():
            synthetic = []
            for offset, name in enumerate(sorted(resources)):
                if name not in self.ids[category]:
                    # Do not pretend to know a missing original ID. Named room
                    # assets still work; raw unresolved numeric uses are audited.
                    self.ids[category][name] = 20000 + offset
                    synthetic.append(name)
            self.report["synthetic_ids"][category] = synthetic
        pathnames = {}
        for _, _, code in self.codes:
            for index, name in re.findall(r"(\d+)\s*/\*\s*(path_\w+)\s*\*/", code):
                if not name.startswith("path_action_"):
                    pathnames[int(index)] = name
        self.paths = pathnames
        self.path_points = self.load_path_data(pathnames)
        self.report["recovered_paths"] = [{"id": i, "name": pathnames[i]} for i in sorted(self.path_points)]
        self.report["missing_paths"] = [{"id": i, "name": n} for i, n in sorted(pathnames.items())
                                        if i not in self.path_points]
        if pathnames and self.report["missing_paths"]:
            self.report["limitations"].append(
                "Movement paths are absent from this GMX export; the ones without a recovered record in "
                "port/path_data.json make path_start fail visibly instead of inventing cutscene/battle movement.")
        elif self.path_points:
            self.report["limitations"].append(
                "Path point data was recovered from an external GameMaker project (see port/path_data.json "
                "and docs/PATHS.md); playback is validated headlessly, not against the original engine.")
        self.report["limitations"].extend([
            "Not every original numeric asset ID is recoverable; synthetic IDs are used only for otherwise-unidentified named resources.",
            "Steam integration is intentionally disabled. Saves use LÖVE's Android/desktop application save directory.",
            "External sprite replacement files and the unused dfb background are not supplied in this checkout.",
            "Translation coverage is syntactic coverage, not a claim that every route/boss/cutscene is playable.",
        ])

    def load_path_data(self, pathnames: dict) -> dict:
        """Attach recovered movement-path point data, keyed by the original numeric ID.

        ``port/path_data.json`` is written by ``tools/recover_paths.py`` and records the
        upstream project, commit and file behind every path. Referenced names with no
        record stay absent, so ``path_start`` keeps failing visibly instead of walking
        an invented route.
        """
        file = self.root / "port" / "path_data.json"
        if not file.is_file():
            return {}
        document = json.loads(self.read(file))
        table = {}
        for index, name in pathnames.items():
            record = (document.get("paths") or {}).get(name) or {}
            points = record.get("points") or []
            if len(points) < 2 or not all(len(point) == 2 for point in points):
                continue
            table[index] = {
                "points": [[float(x), float(y)] for x, y in points],
                "closed": bool(record.get("closed")),
                "kind": int(record.get("kind") or 0),
                "precision": max(1, int(record.get("precision") or 4)),
            }
        self.report["path_provenance"] = {
            "upstream": document.get("upstream"), "ref": document.get("ref"),
            "generated_by": document.get("generated_by"), "generated_on": document.get("generated_on"),
            "referenced": len(pathnames), "with_point_data": len(table),
        }
        return table

    def asset_id(self, category, name):
        return self.ids[category].get(name, -1)

    def check_file(self, path, origin):
        normalized = path.replace("\\", "/")
        if not (self.root / normalized).is_file():
            self.missing.append({"path": normalized, "origin": origin})
        return normalized

    def audit_ast(self, ast, origin):
        slots = {"instance_create": (2, "objects"), "instance_exists": (0, "objects"),
                 "instance_number": (0, "objects"), "instance_find": (0, "objects"),
                 "instance_change": (0, "objects"), "instance_position": (2, "objects"),
                 "collision_point": (2, "objects"), "collision_rectangle": (4, "objects"),
                 "collision_line": (4, "objects"), "collision_circle": (3, "objects"),
                 "script_execute": (0, "scripts"), "draw_set_font": (0, "fonts"),
                 "room_goto": (0, "rooms"), "room_set_persistent": (0, "rooms"),
                 "sprite_replace": (0, "sprites"), "sprite_get_width": (0, "sprites"),
                 "sprite_get_height": (0, "sprites"), "sprite_exists": (0, "sprites"),
                 "snd_play": (0, "sounds"), "snd_stop": (0, "sounds"),
                 "caster_play": (0, "sounds"), "caster_play_l": (0, "sounds"), "caster_loop": (0, "sounds")}
        for n in walk(ast):
            if n[0] == "call" and n[1][0] == "name":
                name, args = n[1][1], n[2]
                self.calls[name] += 1
                if name in ("sprite_replace", "background_add", "file_text_open_read"):
                    slot_index = 1 if name == "sprite_replace" else 0
                    if len(args) > slot_index:
                        filename = args[slot_index]
                        if filename[0] == "binary" and filename[1] == "+" and filename[2] == ("name", "working_directory"):
                            filename = filename[3]
                        if filename[0] == "string":
                            file = filename[1].replace("\\", "/")
                            if (file.startswith(("external/", "data/")) or file in ("testlines.txt", "credits.txt")) and not (self.root / file).exists():
                                self.external_files[file].add(origin)
                setup_args = args if name == "SCR_TEXTSETUP" else args[1:] if name == "script_execute" and args and numeric(args[0]) == self.ids["scripts"].get("SCR_TEXTSETUP") else None
                if setup_args and len(setup_args) >= 8:
                    for slot_index, category in [(0, "fonts"), (7, "sounds")]:
                        index = numeric(setup_args[slot_index])
                        if isinstance(index, int) and index >= 0:
                            self.references.append((category, index, origin, "SCR_TEXTSETUP"))
                if name.startswith("keyboard_") and not name.startswith("keyboard_multicheck") and args:
                    index = numeric(args[0])
                    if isinstance(index, int):
                        self.keys[index].add(origin)
                slot = slots.get(name)
                if name.startswith("draw_sprite"):
                    slot = (0, "sprites")
                if name.startswith("draw_background"):
                    slot = (0, "backgrounds")
                if slot and len(args) > slot[0]:
                    index = numeric(args[slot[0]])
                    if isinstance(index, int) and index >= 0 and index < 100000:
                        self.references.append((slot[1], index, origin, name))
            elif n[0] == "with":
                index = numeric(n[1])
                if isinstance(index, int) and 0 <= index < 100000:
                    self.references.append(("objects", index, origin, "with"))
            elif n[0] == "assign" and n[2] in (("name", "sprite_index"), ("name", "mask_index")):
                index = numeric(n[3])
                if isinstance(index, int) and index >= 0:
                    self.references.append(("sprites", index, origin, n[2][1]))

    def write(self, relative, text):
        path = self.output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if relative not in self.written:
            self.written.append(relative)

    def emit(self):
        code = {}
        total_lines, nonempty = 0, 0
        for key, origin, source in self.codes:
            total_lines += len(source.splitlines())
            nonempty += bool(source.strip())
            try:
                if key.startswith("scripts/"):
                    source = repair_script(key.split("/", 1)[1], source, self.report)
                elif key.startswith("objects/"):
                    parts = key.split("/")
                    source = repair_object_event(parts[1], parts[2], source, self.report)
                # Three decompiled dialogue writers contain a malformed quoted
                # backslash. Restrict this repair to the exact known token and
                # objects; chr(92) preserves the intended text-control marker.
                if key.split("/")[1] in ("OBJ_WRITER", "OBJ_INSTAWRITER", "obj_flowey_writer"):
                    broken = r'''"\" + chr(ord('"'))'''
                    source, repairs = re.subn(re.escape(broken) + r'(?:\s*\+\s*" \+ ")?', 'chr(92)', source)
                    if repairs:
                        self.report["repairs"].append(f"{origin}: repaired {repairs} malformed backslash comparisons to chr(92).")
                if key == "scripts/SCR_TEXT" and 'fileid= file_text_open_read("testlines.txt");' in source:
                    source = source.replace('fileid= file_text_open_read("testlines.txt");', 'if(!file_exists("testlines.txt")) exit;\n        fileid= file_text_open_read("testlines.txt");')
                    self.report["repairs"].append("SCR_TEXT case 0: guard the absent optional testlines.txt debug override; retain the inline dialogue already prepared by callers.")
                compiled, ast = compile_gml(source, origin)
                self.audit_ast(ast, origin)
                code[key] = compiled
            except (CompileError, RecursionError) as exc:
                self.errors.append({"source": origin, "error": str(exc)})
        if self.errors:
            self.report["compile_errors"] = self.errors
            self.write("conversion-report.json", json.dumps(self.report, indent=2) + "\n")
            raise CompileError(f"{len(self.errors)} source units failed; see {self.output}/conversion-report.json")
        for name in self.resources["scripts"]:
            self.write(f"scripts/{name}.lua", code[f"scripts/{name}"])
        for name, (_, obj) in self.resources["objects"].items():
            meta = child_fields(obj, "solid visible depth persistent")
            meta.update(name=name, id=self.ids["objects"][name],
                        sprite=self.asset_id("sprites", obj.findtext("spriteName")),
                        mask=self.asset_id("sprites", obj.findtext("maskName")),
                        parent=self.asset_id("objects", obj.findtext("parentName")))
            out = ["-- Generated object metadata and every original event.", "local object = " + lua(meta), "object.events = {}"]
            for event in obj.findall("events/event"):
                original_key = event.get("eventtype") + ":" + event.get("enumb", event.get("ename", "0"))
                runtime_key = event.get("eventtype") + ":" + str(self.ids["objects"][event.get("ename")]) if event.get("eventtype") == "4" else original_key
                fn = code[f"objects/{name}/{original_key}"]
                out.append(fn.split("\n", 1)[0])
                out.append(f"object.events[{quote(runtime_key)}] = " + fn.split("return ", 1)[1].rstrip())
            out.append("return object\n")
            self.write(f"objects/{name}.lua", "\n".join(out))
        for name, (_, room) in self.resources["rooms"].items():
            meta = child_fields(room, "width height speed persistent colour showcolour enableViews")
            meta.update(id=self.ids["rooms"][name], name=name)
            meta["backgrounds"] = []
            for b in room.findall("backgrounds/background"):
                data = fields(b)
                data["index"] = self.asset_id("backgrounds", data.pop("name", ""))
                meta["backgrounds"].append(data)
            meta["views"] = [fields(v) for v in room.findall("views/view")]
            meta["instances"] = []
            for inst in room.findall("instances/instance"):
                data = fields(inst)
                data["object"] = self.ids["objects"][data.pop("objName")]
                data["id"] = int(data["name"].split("_")[1])
                data.pop("code", None)
                meta["instances"].append(data)
            if name in ("room_area1", "room_area1_2"):
                # These two room exports lack the ground/entrance backdrop.
                # Reconstruct only the known sparse versions, never overpaint a
                # future complete export or change room collision/game logic.
                expected_hashes = {'room_area1': 'ff40c1898c1412e881fc9f5b5490017c0906d9da6da2f84c853d68d5788f136e', 'room_area1_2': 'ed4dedfff917d5ae1d979284686a1d3b058ca1bcbc8e1262110d0d2a35422b79'}
                actual_hash = hashlib.sha256(ET.tostring(room, encoding="utf-8")).hexdigest()
                if actual_hash != expected_hashes[name] or any(b["visible"] for b in meta["backgrounds"]):
                    raise CompileError(f"{name}: room data changed; review reconstructed opening backdrop")
                meta["port_backdrop"] = name
                self.report.setdefault("reconstructed_backdrops", []).append({"room": name, "basis": "user reference screenshots, original room bounds/door positions, supplied palette; original flower tiles retained"})
            meta["tiles"] = []
            for t in room.findall("tiles/tile"):
                data = fields(t)
                data["background"] = self.asset_id("backgrounds", data.pop("bgName"))
                meta["tiles"].append(data)
            out = ["-- Generated room, preserving original instance IDs and tile order.", "local room = " + lua(meta)]
            if room.findtext("code", "").strip():
                out.append("room.create = " + code[f"rooms/{name}/create"].split("return ", 1)[1])
            for i, inst in enumerate(room.findall("instances/instance"), 1):
                if inst.get("code", "").strip():
                    out.append(f"room.instances[{i}].create = " + code[f"rooms/{name}/{inst.get('name')}"].split("return ", 1)[1])
            out.append("return room\n")
            self.write(f"rooms/{name}.lua", "\n".join(out))
        asset_modules = []
        for category in ("sprites", "backgrounds", "sounds", "fonts"):
            chunk, chunkno = {}, 0
            for name, (path, asset) in self.resources[category].items():
                data = {"name": name}
                prefix = path.parent.relative_to(self.root).as_posix() + "/"
                if category == "sprites":
                    data.update(child_fields(asset, "width height xorig yorigin colkind coltolerance sepmasks bboxmode bbox_left bbox_right bbox_top bbox_bottom"))
                    data["frames"] = [self.check_file(prefix + f.text, name) for f in asset.findall("frames/frame")]
                elif category == "backgrounds":
                    data.update(child_fields(asset, "width height"))
                    data["file"] = self.check_file(prefix + asset.findtext("data"), name)
                elif category == "sounds":
                    audio_path = "sound/audio/" + asset.findtext("data")
                    if not (self.root / audio_path).exists():
                        candidates = list((self.root / "sound/audio").glob(Path(audio_path).stem + ".*"))
                        if len(candidates) == 1 and candidates[0].suffix.lower() in (".ogg", ".wav", ".mp3"):
                            repaired = candidates[0].relative_to(self.root).as_posix()
                            self.report["repairs"].append(f"{name}: corrected mismatched audio extension {audio_path} to existing {repaired}.")
                            audio_path = repaired
                    data["file"] = self.check_file(audio_path, name)
                    data["volume"] = value(asset.findtext("volume/volume", "1"))
                else:
                    data["file"] = self.check_file(prefix + asset.findtext("image"), name)
                    glyphs = asset.findall("glyphs/glyph")
                    mangled = all(g.get("character") == "32" + str(i) for i, g in enumerate(glyphs))
                    data["glyphs"] = {}
                    for i, glyph in enumerate(glyphs):
                        g = fields(glyph)
                        character = 32 + i if mangled else int(g.pop("character"))
                        g.pop("character", None)
                        data["glyphs"][character] = g
                    data["height"] = max((int(g.get("h")) for g in glyphs), default=16)
                    if mangled:
                        self.report["repairs"].append(f"{name}: repaired decompiler glyph labels '32' + index to ASCII 32 + index.")
                chunk[self.ids[category][name]] = data
                if len(chunk) >= 64:
                    module = f"assets/{category}_{chunkno}"
                    self.write(module + ".lua", "return " + lua(chunk) + "\n")
                    asset_modules.append((category, module))
                    chunk, chunkno = {}, chunkno + 1
            if chunk:
                module = f"assets/{category}_{chunkno}"
                self.write(module + ".lua", "return " + lua(chunk) + "\n")
                asset_modules.append((category, module))
        manifest = {"format": 1, "source_digest": self.digest.hexdigest(), "names": {},
                    "objects": {}, "scripts": {}, "rooms": {}, "room_order": self.room_order,
                    "paths": self.paths, "path_points": self.path_points,
                    "missing_rooms": self.missing_rooms, "keys": sorted(self.keys),
                    "asset_modules": [{"kind": k, "module": "generated." + m.replace("/", ".")} for k, m in asset_modules]}
        for category, mapping in self.ids.items():
            for name, index in mapping.items():
                manifest["names"][name] = index
                if category in ("objects", "rooms", "scripts"):
                    manifest[category][index] = "generated." + category + "." + name
        for index, name in self.paths.items():
            manifest["names"][name] = index
        self.write("manifest.lua", "-- Recovered IDs, never alphabetical resource indices.\nreturn " + lua(manifest) + "\n")
        refs = defaultdict(lambda: {"uses": 0, "examples": []})
        idsets = {c: set(m.values()) for c, m in self.ids.items()}
        for category, index, origin, use in self.references:
            if index not in idsets[category]:
                record = refs[(category, index)]
                record["uses"] += 1
                if len(record["examples"]) < 3:
                    record["examples"].append(f"{origin}: {use}")
        self.report.update(
            source_digest=self.digest.hexdigest(), resources={c: len(v) for c, v in self.resources.items()},
            code_units=len(self.codes), nonempty_code_units=nonempty, source_lines=total_lines,
            converted_code_units=len(code), compile_errors=[], missing_asset_files=self.missing,
            unresolved_numeric_references=[dict(category=c, id=i, **r) for (c, i), r in sorted(refs.items())],
            builtin_calls={k: v for k, v in sorted(self.calls.items()) if k not in self.resources["scripts"]},
            input_keys=[{"code": k, "sources": sorted(s)} for k, s in sorted(self.keys.items())],
            id_evidence=self.evidence,
            missing_external_files=[{"path": name, "sources": sorted(sources)} for name, sources in sorted(self.external_files.items())],
            mouse_events=[{"source": source, "event": key.rsplit("/", 1)[-1]} for key, source, _ in self.codes if key.startswith("objects/") and key.rsplit("/", 1)[-1].startswith("6:")],
            generated_files=sorted(self.written + ["conversion-report.json"]),
        )
        self.write("conversion-report.json", json.dumps(self.report, indent=2, ensure_ascii=False) + "\n")

    def run(self):
        self.collect()
        self.recover_ids()
        self.emit()
        return self.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "generated")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or output.is_relative_to(ROOT / ".git") or ROOT.is_relative_to(output):
        parser.error("output must be a dedicated generated directory, never the repository or its parent")
    output.mkdir(parents=True, exist_ok=True)
    try:
        report = Converter(ROOT, output).run()
    except (CompileError, OSError, ET.ParseError) as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1
    print(f"Converted {report['converted_code_units']:,}/{report['code_units']:,} code units ({report['source_lines']:,} GML lines).")
    print(f"{len(report['missing_paths'])} missing path resources; {len(report['unresolved_numeric_references'])} unresolved numeric asset references.")
    print(f"Report: {output / 'conversion-report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
