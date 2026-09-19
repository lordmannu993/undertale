#!/usr/bin/env python3
"""Verify the README's download links against the published GitHub releases.

The repository page renders `master`'s README, so a stale link there is exactly
what makes a visitor download the old build. This checks, against the GitHub
API, that the README's `.love` link, release-page link and advertised size still
describe the **newest published release**, and that the linked asset really
exists with the published digest.

Two outcomes are deliberately distinguished:

* the API answered and something is stale or broken -> exit 1, with the exact
  link, the expected tag and what is published instead;
* the API could not be reached -> report it and exit 0, so CI does not fail on
  infrastructure. Nothing is claimed about the links in that case.

Usage:
    python3 tools/check_download_links.py                 # check this checkout's README
    python3 tools/check_download_links.py --tag love-v1.2.1-fusion-experimental
                                                          # show what a stale pin would report
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
WORKFLOW = ROOT / ".github/workflows/love-prerelease.yml"
API = "https://api.github.com"

RELEASE_URL = re.compile(
    r"https://github\.com/(?P<repo>[\w.-]+/[\w.-]+)/releases/(?P<kind>download|tag)/(?P<tag>[\w.-]+)"
    r"(?:/(?P<asset>[^)\s]+))?"
)
SIZE_IN_LINK = re.compile(r"~?([\d.,]+)\s*(MB|MiB|GB|GiB)", re.IGNORECASE)
SCALE = {"mb": 1e6, "mib": 1024.0 ** 2, "gb": 1e9, "gib": 1024.0 ** 3}


def parse_readme(text: str) -> dict:
    """Every release link the README shows, plus the sizes advertised next to them."""
    links = []
    for match in RELEASE_URL.finditer(text):
        # A markdown link's visible text is what precedes it on the same line.
        start = text.rfind("\n", 0, match.start()) + 1
        end = text.find("\n", match.start())
        line = text[start : len(text) if end == -1 else end]
        links.append(
            {
                "repo": match.group("repo"),
                "kind": match.group("kind"),
                "tag": match.group("tag"),
                "asset": match.group("asset"),
                "size": advertised_size(line),
            }
        )
    return {"links": links}


def parse_source_commit(text: str) -> str | None:
    """The `source commit abc1234` the download section claims, if it states one."""
    match = re.search(r"source commit\s*:?\s*`?([0-9a-f]{7,40})`?", text, re.IGNORECASE)
    return match.group(1).lower() if match else None


def advertised_size(line: str) -> int | None:
    """The first `~390 MB`-style figure on a link's line, in bytes."""
    match = SIZE_IN_LINK.search(line)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    return int(number * SCALE[match.group(2).lower()])


def parse_workflow_env(text: str) -> dict:
    """The `RELEASE_TAG`/`ASSET_BASE` the pinned publisher workflow uses."""
    env = {}
    for name in ("RELEASE_TAG", "ASSET_BASE"):
        match = re.search(rf"^\s*{name}:\s*(\S+)\s*$", text, re.MULTILINE)
        if match:
            env[name] = match.group(1)
    return env


def newest_published(releases: list[dict]) -> dict | None:
    """The newest non-draft release, by publication time (drafts have none)."""
    published = [release for release in releases if not release.get("draft") and release.get("published_at")]
    return max(published, key=lambda release: release["published_at"]) if published else None


def fetch_json(url: str, token: str | None, timeout: float) -> dict | list:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def fetch_text(url: str, token: str | None, timeout: float) -> str:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def asset_digest_matches(release: dict, asset: dict, token: str | None, timeout: float) -> tuple[bool, str]:
    """The `.love.sha256` asset's contents against the checksum in the release body."""
    recorded = re.search(r"\b([0-9a-f]{64})\b", release.get("body") or "")
    if not recorded:
        return True, "release notes carry no SHA-256 to compare"
    digest = fetch_text(asset["browser_download_url"], token, timeout).split()[0].strip()
    if digest != recorded.group(1):
        return False, f"sha256 asset says {digest[:16]}…, release notes say {recorded.group(1)[:16]}…"
    return True, f"sha256 asset matches the release notes ({digest[:16]}…)"


