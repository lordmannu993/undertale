import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

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


def test_android_builder_requires_explicit_experimental_acknowledgement():
    result=subprocess.run([sys.executable,str(ROOT/"tools/build_android.py")],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode != 0
    assert "--allow-experimental" in result.stderr
    assert "not a finished full-game port" in result.stderr
