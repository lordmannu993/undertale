"""Yellow's assets in the port's own record shape.

Piece 1 of ``docs/YELLOW.md`` converts every Yellow sprite, sound, font and
tileset into the records ``port/graphics.lua``, ``port/audio.lua`` and
``port/collision.lua`` already read, so nothing downstream has to know which game
an asset came from. The offline half of this file drives a miniature source tree;
the ``live`` half runs against the real fetch and is skipped — never silently
passed — when ``yellow_src/`` is absent.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import yellow_support as support  # noqa: E402
from yellow.assets import AssetConverter  # noqa: E402
from yellow.registry import YELLOW_BASE, Registry  # noqa: E402
from yellow_convert import Writer, stage_assets  # noqa: E402

SOURCE = ROOT / "yellow_src"
LIVE = (SOURCE / "Undertale_Yellow.yyp").is_file() and (SOURCE / "notes/Asset_Order/Asset_Order.txt").is_file()
# CI sets PORT_REQUIRE_YELLOW=1 after fetching, so a broken fetch fails these tests
# instead of quietly skipping the only proof that the real source converts.
REQUIRED = os.environ.get("PORT_REQUIRE_YELLOW") == "1"
live = pytest.mark.skipif(not LIVE and not REQUIRED,
                          reason="yellow_src/ is not fetched; run tools/fetch_yellow.py")

#: the GameMaker 1.4 sprite fields the runtime reads, per port/graphics.lua and port/collision.lua
SPRITE_FIELDS = {"name", "width", "height", "xorig", "yorigin", "colkind", "coltolerance", "sepmasks",
                 "bboxmode", "bbox_left", "bbox_right", "bbox_top", "bbox_bottom", "frames"}


def convert(root: Path, source: Path, provenance: dict) -> tuple[Registry, AssetConverter]:
    registry = Registry(source, provenance)
    converter = AssetConverter(registry, root, provenance)
    converter.run()
    return registry, converter


@pytest.fixture()
def fixture(tmp_path):
    """A miniature Yellow project, converted; ``root`` is what asset paths are relative to."""
    source, provenance = support.build_source(tmp_path)
    registry, converter = convert(tmp_path, source, provenance)
    output = ROOT / "generated" / "yellow_test"
    report = stage_assets(registry, provenance, Writer(output), tmp_path, ROOT,
                          prefix="generated.yellow_test")
    yield SimpleNamespace(root=tmp_path, source=source, provenance=provenance, registry=registry,
                          converter=converter, report=report, output=output)
    shutil.rmtree(output, ignore_errors=True)


def sprite(fixture, name: str) -> dict:
    record = fixture.converter.records["sprites"].get(fixture.registry.merged("sprites", name))
    assert record is not None, f"{name} was not converted"
    return record


# -- record shape ----------------------------------------------------------
def test_sprite_records_carry_exactly_the_fields_the_runtime_reads(fixture):
    record = sprite(fixture, "spr_pl_down")
    assert set(record) - {"yellow"} == SPRITE_FIELDS
    assert record["frames"][0].split("/")[0] == "yellow_src", "paths stay relative to the packaged root"
    for key in ("width", "height", "bbox_left", "bbox_right", "bbox_top", "bbox_bottom"):
        assert isinstance(record[key], int), key


def test_the_runtime_reads_both_games_sprite_records_the_same_way(converted, fixture):
    """One runtime class, two manifests: the field sets have to match, not merely look similar."""
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    keys = vm.execute('''
        Input=require("port.input"); Runtime=require("port.runtime")
        local function fields(asset)
            local names={}
            for k in pairs(asset) do names[#names+1]=k end
            table.sort(names)
            return table.concat(names, ",")
        end
        local undertale=Runtime.new(require("generated.manifest"), Input.new(), {headless=true, seed=42})
        local yellow=Runtime.new(require("generated.yellow_test.manifest"), Input.new(), {headless=true, seed=42})
        local function first(runtime)
            for _,asset in pairs(runtime.assets.sprites) do return fields(asset) end
        end
        return first(undertale) .. "|" .. first(yellow)
    ''')
    ours, theirs = keys.split("|")
    assert set(theirs.split(",")) - {"yellow"} == set(ours.split(",")), (ours, theirs)


def test_the_partial_manifest_names_every_converted_asset(fixture):
    manifest = (fixture.output / "manifest.lua").read_text()
    assert '"undertale-yellow"' in manifest, "the manifest must say which game it carries"
    for records in fixture.converter.records.values():
        assert records
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    counts = vm.execute('''
        Input=require("port.input"); Runtime=require("port.runtime")
        local runtime=Runtime.new(require("generated.yellow_test.manifest"), Input.new(), {headless=true, seed=42})
        local out={}
        for _,kind in ipairs({"sprites","sounds","fonts","backgrounds"}) do
            local n=0 for _ in pairs(runtime.assets[kind]) do n=n+1 end
            out[#out+1]=kind .. "=" .. n
        end
        local sprite=runtime.assets.sprites[%d]
        out[#out+1]="run=" .. sprite.name .. ":" .. #sprite.frames
        out[#out+1]="names=" .. (function() local n=0 for _ in pairs(runtime.manifest.names) do n=n+1 end return n end)()
        return table.concat(out, " ")
    ''' % fixture.registry.merged("sprites", "spr_pl_run_down"))
    converted = fixture.report["assets"]["converted"]
    for kind, count in converted.items():
        assert f"{kind}={count}" in counts, counts
    assert "run=spr_pl_run_down:6" in counts
    assert f"names={sum(converted.values())}" in counts, "every converted asset must be reachable by name"


# -- the documented reinterpretations -------------------------------------
def test_a_custom_origin_is_taken_from_the_sequence_not_assumed(fixture):
    down = sprite(fixture, "spr_pl_down")
    assert (down["xorig"], down["yorigin"]) == (9.0, 17.0)
    centred = sprite(fixture, "spr_a")
    assert (centred["xorig"], centred["yorigin"]) == (10.0, 10.0), "origin 4 is the centre of a 20x20 sprite"
    corner = sprite(fixture, "spr_fps")
    assert (corner["xorig"], corner["yorigin"]) == (0.0, 0.0)
    assert down["yellow"]["origin_mode"] == 9 and corner["yellow"]["origin_mode"] == 0


def test_frames_per_second_animation_is_converted_with_yellows_own_game_speed(fixture):
    assert fixture.converter.game_speed == fixture.provenance["documented_counts"]["game_speed"] == 30
    per_second = sprite(fixture, "spr_fps")
    assert per_second["yellow"]["playback_speed_type"] == 0
    assert per_second["yellow"]["playback_speed"] == 30.0
    assert per_second["yellow"]["image_speed"] == pytest.approx(1.0), "30 frames/second at 30 steps/second"
    per_step = sprite(fixture, "spr_pl_run_down")
    assert per_step["yellow"]["playback_speed_type"] == 1
    assert per_step["yellow"]["image_speed"] == per_step["yellow"]["playback_speed"]


def test_a_per_frame_precise_mask_is_precise_with_separate_masks_and_counted(fixture):
    """Studio 2's collisionKind 4 is *Precise (per frame)* (piece 6d).

    The GMS2 sprite schema numbers the kinds 0 Precise, 1 Rectangle, 2 Ellipse,
    3 Diamond, 4 PrecisePerFrame, 5 RectangleWithRotation. GameMaker 1.4 says
    "precise per frame" as colkind 0 with sepmasks 1; before piece 6d this test
    pinned kind 4 as a rotated rectangle with sepmasks 0, which composited every
    frame into one mask.
    """
    record = sprite(fixture, "spr_rotated")
    assert record["yellow"]["collision_kind"] == 4, "the Studio 2 fact must survive"
    assert (record["colkind"], record["sepmasks"]) == (0, 1), \
        "Precise (per frame) is GameMaker 1.4's precise mask with separate masks"
    assert fixture.report["assets"]["findings"]["precise-per-frame-mask"] == 1
    assert "rotated-rectangle-mask" not in fixture.report["assets"]["findings"]
    # Precise (composite) stays one mask for every frame; Rectangle stays a box.
    assert (sprite(fixture, "spr_a")["colkind"], sprite(fixture, "spr_a")["sepmasks"]) == (1, 0)


def test_nine_slice_sprites_are_reported_rather_than_quietly_flattened(fixture):
    assert sprite(fixture, "spr_nine")["yellow"]["nine_slice"] is True
    assert fixture.report["assets"]["findings"]["nine-slice-sprite"] == 1
    assert any("nine-slice" in line for line in fixture.report["limitations"])


# -- nothing is invented ---------------------------------------------------
def test_a_sprite_with_a_missing_frame_is_not_half_converted(fixture):
    folder = fixture.source / "sprites/spr_pl_run_down"
    victim = sorted(folder.glob("*.png"))[2]
    victim.unlink()
    registry, converter = convert(fixture.root, fixture.source, fixture.provenance)
    assert registry.merged("sprites", "spr_pl_run_down") not in converter.records["sprites"], \
        "emitting the surviving frames would silently renumber the animation"
    assert registry.merged("sprites", "spr_pl_down") in converter.records["sprites"], "other sprites still convert"
    missing = converter.summary()["missing_asset_files"]
    assert len(missing) == 1 and missing[0]["origin"] == "sprites/spr_pl_run_down"
    assert victim.name in missing[0]["path"]


def test_a_pinned_id_with_nothing_upstream_is_listed_not_substituted(tmp_path):
    source, provenance = support.build_source(tmp_path)
    provenance = support.add_unbacked_sprite(source, provenance, "_filter_test_texture")
    registry, converter = convert(tmp_path, source, provenance)
    summary = converter.summary()
    assert summary["unrecoverable_ids"] == [{
        "category": "sprites", "name": "_filter_test_texture",
        "yellow_id": registry.id_of("sprites", "_filter_test_texture"),
        "merged_id": registry.merged("sprites", "_filter_test_texture"),
        "reason": "pinned sprite ID has no folder in the source"}]
    assert summary["missing_asset_files"] == [], "an absent folder is not a missing file of a converted asset"
    assert summary["converted"]["sprites"] == len(support.FIXTURE["sprites"])


def test_sounds_resolve_their_file_whether_or_not_the_extension_is_declared(fixture):
    registry, converter = fixture.registry, fixture.converter
    with_extension = converter.records["sounds"][registry.merged("sounds", "snd_a")]
    without = converter.records["sounds"][registry.merged("sounds", "snd_b")]
    assert with_extension["file"].endswith("snd_a/a_sound.ogg") and with_extension["volume"] == 0.8
    assert without["file"].endswith("snd_b/b_sound.ogg")
    assert (fixture.root / with_extension["file"]).is_file()
    assert (fixture.root / without["file"]).is_file()


def test_fonts_keep_every_glyph_including_the_default_character(fixture):
    record = fixture.converter.records["fonts"][fixture.registry.merged("fonts", "fnt_a")]
    assert sorted(record["glyphs"]) == [32, 65, 9647]
    assert record["glyphs"][65] == {"x": 12, "y": 2, "w": 7, "h": 12, "shift": 9.0, "offset": 1.0}
    assert record["height"] == 16 and record["yellow"]["size"] == 10.0
    assert (fixture.root / record["file"]).is_file()


def test_tilesets_become_backgrounds_carrying_their_tile_grid(fixture):
    record = fixture.converter.records["backgrounds"][fixture.registry.merged("backgrounds", "ts_a")]
    assert (record["width"], record["height"]) == (60, 40), "the texture page's own size"
    grid = record["yellow"]
    assert (grid["tile_width"], grid["tile_height"], grid["out_columns"], grid["tile_count"]) == (20, 20, 3, 6)
    assert grid["texture_sprite"] == "_decompiled_ts_a"
    assert grid["animation_frames"] == list(range(6))
    assert (fixture.root / record["file"]).is_file()


# -- the driver ------------------------------------------------------------
@live
def test_script_stage_is_complete_but_later_stages_still_refuse_partial_games():
    scripts = subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "scripts"],
                             cwd=ROOT, capture_output=True, text=True)
    assert scripts.returncode == 0, scripts.stderr
    assert "Converted Yellow GMS2 scripts: 1155 resources" in scripts.stdout
    report = json.loads((ROOT / "generated/yellow/conversion-report.json").read_text())
    assert report["stage"] == "scripts"
    assert report["scripts"]["converted"] == 1155
    assert report["scripts"]["functions"] == 1178
    # The shipped build's own GMLive source is inert (live_call() returns false,
    # live_init/live_update/live_room_start are empty), so those scripts convert
    # literally instead of stopping; only the live-editing entry point itself,
    # which uses GMS2 constructors this port cannot compile, stays a named stop.
    assert len(report["scripts"]["gmlive_release_stubs"]) == 21
    assert len(report["scripts"]["unsupported"]) == 1
    assert report["scripts"]["unsupported"][0]["script"] == "GMLive"
    assert len(list((ROOT / "generated/yellow/scripts").glob("*.lua"))) == 1155
    manifest = (ROOT / "generated/yellow/manifest.lua").read_text()
    assert '"keyboard_multicheck_pressed"' in manifest
    assert '"yellow_names"' in manifest
    # Later-stage full conversion gates live in test_yellow_objects/rooms.py.


def test_converting_without_the_pinned_source_is_a_named_stop():
    output = ROOT / "generated" / "yellow_missing"
    run = subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "assets",
                          "--source", str(ROOT / "yellow_src_absent"), "--output", str(output)],
                         cwd=ROOT, capture_output=True, text=True)
    shutil.rmtree(output, ignore_errors=True)
    assert run.returncode == 1
    assert "tools/fetch_yellow.py" in run.stderr


def test_the_output_directory_must_stay_inside_the_repository(tmp_path):
    for output in (str(tmp_path), str(ROOT), str(ROOT / ".git" / "yellow")):
        run = subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "assets",
                              "--output", output], cwd=ROOT, capture_output=True, text=True)
        assert run.returncode != 0, output
        assert "dedicated generated directory" in (run.stderr + run.stdout), output


# -- the real source -------------------------------------------------------
@pytest.fixture(scope="module")
def real():
    run = subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "assets"],
                         cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    report = json.loads((ROOT / "generated/yellow/conversion-report.json").read_text())
    registry = Registry(SOURCE, json.loads((ROOT / "port/yellow_source.json").read_text()))
    return report, registry


def read_record(merged_id: int, kind: str) -> dict:
    """Read one emitted asset record back through Lua, the way the runtime will."""
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    table = vm.execute('''
        local manifest = require("generated.yellow.manifest")
        for _,entry in ipairs(manifest.asset_modules) do
            if entry.kind == "%s" then
                local chunk = require(entry.module)
                if chunk[%d] then return chunk[%d] end
            end
        end
        return nil
    ''' % (kind, merged_id, merged_id))
    assert table is not None, f"{kind} {merged_id} was not emitted"
    return to_python(table)


def to_python(value):
    """A Lua table read back as plain Python data, for field-by-field assertions."""
    if not hasattr(value, "items"):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    return {int(key) if isinstance(key, float) else key: to_python(item) for key, item in value.items()}


@live
def test_every_yellow_asset_category_converts(real):
    report, _ = real
    assert report["assets"]["converted"] == {"sprites": 3796, "sounds": 673, "fonts": 11, "backgrounds": 112}
    assert report["assets"]["recovered_ids"] == {"sprites": 3799, "sounds": 673, "fonts": 11, "backgrounds": 112}
    assert report["assets"]["missing_asset_files"] == []
    assert report["registry"]["ids"]["objects"] == 3224 and report["registry"]["ids"]["rooms"] == 287


@live
def test_the_only_unconvertible_ids_are_the_three_shader_textures_upstream_never_shipped(real):
    report, _ = real
    unrecoverable = {entry["name"] for entry in report["assets"]["unrecoverable_ids"]}
    assert unrecoverable == {"_filter_distort_smoothnoise", "_filter_heathaze_noise_sprite", "_filter_vignette_texture"}
    for entry in report["assets"]["unrecoverable_ids"]:
        assert entry["merged_id"] == YELLOW_BASE + entry["yellow_id"]
        assert not (SOURCE / "sprites" / entry["name"]).exists()


@live
def test_clovers_sprite_set_is_present_with_the_ids_the_pinned_records_give_it(real):
    report, registry = real
    order = (SOURCE / "notes/Asset_Order/Asset_Order.txt").read_text(errors="replace")
    listed = {name: int(number) for number, name in re.findall(r"^(\d+) - (\S+)\s*$", order, re.M)}
    expected = {
        "spr_pl_down": 4, "spr_pl_up": 4, "spr_pl_left": 2, "spr_pl_right": 2,
        "spr_pl_run_down": 6, "spr_pl_run_up": 6, "spr_pl_run_left": 6, "spr_pl_run_right": 6,
        "spr_pl_down_geno": 4, "spr_pl_run_down_geno": 6, "spr_pl_mask": 1,
    }
    manifest = (ROOT / "generated/yellow/manifest.lua").read_text()
    for name, frames in expected.items():
        merged = YELLOW_BASE + listed[name]
        assert registry.merged("sprites", name) == merged, name
        assert f'"{name}"' in manifest, f"{name} is not addressable by name"
        record = read_record(merged, "sprites")
        assert len(record["frames"]) == frames, f"{name}: {len(record['frames'])} frames, expected {frames}"
        assert record["yellow"]["image_speed"] > 0


@live
def test_every_file_the_records_point_at_really_exists(real):
    _, registry = real
    provenance = json.loads((ROOT / "port/yellow_source.json").read_text())
    converter = AssetConverter(registry, ROOT, provenance)
    records = converter.run()
    assert converter.summary()["missing_asset_files"] == []
    checked = 0
    for kind in ("sprites", "backgrounds", "fonts"):
        for record in records[kind].values():
            for path in (record["frames"] if kind == "sprites" else [record["file"]]):
                assert (ROOT / path).is_file(), f"{record['name']}: {path}"
                assert path.startswith("yellow_src/"), path
                checked += 1
    for record in records["sounds"].values():
        assert (ROOT / record["file"]).is_file(), record["name"]
        checked += 1
    assert checked > 18000, f"only {checked} asset files were verified"


@live
def test_the_runtime_loads_the_whole_yellow_asset_set(real):
    report, registry = real
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute("package.path='./?.lua;./?/init.lua;'..package.path")
    summary = vm.execute('''
        Input=require("port.input"); Runtime=require("port.runtime")
        local runtime=Runtime.new(require("generated.yellow.manifest"), Input.new(), {headless=true, seed=42})
        local out={}
        for _,kind in ipairs({"sprites","sounds","fonts","backgrounds"}) do
            local n=0 for _ in pairs(runtime.assets[kind]) do n=n+1 end
            out[#out+1]=kind .. "=" .. n
        end
        local run=runtime.assets.sprites[%d]
        out[#out+1]="run=" .. run.name .. ":" .. #run.frames .. ":" .. run.width .. "x" .. run.height
        out[#out+1]="origin=" .. run.xorig .. "," .. run.yorigin
        local font=runtime.assets.fonts[%d]
        out[#out+1]="font=" .. font.name .. ":" .. (font.glyphs[65] and font.glyphs[65].w or -1)
        return table.concat(out, " ")
    ''' % (registry.merged("sprites", "spr_pl_run_down"), registry.merged("fonts", "fnt_main")))
    for kind, count in report["assets"]["converted"].items():
        assert f"{kind}={count}" in summary, summary
    assert "run=spr_pl_run_down:6:20x32" in summary
    assert "origin=9,17" in summary
    assert re.search(r"font=fnt_main:[1-9]\d*$", summary), "glyph 65 must carry a real width"


@live
def test_names_both_games_use_are_enumerated_with_their_separate_ids(real):
    report, registry = real
    table = report["name_collisions_with_undertale"]
    assert {kind: len(entries) for kind, entries in table.items()} == {
        "sprites": 10, "objects": 10, "sounds": 21, "fonts": 1}
    assert any(entry["name"] == "spr_flowey" for entry in table["sprites"])
    assert any(entry["name"] == "obj_alphys_npc" for entry in table["objects"])
    assert any(entry["name"] == "mus_shop" for entry in table["sounds"])
    assert table["fonts"][0]["name"] == "fnt_main"
    for entries in table.values():
        for entry in entries:
            assert entry["yellow_id"] >= YELLOW_BASE


@live
def test_the_conversion_is_reproducible(real):
    first = (ROOT / "generated/yellow/manifest.lua").read_bytes()
    run = subprocess.run([sys.executable, "tools/yellow_convert.py", "--stage", "assets"],
                         cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert (ROOT / "generated/yellow/manifest.lua").read_bytes() == first, "output must not depend on the clock"
