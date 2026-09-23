"""Yellow's sprites, sounds, fonts and tilesets in the port's own record shape.

``port/graphics.lua``, ``port/audio.lua`` and ``port/collision.lua`` already read
asset records with GameMaker 1.4 field names (``width``, ``xorig``, ``frames``,
``colkind``, ``bbox_left``, ``glyphs``, …), so a Yellow asset is converted into
exactly that record and nothing in the runtime has to know which game it came
from. Facts that only exist in GameMaker Studio 2 — the animation speed *and*
whether it is per-second or per-step, a custom origin, nine-slice edges, a
tileset's tile grid — are kept in a ``yellow`` sub-record instead of being
discarded, because pieces 3-5 need them and dropping data silently is how ports
lose fidelity.

Two documented conversions happen here, both arithmetic on Yellow's own numbers:

* ``playbackSpeedType`` 0 means *frames per second*. Yellow's game speed is 30
  (``options/main/options_main.yy``), so the GameMaker 1.4 equivalent is
  ``image_speed = playbackSpeed / 30``. Type 1 already means frames per game
  step, which is GameMaker 1.4's own unit, so it is carried across unchanged.
* ``collisionKind`` 4 is a *rotated rectangle* mask, which GameMaker 1.4 has no
  word for. The sprite keeps its precise mask (``colkind`` 0) and the original
  value is preserved in ``yellow.collision_kind``; the report counts them.

Frames and audio are referenced where they lie in ``yellow_src/`` rather than
copied: the pinned fetch already guarantees their bytes, and duplicating 580 MB
into ``generated/`` would only make every build slower.
"""
from __future__ import annotations

from pathlib import Path

from .gms2 import GMS2Error, png_size, read, ref_name
from .registry import YELLOW_BASE, Registry, tileset_texture


class MissingAsset(GMS2Error):
    """A converted asset needs a file the pinned source does not have."""

#: GMS2 sprite origin enum -> (x fraction, y fraction) of the sprite rectangle.
ORIGIN = {0: (0.0, 0.0), 1: (0.5, 0.0), 2: (1.0, 0.0), 3: (0.0, 0.5), 4: (0.5, 0.5),
          5: (1.0, 0.5), 6: (0.0, 1.0), 7: (0.5, 1.0), 8: (1.0, 1.0)}
AUDIO_SUFFIXES = (".ogg", ".wav", ".mp3")
CHUNK_SIZE = 64


def relative(source: Path, root: Path, path: Path) -> str:
    """A packaged-archive-relative path, so records work from the repo and the .love."""
    return path.resolve().relative_to(root.resolve()).as_posix()


def image_speed(playback_speed, speed_type, game_speed: int) -> float:
    """GameMaker 1.4 ``image_speed`` for a Studio 2 playback speed.

    ``playbackSpeedType`` 0 counts *frames per second*, which GameMaker 1.4 has
    no word for; Yellow's own game speed (``options_main.yy``, 30) converts it.
    Type 1 already counts frames per game step, which is 1.4's own unit.
    """
    speed = float(playback_speed if playback_speed is not None else 1) or 0.0
    return speed if int(speed_type or 0) == 1 else speed / max(1, int(game_speed or 30))