def check(repo: str, links: list[dict], tag: str, asset_base: str, token: str | None,
          timeout: float, problems: list[str], notes: list[str],
          readme_text: str = "") -> dict | None:
    releases = fetch_json(f"{API}/repos/{repo}/releases?per_page=100", token, timeout)
    newest = newest_published(releases)
    if newest is None:
        problems.append(f"{repo} has no published release; the README advertises {tag}")
        return None

    download = [link for link in links if link["kind"] == "download"]
    pages = [link for link in links if link["kind"] == "tag"]
    if len({link["tag"] for link in download}) != 1:
        problems.append(f"README shows downloads for {sorted({link['tag'] for link in download})}; it must show exactly the newest one")
    if [link["tag"] for link in download] != [tag]:
        problems.append(f"README's download link is not the expected tag: expected {tag}, README links {[link['tag'] for link in download]}")
    if [link["tag"] for link in pages] != [tag]:
        problems.append(f"README's release-page link is not the expected tag: expected {tag}, README links {[link['tag'] for link in pages]}")
    if newest["tag_name"] != tag:
        problems.append(
            f"STALE: the newest published release is {newest['tag_name']} "
            f"({newest['published_at'][:10]}), but the README links {tag}"
        )
    else:
        notes.append(f"newest published release is {newest['tag_name']} ({newest['published_at'][:10]}), as the README says")

    released = {asset["name"]: asset for asset in newest["assets"]}
    wanted = f"{asset_base}.love"
    archive = released.get(wanted)
    if archive is None:
        problems.append(f"{newest['tag_name']} has no {wanted}; assets are {sorted(released)}")
    else:
        if archive["state"] != "uploaded":
            problems.append(f"{wanted} is in state {archive['state']!r}")
        size_mib = archive["size"] / 1024.0 ** 2
        notes.append(f"{wanted} is {archive['size']:,} bytes ({size_mib:.1f} MiB) on {newest['tag_name']}")
        advertised = next((link["size"] for link in download if link["size"]), None)
        if advertised is None:
            notes.append("README advertises no size next to the download link; add one so a truncated upload is visible")
        elif not (0.95 <= archive["size"] / advertised <= 1.05):
            problems.append(
                f"README advertises {advertised:,} bytes, the published asset is {archive['size']:,} bytes"
            )
        else:
            notes.append(
                f"README's advertised size is close enough ({advertised:,} bytes advertised, "
                f"{archive['size']:,} published, {size_mib:.1f} MiB)"
            )
        checksum = released.get(f"{asset_base}.love.sha256")
        if checksum is None:
            notes.append(f"{newest['tag_name']} publishes no {asset_base}.love.sha256 asset")
        else:
            try:
                ok, detail = asset_digest_matches(newest, checksum, token, timeout)
            except (urllib.error.URLError, OSError, ValueError) as error:
                notes.append(f"could not read the checksum asset ({error})")
            else:
                (notes if ok else problems).append(detail)
    if newest["tag_name"] == tag:
        for name in (f"{asset_base}.conversion-report.json", f"{asset_base}.yellow-conversion-report.json"):
            notes.append(("present: " if name in released else "MISSING: ") + name)
        # The download section claims which source commit the archive was built
        # from; that claim is checkable, so check it.
        source = parse_source_commit(readme_text)
        target = newest.get("target_commitish") or ""
        if source is None:
            notes.append("README states no source commit for the archive")
        elif target.lower().startswith(source):
            notes.append(f"source commit {source} matches the release target")
        else:
            problems.append(
                f"README says the archive was built from {source}, but the release targets {target[:12] or '(unknown)'}"
            )
    return newest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", help="owner/name; default: the repository the README links")
    parser.add_argument("--tag", help="release tag to require; default: the pinned RELEASE_TAG")
    parser.add_argument("--asset-base", help="asset name without .love; default: the pinned ASSET_BASE")
    parser.add_argument("--readme", type=Path, default=README)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    readme_text = args.readme.read_text(encoding="utf-8")
    links = parse_readme(readme_text)["links"]
    if not links:
        print(f"FAIL: {args.readme} shows no GitHub release link at all")
        return 1
    env = parse_workflow_env(WORKFLOW.read_text(encoding="utf-8"))
    tag = args.tag or env.get("RELEASE_TAG")
    asset_base = args.asset_base or env.get("ASSET_BASE")
    repo = args.repo or links[0]["repo"]
    if not tag or not asset_base:
        print(f"FAIL: {WORKFLOW} does not pin RELEASE_TAG and ASSET_BASE")
        return 1
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    print(f"Checking {repo} against {args.readme.name} (expecting {tag} / {asset_base}.love)")
    problems: list[str] = []
    notes: list[str] = []
    try:
        check(repo, links, tag, asset_base, token, args.timeout, problems, notes, readme_text)
    except urllib.error.HTTPError as error:
        if error.code in (403, 429):
            print(f"Could not check: the GitHub API rate-limited this request (HTTP {error.code}). "
                  "Set GH_TOKEN to authenticate. No claim is made about the links.")
            return 0
        problems.append(f"the GitHub API answered HTTP {error.code} for {repo} ({error.reason})")
    except (urllib.error.URLError, OSError, ValueError) as error:
        print(f"Could not check: GitHub is unreachable from here ({error}). No claim is made about the links.")
        return 0

    for note in notes:
        print(f"  - {note}")
    for problem in problems:
        print(f"  ! {problem}")
    if problems:
        print(f"FAIL: {len(problems)} problem(s); the repo page would send people to the wrong build")
        return 1
    print(f"OK: {args.readme.name} points at the newest published release, {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
