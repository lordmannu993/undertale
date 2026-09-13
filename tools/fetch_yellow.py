#!/usr/bin/env python3
"""Fetch the pinned Undertale Yellow decompilation this port merges.

Yellow's assets are roughly 580 MB, so they are not committed. They are fetched
from one immutable commit of ``lordmannu993/UnderTale-Yellow`` into the
git-ignored ``yellow_src/`` directory, exactly as ``tools/recover_paths.py``
fetches movement-path data from a pinned upstream dump.

Everything needed to reproduce the fetch lives in ``port/yellow_source.json``:
the commit, the tarball digest and size, and the digests of the two index files
the converter derives asset IDs from. A mismatch is a hard failure that names
both digests; nothing is repaired, substituted or invented.

Usage::

    python3 tools/fetch_yellow.py                       # download, verify, extract
    python3 tools/fetch_yellow.py --check               # verify yellow_src/ offline
    python3 tools/fetch_yellow.py --tarball-cache DIR   # reuse/keep the download (CI)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = ROOT / "port" / "yellow_source.json"
CHUNK = 1 << 20


class FetchError(RuntimeError):
    """Raised when the pinned source cannot be reproduced exactly."""


def provenance() -> dict:
    if not PROVENANCE.is_file():
        raise FetchError(f"missing provenance record {PROVENANCE}")
    record = json.loads(PROVENANCE.read_text())
    for field in ("upstream", "ref", "tarball", "index_files", "extract_to"):
        if field not in record:
            raise FetchError(f"{PROVENANCE.name}: provenance has no '{field}'")
    if len(record["ref"]) != 40 or any(c not in "0123456789abcdef" for c in record["ref"]):
        raise FetchError("provenance ref must be a full immutable commit SHA, never a branch")
    return record


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            hasher.update(block)
    return hasher.hexdigest()


def source_dir(record: dict) -> Path:
    return ROOT / record["extract_to"]


def pinned_marker(record: dict) -> Path:
    return source_dir(record) / ".pinned.json"


def verify_index_files(record: dict) -> list[str]:
    """Check the extracted tree carries the exact index files the IDs come from."""
    checked = []
    for name, entry in sorted(record["index_files"].items()):
        path = source_dir(record) / entry["path"]
        if not path.is_file():
            raise FetchError(f"yellow_src is missing the pinned {name} file: {entry['path']}")
        actual = digest(path)
        if actual != entry["sha256"]:
            raise FetchError(
                f"{entry['path']} does not match the pinned {name} digest\n"
                f"  expected {entry['sha256']}\n  actual   {actual}")
        checked.append(entry["path"])
    return checked


def already_fetched(record: dict) -> bool:
    marker = pinned_marker(record)
    if not marker.is_file():
        return False
    try:
        pinned = json.loads(marker.read_text())
    except json.JSONDecodeError:
        return False
    return pinned.get("ref") == record["ref"] and pinned.get("tarball_sha256") == record["tarball"]["sha256"]


def download(record: dict, destination: Path) -> str:
    url = record["tarball"]["url"]
    if record["ref"] not in url:
        raise FetchError(f"tarball URL is not pinned to the provenance commit: {url}")
    print(f"Downloading {url} ({record['tarball']['bytes'] / 1024**2:.0f} MiB) ...")
    hasher = hashlib.sha256()
    written = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "undertale-love-port-yellow-merge"})
    with urllib.request.urlopen(request, timeout=1800) as response, temporary.open("wb") as handle:
        while True:
            block = response.read(CHUNK)
            if not block:
                break
            handle.write(block)
            hasher.update(block)
            written += len(block)
    temporary.replace(destination)
    actual = hasher.hexdigest()
    if actual != record["tarball"]["sha256"]:
        raise FetchError(
            "downloaded tarball does not match the pinned digest\n"
            f"  expected {record['tarball']['sha256']}\n  actual   {actual}\n"
            f"  wrote {written} bytes, provenance says {record['tarball']['bytes']}")
    if written != record["tarball"]["bytes"]:
        raise FetchError(f"tarball size changed: {written} bytes, pinned {record['tarball']['bytes']}")
    return actual


def safe_members(archive: tarfile.TarFile, prefix: str):
    """Yield only regular files under the archive's single top-level directory."""
    for member in archive.getmembers():
        if not member.isfile():
            if member.isdir() or member.issym() or member.islnk():
                continue
            raise FetchError(f"refusing to extract unsupported archive member: {member.name}")
        parts = Path(member.name).parts
        if len(parts) < 2 or parts[0] != prefix:
            raise FetchError(f"unexpected archive layout: {member.name}")
        if any(part in ("..", "") or part.startswith("/") for part in parts):
            raise FetchError(f"unsafe archive path: {member.name}")
        member.name = "/".join(parts[1:])
        yield member