class AssetConverter:
    def __init__(self, registry: Registry, root: Path, provenance: dict):
        self.registry = registry
        self.source = registry.source
        self.root = root
        self.provenance = provenance
        self.game_speed = int(provenance.get("documented_counts", {}).get("game_speed") or 30)
        self.findings: list[dict] = []
        #: Pinned IDs whose folder upstream does not have: unrecoverable, never substituted.
        self.unrecoverable: list[dict] = []
        #: Files a converted asset needs but the pinned source does not have: blocks packaging.
        self.missing_files: list[dict] = []
        self.records: dict[str, dict[int, dict]] = {}

    # -- helpers ---------------------------------------------------------
    def note(self, kind: str, **fields) -> None:
        self.findings.append({"kind": kind, **fields})

    def require(self, path: Path, origin: str) -> Path:
        if not path.is_file():
            self.missing_files.append({"path": relative(self.source, self.root, path), "origin": origin})
            raise MissingAsset(f"{origin}: missing asset file {path}")
        return path

    def absent(self, category: str, name: str, reason: str) -> None:
        """A recovered ID with nothing upstream to convert; recorded, never invented."""
        self.unrecoverable.append({"category": category, "name": name,
                                   "yellow_id": self.registry.id_of(category, name),
                                   "merged_id": YELLOW_BASE + (self.registry.id_of(category, name) or -1),
                                   "reason": reason})

    # -- sprites ---------------------------------------------------------
    def sprite(self, name: str) -> dict | None:
        folder = self.source / "sprites" / name
        record_path = folder / f"{name}.yy"
        if not record_path.is_file():
            self.absent("sprites", name, "pinned sprite ID has no folder in the source")
            return None
        data = read(record_path)
        width, height = int(data["width"]), int(data["height"])
        sequence = data.get("sequence") or {}
        origin_mode = data.get("origin")
        if origin_mode == 9:
            xorig, yorigin = float(sequence.get("xorigin", 0)), float(sequence.get("yorigin", 0))
        elif origin_mode in ORIGIN:
            xorig, yorigin = ORIGIN[origin_mode][0] * width, ORIGIN[origin_mode][1] * height
        else:
            raise GMS2Error(f"sprites/{name}: unknown origin mode {origin_mode!r}")
        frames = []
        try:
            for entry in data.get("frames") or []:
                frame = ref_name(entry)
                if not frame:
                    raise GMS2Error(f"sprites/{name}: frame entry without a name")
                path = self.require(folder / f"{frame}.png", f"sprites/{name}")
                actual = png_size(path)
                if actual != (width, height):
                    self.note("frame-size-differs-from-sprite", sprite=name, frame=frame,
                              frame_size=list(actual), sprite_size=[width, height])
                frames.append(relative(self.source, self.root, path))
        except MissingAsset:
            # A sprite with a missing frame is not converted at all: emitting the
            # frames that do exist would silently renumber the animation.
            return None
        if not frames:
            self.note("sprite-without-frames", sprite=name)
        # A missing speed defaults to 1; an authored 0 is kept. Nineteen pinned
        # sprites author playbackSpeed 0 (they only change frame when their
        # code sets image_index), and coercing that to 1 would animate them
        # once the runtime honours the rate (piece 6b).
        raw_speed = sequence.get("playbackSpeed", 1)
        speed = float(raw_speed if raw_speed is not None else 1)
        speed_type = int(sequence.get("playbackSpeedType", 1) or 0)
        collision_kind = int(data.get("collisionKind", 1))
        layers = data.get("layers") or []
        if len(layers) > 1:
            self.note("multi-layer-sprite", sprite=name, layers=len(layers))
        nine = data.get("nineSlice")
        record = {
            "name": name,
            "width": width, "height": height,
            "xorig": xorig, "yorigin": yorigin,
            # Rotated-rectangle masks have no GameMaker 1.4 equivalent; keep the
            # precise mask and the original value instead of pretending.
            "colkind": collision_kind if collision_kind in (0, 1, 2, 3) else 0,
            "coltolerance": int(data.get("collisionTolerance", 0) or 0),
            "sepmasks": 0,
            "bboxmode": int(data.get("bboxMode", 0) or 0),
            "bbox_left": int(data.get("bbox_left", 0)), "bbox_right": int(data.get("bbox_right", width - 1)),
            "bbox_top": int(data.get("bbox_top", 0)), "bbox_bottom": int(data.get("bbox_bottom", height - 1)),
            "frames": frames,
            "yellow": {
                "id": self.registry.id_of("sprites", name),
                "origin_mode": origin_mode,
                "collision_kind": collision_kind,
                "playback_speed": speed,
                "playback_speed_type": speed_type,
                # GameMaker 1.4 image_speed, derived from Yellow's own numbers.
                "image_speed": image_speed(speed, speed_type, self.game_speed),
                "length": float(sequence.get("length", len(frames)) or len(frames)),
                "playback": int(sequence.get("playback", 1) or 0),
                "nine_slice": bool(nine),
                "layers": len(layers),
                "texture_group": ref_name(data.get("textureGroupId")),
            },
        }
        if collision_kind == 4:
            self.note("rotated-rectangle-mask", sprite=name)
        if nine:
            self.note("nine-slice-sprite", sprite=name)
        return record

    def sprites(self) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for name in sorted(self.registry.ids["sprites"]):
            if name.startswith("_decompiled_"):
                continue  # tileset texture pages, addressed through their tileset
            record = self.sprite(name)
            if record is not None:
                out[self.registry.merged("sprites", name)] = record
        return out

    # -- sounds ----------------------------------------------------------
    def sound(self, name: str) -> dict | None:
        folder = self.source / "sounds" / name
        record_path = folder / f"{name}.yy"
        if not record_path.is_file():
            self.absent("sounds", name, "pinned sound ID has no folder in the source")
            return None
        data = read(record_path)
        declared = data.get("soundFile") or name
        candidates = [folder / declared] + [folder / (declared + suffix) for suffix in AUDIO_SUFFIXES]
        candidates += [folder / (Path(declared).stem + suffix) for suffix in AUDIO_SUFFIXES]
        path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if path is None:
            present = sorted(p.name for p in folder.iterdir() if p.suffix.lower() in AUDIO_SUFFIXES)
            if len(present) == 1:
                path = folder / present[0]
                self.note("sound-file-renamed", sound=name, declared=declared, used=present[0])
            else:
                self.missing_files.append({"path": f"yellow_src/sounds/{name}/{declared}", "origin": f"sounds/{name}",
                                           "candidates": present})
                return None
        volume = data.get("volume")
        return {
            "name": name,
            "file": relative(self.source, self.root, path),
            "volume": float(1.0 if volume is None else volume),
            "yellow": {
                "id": self.registry.id_of("sounds", name),
                "declared": declared,
                "type": data.get("type"), "compression": data.get("compression"),
                "bit_depth": data.get("bitDepth"), "sample_rate": data.get("sampleRate"),
                "duration": data.get("duration"), "preload": bool(data.get("preload")),
                "audio_group": ref_name(data.get("audioGroupId")),
            },
        }

    def sounds(self) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for name in sorted(self.registry.ids["sounds"]):
            record = self.sound(name)
            if record is None:
                continue
            out[self.registry.merged("sounds", name)] = record
        return out

    # -- fonts -----------------------------------------------------------
    def font(self, name: str) -> dict | None:
        folder = self.source / "fonts" / name
        record_path = folder / f"{name}.yy"
        if not record_path.is_file():
            self.absent("fonts", name, "pinned font ID has no folder in the source")
            return None
        data = read(record_path)
        try:
            texture = self.require(folder / f"{name}.png", f"fonts/{name}")
        except MissingAsset:
            return None
        glyphs: dict[int, dict] = {}
        for key, glyph in (data.get("glyphs") or {}).items():
            character = glyph.get("character")
            if character is None:
                # The dictionary key is the character code, as a decimal string.
                character = int(key)
            glyphs[int(character)] = {
                "x": int(glyph["x"]), "y": int(glyph["y"]),
                "w": int(glyph["w"]), "h": int(glyph["h"]),
                "shift": float(glyph["shift"]), "offset": float(glyph.get("offset", 0)),
            }
        if not glyphs:
            raise GMS2Error(f"fonts/{name}: no glyphs")
        kerning = data.get("kerningPairs") or []
        if kerning:
            self.note("font-kerning-not-supported", font=name, pairs=len(kerning))
        return {
            "name": name,
            "file": relative(self.source, self.root, texture),
            "glyphs": glyphs,
            "height": max(g["h"] for g in glyphs.values()),
            "yellow": {
                "id": self.registry.id_of("fonts", name),
                "size": data.get("size"), "ascender": data.get("ascender"),
                "ascender_offset": data.get("ascenderOffset"), "first": data.get("first"),
                "last": data.get("last"), "anti_alias": data.get("AntiAlias"),
                "font_name": data.get("fontName"), "bold": bool(data.get("bold")),
                "italic": bool(data.get("italic")), "kerning_pairs": len(kerning),
                "maintain_gms1_font": bool(data.get("maintainGms1Font")),
            },
        }

    def fonts(self) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for name in sorted(self.registry.ids["fonts"]):
            record = self.font(name)
            if record is None:
                continue
            out[self.registry.merged("fonts", name)] = record
        return out

    # -- tilesets --------------------------------------------------------
    def tileset(self, name: str) -> dict | None:
        folder = self.source / "tilesets" / name
        record_path = folder / f"{name}.yy"
        if not record_path.is_file():
            self.absent("backgrounds", name, "pinned tileset ID has no folder in the source")
            return None
        data = read(record_path)
        texture_sprite = tileset_texture(self.registry, name)
        if not texture_sprite:
            self.missing_files.append({"path": f"yellow_src/tilesets/{name}/{name}.yy", "origin": f"tilesets/{name}",
                                       "reason": "no spriteId"})
            return None
        frame_folder = self.source / "sprites" / texture_sprite
        frames = [ref_name(entry) for entry in (read(frame_folder / f"{texture_sprite}.yy").get("frames") or [])]
        if len(frames) != 1:
            self.note("tileset-texture-frame-count", tileset=name, texture=texture_sprite, frames=len(frames))
        if not frames:
            self.missing_files.append({"path": f"yellow_src/sprites/{texture_sprite}", "origin": f"tilesets/{name}"})
            return None
        try:
            texture = self.require(frame_folder / f"{frames[0]}.png", f"tilesets/{name}")
        except MissingAsset:
            return None
        width, height = png_size(texture)
        animation = data.get("tileAnimation") or {}
        frame_count = int(animation.get("SerialiseFrameCount", 1) or 1)
        frame_data = animation.get("FrameData") or []
        tile_count = int(data.get("tile_count", 0) or 0)
        if frame_count > 1 and len(frame_data) != tile_count * frame_count:
            # FrameData is one row of `frame_count` tile indices per tile, so a
            # short or long table means the pinned record cannot be read as
            # authored animation. Never pad, truncate or guess it.
            raise GMS2Error(f"tilesets/{name}: tileAnimation.FrameData has {len(frame_data)} entries, "
                            f"expected tile_count {tile_count} x SerialiseFrameCount {frame_count}")
        return {
            "name": name,
            "width": width, "height": height,
            "file": relative(self.source, self.root, texture),
            "yellow": {
                "id": self.registry.id_of("backgrounds", name),
                "texture_sprite": texture_sprite,
                "tile_width": int(data.get("tileWidth", 0) or 0),
                "tile_height": int(data.get("tileHeight", 0) or 0),
                "tile_count": tile_count,
                "out_columns": int(data.get("out_columns", 0) or 0),
                "tile_x_offset": int(data.get("tilexoff", 0) or 0),
                "tile_y_offset": int(data.get("tileyoff", 0) or 0),
                "tile_h_separation": int(data.get("tilehsep", 0) or 0),
                "tile_v_separation": int(data.get("tilevsep", 0) or 0),
                "output_h_border": int(data.get("out_tilehborder", 0) or 0),
                "output_v_border": int(data.get("out_tilevborder", 0) or 0),
                "animation_frames": frame_data,
                "animation_frame_count": frame_count,
                # Studio 2 tileset animation speed is authored in FPS (the tile
                # set editor's "FPS" field), unlike a sprite's playback speed.
                "animation_speed": data.get("tileAnimationSpeed"),
                "auto_tile_sets": len(data.get("autoTileSets") or []),
            },
        }

    def backgrounds(self) -> dict[int, dict]:
        out: dict[int, dict] = {}
        for name in sorted(self.registry.ids["backgrounds"]):
            record = self.tileset(name)
            if record is None:
                continue
            out[self.registry.merged("backgrounds", name)] = record
        return out

    # -- run -------------------------------------------------------------
    def run(self) -> dict[str, dict[int, dict]]:
        self.records = {
            "sprites": self.sprites(),
            "sounds": self.sounds(),
            "fonts": self.fonts(),
            "backgrounds": self.backgrounds(),
        }
        return self.records

    def summary(self) -> dict:
        expected = {category: len(self.registry.ids[category]) for category in self.records}
        expected["backgrounds"] = len(self.registry.ids["backgrounds"])
        kinds: dict[str, int] = {}
        for finding in self.findings:
            kinds[finding["kind"]] = kinds.get(finding["kind"], 0) + 1
        return {
            "converted": {category: len(records) for category, records in self.records.items()},
            "recovered_ids": expected,
            "findings": kinds,
            "finding_examples": {kind: [f for f in self.findings if f["kind"] == kind][:5] for kind in sorted(kinds)},
            "missing_asset_files": self.missing_files,
            "unrecoverable_ids": self.unrecoverable,
        }
