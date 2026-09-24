import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from conftest import ROOT
from tools.package import package


def test_archive_is_self_contained_reproducible_and_excludes_scratch(converted,tmp_path):
    # Explicit allowlists, not zip-the-entire-repository (including .git/saves).
    scratch=converted/"must-not-ship.lua"
    scratch.write_text('error("scratch must never ship")')
    try:
        first=package(tmp_path/"first.love",regenerate=False)
        second=package(tmp_path/"second.love",regenerate=False)
        assert hashlib.sha256(first.read_bytes()).digest()==hashlib.sha256(second.read_bytes()).digest()
        with zipfile.ZipFile(first) as archive:
            names=set(archive.namelist())
            assert {"main.lua","conf.lua","port/input.lua","generated/manifest.lua","generated/scripts/SCR_TEXT.lua"}<=names
            assert "sprites/images/spr_maincharad_0.png" in names
            assert "sound/audio/mus_story.ogg" in names
            assert "generated/must-not-ship.lua" not in names
            assert not any(".git" in n.split("/") or n.endswith((".gmx",".gml",".py",".jks",".keystore")) for n in names)
            assert not any(n in names for n in ["file0","file9","undertale.ini","touch-settings-v1.txt"])
            assert archive.testzip() is None
            report=json.loads(archive.read("generated/conversion-report.json"))
            assert not report["compile_errors"]
            # Known limits stay advertised: the report must still carry limitations and
            # the recovered-path set it was built from.
            assert report["limitations"] and report["path_provenance"]["upstream"]
            assert report["path_provenance"]["with_point_data"]==len(report["recovered_paths"])
            assert b"path_points" in archive.read("generated/manifest.lua")
            assert all(i.date_time==(1980,1,1,0,0,0) for i in archive.infolist())
    finally:
        scratch.unlink()


def _fake_merged_tree(tmp_path):
    generated = tmp_path / "generated"
    (generated / "yellow/assets").mkdir(parents=True)
    (generated / "merged").mkdir(parents=True)
    (generated / "yellow/conversion-report.json").write_text(json.dumps(
        {"stage": "rooms", "scripts": {"compile_errors": []}, "objects": {"compile_errors": []},
         "rooms": {"compile_errors": []}}))
    (generated / "yellow/assets/sprites_0.lua").write_text("return {}\n")
    (generated / "merged/manifest.lua").write_text("-- test\n")
    return generated


def test_merged_package_ships_the_item_catalog_and_stops_without_it(tmp_path, monkeypatch):
    """v1.2.4 stopped on boot: the .love had the merged manifest and not the catalog.

    tools/merge.py writes generated/merged/items.lua, and port/inventory.lua
    requires it on every merged launch. The file list that becomes the archive
    omitted it. This fails if that list drops the module again.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import package as packaging

    generated = _fake_merged_tree(tmp_path)
    monkeypatch.setattr(packaging.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(packaging, "ROOT", tmp_path)

    with pytest.raises(ValueError, match="generated/merged/items.lua"):
        packaging.merged_files(generated)

    (generated / "merged/items.lua").write_text("return {ut={}, yellow={}, pairs={}}\n")
    files = packaging.merged_files(generated)
    assert generated / "merged/items.lua" in files
    assert generated / "merged/manifest.lua" in files


def test_android_builder_requires_explicit_experimental_acknowledgement():
    result=subprocess.run([sys.executable,str(ROOT/"tools/build_android.py")],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode != 0
    assert "--allow-experimental" in result.stderr
    assert "not a finished full-game port" in result.stderr
