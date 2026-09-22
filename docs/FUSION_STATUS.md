# Unified fusion — living work queue (the "Proceed ❤️" source of truth)

This file is the **single, authoritative, GitHub-readable record** of the
Undertale + Undertale Yellow unified-fusion work. It exists so that a brand-new
session — with no memory of any chat — can say *what is done, what is pending, in
what order, and exactly how to continue* just by reading `AGENTS.md` → here.

**Binding requirement set:** [`UNIFIED_FUSION_SPEC.md`](UNIFIED_FUSION_SPEC.md)
(16 numbered requirements, owner-issued, verbatim). Where this file and the spec
disagree on a requirement, the spec wins. Limitations and deviations live in
[`PORTING.md`](PORTING.md).

> **If the user says "Proceed ❤️", do exactly this** (the full protocol is in
> `AGENTS.md` → "Standing instruction: 'Proceed ❤️'"): bring the current fusion
> head onto your branch, set up the pipeline, run the suite green, then do the
> **single highest-numbered ⬜ piece** below, in order. One piece per session is
> fine. Do **not** merge the final fusion until the §15/§16 acceptance piece is
> itself green.

---

## 1. Where completed work lives (read this first)

Completed fusion pieces are **merged to `master`** as they go green. A fresh
session is branched from `master`, so it **already has every merged piece** — no
extra step for completed work. Do the next ⬜ piece from §3.

Only if the *next* piece's PR is still **open** (work in flight, not yet merged)
do you bring it in first:

```bash
cd /home/user/undertale
git fetch origin
git merge --no-edit origin/<that-open-PR-branch>   # clean fast-forward from master
```

**Progress:**

