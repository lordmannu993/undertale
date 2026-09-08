# Agent continuity notes — read me first

Purpose: a new session pointed at this repository should be able to continue the work
without re-deriving history from a chat log. Everything below is verifiable in-repo or
via `gh`.

## What this repository is

An experimental **LÖVE 11.5 / Android port of a decompiled GameMaker 1.4 Undertale
export**. `tools/convert.py` translates the `.gmx`/`.gml` checkout into Lua under
`generated/` (git-ignored, rebuilt on demand); `port/*.lua` is a hand-written
GameMaker-semantics runtime; `tools/package.py` builds a `.love` release asset. It is
explicitly **not a finished game** and every release note says so.

## Start here, in order

1. `git fetch origin && git log --oneline origin/master -3` and `gh pr list --state all`.
2. Read the piece list and its statuses in [`docs/PATHS.md`](docs/PATHS.md), then the
   limitation set in `docs/PORTING.md`.
3. Set up: `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt`.
4. Pick the **highest unchecked piece** and treat it as the whole job. One piece per commit,
   small commits, one PR.
5. Before pushing: `.venv/bin/python -m pytest -q` green, and update the piece list in the
   same commit. CI runs the rest (`pytest` **and** the native LÖVE gate).

### Sandbox gotchas that cost time

- The clone is **shallow** (`.git/shallow`). Your session branch usually has one commit that
  already landed on master, so `git merge origin/master` fails with *unrelated histories*.
  Confirm the commit is upstream (`gh api .../compare/<sha>...origin/master` → `behind_by: 0`)
  and then `git reset --hard origin/master`.
- **Never rename or delete the session branch** (`arena/<id>-undertale`); Arena tracks the
  session by that name.
- No `apt` network here, so **LOVE cannot be installed in the sandbox**: native rendering can
  only be verified in CI. `port-test-output/` from the CI run carries the screenshots.
- `tools/recover_paths.py` needs a token for the GitHub contents API:
  `GITHUB_TOKEN="$(gh auth token)"`.
- **Issues are disabled** on this repo. Plans, piece lists and verification results go into PR
  descriptions/comments and `docs/`, not issues.

## Current state

| item | state |
| --- | --- |
| `master` | PRs 1-11 merged (through `e5705d2`): the LÖVE port, touch controls and Android tooling, the v0.1.1-v0.1.3 softlock/sprite/scenery fixes, path-recovery pieces 1-5, registry and room-159 evidence, the v0.1.4-v0.1.6 publications, and PR #11's Ruins spike-bridge softlock, X-skip text-overlap and touch COLLISION-toggle fixes |
| Published release | `love-v0.1.7-experimental` (prerelease, 3 assets, checksum in notes) is published by the pinned workflow from this session's branch and carries PR #11's fixes. `love-v0.1.5/6-experimental` stay up, renamed with a "Superseded —" prefix. Every published release is immutable: do not re-publish over it |
| Open PR | this session's PR: publish PR #11's three merged fixes as a downloadable `love-v0.1.7-experimental` build — `port/version.lua` bump, `docs/RELEASE_NOTES.md`, README download links and the "Fixed in v0.1.7" section, `docs/CONTROLS.md` for the new PAUSE row, and the workflow retarget. The **draft prerelease is created before** the workflow-touching push, because the job refuses to run without it |
| Old releases | `love-v0.1.0`..`love-v0.1.6-experimental` are **kept on purpose** (owner declined deletion) and renamed with a "Superseded (…)" prefix as each is replaced. Version branches `v0.1.0`..`v0.1.3` point at each tagged build |
| Release plumbing | `.github/workflows/love-prerelease.yml` publishes on push to one pinned branch and **refuses unless a draft release with that tag already exists** |

### To publish a version (only when a piece list says a release is due)

1. Bump `port/version.lua`, rewrite `docs/RELEASE_NOTES.md`.
2. Edit `love-prerelease.yml`: `RELEASE_TAG`, `ASSET_BASE`, `concurrency.group`, the title,
   the `on.push.branches` ref and the job's `if:` guard — all five, they are duplicated on purpose.
3. Create the **draft** prerelease first: `gh release create "$TAG" --draft --prerelease --title ... --target "$SHA"`.
4. Push the branch that triggers it; the job runs the tests, the packaging check and the native
   LÖVE gate, then verifies asset sizes/digests and flips `--draft=false`. It cannot overwrite a
   published build, which is intended.
5. Update the README download links (the repo page shows `master`'s README; a stale link there is
   what makes people download the old build).

## Hard rules, and why

1. **Never fabricate a resource or silently replace one.** A missing path/room/sound must stop
   with its name — that visible stop is what let the owner report a precise bug. `Runtime:unsupported`.
2. **Recovered data is fetched by a script and pinned to one immutable commit**, per-item
   provenance stored with it, and "no value was invented" is asserted in a test
   (`tests/test_paths.py::test_no_point_was_invented_locally`). Hand-typed numbers are not acceptable.
3. **Behaviour changes need evidence in the repo**, and deviations from documented GameMaker
   behaviour are listed, not hidden. Example: absolute-vs-relative path coordinates were settled
   by comparing `room_ruins1`'s instance placement with the path's first point.
4. **Claims stay scoped.** Tests prove: Lua syntax, converted flow up to the ruins entry, path
   math, native Linux rendering with software GL and null audio. They do not prove: Android GPU
   behaviour, audio fidelity, touch latency, or full-game playability. Release notes say this.
5. **Never delete published releases or force-push master.** Land work by PR and merge with
   `gh pr merge N --merge` (this repo's history is merge commits).

## Owner preferences observed

Playing on an **Android phone, no PC**, so anything requiring a local build, a `data.win` from
their own install, or re-signing an APK is a dead end — propose CI-buildable and downloadable
outcomes. They want work in **small pieces with each one recorded on GitHub**, and they do not
want licence or legality re-litigated: record provenance in `docs/PATHS.md` and move on. Prefer
"done, here is the evidence, here is the next piece" over option menus.

## Verification commands

```bash
.venv/bin/python -m pytest -q                                   # headless suite (157 at time of writing)
python3 tools/recover_paths.py --check                          # path data still matches its pinned source
python3 tools/package.py --output artifacts/check.love          # reproducible archive + report gates
bash tools/native_smoke.sh artifacts/check.love                 # needs LOVE+xvfb: CI only
python3 tools/build_android.py --allow-experimental             # APK, needs JDK17 + SDK 34 + NDK 25.2.9519653
```

The native gate (`port/smoke.lua`) drives the real touch callbacks through the whole scripted
opening and asserts pixel/backdrop/draw-call facts; `tools/native_smoke.sh` fails the build unless
every named screenshot exists and `NATIVE SMOKE PASS` is in the log. Its tick budget and wall
timeout were both raised when the corridor walk was added — keep them raised, or the gate flakes.
