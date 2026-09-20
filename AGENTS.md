# Agent continuity notes — read me first

Purpose: a new session pointed at this repository should be able to continue the work
without re-deriving history from a chat log. Everything below is verifiable in-repo or
via `gh`.

## Standing instruction: when the user says "Proceed ❤️"

This is a durable, cross-session trigger. **When the user messages "Proceed ❤️" (or an
obvious variant), do not ask what to do — continue the Undertale + Undertale Yellow
**unified fusion** exactly as recorded on GitHub.** The requirement set is
[docs/UNIFIED_FUSION_SPEC.md](docs/UNIFIED_FUSION_SPEC.md) (binding, owner-issued); the
**live work queue, current head, and exact steps** are
[docs/FUSION_STATUS.md](docs/FUSION_STATUS.md). Do these, in order:

1. **Orient.** `git fetch origin`. Read `docs/FUSION_STATUS.md` §1 (current fusion
   head) and §3 (ordered piece list). The work is "do the single highest-numbered ⬜
   piece, in order."
2. **Inherit completed work.** A fresh session is branched from `master`, and the
   owner asked that the fusion not be merged until the end — so completed pieces live
   on the current open fusion PR branch. Bring it in first:
   `git merge --no-edit origin/arena/01a0be2f-undertale` (the head named in
   `docs/FUSION_STATUS.md` §1). If it conflicts, resolve in favour of the newer
   `docs/PORTING.md`/`AGENTS.md` and re-run the suite before continuing.
3. **Set up + get green.** Run `docs/FUSION_STATUS.md` §4 (venv, fetch Yellow,
   `yellow_convert --stage rooms` → `merge` → `convert`, then `pytest -q`). The suite
   **must be green before you change anything.**
4. **Do the next ⬜ piece** (§3), smallest-green-increment first if a piece is large.
   Follow the non-negotiable rules in `docs/FUSION_STATUS.md` §2 — one player state,
   no per-room/character hacks, depth = logical Y + sprite visual bottom point,
   recovered data pinned & fetched (never hand-typed), missing resources stop by name.
5. **A piece is done** only when `docs/FUSION_STATUS.md` §5 holds: a test that fails
   without it, a `docs/` line, a scoped claim, green local + CI, and this file and
   `FUSION_STATUS.md` updated **in the same commit**.
6. **Record + push.** Commit on the session branch, push, keep the fusion PR **open**
   (advance the "current head" in `FUSION_STATUS.md` §1), and note "piece N done, here
   is the evidence, here is piece N+1" in the PR body.

**Do not merge the final fusion** until piece #8 (the §15/§16 acceptance matrix) is
itself green — that is the single merge, per the owner's instruction. Never
force-push `master`; never delete a release.

If you are *already* on the current head branch and the top piece is already done,
just continue to the next ⬜ piece — the trigger is idempotent.

## What this repository is

An experimental **LÖVE 11.5 / Android port of a decompiled GameMaker 1.4 Undertale
export**. `tools/convert.py` translates the `.gmx`/`.gml` checkout into Lua under
`generated/` (git-ignored, rebuilt on demand); `port/*.lua` is a hand-written
GameMaker-semantics runtime; `tools/package.py` builds a `.love` release asset. It is
explicitly **not a finished game** and every release note says so.

Since pieces 1 and 2 of the **Undertale Yellow merge** it also carries a GameMaker
*Studio 2* front end (`tools/yellow/`, `tools/gml2.py`, `tools/yellow_convert.py`,
`tools/fetch_yellow.py`) that converts a second, fetched-on-demand project into the
same runtime. All five conversion pieces shipped (published as
`love-v1.2.0-fusion-experimental`, since v1.2.3); its piece list and the shipped
scope are [docs/YELLOW.md](docs/YELLOW.md).

**"Five pieces complete" means the conversion pipeline is complete — it does not
mean the two games play as one game.** The owner reports that the shipped fusion
still behaves as two games in one executable (separate inventory/progression,
swapped-in character controllers, broken overworld depth, duplicated sprite
layers). The binding requirement set for fixing that is
[`docs/UNIFIED_FUSION_SPEC.md`](docs/UNIFIED_FUSION_SPEC.md) — read it before
touching the merge, and treat it as authoritative where it and `docs/YELLOW.md`
disagree.

## Start here, in order