| field | value |
| --- | --- |
| most recent merged piece | **#2** Depth / Y-sort (§4 §5) — [PR #37](https://github.com/lordmannu993/undertale/pull/37), merged to `master` |
| in-flight piece | **#3 River Person boat/water (§6)** — 🚧 local suite green (474 passed, 1 skipped); push/PR blocked on GitHub reconnection (401), then merge once CI is green |
| next ⬜ piece | **#4 No duplicated characters/sprite layers (§8)** — starts after #3 lands |
| in-flight open PR | *(none yet — #3 awaits GitHub reconnection)* |

---

## 2. Non-negotiable rules (do not re-litigate, do not weaken)

1. **One player state / inventory / equipment / progression / save.** No launcher,
   mode switch, or parallel `undertaleLV`/`yellowLV`/`*EXP`/`*Inventory`/
   `cloverInventory`/`friskInventory`. One Player record projected at world
   boundaries; serialised as `Player` + `World` blocks.
2. **No per-room or per-character hacks, no hiding duplicates.** Fix the shared
   system (depth-sort, inventory, entity/animation rendering). Room-specific
   overrides only where the original scene genuinely requires them.
3. **Depth = logical Y + the sprite's visual bottom point** — the canvas height,
   not the cropped-PNG top-left. Per-world `scr_depth` routing is kept
   (UT `50000 - 10y + 10h`; Yellow `-y`).
4. **Missing resources stop by name** via `Runtime:unsupported` — a visible stop,
   never a silent substitution.
5. **Recovered data is fetched by a script, pinned to one immutable ref
   (`kittibyte/UndertaleDecomp @ 249ffa27`), re-checkable offline (`--check`),
   never hand-typed.** IDs come only from this checkout's own literals; upstream
   contributes names, never numbers.
6. **Every behaviour change needs** a test that **fails without it**, a line in
   `docs/`, and a **scoped claim** about what it does *not* prove. Never leave a
   red test; never delete one.
7. **Yellow assets are never committed (~580 MB).** Fetch with
   `python3 tools/fetch_yellow.py --tarball-cache .yellow-cache`. Yellow IDs =
   `1000000 + the pinned Asset_Order ID`.
8. **Small pieces, each pushed with its evidence.** Land by PR; this repo's
   history is merge commits. Never force-push `master`; never delete a release.
9. **Issues are disabled** on this repo. Evidence goes in PR bodies and `docs/`.

---

## 3. Ordered piece list

Status: ✅ done & evidenced · ⬜ pending · 🚧 in progress. Work top-to-bottom; a
piece may be split into sub-pieces if it is too large for one green increment.

| # | spec § | Piece | Status | Files | Evidence (PR / test) |
| --- | --- | --- | --- | --- | --- |
| 1 | §7, §12 (2nd) | Recover asset IDs kept inside instance arrays (Snowdin shopkeeper emotion faces + 5 siblings) | ✅ | `tools/recover_asset_arrays.py`, `port/recovered_asset_arrays.json`, `tools/convert.py`, `tests/test_asset_arrays.py`, `docs/PORTING.md`, `AGENTS.md` | [PR #36](https://github.com/lordmannu993/undertale/pull/36) / `tests/test_asset_arrays.py` (10 tests; 3 proven to fail without the fix, logging `Unresolved sprite ID 881…877`) |
| 2 | §4, §5 | **Depth / Y-sort** — order the draw list by the sprite's visual bottom point, stable tie-break, keep per-world `scr_depth` routing | ✅ | `tools/convert.py` (canvas carriage), `port/runtime.lua` (canvas reads, depth hook), `port/yellow_layers.lua` (managed layers), `port/graphics.lua` (slot tie-break), `tests/test_depth_sort.py`, `docs/PORTING.md`, `AGENTS.md` | [PR #37](https://github.com/lordmannu993/undertale/pull/37) / `tests/test_depth_sort.py` (11 tests; 10 proven to fail without the fix) |
| 3 | §6 | River Person boat/water rendering — split into components, not a blanket global layer | 🚧 local green, push/PR awaiting GitHub reconnection | `tools/recover_sprite_offsets.py` (anchored path), `port/sprite_offsets.json` (448/980), `port/graphics.lua` (fractional sub-index crossfade), `tests/test_boat_water.py`, `tests/test_sprite_offsets.py`, `docs/PORTING.md` (rooms 125/70/140/316 pinned: depths 49330/49320/49300, ride 340→118, pillar −1 in front) | `tests/test_boat_water.py` (10 tests; the offset test and the ripple test proven to fail without the change) + the anchored provenance test in `tests/test_sprite_offsets.py` |
| 4 | §8 | No duplicated characters/sprite layers — system test for a character drawn twice (incl. a UT + Yellow twin in one scene); audit `port/merge.lua` and its 42 name collisions | ⬜ | `port/merge.lua`, `tests/`, `docs/PORTING.md` | — |
| 5 | §1 §3 §9–§11 §13 §14 | **Unified Player state** (the biggest): one Player record + shared item table, projected at world boundaries, serialised as `Player` + `World` blocks; crossing zeroes `flag[0..29]` (do not park state there). Grow `tests/test_yellow_merge.py` (`playerOf`, `crossTo`) into `tests/test_unified_player_state.py` | ⬜ | `port/travel.lua`, `port/storage.lua`, `port/merge.lua`, `port/frisk.lua`, `tests/test_unified_player_state.py`, `docs/` | — |
| 6 | §12 | Asset compatibility layer — `sprite_get_width/height` return cropped size at ~95 sites; per-frame origins; movement speed (UT 3 px/frame, Yellow +2 autorun); hitboxes/collision; the 980 `unresolved[]` crop offsets (never guess) | ⬜ | `port/graphics.lua`, `port/collision.lua`, `tools/yellow/assets.py`, `tests/`, `docs/PORTING.md` | — |
| 7 | §7 (visual) | Shopkeeper §7 visual sweep — confirm, via the draw log, exactly one pair of eyes + a correctly-seated mouth for `faceemotion` 0–6 in room 311 (the ID half is piece 1) | ⬜ | `tests/test_asset_arrays.py` (extend), draw-log evidence in PR | — |
| 8 | §15, §16 | Acceptance matrix + final merge — this file maps every requirement → code path / test / evidence; keep `AGENTS.md` current; then the single final merge | ⬜ | this file, `AGENTS.md`, PR body | — |

---

## 4. Setup (run this in every new session before coding)

```bash
cd /home/user/undertale
git fetch origin
git merge --no-edit origin/arena/01a0be2f-undertale   # bring in completed pieces (§1)

python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt       # never system pip (PEP 668)

python3 tools/fetch_yellow.py --tarball-cache .yellow-cache
python3 tools/yellow_convert.py --stage rooms \
  && python3 tools/merge.py \
  && python3 tools/convert.py

.venv/bin/python -m pytest -q                          # must be green before you change anything
```

Notes:
- **Native LÖVE runs only in CI** (`tools/native_smoke.sh`); there is no LOVE in
  the sandbox. Authoritative rendering evidence = the CI native gate + the headless
  draw log. Layering *parity with the original game* is a CI-only visual claim and
  must be stated as scoped.
- **Offline visual probes** (used to inspect `R.drawLog` without LOVE) live in
  `/home/user/scratch` (sandbox-local, **not persisted** — rebuild on demand).
  They drive `R:step(); R:renderFrame()` through `lupa.luajit21` (plain `lupa` is
  Lua 5.5 and has no `bit`) and print `R.drawLog` entries such as
  `{"sprite", name, subframe, x, y, sx, sy, angle, tint, alpha, ox, oy[,
  blendFrame, blendT]}` — the last two fields are present only when the
  sub-index is fractional (piece 3's crossfade).
  Keep any screenshots/evidence in `/home/user/scratch/evidence/`. The committed
  pytest suite is the source of truth; the probes are for investigation only.

---

## 5. Definition of a finished piece (gate before you push)

A piece is not done until **all** of these hold:

1. A **test that fails without the change** is added (and passes with it).
2. A **line in `docs/PORTING.md`** (or the relevant doc) records what changed, the
   evidence, and its scope.
3. The claim is **scoped** to what was actually run (headless converted flow +
   draw log + CI native smoke). It does *not* claim Android GPU behaviour, audio
   fidelity, or pixel-perfect original parity unless that was actually verified.
4. `.venv/bin/python -m pytest -q` is **green** locally **and** CI is green
   (`PORT_REQUIRE_YELLOW=1` + native LÖVE gate).
5. `docs/FUSION_STATUS.md` and `AGENTS.md` are **updated in the same commit**
   (status flipped to ✅, evidence row filled, §1 "most recent merged piece" advanced).
6. Committed + pushed on the session branch; **the piece's PR is merged once green**
   (this repo's history is merge commits). The *final fusion* — all 16 requirements
   plus the §15/§16 acceptance matrix (piece #8) — is the last step.

## 6. How a session records its progress

After a green piece:
1. Mark its row ✅ in §3 and fill the evidence column (PR + test names).
2. Set it as the **most recent merged piece** in §1 once its PR is merged.
3. Add a row to `AGENTS.md` "Current state" if warranted, and keep the
   verification-commands section accurate.
4. One commit: `git add -A docs AGENTS.md <piece files> && git commit`. Push on the
   session branch.
5. Add a short "piece N done, here is the evidence, here is piece N+1" note to the
   PR body (the owner prefers that over option menus), then **merge the PR once CI
   is green** so the piece lands on `master` for the next session.