def extract(record: dict, tarball: Path) -> int:
    target = source_dir(record)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    prefix = f"UnderTale-Yellow-{record['ref']}"
    count = 0
    with tarfile.open(tarball, "r:gz") as archive:
        names = archive.getnames()
        tops = {n.split("/", 1)[0] for n in names}
        if tops != {prefix}:
            # GitHub names the folder after the repository and commit; accept that
            # single folder only, and say so if upstream packaging ever changes.
            if len(tops) != 1:
                raise FetchError(f"tarball does not have one top-level directory: {sorted(tops)[:5]}")
            prefix = tops.pop()
        for member in safe_members(archive, prefix):
            destination = target / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise FetchError(f"archive member vanished while extracting: {member.name}")
            with source, destination.open("wb") as handle:
                shutil.copyfileobj(source, handle, CHUNK)
            count += 1
    if count == 0:
        raise FetchError("tarball extracted no files")
    pinned_marker(record).write_text(json.dumps(
        {"ref": record["ref"], "tarball_sha256": record["tarball"]["sha256"], "files": count}, indent=2) + "\n")
    return count


def fetch(record: dict, cache: Path | None, force: bool) -> int:
    if already_fetched(record) and not force:
        verify_index_files(record)
        print(f"yellow_src/ already holds the pinned commit {record['ref'][:12]}; nothing to download.")
        return 0
    tarball = (cache / f"undertale-yellow-{record['ref']}.tar.gz") if cache else \
        Path(tempfile.gettempdir()) / f"undertale-yellow-{record['ref']}.tar.gz"
    if tarball.is_file() and digest(tarball) == record["tarball"]["sha256"]:
        print(f"Using cached tarball {tarball}")
    else:
        if tarball.is_file():
            tarball.unlink()
        download(record, tarball)
    try:
        count = extract(record, tarball)
        verify_index_files(record)
    finally:
        if cache is None:
            tarball.unlink(missing_ok=True)
    print(f"Extracted {count} files into {record['extract_to']}/ at commit {record['ref'][:12]}.")
    return count


def check(record: dict) -> int:
    """Offline verification: is the pinned source present and byte-identical where it matters?"""
    target = source_dir(record)
    if not target.is_dir():
        raise FetchError(f"{record['extract_to']}/ is absent; run: python3 tools/fetch_yellow.py")
    if not already_fetched(record):
        raise FetchError(f"{record['extract_to']}/ is not the pinned commit {record['ref']}")
    verify_index_files(record)
    counts = {}
    for folder in ("sprites", "objects", "rooms", "sounds", "tilesets", "fonts", "paths", "scripts", "shaders", "sequences"):
        counts[folder] = len([p for p in (target / folder).iterdir() if p.is_dir()]) if (target / folder).is_dir() else 0
    documented = record["documented_counts"]
    problems = []
    for folder, key in [("sprites", "sprite_folders_on_disk"), ("scripts", "script_folders_on_disk")]:
        if counts[folder] != documented[key]:
            problems.append(f"{folder}: {counts[folder]} folders on disk, provenance documents {documented[key]}")
    print("Pinned Yellow source verified:")
    print(f"  commit   {record['ref']}")
    print(f"  indexes  {', '.join(sorted(record['index_files']))}")
    print("  folders  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if problems:
        raise FetchError("yellow_src/ disagrees with the pinned provenance:\n  " + "\n  ".join(problems))
    return sum(counts.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="verify an existing yellow_src/ without any network access")
    parser.add_argument("--force", action="store_true", help="re-download and re-extract even if the pinned source is present")
    parser.add_argument("--tarball-cache", type=Path, help="directory used to keep the downloaded tarball between runs (CI cache)")
    args = parser.parse_args()
    record = provenance()
    try:
        if args.check:
            check(record)
        else:
            fetch(record, args.tarball_cache.resolve() if args.tarball_cache else None, args.force)
    except (FetchError, OSError, urllib.error.URLError, tarfile.TarError) as exc:  # noqa: PERF203
        print(f"Yellow source fetch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
