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

Since pieces 1 and 2 of the **Undertale Yellow merge** it also carries a GameMaker
*Studio 2* front end (`tools/yellow/`, `tools/gml2.py`, `tools/yellow_convert.py`,
`tools/fetch_yellow.py`) that converts a second, fetched-on-demand project into the
same runtime. That merge is **complete** (all five pieces, published as
`love-v1.2.0-fusion-experimental`); its piece list and the shipped scope are
[docs/YELLOW.md](docs/YELLOW.md). Future work is expected to be owner-reported
bugs and fidelity gaps, not unchecked pieces.

## Start here, in order

1. `git fetch origin && git log --oneline origin/master -3` and `gh pr list --state all`.
2. Read the piece list and its statuses in [`docs/PATHS.md`](docs/PATHS.md), then the
   limitation set in `docs/PORTING.md`.
3. Set up: `python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt`.
4. Pick the **highest unchecked piece** and treat it as the whole job. One piece per commit,
   small commits, one PR.
5. Before pushing: `.venv/bin/python -m pytest -q` green, and update the piece list in the
   same commit. CI runs the rest (`pytest` **and** the native LÖVE gate).

### Undertale Yellow merge: what to know before touching it

- Piece 3 added event dispatches Yellow needs and Undertale never uses (Clean Up,
  Draw Begin/End, Draw GUI Begin/GUI/GUI End, Pre/Post-Draw, per-instance mouse).
  They are inert for Undertale, but keep them inert: a new dispatch that fires for
  an Undertale object changes verified draw-call and event counts.
- The goal is **one traversable world**: River Person boat rides (`obj_dogboat_thing`,
  `SCR_TEXT` cases 587-585, destination `global.flag[459]`) and Yellow's UGPS mail whale
  (`obj_mail_whale` → `obj_fast_travel_menu`, `global.fast_travel_list`) are the two hubs
  that will connect the games. The owner explicitly rejected bolting Yellow items onto
  Undertale shops as a shortcut.
- The player is **Frisk** (`obj_mainchara`) everywhere. Clover is not playable; Yellow's
  `obj_pl` keeps its mechanics but is drawn as Frisk, with Clover's `spr_pl_run_*` set
  supplying the run animation the owner wants on the **X button**.
- Frisk keeps Undertale's weapons/armours and gains Clover's **ammunition** (weapon
  modifier: Rubber/Pebble/Silver/Glass/Ice Pellets/Cff Bean/Flint/Nails/Friendliness
  Pellets, `scr_item_stats_weapon_mod`) and **accessories** (armour modifier: Patch,
  Feather, Honeydew Pin, Band Merch Pin, Safety Jacket, Steel Buckle, Fancy Holster,
  Safety Goggles, Silver Scarf, G. Bandana, Delta Rune Patch, Golden Scarf,
  `scr_item_stats_armor_mod`).
- Yellow assets are **never committed** (~580 MB). Fetch once with
  `python3 tools/fetch_yellow.py` (309 MB tarball, ~11 s to extract, 856 MB on disk);
  CI caches the tarball in `.yellow-cache/` and sets `PORT_REQUIRE_YELLOW=1` so the live
  gates fail rather than skip. Without `yellow_src/`, those gates skip locally.
- Yellow IDs live at `1000000 + the pinned Asset_Order ID`. Undertale's highest ID is
  22,471, so the bands cannot meet; `tests/test_yellow_source.py` asserts that.
