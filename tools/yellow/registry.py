"""Yellow's numeric asset IDs, recovered from two independent pinned records.

Yellow's decompiled GML mostly names its assets (``room_goto(rm_dunes_01)``), but
it also carries raw compiled indices where the decompiler could not guess —
``global.fast_travel_newroom = 56`` in ``obj_fast_travel_menu`` is a room index.
Those numbers only work if this port uses Yellow's *own* ID space, so the IDs are
recovered rather than invented, from two records inside the pinned source:

``Undertale_Yellow.yyp``
    the project's resource order, which is what GameMaker compiled into indices;
``notes/Asset_Order/Asset_Order.txt``
    the decompiler's dump of those same compiled indices.

Both must agree, and the agreement is checked here rather than assumed: the
``.yyp`` sequence filtered to one category has to be exactly the Asset_Order
numbering ``0..N-1`` for that category. If upstream ever reorders one file
without the other, the merge stops with the disagreement named.

Merged IDs are ``YELLOW_BASE + yellow_id`` so Undertale's recovered IDs (which
reach 22 471 with its synthetic band) are never touched.
"""
from __future__ import annotations

from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .gms2 import GMS2Error, read, ref_name

YELLOW_BASE = 1_000_000

#: merged runtime category -> (Yellow folder on disk, Asset_Order section)
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
#: Yellow folders with no compiled ID list at all; they cannot be addressed by ID.
UNNUMBERED = {"sequences": "sequences"}

ASSET_ORDER = Path("notes/Asset_Order/Asset_Order.txt")
PROJECT = Path("Undertale_Yellow.yyp")
SECTION = re.compile(r"-{5,}\s*([A-Za-z]+)\s*-{5,}")
ENTRY = re.compile(r"^(\d+) - (\S+)\s*$", re.M)
COUNTS = re.compile(r"^([A-Za-z]+):\s*(\d+)\s*$", re.M)

UNDERTALE_CATEGORIES = {
    "sprites": ("sprite", ".sprite.gmx"),
    "objects": ("object", ".object.gmx"),
    "rooms": ("room", ".room.gmx"),
    "scripts": ("script", ""),
    "sounds": ("sound", ".sound.gmx"),
    "backgrounds": ("background", ".background.gmx"),
    "fonts": ("font", ".font.gmx"),
}


def parse_asset_order(text: str) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    """Section -> name -> compiled ID, plus the header's own asset counts."""
    declared = {name.lower(): int(value) for name, value in COUNTS.findall(text.split("---------------------")[0])}
    sections: dict[str, dict[str, int]] = {}
    parts = SECTION.split(text)
    for index in range(1, len(parts) - 1, 2):
        name = parts[index].strip().lower()
        entries: dict[str, int] = {}
        for number, asset in ENTRY.findall(parts[index + 1]):
            if asset in entries and entries[asset] != int(number):
                raise GMS2Error(f"{ASSET_ORDER}: duplicate conflicting ID for {name}/{asset}")
            entries[asset] = int(number)
        sections[name] = entries
    if not sections:
        raise GMS2Error(f"{ASSET_ORDER}: no asset sections found")
    return sections, declared


def parse_project_order(source: Path) -> dict[str, list[str]]:
    """The ``.yyp`` resource list, grouped by top-level folder, in file order."""
    project = read(source / PROJECT)
    resources = project.get("resources")
    if not isinstance(resources, list) or not resources:
        raise GMS2Error(f"{PROJECT}: no resource list")
    grouped: dict[str, list[str]] = {}
    for entry in resources:
        reference = (entry or {}).get("id") or {}
        name, path = reference.get("name"), reference.get("path")
        if not isinstance(name, str) or not isinstance(path, str) or "/" not in path:
            raise GMS2Error(f"{PROJECT}: unreadable resource entry {entry!r}")
        grouped.setdefault(path.split("/", 1)[0], []).append(name)
    return grouped


