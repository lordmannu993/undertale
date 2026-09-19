"""The repo page shows master's README, so a stale download link there is what
sends people to the previous build. These checks are offline: they compare the
README, the pinned publisher workflow, `port/version.lua` and the release notes
with each other. `tools/check_download_links.py` is the online half (run in
CI), and its pure parsing/staleness helpers are unit-tested here too.
"""
import re

import pytest

from conftest import ROOT
from tools.check_download_links import (
    advertised_size,
    newest_published,
    parse_readme,
    parse_source_commit,
    parse_workflow_env,
)

README = (ROOT / "README.md").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/love-prerelease.yml").read_text(encoding="utf-8")
NOTES = (ROOT / "docs/RELEASE_NOTES.md").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

ENV = parse_workflow_env(WORKFLOW)
LINKS = parse_readme(README)["links"]
DOWNLOAD = [link for link in LINKS if link["kind"] == "download"]
PAGES = [link for link in LINKS if link["kind"] == "tag"]
RUNTIME_VERSION = re.search(r'number="([^"]+)"', (ROOT / "port/version.lua").read_text(encoding="utf-8")).group(1)


def test_readme_advertises_exactly_the_release_the_workflow_would_publish():
    assert ENV["RELEASE_TAG"] and ENV["ASSET_BASE"]
    # One download link, not a current one plus a leftover older one.
    assert [link["tag"] for link in DOWNLOAD] == [ENV["RELEASE_TAG"]]
    assert [link["asset"] for link in DOWNLOAD] == [f"{ENV['ASSET_BASE']}.love"]
    assert [link["tag"] for link in PAGES] == [ENV["RELEASE_TAG"]]
    assert all(link["repo"] == PAGES[0]["repo"] for link in LINKS)


def test_readme_shows_the_asset_name_size_and_a_newest_releases_route():
    line = next(line for line in README.splitlines() if ENV["ASSET_BASE"] + ".love" in line and "releases/download" in line)
    assert f"{ENV['ASSET_BASE']}.love" in line, "the clickable text must name the file people are downloading"
    assert advertised_size(line), "the download line must advertise an approximate size"
    repo = PAGES[0]["repo"]
    assert f"https://github.com/{repo}/releases)" in README, "link the releases index so older builds are findable"
    assert f"**Newest build: v{RUNTIME_VERSION}**" in README, "say which build is newest, in words"
    assert parse_source_commit(README), "state the source commit the archive was built from"


def test_no_older_download_link_survives_in_any_document():
    stale = []
    for path in ROOT.rglob("*.md"):
        parts = set(path.relative_to(ROOT).parts)
        if parts & {"generated", "yellow_src", "artifacts", ".git", "node_modules"}:
            continue
        for link in parse_readme(path.read_text(encoding="utf-8"))["links"]:
            if link["kind"] == "download" and link["tag"] != ENV["RELEASE_TAG"]:
                stale.append(f"{path.relative_to(ROOT)} links {link['tag']}")
    assert not stale, "a superseded build is still advertised: " + "; ".join(stale)


def test_release_tag_asset_and_notes_carry_the_runtime_version():
    assert ENV["RELEASE_TAG"] == f"love-v{RUNTIME_VERSION}-fusion-experimental"
    assert ENV["ASSET_BASE"] == f"undertale-yellow-fusion-v{RUNTIME_VERSION}-experimental"
    assert f"v{RUNTIME_VERSION}" in WORKFLOW, "the workflow's release title/pins must name the version"
    assert README.startswith("# UNDERTALE"), "sanity: README is the file the repo page renders"
    first_version_heading = re.search(r"^## v(\d+\.\d+\.\d+)", NOTES, re.MULTILINE)
    assert first_version_heading and first_version_heading.group(1) == RUNTIME_VERSION, (
        "docs/RELEASE_NOTES.md must lead with the version being published"
    )


def test_the_published_release_record_names_the_same_tag():
    row = next((line for line in AGENTS.splitlines() if line.startswith("| Published release |")), None)
    assert row and ENV["RELEASE_TAG"] in row, "AGENTS.md's published-release row must name the tag the README links"


def test_source_only_note_is_tied_to_the_build_it_describes():
    """Fixes merged after a build are advertised as source-only, not as shipped.

    This is the honesty rule for the download section: if such a note is
    present, it must name the version of the archive it is talking about and
    cite the pull request that carries the fixes.
    """
    section = README.split("### Merged after this archive was built", 1)
    if len(section) == 1:
        pytest.skip("no source-newer-than-the-download note in the README")
    note = section[1].split("\n### ", 1)[0]
    assert f"v{RUNTIME_VERSION}" in note
    assert "https://github.com/lordmannu993/undertale/pull/" in note


def test_link_checker_parses_the_readme_and_finds_the_newest_release():
    parsed = parse_readme(
        "See [the build (~390 MB)](https://github.com/o/r/releases/download/tag-1/thing.love)\n"
        "and [the notes](https://github.com/o/r/releases/tag/tag-1).\n"
    )["links"]
    assert [(link["kind"], link["tag"], link["asset"]) for link in parsed] == [
        ("download", "tag-1", "thing.love"),
        ("tag", "tag-1", None),
    ]
    assert parsed[0]["size"] == advertised_size("x (~390 MB)")
    assert advertised_size("no size here") is None


def test_link_checker_reads_the_claimed_source_commit():
    assert parse_source_commit("source commit `1538133`, SHA-256 in the release notes") == "1538133"
    assert parse_source_commit("**Source commit: 1538133e23de**") == "1538133e23de"
    assert parse_source_commit("no provenance claimed here") is None


def test_link_checker_ignores_drafts_when_deciding_which_release_is_newest():
    releases = [
        {"tag_name": "published-old", "draft": False, "published_at": "2026-01-01T00:00:00Z"},
        {"tag_name": "published-new", "draft": False, "published_at": "2026-09-19T10:35:05Z"},
        {"tag_name": "draft-next", "draft": True, "published_at": None},
    ]
    assert newest_published(releases)["tag_name"] == "published-new"
    assert newest_published([]) is None
