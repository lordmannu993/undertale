#!/usr/bin/env python3
"""Fetch the one absent room source, pinned for a later GMX adapter."""
from __future__ import annotations
import argparse, base64, hashlib, json, pathlib, urllib.request, os

ROOT = pathlib.Path(__file__).resolve().parents[1]
REF = "249ffa27ee7e7eee0d7ce84b736c294458b38685"
URL = f"https://raw.githubusercontent.com/kittibyte/UndertaleDecomp/{REF}/rooms/room_fire_walkandbranch/room_fire_walkandbranch.yy"
OUT = ROOT / "port" / "recovered_rooms" / "room_fire_walkandbranch.yy"
META = ROOT / "port" / "recovered_rooms" / "manifest.json"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    api = f"https://api.github.com/repos/kittibyte/UndertaleDecomp/contents/rooms/room_fire_walkandbranch/room_fire_walkandbranch.yy?ref={REF}"
    request = urllib.request.Request(api, headers={"Accept": "application/vnd.github+json"})
    if os.environ.get("GITHUB_TOKEN"):
        request.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
    data = base64.b64decode(json.load(urllib.request.urlopen(request))["content"])
    digest = hashlib.sha256(data).hexdigest()
    if args.check:
        if not OUT.exists() or hashlib.sha256(OUT.read_bytes()).hexdigest() != digest:
            raise SystemExit("recovered room is stale or absent")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(data)
    META.write_text(json.dumps({"format": 1, "room_id": 159, "name": "room_fire_walkandbranch",
        "upstream": "kittibyte/UndertaleDecomp", "ref": REF,
        "file": "rooms/room_fire_walkandbranch/room_fire_walkandbranch.yy",
        "sha256": digest, "status": "source recovered; GMX adapter still required"}, indent=2) + "\n")
    print(f"wrote {OUT} ({len(data)} bytes, sha256 {digest})")

if __name__ == "__main__":
    main()
