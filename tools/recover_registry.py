#!/usr/bin/env python3
"""Recover resource-ID evidence that is safe to import from the pinned dump.

The decompiled checkout lost its resource registry.  This tool deliberately only
imports exact name/ID matches for resources present locally; it never assigns an
alphabetical or guessed ID.  The upstream lists are kept as audit evidence.
"""
from __future__ import annotations
import argparse, base64, json, os, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
REF = "249ffa27ee7e7eee0d7ce84b736c294458b38685"
REPO = "kittibyte/UndertaleDecomp"
SOURCES = {
    "sprites": "notes/OG%20Spritelist/OG%20Spritelist.txt",
    "sounds": "notes/OG%20Audiolist/OG%20Audiolist.txt",
    "rooms": "notes/OG%20Roomlist/OG%20Roomlist.txt",
}
OUT = ROOT / "port" / "recovered_registry.json"


def fetch(path: str) -> list[str]:
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?ref={REF}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as response:
        data = json.load(response)
    return [line.strip() for line in base64.b64decode(data["content"]).decode().splitlines() if line.strip()]


def local_names(category: str) -> set[str]:
    suffix = {"sprites": ".sprite.gmx", "sounds": ".sound.gmx", "rooms": ".room.gmx"}[category]
    directory = ROOT / {"sprites": "sprites", "sounds": "sound", "rooms": "rooms"}[category]
    return {p.name.removesuffix(suffix) for p in directory.glob(f"*{suffix}")}


def build() -> dict:
    lists = {category: fetch(path) for category, path in SOURCES.items()}
    recovered = {}
    for category, names in lists.items():
        # This is intentionally exact and case-sensitive.  The existing override
        # file remains authoritative when the two projects disagree.
        recovered[category] = {
            name: {"id": index, "source": {"upstream": REPO, "ref": REF, "file": SOURCES[category]}}
            for index, name in enumerate(names) if name in local_names(category)
        }
    return {"format": 1, "upstream": REPO, "ref": REF, "lists": lists, "recovered": recovered}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = build()
    if args.check:
        if not OUT.exists() or json.loads(OUT.read_text()) != data:
            raise SystemExit("recovered registry is stale; rerun tools/recover_registry.py")
    else:
        OUT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        print(f"wrote {OUT}")
        for category, values in data["recovered"].items():
            print(f"{category}: {len(values)} exact local names with pinned ID evidence")


if __name__ == "__main__":
    main()