1. `git fetch origin && git log --oneline origin/master -3` and `gh pr list --state all`.
2. Read the owner's binding brief, [`docs/UNIFIED_FUSION_SPEC.md`](docs/UNIFIED_FUSION_SPEC.md)
   (16 numbered requirements + acceptance criteria), then the **fusion work queue**
   and current head in [`docs/FUSION_STATUS.md`](docs/FUSION_STATUS.md) (this is what
   "Proceed ❤️" continues), then the Yellow piece list in [`docs/PATHS.md`](docs/PATHS.md),
   then the limitation set in `docs/PORTING.md`.
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

## v1.2.3 release task (2026-09-19)

- [x] Carry PR #30's four phone fixes (dialogue-box depth −400, GameMaker
  Studio 2 touch built-ins, River Person pager label layout, cached
  `isA`/collision/static-tile drawing) in the next downloadable archive.
- [x] Bump runtime, README download links, release notes and pinned publisher
  to v1.2.3 on `arena/01a0b9dd-undertale`; delete the README's "Merged after
  this archive was built" note, since this build contains those fixes.
- [x] Publish `love-v1.2.3-fusion-experimental` through the draft-only
  workflow: [run 35446420402](https://github.com/lordmannu993/undertale/actions/runs/35446420402)
  passed all 421 tests, merged packaging, native Linux LÖVE and four-asset
  size/digest verification. Source commit:
  `6d59f5d32b9820340877393eb97df284ce663904`. The README/source-commit
  follow-up is this branch's second metadata commit (no code changes).
- [x] Retitle the superseded v1.2.2 release with the "Superseded — " prefix.

## v1.2.2 release task (2026-09-19)

- [x] Replace the Snowdin Inn's fixed low-LV HP table with a temporary heal to
  at least `global.maxhp + 10`; never raise maxhp or stack repeat-stay bonuses.
  This is an owner-requested gameplay rule, documented in `docs/PORTING.md`.
- [x] Add wake-up regression coverage at every LV, including LV 20's 99 maxhp,
  injured/full/overhealed HP, repeat stays and leveling between stays.
- [x] Carry merged PR #27's River Person Yellow destination fix in the next
  downloadable archive (v1.2.1 predates it).
- [x] Bump runtime, README download links, release notes and pinned publisher
  to v1.2.2 on `arena/01a0b92c-undertale`.
- [x] Publish `love-v1.2.2-fusion-experimental` through the draft-only workflow:
  [run 35437354479](https://github.com/lordmannu993/undertale/actions/runs/35437354479)
  passed all 413 tests, merged packaging, native Linux LÖVE and four-asset
  size/digest verification. Source commit: `1538133e23dee7605401768c38d875eb41e53e74`.
  README/source changes are in [PR #29](https://github.com/lordmannu993/undertale/pull/29).
  GitHub's published archive digest matches the release-note checksum; sandbox
  re-download was blocked by TLS/EOF to GitHub's release-asset host, so no
  independent local download verification is claimed.
- [x] Make the README's download section say plainly which build is newest (tag,
  date, source commit, size, release-page and all-releases links) and which
  merged fixes that archive does not contain yet. Two guards now keep it from
  going stale again: `tests/test_release_docs.py` (offline — README against the
  workflow's `RELEASE_TAG`/`ASSET_BASE`, `port/version.lua`, the release notes
  and every other `.md` in the repo) and `tools/check_download_links.py`
  (online — the linked tag is the *newest published* release, the asset exists
  with the advertised size and a checksum matching the release notes), which the
  `LOVE port tests` workflow runs. Both were verified to fail on a stale pin.

## Current state

| item | state |
| --- | --- |
| `master` | PRs 1-13 merged (through `229db7a`): the LÖVE port, touch controls and Android tooling, the v0.1.1-v0.1.3 softlock/sprite/scenery fixes, path-recovery pieces 1-5, registry and room-159 evidence, the v0.1.4-v0.1.7 publications, PR #11's Ruins spike-bridge softlock, X-skip text-overlap and touch COLLISION-toggle fixes, and PR #13's monster body-part ID recovery that fixed the reported "cannot battle in Snowdin — instance_create Missing object ID 255" crash. PRs #14-#17 shipped v0.1.8-v0.1.10 (part-ID recovery, one-shot alarms, Glyde 20x + 709 EXP). PRs #18-#22 landed the Undertale Yellow merge pieces 1-5 through the partial piece-5 world. PR #23 finishes piece 5 and publishes the fusion |
| Published release | `love-v1.2.3-fusion-experimental` (prerelease, 4 assets incl. both conversion reports, checksum in notes), source `6d59f5d`, published 2026-09-19 by the pinned workflow after **421 tests** and the fused native gate. Carries PR #30's four phone fixes (dialogue-box depth −400, GMS2 touch built-ins, pager label layout, cached drawing) that post-date the v1.2.2 archive. Prior releases stay available; v1.2.2 (`love-v1.2.2-fusion-experimental`, source `1538133`, **413 tests**) is renamed with a "Superseded —" prefix. Published release assets are immutable: do not re-publish over them |
| Open PR | **#24** (owner rounds 1-2): `port/frisk.lua` now asserts every one of the 24 run poses stays Clover's and none enters the walk remap (the startup report counts them instead of `#remap`, which was always 0), and PAUSE gains **AUTO RUN: ON/OFF** beside COLLISION - Yellow's own `option_autorun`, persisted in `touch-settings-v1.txt`, mirrored to the `Controls.sav` key Yellow's `scr_savecontrols` writes, and re-applied on boot and after every crossing. Round 2 makes both travel services available from the first frame: `Travel:openRiverService()` lifts `obj_dogboat_thing`'s own `global.plot < 122` guard for that one Create event (restored after, warn `travel-river-service`), `Travel:openWhaleService()` sets Yellow's `global.player_can_travel` and seeds ten stops through Yellow's own `scr_fasttravel_add` (warn `travel-ugps`), Yellow stops resolve through the merged ID band (`56` -> `1000056`, not Undertale's 56), `Travel:landWhales()` reads the whale's unreachable `fly_speed == 0` landing as the landing it was written to be (warn `travel-ugps-landing`), and `port/runtime.lua` gives every viewport a `view_camera` so a mail-station bell no longer stops the frame on "Camera 0 does not exist". Tests: boat at all three docks at plot 10, the whole bell -> Mail/Travel -> menu -> Yellow-stop flight, and every offered stop pinned against the pinned Yellow source (294 pass). Documented in `docs/YELLOW.md` and the release notes. Known gap reported, not hidden: the "Snowdin - Forest" stop needs the particle system the runtime lacks, so `rm_snowdin_11_yellow` stays a named stop. Still open from round 1: "it bugs a lot" (no reproducible symptom yet) |
| Yellow merge | **Complete.** `tools/fetch_yellow.py` pins commit `4ec23bd9` of `lordmannu993/UnderTale-Yellow`; `tools/yellow_convert.py --stage rooms` converts 3 796 sprites / 673 sounds / 11 fonts / 1 155 script resources / 3 224 objects with 8 494 events / **287 rooms, 68 paths, 199 454 drawables, 3 006 layers** into `generated/yellow/`, with 1 178 named function exports, 1 explicit GMLive stop (the shipped build's GMLive is inert, so the other 21 convert literally) and 0 compile errors. `tools/merge.py` + `port/merge.lua` build one manifest from both games, `port/travel.lua` connects the River Person boat (hold X during the ride; open below its plot gate) and Yellow's UGPS whale (every stop offered from Yellow's world init), `port/frisk.lua` draws Yellow's player as Frisk (28 walk poses remapped; the 24 run poses, the gun poses, goggles, dance and lying stay Clover - listed and asserted, so a run pose entering the remap stops the build), Yellow's own pause menu equips Clover's ammo/accessories beside Frisk's own gear, and the port's pause menu carries the merged AUTO RUN toggle, and `merge.sav` versions the merged layer including the loadout. The native LÖVE/xvfb gate crosses between worlds and back. Still unclaimed: Yellow's battle/story systems, shaders (reported, skipped), 25 rooms with named stops, and any Android-device certification |
| Part-ID recovery | `tools/recover_parts.py` fetches nothing by default: the checked-in `port/recovered_parts.json` is imported by `convert.py`. Regenerate with `GITHUB_TOKEN="$(gh auth token)" python3 tools/recover_parts.py` (pinned to the same `249ffa27` ref as the registry/path recoveries), re-verify offline with `--check`. IDs come from this checkout's own `partN=` literals; only names are paired from upstream; 38 annotated sites are re-validated as anchors. `tests/test_monster_parts.py` guards all of it plus every Snowdin battlegroup end-to-end |
| Asset-array ID recovery | The decompiler also leaves bare original IDs *inside instance arrays* read back through a computed index — `facespr[1]= 881; draw_sprite(facespr[global.faceemotion],…)` (Snowdin shopkeeper emotion faces, the owner-reported §7 "four eyes, floating mouth"), `obj_shop1`'s own `facespr`, Asgore's eight `part` sprites, and three `background_index` slots. No annotation covers array literals, so they hit `Unresolved sprite ID`. `tools/recover_asset_arrays.py` pairs each literal with the asset name the pinned upstream decompilation (same `249ffa27` ref) uses for the same statement; 18 IDs / 32 sites land in `port/recovered_asset_arrays.json`, imported by `convert.py`, re-verifiable offline with `--check`. `tests/test_asset_arrays.py` pins it: the shopkeeper's `faceemotion` 1-6 draw in room 311, which fails (and logs `Unresolved sprite ID 881`…`877`) without the converter import. The scalar form (`obj_torielbody` `facespr= 2285`, nine Toriel faces) is a separate, still-open finding |
| Unified fusion (binding spec) | The owner's 16-requirement [`UNIFIED_FUSION_SPEC.md`](docs/UNIFIED_FUSION_SPEC.md) is being worked as a **living queue** in [`docs/FUSION_STATUS.md`](docs/FUSION_STATUS.md) — that file is the single GitHub-readable source of truth for what is done, what is pending (in order), the current fusion head, the non-negotiable rules, and the "definition of a finished piece." **The user trigger "Proceed ❤️" continues it** (see the standing instruction at the top of this file). Current head: [PR #36](https://github.com/lordmannu993/undertale/pull/36) (`852ab34`, CI green, open — piece 1 done; next ⬜ is piece 2, Depth/Y-sort §4 §5). Merge the whole fusion **only** once piece 8 (the §15/§16 acceptance matrix) is green |
| Source newer than the archive | none — v1.2.3 (source `6d59f5d`) is the newest published build and carries [PR #30](https://github.com/lordmannu993/undertale/pull/30)'s four fixes; this branch's second commit is metadata only (README source-commit claim, AGENTS.md record), so once it merges, `master` and the newest archive agree in content |
| Download links | README's download section is guarded by `tests/test_release_docs.py` and `tools/check_download_links.py` (CI, token-authenticated). Publishing a version means the README, the workflow pins, `port/version.lua` and `docs/RELEASE_NOTES.md` all move together, and no superseded `releases/download/<tag>` link may survive in any document |
| Old releases | `love-v0.1.0`…`love-v1.2.1-fusion-experimental` are **kept on purpose** (owner declined deletion) and renamed with a "Superseded (…)" prefix as each is replaced. Version branches `v0.1.0`..`v0.1.3` point at each tagged build |
| Release plumbing | `.github/workflows/love-prerelease.yml` publishes on push to one pinned branch (`arena/01a0b9dd-undertale` for the v1.2.3 fusion; `arena/01a0b92c-undertale` for the v1.2.2 fusion, now deleted) and **refuses unless a draft release with that tag already exists**; `workflow_dispatch` re-runs it. The publish job fetches Yellow, converts, runs the suite with `PORT_REQUIRE_YELLOW=1`, packages `--merged`, runs the fused native gate, uploads four assets and flips `--draft=false` |

### To publish a version (only when a piece list says a release is due)

1. Bump `port/version.lua`, rewrite `docs/RELEASE_NOTES.md`.
2. Edit `love-prerelease.yml`: `RELEASE_TAG`, `ASSET_BASE`, `concurrency.group`, the title,
   the `on.push.branches` ref and the job's `if:` guard — all five, they are duplicated on purpose.
3. Create the **draft** prerelease first: `gh release create "$TAG" --draft --prerelease --title ... --target "$SHA"`.
4. Push the branch that triggers it; the job runs the tests, the packaging check and the native
   LÖVE gate, then verifies asset sizes/digests and flips `--draft=false`. It cannot overwrite a
   published build, which is intended.
5. Update the README download links (the repo page shows `master`'s README; a stale link there is
   what makes people download the old build). `python3 tools/check_download_links.py` must pass once
   the release is published, the "Merged after this archive was built" note must be deleted (the new
   build contains those fixes), and `tests/test_release_docs.py` fails if the README, the workflow
   pins, `port/version.lua` and the release notes disagree or a superseded download link survives
   anywhere in the repository's documents.

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
python3 tools/recover_asset_arrays.py --check                   # instance-array asset IDs still match the local tree (offline)
python3 tools/package.py --output artifacts/check.love          # reproducible archive + report gates
bash tools/native_smoke.sh artifacts/check.love                 # needs LOVE+xvfb: CI only
python3 tools/build_android.py --allow-experimental             # APK, needs JDK17 + SDK 34 + NDK 25.2.9519653
```

The native gate (`port/smoke.lua`) drives the real touch callbacks through the whole scripted
opening and asserts pixel/backdrop/draw-call facts; `tools/native_smoke.sh` fails the build unless
every named screenshot exists and `NATIVE SMOKE PASS` is in the log. Its tick budget and wall
timeout were both raised when the corridor walk was added — keep them raised, or the gate flakes.
