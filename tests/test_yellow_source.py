"""The pinned Undertale Yellow source pipeline.

Piece 1 of ``docs/YELLOW.md`` merges a second game, so the boring parts matter
most: the source has to come from one immutable commit, its Studio 2 JSON has to
be read without guessing, and Yellow's numeric asset IDs have to be *recovered*
from two independent records inside that source. These tests hold each of those
to account with a miniature source tree, so they run without the 580 MB fetch.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import fetch_yellow  # noqa: E402
import yellow_support as support  # noqa: E402
from yellow.gms2 import GMS2Error, json_text, loads, png_size, read, ref_name  # noqa: E402
from yellow.registry import YELLOW_BASE, Registry, collisions, undertale_names  # noqa: E402

PROVENANCE = json.loads((ROOT / "port/yellow_source.json").read_text())
ASSET_KINDS = ("sprites", "sounds", "fonts", "backgrounds")


@pytest.fixture()
def fixture(tmp_path):
    source, provenance = support.build_source(tmp_path)
    return source, provenance, Registry(source, provenance)


# -- provenance ------------------------------------------------------------
def test_provenance_pins_an_immutable_commit_and_every_digest():
    assert re.fullmatch(r"[0-9a-f]{40}", PROVENANCE["ref"]), "a branch or tag could drift under the merge"
    assert PROVENANCE["ref"] in PROVENANCE["tarball"]["url"]
    assert re.fullmatch(r"[0-9a-f]{64}", PROVENANCE["tarball"]["sha256"])
    assert PROVENANCE["tarball"]["bytes"] > 100 * 1024 * 1024, "Yellow is a large project; a small tarball is wrong"
    assert PROVENANCE["upstream"] == "lordmannu993/UnderTale-Yellow"
    assert PROVENANCE["fork_of"] == "burnedpopcorn/UnderTale-Yellow-Decompilation"
    for name, entry in PROVENANCE["index_files"].items():
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), name
        assert entry["role"], f"{name}: provenance must say what the file is used for"
    assert PROVENANCE["id_band"]["yellow_base"] == YELLOW_BASE


def test_provenance_documents_the_counts_the_pipeline_is_held_to():
    counts = PROVENANCE["documented_counts"]
    for category in ("sprites", "objects", "rooms", "sounds", "backgrounds", "fonts", "paths"):
        assert isinstance(counts[category], int) and counts[category] > 0, category
    assert counts["game_speed"] == 30, "frames-per-second animations are converted with this number"


# -- fetch verification ----------------------------------------------------
def test_check_refuses_a_source_that_was_never_fetched():
    record = dict(PROVENANCE, extract_to="definitely-not-fetched")
    with pytest.raises(fetch_yellow.FetchError, match="absent"):
        fetch_yellow.check(record)


def test_check_refuses_a_source_that_is_not_the_pinned_commit(tmp_path):
    record = dict(PROVENANCE, extract_to=str(tmp_path / "yellow_src"))
    (tmp_path / "yellow_src").mkdir()
    with pytest.raises(fetch_yellow.FetchError, match="not the pinned commit"):
        fetch_yellow.check(record)


def test_check_names_both_digests_when_an_index_file_changed(tmp_path):
    source, _ = support.build_source(tmp_path)
    record = dict(PROVENANCE, extract_to=str(source))
    (source / ".pinned.json").write_text(json.dumps(
        {"ref": record["ref"], "tarball_sha256": record["tarball"]["sha256"]}))
    for name, entry in record["index_files"].items():
        path = source / entry["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("something else\n" if name != "project" else "{}")
    with pytest.raises(fetch_yellow.FetchError) as failure:
        fetch_yellow.check(record)
    message = str(failure.value)
    assert "expected" in message and "actual" in message, message


def test_download_refuses_a_url_that_is_not_pinned_to_the_commit(tmp_path):
    record = dict(PROVENANCE)
    record["tarball"] = dict(record["tarball"], url="https://codeload.example.com/tar.gz/main")
    with pytest.raises(fetch_yellow.FetchError, match="not pinned"):
        fetch_yellow.download(record, tmp_path / "download.tar.gz")


def _tarball(path: Path, names: list[str]) -> Path:
    import io
    import tarfile

    with tarfile.open(path, "w:gz") as tar:
        for name in names:
            data = b"x"
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def test_extraction_refuses_a_member_that_would_escape_the_source_folder(tmp_path):
    archive = _tarball(tmp_path / "evil.tar.gz", ["../escape.txt"])
    record = dict(PROVENANCE, ref="deadbeef", extract_to=str(tmp_path / "out"))
    with pytest.raises(fetch_yellow.FetchError, match="unsafe archive path"):
        fetch_yellow.extract(record, archive)
    assert not (tmp_path / "escape.txt").exists()


def test_extraction_refuses_an_archive_with_several_top_level_folders(tmp_path):
    archive = _tarball(tmp_path / "two.tar.gz", ["a/README.md", "b/README.md"])
    record = dict(PROVENANCE, ref="deadbeef", extract_to=str(tmp_path / "out2"))
    with pytest.raises(fetch_yellow.FetchError, match="one top-level directory"):
        fetch_yellow.extract(record, archive)


# -- the Studio 2 JSON reader ---------------------------------------------
def test_reader_strips_trailing_commas_from_objects_and_arrays():
    assert loads('{"a": 1, "b": [1, 2,],}') == {"a": 1, "b": [1, 2]}


def test_reader_never_edits_a_comma_inside_a_string():
    text = '{"sampleText": "abc, } and ], too", "list": [",}",],}'
    assert loads(text) == {"sampleText": "abc, } and ], too", "list": [",}"]}
    assert "abc, } and ], too" in json_text(text), "the string must survive untouched"


def test_reader_strips_comments_outside_strings_only():
    assert loads('{"a": 1, // trailing note\n}') == {"a": 1}
    assert loads('{"a": "http://example.com",}') == {"a": "http://example.com"}


def test_reader_names_the_file_it_cannot_parse(tmp_path):
    broken = tmp_path / "broken.yy"
    broken.write_text('{"a": ')
    with pytest.raises(GMS2Error, match="broken.yy"):
        read(broken)


def test_reference_helper_reads_gms2_asset_links():
    assert ref_name({"name": "spr_pl_down", "path": "sprites/spr_pl_down/spr_pl_down.yy"}) == "spr_pl_down"
    assert ref_name(None) is None and ref_name({"path": "x"}) is None


def test_png_size_reads_the_header_without_an_imaging_library(tmp_path):
    path = support.write_png(tmp_path / "img.png", 12, 7)
    assert png_size(path) == (12, 7)
    text = tmp_path / "not-a-png.png"
    text.write_bytes(b"PNG please")
    with pytest.raises(GMS2Error, match="not a PNG"):
        png_size(text)


# -- ID recovery -----------------------------------------------------------
def test_ids_come_from_both_pinned_records_and_land_in_their_own_band(fixture):
    _, _, registry = fixture
    assert registry.id_of("sprites", "spr_a") == 0
    assert registry.id_of("sprites", "spr_pl_down") == 1
    assert registry.merged("sprites", "spr_pl_down") == YELLOW_BASE + 1
    assert registry.merged("objects", "obj_pl") == YELLOW_BASE + 0
    assert registry.merged("rooms", "rm_a") == YELLOW_BASE + 0
    assert registry.counts()["sprites"] == len(support.FIXTURE["sprites"])
    with pytest.raises(GMS2Error, match="not inventing one"):
        registry.merged("sprites", "spr_never_existed")


def test_the_two_records_must_agree_or_nothing_is_converted(tmp_path):
    source, provenance = support.build_source(tmp_path, swap_sprite_order=True)
    with pytest.raises(GMS2Error, match="disagrees"):
        Registry(source, provenance)


def test_a_gapped_id_list_is_refused(tmp_path):
    source, provenance = support.build_source(tmp_path)
    order = source / "notes/Asset_Order/Asset_Order.txt"
    order.write_text(order.read_text().replace("3 - spr_fps", "7 - spr_fps"))
    with pytest.raises(GMS2Error, match="not 0..N-1"):
        Registry(source, provenance)


def test_provenance_that_disagrees_with_the_source_is_refused(tmp_path):
    source, provenance = support.build_source(tmp_path)
    provenance["documented_counts"]["sprites"] += 1
    with pytest.raises(GMS2Error, match="port/yellow_source.json documents"):
        Registry(source, provenance)


def test_folders_and_ids_that_do_not_line_up_are_reported_not_hidden(fixture):
    _, _, registry = fixture
    findings = {f["finding"]: f for f in registry.findings}
    assert "folder-without-id" in findings, "the tileset texture page has no sprite ID of its own"
    texture = findings["folder-without-id"]
    assert texture["category"] == "sprites" and "_decompiled_ts_a" in texture["names"]
    assert any(f["finding"] == "no-compiled-id-list" and f["category"] == "sequences" for f in registry.findings)


def test_a_name_both_games_use_keeps_its_own_id_on_each_side(tmp_path):
    source, provenance = support.build_source(tmp_path, collide_with_undertale=True)
    registry = Registry(source, provenance)
    table = collisions(registry, ROOT)
    assert table["sprites"] == [{"name": support.UNDERTALE_COLLISION,
                                 "yellow_id": YELLOW_BASE + registry.id_of("sprites", support.UNDERTALE_COLLISION)}]
    ours = undertale_names(ROOT)
    assert support.UNDERTALE_COLLISION in ours["sprites"], "the fixture must collide with a real Undertale sprite"
    assert "spr_maincharad" in ours["sprites"] and "obj_mainchara" in ours["objects"]


def test_the_yellow_band_cannot_reach_an_undertale_id(converted):
    manifest = (converted / "manifest.lua").read_text()
    names = re.search(r'\["names"\]=\{(.*?)\},\["objects"\]', manifest, re.S)
    assert names, "the Undertale manifest no longer exposes its names table"
    highest = max(int(value) for value in re.findall(r"=(-?\d+)", names.group(1)))
    assert highest < YELLOW_BASE, f"Undertale reaches ID {highest}; the Yellow band would collide"
    rooms = re.search(r'\["room_order"\]=\{(.*?)\}', manifest, re.S)
    assert max(int(v) for v in re.findall(r"-?\d+", rooms.group(1))) < YELLOW_BASE