- Ten sprite, ten object, twenty-one sound and one font name exist in **both** games.
  The merged manifest must keep Undertale's `names` map and Yellow's beside it, never
  overwrite one with the other.

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
| `master` | PRs 1-13 merged (through `229db7a`): the LÖVE port, touch controls and Android tooling, the v0.1.1-v0.1.3 softlock/sprite/scenery fixes, path-recovery pieces 1-5, registry and room-159 evidence, the v0.1.4-v0.1.7 publications, PR #11's Ruins spike-bridge softlock, X-skip text-overlap and touch COLLISION-toggle fixes, and PR #13's monster body-part ID recovery that fixed the reported "cannot battle in Snowdin — instance_create Missing object ID 255" crash. PRs #14-#17 shipped v0.1.8-v0.1.10 (part-ID recovery, one-shot alarms, Glyde 20x + 709 EXP). PRs #18-#22 landed the Undertale Yellow merge pieces 1-5 through the partial piece-5 world. PR #23 finishes piece 5 and publishes the fusion |
| Published release | `love-v1.2.0-fusion-experimental` (prerelease, 4 assets incl. both conversion reports, checksum in notes) is the merged Undertale ⊕ Undertale Yellow build, published by the pinned workflow with the fused native gate. `love-v0.1.5`…`v0.1.10-experimental` stay up, renamed with a "Superseded —" prefix. Every published release is immutable: do not re-publish over it |
| Open PR | **#24** (owner round 1): `port/frisk.lua` now asserts every one of the 24 run poses stays Clover's and none enters the walk remap (the startup report counts them instead of `#remap`, which was always 0), and PAUSE gains **AUTO RUN: ON/OFF** beside COLLISION - Yellow's own `option_autorun`, persisted in `touch-settings-v1.txt`, mirrored to the `Controls.sav` key Yellow's `scr_savecontrols` writes, and re-applied on boot and after every crossing. Documented in `docs/CONTROLS.md` and the README. Still open from the report: "it bugs a lot" (no reproducible symptom yet) and the newer River Person / UGPS availability request |
| Yellow merge | **Complete.** `tools/fetch_yellow.py` pins commit `4ec23bd9` of `lordmannu993/UnderTale-Yellow`; `tools/yellow_convert.py --stage rooms` converts 3 796 sprites / 673 sounds / 11 fonts / 1 155 script resources / 3 224 objects with 8 494 events / **287 rooms, 68 paths, 199 454 drawables, 3 006 layers** into `generated/yellow/`, with 1 178 named function exports, 1 explicit GMLive stop (the shipped build's GMLive is inert, so the other 21 convert literally) and 0 compile errors. `tools/merge.py` + `port/merge.lua` build one manifest from both games, `port/travel.lua` connects the River Person boat (hold X during the ride) and Yellow's UGPS whale, `port/frisk.lua` draws Yellow's player as Frisk (28 walk poses remapped; the 24 run poses, the gun poses, goggles, dance and lying stay Clover - listed and asserted, so a run pose entering the remap stops the build), Yellow's own pause menu equips Clover's ammo/accessories beside Frisk's own gear, and the port's pause menu carries the merged AUTO RUN toggle, and `merge.sav` versions the merged layer including the loadout. The native LÖVE/xvfb gate crosses between worlds and back. Still unclaimed: Yellow's battle/story systems, shaders (reported, skipped), 25 rooms with named stops, and any Android-device certification |
| Part-ID recovery | `tools/recover_parts.py` fetches nothing by default: the checked-in `port/recovered_parts.json` is imported by `convert.py`. Regenerate with `GITHUB_TOKEN="$(gh auth token)" python3 tools/recover_parts.py` (pinned to the same `249ffa27` ref as the registry/path recoveries), re-verify offline with `--check`. IDs come from this checkout's own `partN=` literals; only names are paired from upstream; 38 annotated sites are re-validated as anchors. `tests/test_monster_parts.py` guards all of it plus every Snowdin battlegroup end-to-end |
| Old releases | `love-v0.1.0`..`love-v0.1.10-experimental` are **kept on purpose** (owner declined deletion) and renamed with a "Superseded (…)" prefix as each is replaced. Version branches `v0.1.0`..`v0.1.3` point at each tagged build |
| Release plumbing | `.github/workflows/love-prerelease.yml` publishes on push to one pinned branch (`arena/01a09ffd-undertale` for the v1.2.0 fusion) and **refuses unless a draft release with that tag already exists**; `workflow_dispatch` re-runs it. The publish job fetches Yellow, converts, runs the suite with `PORT_REQUIRE_YELLOW=1`, packages `--merged`, runs the fused native gate, uploads four assets and flips `--draft=false` |

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
.venv/bin/python -m pytest -q                                   # headless suite (285 at this validation)
python3 tools/fetch_yellow.py --check                           # pinned Yellow source present and intact
python3 tools/yellow_convert.py --stage scripts                 # Yellow pieces 1-2: assets plus 1,155 GMS2 script resources
python3 tools/yellow_convert.py --stage objects                 # Yellow pieces 1-3: plus all 3,224 objects and 8,494 events
python3 tools/yellow_convert.py --stage rooms                   # Yellow piece 4: plus all 287 rooms, 68 paths and their drawables
python3 tools/merge.py                                          # piece 5: write generated/merged/manifest.lua from both conversions
python3 tools/package.py --merged --no-convert                  # the fusion archive: carries every referenced pinned Yellow asset file, gated on a complete Yellow rooms stage
python3 tools/recover_paths.py --check                          # path data still matches its pinned source
python3 tools/package.py --output artifacts/check.love          # reproducible archive + report gates
bash tools/native_smoke.sh artifacts/check.love                 # needs LOVE+xvfb: CI only
python3 tools/build_android.py --allow-experimental             # APK, needs JDK17 + SDK 34 + NDK 25.2.9519653
```

The native gate (`port/smoke.lua`) drives the real touch callbacks through the whole scripted
opening and asserts pixel/backdrop/draw-call facts; `tools/native_smoke.sh` fails the build unless
every named screenshot exists and `NATIVE SMOKE PASS` is in the log. Its tick budget and wall
timeout were both raised when the corridor walk was added — keep them raised, or the gate flakes.
