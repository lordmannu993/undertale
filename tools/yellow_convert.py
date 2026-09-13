#!/usr/bin/env python3
"""Convert the pinned Undertale Yellow decompilation into this port's formats.

Yellow is a GameMaker Studio 2 project; ``tools/convert.py`` reads GameMaker 1.4
``.gmx``. This driver is the Studio 2 front end, and it is deliberately staged so
each piece of ``docs/YELLOW.md`` lands on its own, tested:

    --stage assets    every sprite, sound, font and tileset texture (piece 1)
    --stage scripts   every Yellow script, name-resolved      (piece 2)
    --stage objects   every Yellow object and event           (piece 3)
    --stage rooms     every Yellow room, tile layer and path   (piece 4)

Output goes to ``generated/yellow/`` (git-ignored, rebuilt on demand) and always
includes a report: what was converted, which IDs came from which pinned record,
and every GameMaker Studio 2 fact this port had to reinterpret. Asset conversion
is piece 1, script conversion builds on it for piece 2 and object conversion on
both for piece 3. Room conversion builds on all three stages; unsupported features remain named stops.

Usage::

    python3 tools/fetch_yellow.py            # once, needs network
    python3 tools/yellow_convert.py --stage assets
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from convert import lua  # noqa: E402 - same serialiser the .gmx converter uses
from gml import CompileError, walk  # noqa: E402
from gml2 import compile_gml2_functions, function_expression  # noqa: E402
from yellow.assets import AssetConverter  # noqa: E402
from yellow.gms2 import GMS2Error  # noqa: E402
from yellow.objects import ObjectConverter
from yellow.rooms import RoomConverter  # noqa: E402
from yellow.registry import YELLOW_BASE, Registry, collisions  # noqa: E402

STAGES = ("assets", "scripts", "objects", "rooms")
PIECE = {"scripts": 2, "objects": 3, "rooms": 4}
ASSET_KINDS = ("sprites", "sounds", "fonts", "backgrounds")
RESOURCE_KINDS = ("sprites", "objects", "rooms", "sounds", "fonts", "backgrounds", "paths")


class Writer:
    """Deterministic output: sorted keys, no timestamps, one asset chunk per 64."""

    def __init__(self, output: Path):
        self.output = output
        self.written: list[str] = []

    def write(self, relative: str, text: str) -> None:
        path = self.output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if relative not in self.written:
            self.written.append(relative)

    def asset_chunks(self, kind: str, records: dict[int, dict]) -> list[str]:
        modules = []
        ordered = [records[key] for key in sorted(records)]
        for index in range(0, max(1, len(ordered)), 64):
            chunk = {record_id: records[record_id] for record_id in sorted(records)[index:index + 64]}
            module = f"assets/{kind}_{index // 64}"
            self.write(module + ".lua", f"-- Yellow {kind}, IDs are {YELLOW_BASE} + the pinned Asset_Order ID.\nreturn "
                       + lua(chunk) + "\n")
            modules.append(module)
        return modules


def manifest_text(registry: Registry, provenance: dict, modules: list[tuple[str, str]], names: dict[str, int],
                  prefix: str = "generated.yellow", scripts: dict | None = None,
                  yellow_names: dict | None = None, objects: dict | None = None,
                  keys: list[int] | None = None, mouse_events: list[int] | None = None, rooms=None) -> str:
    manifest = {
        "format": 1,
        "game": "undertale-yellow",
        "source": {"upstream": provenance.get("upstream"), "ref": provenance.get("ref"),
                   "fork_of": provenance.get("fork_of"), "gamemaker": provenance.get("gamemaker_version")},
        "yellow_base": YELLOW_BASE,
        "names": names,
        "yellow_names": yellow_names or {category: registry.names(category) for category in RESOURCE_KINDS},
        "objects": objects or {}, "scripts": scripts or {}, "rooms": {}, "room_order": [],
        "paths": {}, "path_points": {}, "missing_rooms": {}, "keys": sorted(keys or []),
        # Per-instance mouse subtypes the converted objects actually use; the
        # runtime skips the pointer test entirely when nothing needs it.
        "mouse_events": sorted(mouse_events or []),
        "asset_modules": [{"kind": kind, "module": prefix + "." + module.replace("/", ".")}
                          for kind, module in modules],
    }
    if rooms is not None:
        manifest.update(rooms=rooms.modules, room_order=rooms.order, paths=rooms.paths, path_points=rooms.path_points)
    if objects is not None:
        status = "-- Piece 3 manifest: assets, name-resolved GMS2 scripts and every Yellow object.\n"
    elif scripts is not None:
        status = "-- Piece 2 manifest: assets plus name-resolved GMS2 scripts.\n"
    else:
        status = "-- Partial manifest: piece 1 of docs/YELLOW.md converts assets only.\n"
    return ("-- Recovered Yellow asset IDs, never alphabetical indices.\n"
            + status + "return " + lua(manifest) + "\n")


def stage_assets(registry: Registry, provenance: dict, writer: Writer, root: Path = ROOT,
                 repository: Path = ROOT, prefix: str = "generated.yellow") -> dict:
    """Convert every asset category and write the partial manifest plus its report.

    ``root`` is what emitted asset paths are relative to (the repository, so the
    packaged archive resolves them); ``repository`` is where Undertale's own
    project file lives, for the cross-game name-collision table.
    """
    converter = AssetConverter(registry, root, provenance)
    records = converter.run()
    modules: list[tuple[str, str]] = []
    for kind in ASSET_KINDS:
        for module in writer.asset_chunks(kind, records[kind]):
            modules.append((kind, module))
    names: dict[str, int] = {}
    conflicts = registry.name_conflicts(ASSET_KINDS)
    if conflicts:
        raise GMS2Error("Yellow reuses one asset name in several categories, which GameMaker Studio 2 "
                        f"forbids; the merged name map would be ambiguous: {dict(list(conflicts.items())[:5])}")
    for category in ASSET_KINDS:
        names.update(registry.names(category))
    writer.write("manifest.lua", manifest_text(registry, provenance, modules, names, prefix))
    report = {
        "format": 1,
        "stage": "assets",
        "status": "experimental; Yellow asset conversion is not a claim that Yellow is playable",
        "source": {"upstream": provenance.get("upstream"), "ref": provenance.get("ref"),
                   "fork_of": provenance.get("fork_of"), "gamemaker": provenance.get("gamemaker_version"),
                   "id_sources": [str(Path("Undertale_Yellow.yyp")), str(Path("notes/Asset_Order/Asset_Order.txt"))]},
        "yellow_base": YELLOW_BASE,
        "game_speed": converter.game_speed,
        "registry": registry.report(),
        "assets": converter.summary(),
        "name_collisions_with_undertale": collisions(registry, repository),
        "generated_files": sorted(writer.written + ["conversion-report.json"]),
        "limitations": [
            "Piece 1 converts assets only: no Yellow script, object or room is executable yet.",
            "collisionKind 4 (rotated rectangle) has no GameMaker 1.4 mask; those sprites keep a precise mask "
            "and the original value stays in the record's yellow.collision_kind.",
            "playbackSpeedType 0 (frames per second) is converted to image_speed with Yellow's own 30 FPS game speed.",
            "Nine-slice sprites are converted as ordinary sprites; the runtime has no nine-slice drawing.",
            "Pinned IDs with no folder upstream are listed as unrecoverable and are not converted; a reference to "
            "one stays an unresolved asset ID instead of being pointed at a substitute.",
            "Font kerning pairs, shaders, sequences and GMLive are not converted by this piece.",
            "Yellow assets are referenced in yellow_src/, which is fetched from the pinned commit and never committed.",
        ],
    }
    writer.write("conversion-report.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report



class ScriptConverter:
    """Convert Yellow's on-disk GMS2 script resources by name.

    Studio 2 does not give the decompiler a stable script index.  Asset names
    still use the recovered ``YELLOW_BASE`` IDs, while script calls remain
    explicit names in the manifest.  This avoids treating the 2,345-name
    decompiler audit list (which includes synthetic ``gml_Script_*`` entries)
    as 1,155 executable resources.
    """

    def __init__(self, registry: Registry, root: Path, provenance: dict, prefix: str):
        self.registry = registry
        self.source = registry.source
        self.root = root
        self.provenance = provenance
        self.prefix = prefix
        self.script_names = list(registry.project_order.get("scripts", []))
        self.resolver: dict[str, int | str] = {}
        for category in RESOURCE_KINDS:
            # GMS2 has no stable runtime script index.  Its script section in
            # Asset_Order also contains synthetic gml_Script_* audit entries,
            # so never feed that numeric list to the expression resolver.
            if category != "scripts":
                self.resolver.update(registry.names(category))
        # A script reference is a name, not an invented numeric ID.  The
        # emitter writes these as string constants when they occur as values
        # (script_execute(foo)); ordinary calls stay name-resolved in Runtime.
        for name in self.script_names:
            self.resolver[name] = name
        self.records: dict[str, dict] = {}
        self.calls: dict[str, int] = {}
        self.rewrites: dict[str, int] = {}
        self.unsupported: list[dict] = []
        self.compile_errors: list[dict] = []
        self.total_lines = 0
        self.function_count = 0

    def _note_calls(self, ast) -> None:
        for node in walk(ast):
            if node[0] == "call" and node[1][0] == "name":
                name = node[1][1]
                self.calls[name] = self.calls.get(name, 0) + 1
            if node[0] == "name" and node[1] in self.resolver:
                self.rewrites[node[1]] = self.rewrites.get(node[1], 0) + 1

    @staticmethod
    def _unsupported_module(name: str, reason: str, functions: list[str]) -> str:
        message = lua(f"{name}: {reason}")
        fn = f"function(R, E) R:unsupported({lua(name)}, {message}) end"
        if len(functions) == 1:
            return "-- Explicit compatibility stop for an unsupported Studio 2 subsystem.\nreturn " + fn + "\n"
        return "-- Explicit compatibility stops for an unsupported Studio 2 subsystem.\nlocal exports={}\n" + \
            "\n".join(f"exports[{lua(function)}]={fn}" for function in functions) + "\nreturn exports\n"

    def convert_one(self, name: str, writer: Writer) -> None:
        path = self.source / "scripts" / name / f"{name}.gml"
        if not path.is_file():
            raise GMS2Error(f"scripts/{name}: missing GMS2 source file")
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        self.total_lines += len(source.splitlines())
        module = f"scripts/{name}"
        # GMLive is deliberately not emulated.  It is a Studio extension and
        # docs/YELLOW.md requires its use to stop visibly rather than becoming
        # a no-op.  Keep every named export addressable for a precise stop.
        if name.startswith("GMLive"):
            import re
            functions = re.findall(r"(?m)^\s*function\s+([A-Za-z_]\w*)\s*\(", source)
            exports = functions or [name]
            text = self._unsupported_module("GMLive", "GMLive/Steam live editing is not supported", exports)
            writer.write(module + ".lua", text)
            self.records[name] = {"module": self.prefix + "." + module.replace("/", "."),
                                  "exports": exports, "status": "explicit-stop"}
            self.unsupported.append({"script": name, "feature": "GMLive", "exports": exports,
                                     "reason": "Studio live editing has no GameMaker 1.4 runtime equivalent"})
            return
        try:
            records, meta = compile_gml2_functions(source, str(path), self.resolver)
            self.function_count += len(records)
            for _, _, ast in records:
                self._note_calls(ast)
            expressions = [(function, function_expression(code)) for function, code, _ in records]
            if len(expressions) == 1:
                text = "-- Generated from GMS2\nreturn " + expressions[0][1] + "\n"
            else:
                text = "-- Generated exports from GMS2\nlocal exports={}\n" + \
                    "\n".join(f"exports[{lua(function)}]={expression}" for function, expression in expressions) + \
                    "\nreturn exports\n"
            writer.write(module + ".lua", text)
            self.records[name] = {"module": self.prefix + "." + module.replace("/", "."),
                                  "exports": [function for function, _ in expressions],
                                  "enums": sorted(meta.get("enums", {})), "status": "converted"}
        except (CompileError, RecursionError) as exc:
            self.compile_errors.append({"script": name, "source": str(path), "error": str(exc)})

    def run(self, writer: Writer) -> dict:
        for name in self.script_names:
            self.convert_one(name, writer)
        # All on-disk project resources must have a module.  This is separate
        # from compilation errors so a missing source can never look converted.
        missing = sorted(set(self.script_names) - set(self.records))
        if self.compile_errors:
            raise CompileError(f"{len(self.compile_errors)} Yellow scripts failed; see the conversion report")
        if missing:
            raise GMS2Error(f"Yellow scripts without generated modules: {missing[:5]}")
        modules: dict[str, str | dict] = {}
        for name, record in self.records.items():
            path = record["module"]
            exports = record["exports"]
            if len(exports) == 1 and exports[0] == "__main__":
                modules[name] = path
            elif len(exports) == 1:
                modules[name] = {"module": path, "export": exports[0]}
                modules.setdefault(exports[0], {"module": path, "export": exports[0]})
            else:
                for export in exports:
                    modules[export] = {"module": path, "export": export}
                # A resource name is still callable even when its file contains
                # several decompiler functions; use the first named export only
                # for the file-level alias.
                modules.setdefault(name, {"module": path, "export": exports[0]})
        return {
            "converted": len(self.records), "functions": self.function_count,
            "source_lines": self.total_lines, "compile_errors": self.compile_errors,
            "unsupported": self.unsupported,
            "calls": dict(sorted(self.calls.items())),
            "builtin_calls": {name: self.calls[name] for name in sorted(self.calls) if name not in modules},
            "name_rewrites": dict(sorted(self.rewrites.items())),
            "script_modules": modules,
            "script_names": self.script_names,
        }


def asset_module_pairs(report: dict) -> list[tuple[str, str]]:
    """The asset modules an earlier stage emitted, taken from its own report.

    ``stage_assets`` already wrote every module and listed them; rebuilding the
    list from the serialized manifest text would only risk the two disagreeing.
    """
    pairs = []
    for item in report.get("generated_files", []):
        if item.startswith("assets/") and item.endswith(".lua"):
            pairs.append((item.split("/", 1)[1].split("_", 1)[0], item[:-4]))
    return pairs


def stage_scripts(registry: Registry, provenance: dict, writer: Writer, root: Path = ROOT,
                  repository: Path = ROOT, prefix: str = "generated.yellow") -> dict:
    """Build piece 1 assets plus every GMS2 script for piece 2."""
    asset_report = stage_assets(registry, provenance, writer, root, repository, prefix)
    converter = ScriptConverter(registry, root, provenance, prefix)
    scripts = converter.run(writer)
    asset_names = {category: registry.names(category) for category in RESOURCE_KINDS}
    manifest = manifest_text(registry, provenance, asset_module_pairs(asset_report),
                             {name: value for category in ASSET_KINDS for name, value in registry.names(category).items()},
                             prefix, scripts=scripts["script_modules"], yellow_names=asset_names)
    writer.write("manifest.lua", manifest)
    report = dict(asset_report)
    report["stage"] = "scripts"
    report["status"] = "experimental; Yellow assets and scripts are converted, but objects and rooms are not executable yet"
    report["scripts"] = {key: value for key, value in scripts.items() if key != "script_modules"}
    # The manifest's script table, kept in the report so a later stage can
    # rewrite the manifest without re-deriving it from generated text.
    report["script_modules"] = scripts["script_modules"]
    report["generated_files"] = sorted(writer.written + ["conversion-report.json"])
    report["limitations"] = [
        limitation for limitation in report.get("limitations", [])
        if not limitation.startswith("Piece 1 converts assets only")
    ] + [
        "Piece 2 converts scripts only: Yellow objects, events and rooms remain unavailable until pieces 3 and 4.",
        "GMS2 script names are resolved by name; the decompiler's synthetic gml_Script_* audit entries are not executable resources.",
        "GMLive scripts are emitted as explicit compatibility stops because live editing has no safe Studio 1.4 equivalent.",
        "GMS2 builtins without a handler remain named Runtime:unsupported stops; no call is silently discarded.",
    ]
    writer.write("conversion-report.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def stage_objects(registry: Registry, provenance: dict, writer: Writer, root: Path = ROOT,
                  repository: Path = ROOT, prefix: str = "generated.yellow") -> dict:
    """Build pieces 1-2, then every Yellow object and event for piece 3."""
    script_report = stage_scripts(registry, provenance, writer, root, repository, prefix)
    converter = ObjectConverter(registry, root, provenance, prefix)
    objects = converter.run(writer)
    manifest = manifest_text(
        registry, provenance, asset_module_pairs(script_report),
        {name: value for category in ASSET_KINDS for name, value in registry.names(category).items()},
        prefix, scripts=script_report["script_modules"],
        yellow_names={category: registry.names(category) for category in RESOURCE_KINDS},
        objects=converter.modules, keys=sorted(converter.keys),
        mouse_events=sorted(converter.mouse_subtypes))
    writer.write("manifest.lua", manifest)
    report = dict(script_report)
    report["stage"] = "objects"
    report["status"] = ("experimental; Yellow assets, scripts and objects are converted, "
                        "but no Yellow room exists yet, so none of it runs in a room")
    report["objects"] = objects
    report["generated_files"] = sorted(writer.written + ["conversion-report.json"])
    report["limitations"] = [
        limitation for limitation in report.get("limitations", [])
        if not limitation.startswith("Piece 2 converts scripts only")
    ] + [
        "Piece 3 converts objects only: Yellow rooms, tile layers, backgrounds and paths are piece 4, so no "
        "Yellow object is ever placed in a room yet.",
        "GameMaker Studio 2 has no per-object depth; every converted object carries depth 0 and records "
        "yellow.depth_source, and piece 4 assigns each instance the depth of the room layer it sits on.",
        "Physics objects are converted with their whole Box2D record in yellow.physics, and Runtime:create "
        "stops with the object's name: this runtime has no physics engine, and a silently motionless seesaw "
        "would be worse than an error.",
        "Yellow's Async HTTP event (GMLive's poll) and its Broadcast Message events (sprite frame events) are "
        "converted and listed per object, but nothing dispatches them.",
        "Clean Up events run when an instance is destroyed and when a non-persistent instance is dropped on a "
        "room change; persistent instances keep GameMaker's rule of no Create/Destroy across rooms.",
        "Draw Begin/Draw/Draw End run as three passes over instances in depth order, as GameMaker does; tiles "
        "keep their own interleaved pass until piece 4 converts Yellow's tile layers.",
    ]
    writer.write("conversion-report.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def stage_rooms(registry: Registry, provenance: dict, writer: Writer, root: Path = ROOT,
                repository: Path = ROOT, prefix: str = "generated.yellow") -> dict:
    report = stage_objects(registry, provenance, writer, root, repository, prefix)
    converter = RoomConverter(registry, root, provenance, prefix)
    report["rooms"] = converter.run(writer)
    writer.write("manifest.lua", manifest_text(
        registry, provenance, asset_module_pairs(report),
        {name: value for category in ASSET_KINDS for name, value in registry.names(category).items()},
        prefix, scripts=report["script_modules"],
        objects={registry.merged("objects", name): prefix + ".objects." + name
                 for name in registry.project_order["objects"]},
        keys=report["objects"]["keyboard_keys"], mouse_events=report["objects"]["mouse_subtypes"], rooms=converter))
    report["stage"] = "rooms"
    report["status"] = "experimental room conversion; not a connected or playable Yellow game"
    report["limitations"] = [s for s in report["limitations"]
                              if not s.startswith("Piece 3 converts objects only")]
    report["limitations"].append("Unsupported room features stop before room entry; see rooms.unsupported. "
                                  "Cross-game travel, state, packaging and release remain piece 5.")
    report["generated_files"] = sorted(writer.written)
    writer.write("conversion-report.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", choices=STAGES, default="assets")
    parser.add_argument("--source", type=Path, default=ROOT / "yellow_src", help="fetched Yellow project tree")
    parser.add_argument("--output", type=Path, default=ROOT / "generated" / "yellow")
    args = parser.parse_args()
    provenance_path = ROOT / "port" / "yellow_source.json"
    try:
        provenance = json.loads(provenance_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read {provenance_path}: {exc}", file=sys.stderr)
        return 1
    output = args.output.resolve()
    if output == ROOT or not output.is_relative_to(ROOT) or output.is_relative_to(ROOT / ".git"):
        parser.error("output must be a dedicated generated directory inside the repository, never .git")
    try:
        registry = Registry(args.source.resolve(), provenance)
        writer = Writer(output)
        report = {"scripts": stage_scripts, "objects": stage_objects, "rooms": stage_rooms}.get(args.stage, stage_assets)(
            registry, provenance, writer, ROOT, ROOT)
    except (GMS2Error, CompileError, OSError, ValueError) as exc:
        print(f"Yellow conversion failed: {exc}", file=sys.stderr)
        return 1
    assets = report["assets"]
    print("Converted Yellow assets: " + ", ".join(f"{kind}={count}" for kind, count in sorted(assets["converted"].items())))
    if args.stage in ("scripts", "objects", "rooms"):
        print(f"Converted Yellow GMS2 scripts: {report['scripts']['converted']} resources, "
              f"{report['scripts']['functions']} functions")
        print(f"GMLive explicit stops: {len(report['scripts']['unsupported'])}")
    if args.stage in ("objects", "rooms"):
        objects = report["objects"]
        print(f"Converted Yellow objects: {objects['converted']} objects, {objects['events']} events "
              f"({objects['source_lines']:,} GML lines)")
        print(f"Parents: {objects['with_parent']}; sprites: {objects['with_sprite']}; masks: {objects['with_mask']}; "
              f"collision events: {objects['collision_events']}; physics objects: {len(objects['physics_objects'])}")
        if objects["undispatched_events"]:
            print("Converted but not dispatched: "
                  + ", ".join(f"{name} ({count['objects']} objects)"
                              for name, count in objects["undispatched_events"].items()))
    if args.stage == "rooms":
        print(f"Converted Yellow rooms: {report['rooms']['converted']}; paths: {report['rooms']['paths']}; "
              f"named room feature stops: {len(report['rooms']['unsupported'])}")
    print(f"Recovered IDs from two pinned records: {assets['recovered_ids']}")
    print(f"Missing asset files: {len(assets['missing_asset_files'])}; "
          f"unrecoverable pinned IDs: {len(assets['unrecoverable_ids'])}; findings: {assets['findings']}")
    print(f"Report: {output / 'conversion-report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
