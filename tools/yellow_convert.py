#!/usr/bin/env python3
"""Convert the pinned Undertale Yellow decompilation into this port's formats.

Yellow is a GameMaker Studio 2 project; ``tools/convert.py`` reads GameMaker 1.4
``.gmx``. This driver is the Studio 2 front end, and it is deliberately staged so
each piece of ``docs/YELLOW.md`` lands on its own, tested:

    --stage assets    every sprite, sound, font and tileset texture (piece 1)
    --stage scripts   every Yellow script, name-resolved      (piece 2, not yet)
    --stage objects   every Yellow object and event           (piece 3, not yet)
    --stage rooms     every Yellow room, tile layer and path   (piece 4, not yet)

Output goes to ``generated/yellow/`` (git-ignored, rebuilt on demand) and always
includes a report: what was converted, which IDs came from which pinned record,
and every GameMaker Studio 2 fact this port had to reinterpret. A stage that is
not implemented yet says so and exits non-zero; it never emits a half-converted
game that looks complete.

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
from yellow.assets import AssetConverter  # noqa: E402
from yellow.gms2 import GMS2Error  # noqa: E402
from yellow.registry import YELLOW_BASE, Registry, collisions  # noqa: E402

STAGES = ("assets", "scripts", "objects", "rooms")
PIECE = {"scripts": 2, "objects": 3, "rooms": 4}
ASSET_KINDS = ("sprites", "sounds", "fonts", "backgrounds")


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
                  prefix: str = "generated.yellow") -> str:
    manifest = {
        "format": 1,
        "game": "undertale-yellow",
        "source": {"upstream": provenance.get("upstream"), "ref": provenance.get("ref"),
                   "fork_of": provenance.get("fork_of"), "gamemaker": provenance.get("gamemaker_version")},
        "yellow_base": YELLOW_BASE,
        "names": names,
        "objects": {}, "scripts": {}, "rooms": {}, "room_order": [],
        "paths": {}, "path_points": {}, "missing_rooms": {}, "keys": [],
        "asset_modules": [{"kind": kind, "module": prefix + "." + module.replace("/", ".")}
                          for kind, module in modules],
    }
    return ("-- Recovered Yellow asset IDs, never alphabetical indices.\n"
            "-- Partial manifest: piece 1 of docs/YELLOW.md converts assets only.\n"
            "return " + lua(manifest) + "\n")


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", choices=STAGES, default="assets")
    parser.add_argument("--source", type=Path, default=ROOT / "yellow_src", help="fetched Yellow project tree")
    parser.add_argument("--output", type=Path, default=ROOT / "generated" / "yellow")
    args = parser.parse_args()
    if args.stage != "assets":
        print(f"--stage {args.stage} is piece {PIECE[args.stage]} of docs/YELLOW.md and is not implemented yet.",
              file=sys.stderr)
        return 2
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
        report = stage_assets(registry, provenance, Writer(output), ROOT)
    except (GMS2Error, OSError, ValueError) as exc:
        print(f"Yellow conversion failed: {exc}", file=sys.stderr)
        return 1
    assets = report["assets"]
    print("Converted Yellow assets: " + ", ".join(f"{kind}={count}" for kind, count in sorted(assets["converted"].items())))
    print(f"Recovered IDs from two pinned records: {assets['recovered_ids']}")
    print(f"Missing asset files: {len(assets['missing_asset_files'])}; "
          f"unrecoverable pinned IDs: {len(assets['unrecoverable_ids'])}; findings: {assets['findings']}")
    print(f"Report: {output / 'conversion-report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