class Registry:
    """Yellow's recovered IDs, the merged ID band, and every discrepancy found."""

    def __init__(self, source: Path, provenance: dict):
        self.source = source
        self.provenance = provenance
        if not (source / PROJECT).is_file() or not (source / ASSET_ORDER).is_file():
            raise GMS2Error(f"{source}: not a fetched Yellow source tree; run tools/fetch_yellow.py")
        order_text = (source / ASSET_ORDER).read_text(encoding="utf-8", errors="replace")
        self.sections, self.declared_counts = parse_asset_order(order_text)
        self.project_order = parse_project_order(source)
        self.ids: dict[str, dict[str, int]] = {}
        self.findings: list[dict] = []
        self._verify()
        self.disk = {folder: ({p.name for p in (source / folder).iterdir() if p.is_dir()}
                              if (source / folder).is_dir() else set())
                     for folder in {folder for folder, _ in CATEGORIES.values()} | set(UNNUMBERED)}
        self._survey_disk()

    # -- verification ----------------------------------------------------
    def _verify(self) -> None:
        for category, (folder, section) in CATEGORIES.items():
            entries = self.sections.get(section)
            if entries is None:
                raise GMS2Error(f"{ASSET_ORDER}: no '{section}' section for {category}")
            numbers = sorted(entries.values())
            if numbers != list(range(len(numbers))):
                gaps = [i for i, n in enumerate(numbers) if n != i][:5]
                raise GMS2Error(f"{category}: Asset_Order IDs are not 0..N-1 (first gaps at {gaps})")
            declared = self.declared_counts.get(section)
            if declared is not None and declared != len(entries):
                raise GMS2Error(f"{category}: header declares {declared} assets, the list holds {len(entries)}")
            documented = self.provenance.get("documented_counts", {}).get(category)
            if documented is not None and documented != len(entries):
                raise GMS2Error(
                    f"{category}: port/yellow_source.json documents {documented} IDs, the pinned list holds {len(entries)}")
            listed = [name for name, _ in sorted(entries.items(), key=lambda kv: kv[1])]
            ordered = [name for name in self.project_order.get(folder, []) if name in entries]
            if ordered != [name for name in listed if name in set(ordered)]:
                first = next((i for i, (a, b) in enumerate(
                    zip(ordered, [n for n in listed if n in set(ordered)])) if a != b), 0)
                raise GMS2Error(
                    f"{category}: {PROJECT} order disagrees with {ASSET_ORDER} at position {first}; "
                    "two pinned records name different IDs, so neither can be trusted")
            only_project = sorted(set(self.project_order.get(folder, [])) - set(entries))
            only_listed = sorted(set(entries) - set(self.project_order.get(folder, [])))
            if only_project or only_listed:
                self.findings.append({"category": category, "finding": "records-cover-different-assets",
                                      "only_in_project": only_project[:20], "only_in_project_count": len(only_project),
                                      "only_in_asset_order": only_listed[:20], "only_in_asset_order_count": len(only_listed)})
            self.ids[category] = dict(entries)

    def _survey_disk(self) -> None:
        for category, (folder, section) in CATEGORIES.items():
            on_disk = self.disk.get(folder, set())
            known = set(self.ids[category])
            missing = sorted(known - on_disk)
            extra = sorted(on_disk - known)
            if missing:
                self.findings.append({"category": category, "finding": "id-without-folder",
                                      "names": missing, "count": len(missing)})
            if extra:
                self.findings.append({"category": category, "finding": "folder-without-id",
                                      "names": extra[:20], "count": len(extra)})
        for name, folder in UNNUMBERED.items():
            self.findings.append({"category": name, "finding": "no-compiled-id-list",
                                  "folder": folder, "count": len(self.disk.get(folder, ()))})

    # -- lookups ---------------------------------------------------------
    def id_of(self, category: str, name: str) -> int | None:
        return self.ids.get(category, {}).get(name)

    def require_id(self, category: str, name: str) -> int:
        index = self.id_of(category, name)
        if index is None:
            raise GMS2Error(f"{category}/{name}: no recovered Yellow ID; not inventing one")
        return index

    def merged(self, category: str, name: str) -> int:
        return YELLOW_BASE + self.require_id(category, name)

    def names(self, category: str) -> dict[str, int]:
        """Yellow name -> merged ID, for one category."""
        return {name: YELLOW_BASE + index for name, index in sorted(self.ids.get(category, {}).items())}

    def name_conflicts(self, categories: tuple[str, ...] | list[str]) -> dict[str, list[str]]:
        """Names used by more than one category.

        GameMaker Studio 2 enforces globally unique asset names, so a conflict here
        means this port parsed one of the two pinned records wrongly. It is a hard
        failure rather than a silent overwrite of the merged name map.
        """
        seen: dict[str, list[str]] = {}
        for category in categories:
            for name in self.ids.get(category, {}):
                seen.setdefault(name, []).append(category)
        return {name: found for name, found in sorted(seen.items()) if len(found) > 1}

    def yellow_name(self, category: str, merged_id: int) -> str | None:
        index = merged_id - YELLOW_BASE
        for name, number in self.ids.get(category, {}).items():
            if number == index:
                return name
        return None

    def counts(self) -> dict[str, int]:
        return {category: len(entries) for category, entries in sorted(self.ids.items())}

    def report(self) -> dict:
        return {
            "source": str(self.source),
            "ref": self.provenance.get("ref"),
            "yellow_base": YELLOW_BASE,
            "id_sources": [str(PROJECT), str(ASSET_ORDER)],
            "ids": self.counts(),
            "disk_folders": {folder: len(names) for folder, names in sorted(self.disk.items())},
            "findings": self.findings,
        }


def undertale_names(root: Path) -> dict[str, set[str]]:
    """Undertale's own resource names, for the cross-game collision table."""
    project = ET.fromstring((root / "projectA.project.gmx").read_text(encoding="utf-8-sig", errors="replace"))
    names: dict[str, set[str]] = {}
    for category, (tag, _) in UNDERTALE_CATEGORIES.items():
        names[category] = {e.text.replace("\\", "/").split("/")[-1] for e in project.findall(".//" + tag) if e.text}
    return names


def collisions(registry: Registry, root: Path) -> dict[str, list[dict]]:
    """Names both games use, and the merged ID each side keeps."""
    ours = undertale_names(root)
    table: dict[str, list[dict]] = {}
    for category in ours:
        theirs = registry.ids.get(category, {})
        for name in sorted(ours[category] & set(theirs)):
            table.setdefault(category, []).append({"name": name, "yellow_id": YELLOW_BASE + theirs[name]})
    return table


def tileset_texture(registry: Registry, tileset: str) -> str | None:
    """The ``_decompiled_*`` sprite folder that carries a tileset's texture page."""
    record = read(registry.source / "tilesets" / tileset / f"{tileset}.yy")
    return ref_name(record.get("spriteId"))
