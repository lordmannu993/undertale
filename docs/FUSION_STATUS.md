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
> **next pending piece, top-to-bottom**. If a piece is split, finish its next
> pending sub-piece before advancing to the next numbered piece. One green
> sub-piece per session is fine. Do **not** merge the final fusion until the §15/§16 acceptance piece is
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
| most recent merged piece | **#8 the §15/§16 acceptance matrix — the last piece; the fusion is complete** — [PR #52](https://github.com/lordmannu993/undertale/pull/52), merged to `master` as `43aa57f` on 2026-09-24; [CI + native gate 35965721372](https://github.com/lordmannu993/undertale/actions/runs/35965721372) green (`NATIVE SMOKE PASS`, `CORE PLAYER PASS`, the new `ACCEPTANCE PASS`). Piece 7 before it: [PR #50](https://github.com/lordmannu993/undertale/pull/50) merge `8bc1f89`; piece 8 is also recorded by [PR #53](https://github.com/lordmannu993/undertale/pull/53) |
| in-flight piece | **none** — piece 8 merged as `43aa57f`; nothing is pending |
| next ⬜ piece | **none** — with piece 8 green and merged, all 16 requirements and the §15/§16 acceptance matrix are done and the fusion is certified |
| download boot | **not a fusion piece.** v1.2.4's archive omitted `generated/merged/items.lua` and stopped on launch (`module 'generated.merged.items' not found`). `tools/package.py` now ships that catalog, and the native gate rejects a merged archive that lacks it. The corrected download is v1.2.5 |
| in-flight open PR | **none** — [#52](https://github.com/lordmannu993/undertale/pull/52) merged; [#53](https://github.com/lordmannu993/undertale/pull/53) only records that landing |

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
| 3 | §6 | River Person boat/water rendering — split into components, not a blanket global layer | ✅ | `tools/recover_sprite_offsets.py` (anchored path), `port/sprite_offsets.json` (448/980), `port/graphics.lua` (fractional sub-index crossfade), `tests/test_boat_water.py`, `tests/test_sprite_offsets.py`, `docs/PORTING.md` (rooms 125/70/140/316 pinned: depths 49330/49320/49300, ride 340→118, pillar −1 in front) | [PR #38](https://github.com/lordmannu993/undertale/pull/38) / `tests/test_boat_water.py` (10 tests; the offset test and the ripple test proven to fail without the change) + the anchored-provenance test in `tests/test_sprite_offsets.py` |
| 4 | §8 | No duplicated characters/sprite layers — a character is drawn once; the 42 shared asset names resolve per world | ✅ | `port/graphics.lua` (draw provenance + unconverted-shader duplicate drop), `port/merge.lua` (`double_named`), `port/runtime.lua` (`assetName`/`assetOwnerIsYellow`/`reportNameSplit`), `port/yellow_builtins.lua` (world-aware `asset_get_index`), `tools/merge.py` (honest 42), `tests/test_duplicate_draws.py`, `docs/PORTING.md` | `tests/test_duplicate_draws.py` (11 tests; all five changes proven load-bearing by reverting each file: `sprite draw without provenance: spr_regboat`, `the flat collision list disagrees with the audit: 0 vs 32`, `spr_flowey gave 1095, not Yellow's 1000243`, `name collisions with Undertale: 4`) — [PR #39](https://github.com/lordmannu993/undertale/pull/39) |
| 5 | §1 §3 §9–§11 §13 §14 | **Unified Player state** (split into 5a–5d below): one Player record + shared item table, projected at world boundaries, serialised as `Player` + `World` blocks; crossing zeroes `flag[0..29]` (do not park state there) | ✅ **5a–5d merged** | `port/player.lua`, `port/inventory.lua`, `port/controller.lua`, `port/save.lua`, `port/runtime.lua`, `port/travel.lua`, `port/storage.lua`, `port/merge.lua`, `port/frisk.lua`, `tools/item_catalog.py`, `tests/test_unified_player_state.py`, `tests/test_unified_inventory.py`, `tests/test_unified_controller.py`, `tests/test_unified_save.py`, `docs/` | 5a: [PR #41](https://github.com/lordmannu993/undertale/pull/41). 5b: [PR #43](https://github.com/lordmannu993/undertale/pull/43). 5c: [PR #44](https://github.com/lordmannu993/undertale/pull/44). 5d: [PR #46](https://github.com/lordmannu993/undertale/pull/46), 8 tests. Piece 8 still certifies the final fusion |
| 6 | §12 | Asset compatibility layer — `sprite_get_width/height` return cropped size at ~95 sites; per-frame origins; movement speed (UT 3 px/frame, Yellow +2 autorun); hitboxes/collision; the 980 `unresolved[]` crop offsets (never guess) | ✅ **6a–6d done** | `port/assetcompat.lua`, `port/graphics.lua`, `port/runtime.lua`, `port/controller.lua`, `port/frisk.lua`, `port/collision.lua`, `port/yellow_studio.lua`, `port/yellow_builtins.lua`, `tools/recover_sprite_offsets.py`, `tools/yellow/assets.py`, `port/recovered_sprite_metadata.json`, `port/sprite_offsets.json`, `tools/convert.py`, `tests/test_asset_sizes.py`, `tests/test_asset_frames.py`, `tests/test_movement_speed.py`, `tests/test_asset_collision.py`, `docs/PORTING.md` | 6a: `tests/test_asset_sizes.py` (13 tests). 6b: `tests/test_asset_frames.py` (6 tests). 6c: `tests/test_movement_speed.py` (3 tests). 6d: `tests/test_asset_collision.py` (6 tests) — see the sub-piece table below |
| 7 | §7 (visual) | Shopkeeper §7 visual sweep — confirm, via the draw log, exactly one pair of eyes + a correctly-seated mouth for `faceemotion` 0–6 in room 311 (the ID half is piece 1) | ✅ | `tests/test_asset_arrays.py` (extended), `docs/PORTING.md`, draw-log evidence in PR | [PR #50](https://github.com/lordmannu993/undertale/pull/50), merge `8bc1f89`, [CI + native gate 35893553410](https://github.com/lordmannu993/undertale/actions/runs/35893553410). `test_shopkeeper_default_face_layers_seat_exactly` (fails without the crop carriage: the offset pin reads `(0, 0)` instead of `(1, 9)`) + `test_shopkeeper_emotion_faces_cover_the_default_face_and_swap_out_the_mouth` (fails without piece 1's recovered array IDs; each emotion 1–6 draws exactly one face at `(150, 36)` with origin `(1, 4)`, the mouth layer swapped out, the strip's eye band covered); draw-log rows quoted in the PR. Full local suite **564 passed, 1 skipped** |
| 8 | §15, §16 | Acceptance matrix + final merge — every requirement mapped → code path / test / evidence (§7 below); keep `AGENTS.md` current; then the single final merge | ✅ | `tests/test_acceptance_matrix.py`, `port/smoke.lua`, `tools/native_smoke.sh`, `docs/PORTING.md`, `docs/UNIFIED_FUSION_SPEC.md` (§15/§16 claims), this file, `AGENTS.md` | [PR #52](https://github.com/lordmannu993/undertale/pull/52), **merged as `43aa57f`** (2026-09-24) — [CI + native gate 35965721372](https://github.com/lordmannu993/undertale/actions/runs/35965721372) green. `tests/test_acceptance_matrix.py` (7 tests): the §15 checklists as one continuous session — Undertale items/EXP → Yellow → home, the same walk/run rule with the pose each state draws, a ten-room render sweep plus the dock/shop/forest scenes, and save/load through both worlds' save points; §16 audits by identity (one `R.player`, one inventory/equipment table, one controller, one `merge.sav`) and by scan (no `cloverInventory`-style spelling, one installer per shared system). Five reverts tabulated in `docs/PORTING.md` fail it by name (`inventory after crossing: Missing Poster,0`; `LV/EXP lost`; `Undertale run distance: 3,3,3,3`; `Undertale run drew spr_maincharar`; the reversed depth comparison puts the dock's water in front of the hull). Native gate now requires `ACCEPTANCE PASS` (a Yellow item and equipped ammo through both packaged crossings). Full local suite **571 passed, 1 skipped** |

### Piece 6 sub-pieces (finish these before #7)

Piece 6 is the asset-compatibility layer of spec §12, and it is larger than one
green increment: it covers sprite size reporting, per-frame origins, movement
speed, hitboxes/collision boxes, scaling and sheet coordinates. The split below is
the order, and all four are done and merged (6a in PR #48; 6b–6d in PR #49):
6a (size), 6b (frames, rate, anchors), 6c (movement speed) and 6d (collision
boxes/hitboxes, scaling, sheet coordinates). Piece 7 (the shopkeeper §7 sweep)
is done; piece 8 is next.

| sub-piece | deliverable | state / evidence |
| --- | --- | --- |
| **6a** | One asset-size compatibility layer. `sprite_get_width/height` (Undertale's and Yellow's builtins), the `sprite_width`/`sprite_height`/origin instance reads, and the origin builtins answer in original-canvas pixels for both worlds through `port/assetcompat.lua`. The recovery tool reads the pinned upstream's real format (GMS2 `.yy`) again and re-derives the whole offsets file offline from `port/recovered_sprite_metadata.json`; 366 more offsets are proven (`canvas-span`), 553 candidates get a pinned canvas with no provable offset (never shifted), 61 stay unresolved with reasons. | ✅ [PR #48](https://github.com/lordmannu993/undertale/pull/48), merge `fedae36`, [CI 35831922600](https://github.com/lordmannu993/undertale/actions/runs/35831922600). `tests/test_asset_sizes.py` (13 tests; `sprite_get_width` 13→14 for `spr_5_mouth2`, canvas-only 8×7→13×10, Frisk's `scr_depth` key 29→30 and the no-guess cases all fail without their part of the change), `tests/test_depth_sort.py` and `tests/test_sprite_offsets.py` updated for the stronger evidence, `--check` re-derives offline. Scoped: 553 sprites are still drawn at the exported position; per-frame origins, speeds, hitboxes and scaling stay open. |
| **6b — done** | Frame selection, animation rate and render anchors (spec §12 "sprite origins", "animation frame handling", "render anchors"). One sub-image per draw (GameMaker's rounded-down `image_index`, not piece 3's crossfade); Studio 2's `image_speed` multiplies the sprite's own playback speed (`AssetCompat.playbackRate`, 1 for every Undertale record); a pixels-only remap stands on the requested sprite's feet (`AssetCompat.anchor`, canvas bottom centres) at the same phase of its own cycle (`AssetCompat.remapFrame`). | ✅ this branch (`arena/01a0cd44-undertale`). `tests/test_asset_frames.py` (6 tests): reverting the renderer fails 4 (fractional draw logs `0/1/0.5 1/2/0.7 0/1/4.1`; Frisk's canvas 9px right and 15px down of Clover's body; the run pose 10px left and 15px up; identity), reverting the rate fails 1 (10 fps sprite moves 3 frames in 3 steps, not 1), reverting the controller's run rate fails 1 (each run frame shows 1 step, not 3). Piece 3's ripple pin and piece 5c's sprint-rate pin updated with rationale. Full local suite **553 passed, 1 skipped** (`PORT_REQUIRE_YELLOW=1`). Scoped: headless + draw log; no pixel-perfect, Android or played-through claim. |
| **6c — done** | Movement speed as one shared layer (spec §12 "movement speed"): both worlds walk 3px and run Yellow's `plspd + 2` (5px a step). The controller owns `WALK_STEP` 3 and `RUN_BONUS` 2; Undertale's +2 bonus follows its walk step and collides through Undertale's own collision events, replacing piece 5c's extra 3px lattice step. | ✅ this branch. `tests/test_movement_speed.py` (3 tests): the constants are re-read from `obj_mainchara`'s Step, `obj_pl`'s Create and `scr_normal_state`; Undertale runs `5:0` per step in every direction (`6:0` without the change) with the walk at 3 and Yellow's own run at 3+2; running into room_area1's east wall from every 5px phase never enters it (without the bonus collision, x=231 ends at x=261 inside the wall). Piece 5c's pins updated with rationale (two run steps 12 → 10). Full local suite **556 passed, 1 skipped**. Scoped: headless distances; no played-through route, latency or Android claim. |
| **6d — done** | Collision boxes and hitboxes, scaling and GMS2 sheet coordinates (spec §12): precise masks read in canvas pixels (a cropped export's pixels start at its recovered offset) and composite every frame unless masks are separate; Studio 2's `collisionKind` 4 is *Precise (per frame)* in the GMS2 sprite schema (not a rotated rectangle) and converts to `colkind` 0 + `sepmasks` 1; `place_meeting`/`instance_place`/`instance_place_list` test the caller's collision box, not a point; stretched and tiled draws scale from the canvas; `sprite_get_uvs` answers from the frame instead of stopping. | ✅ this branch. `tests/test_asset_collision.py` (6 tests): reverting `port/collision.lua` fails 3 (cropped mask `00000` vs `11000`; composite `1000` vs `1001`; `place_meeting` 0 for a box crossing the target), reverting `port/graphics.lua` fails the stretch (`2.2985, 2.6296` vs `2, 2`), reverting `port/yellow_studio.lua` fails `sprite_get_uvs` (nil call; 6d also removed it from the stop list in `port/yellow_builtins.lua` — reverting both Yellow files together shows `Compatibility stop: sprite_get_uvs`), reverting the converter fails the kind-4 test (all 74 kinds convert wrongly, first `spr_battle_flowey_yarn_lhand_1`). Piece 1's rotated-rectangle pin replaced with the per-frame pin (schema cited). Full local suite **562 passed, 1 skipped**. Scoped: headless + draw log with a stand-in `love.image`; particle sprites keep their exported origin; no pixel-perfect, Android or played-through-battle claim. |

### Piece 5 sub-pieces (finish these before #6)

5a is intentionally a small, verifiable increment. Inventory (5b), the shared
controller (5c) and the Player+World save (5d) are merged. Piece 5's
implementation is done. Piece 8 is still the acceptance matrix; it is not done.

| sub-piece | deliverable | state / evidence |
| --- | --- | --- |
| **5a** | One live `R.player` owner of HP, max HP, LV, EXP, money, name and base AT/DF; both games' global spellings are views. Content initialization cannot reset those fields. Clear crossing scratch flags in both directions. | ✅ [PR #41](https://github.com/lordmannu993/undertale/pull/41), `tests/test_unified_player_state.py` (23 tests; full local suite 508 passed / 1 skipped), required `native-unified-player.txt` gate; [CI 35708911107](https://github.com/lordmannu993/undertale/actions/runs/35708911107) passed. |
| **5b — done** | Shared item catalog from source, one inventory (including boxes/key items), numeric/string item adapters, common item actions and four-slot equipment; items must be usable in either content set, not just carried in hidden snapshots. Replace legacy gear/name UI consumers. | ✅ `port/inventory.lua` + `tools/item_catalog.py` (writes `generated/merged/items.lua`, 64 UT / 78 Yellow rows / 5 name pairs, extracted from the repaired UT switches and Yellow's GMS2 sources — nothing hand-typed). Both spellings are live views of `R.player.inventory[1..8]` and `R.player.equipment{weapon,armor,ammo,accessory}`; gear-stat globals derive from the equipped tokens; foreign items use/equip/name/desc/value/stat through the catalog in either content set. 13 new tests in `tests/test_unified_inventory.py`; `Travel:applyEquipment` (the merge.sav snapshot) removed as a stale-clobber — live state replaces it. Full local suite 521 passed / 1 skipped (`PORT_REQUIRE_YELLOW=1`; native gate is CI-only). STAT panel's hard-coded labels stay unclaimed with 5c/5d's UI work. |
| **5c — done** | One `R.player.controller` over both adapters. Entities stay `obj_mainchara` / `obj_pl` (exactly one). Undertale runs on X/Shift: one extra 3px lattice step at the start of End Step, collided, then `xprevious` restored; the four base walk poses draw Clover's run cycle. Yellow's own 3+2 step is not rewritten. AUTO RUN stays Yellow-only. Menu and interact are shared abilities. Battle scripts temporarily compose ammo / armour-bonus / accessory defense; standing views do not. Level-up is `scr_levelup` (LV 20 is 99/99/99, EXP caps at 99999); current HP is not a level-up output. | ✅ [PR #44](https://github.com/lordmannu993/undertale/pull/44), merge `bdef72f`. `port/controller.lua`, draw remap in `port/frisk.lua`, temporary `battleCompose` in `port/inventory.lua`. `tests/test_unified_controller.py` (5 tests). Uninstalling the controller fails all five (`holding X did not sprint`, `the solid probe did not sprint`, `no shared controller`, `LV 2 max HP is 20, not scr_levelup's 24`, `Undertale fight pwr is 119`). Skipping the bonus `collisionEvents` fails the wall test a different way (`moved 6, not the walked 3`). Full local suite **526 passed, 1 skipped** (`PORT_REQUIRE_YELLOW=1`). [CI + native gate 35810358055](https://github.com/lordmannu993/undertale/actions/runs/35810358055) passed. Headless + draw log + that gate's existing `CORE PLAYER PASS` crossing probe: no Android, audio, pixel-perfect origins, piece 6 speeds, or a native X-run proof. |
| **5d — done** | One `Player` + `World` save/load, explicit legacy migration, save points/loading from either world, and content initialization that does not reset world progress on re-entry. | ✅ [PR #46](https://github.com/lordmannu993/undertale/pull/46), merge `9a3bbae`. `port/save.lua` writes `merge.sav` version 2 (`[Player]`, `[World]`, `[merge]`). `scr_save` and `scr_savegame` both write it; `scr_load` and `scr_loadgame` both read it and do not heal. Yellow's own `scr_savegame` is not the writer (`ds_grid_write` stays a named stop). Version 1 is copied to `merge.sav.v1` and migrated without inventing LV. Version 99 stops by name and is not rewritten. A foreign `Save.sav` ds blob stops by name and is not deleted. Re-entry skips `scr_initialize` and restores `saveroom`/`tinypuzzle` after the controller Create. A crossing writes before the destination Create, so `SCR_GAMESTART` on the return to Undertale is not the save. `tests/test_unified_save.py` (8 tests). Full local suite **534 passed, 1 skipped** (`PORT_REQUIRE_YELLOW=1`). [CI + native gate 35815755848](https://github.com/lordmannu993/undertale/actions/runs/35815755848) passed. Not claimed: Android, audio, a played save-point menu, pixel-perfect parity, or piece 8. |

---

## 4. Setup (run this in every new session before coding)

```bash
cd /home/user/undertale
git fetch origin
# Already-merged pieces are inherited from master. Only merge an open PR's
# branch when §1 records unfinished work there; do not merge an obsolete branch.

python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt       # never system pip (PEP 668)

python3 tools/fetch_yellow.py --tarball-cache .yellow-cache
python3 tools/convert.py \
  && python3 tools/yellow_convert.py --stage rooms \
  && python3 tools/merge.py

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
  `{"sprite", name, subframe, x, y, sx, sy, angle, tint, alpha, ox, oy,
  blendFrame, blendT, index, ownerId, originX, originY}` — `blendFrame`/`blendT`
  are always `nil` since piece 6b (one sub-image per draw), and
  `originX`/`originY` are the canvas point placed at (x, y), anchored for a
  remapped draw.
  Keep any screenshots/evidence in `/home/user/scratch/evidence/`. The committed
  pytest suite is the source of truth; the probes are for investigation only.

---

## 5. Definition of a finished piece (gate before you push)

A piece (or a scoped sub-piece) is not done until **all** of these hold.
A completed sub-piece does not turn its parent ✅ while sibling work remains:

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

---

## 7. Acceptance matrix (spec §15, §16 — piece 8)

Piece 8 certifies the fusion by mapping **every** requirement of
[`UNIFIED_FUSION_SPEC.md`](UNIFIED_FUSION_SPEC.md) to the code that implements
it, the tests that prove it, and the evidence that was actually run. The
acceptance suite is `tests/test_acceptance_matrix.py` (7 tests: §15's checklists
as one continuous session) plus §16's two audits; the packaged archive repeats
the inventory/equipment claim in the CI native gate (`ACCEPTANCE PASS`).

| spec § | requirement | code path | test / evidence |
| --- | --- | --- | --- |
| 1 | one shared inventory, equipment and progression; items usable in either content set; nothing resets on a crossing | `port/player.lua`, `port/inventory.lua`, `tools/item_catalog.py`, `generated/merged/items.lua` | `tests/test_unified_player_state.py`, `tests/test_unified_inventory.py`; acceptance `test_spec15_one_journey_keeps_inventory_equipment_and_progression`; native `CORE PLAYER PASS` + `ACCEPTANCE PASS` |
| 2 | one fused game, not two games in one executable | `port/merge.lua`, `port/travel.lua`, `port/runtime.lua` | `tests/test_yellow_merge.py` (ID bands, both travel hubs, one player per world); acceptance `test_spec16_one_player_one_inventory_one_controller_one_save` |
| 3 | Frisk's and Clover's abilities merged (Clover's run available in Undertale areas, Frisk's art in Yellow) | `port/controller.lua`, `port/frisk.lua` | `tests/test_unified_controller.py`, `tests/test_movement_speed.py`; acceptance `test_spec15_movement_and_its_animations_match_in_both_worlds` (the pose drawn per frame) |
| 4 | overworld rendering: depth/Y-sort, no manual per-sprite moves | `tools/convert.py` (canvas carriage), `port/graphics.lua`, `port/yellow_layers.lua` | `tests/test_depth_sort.py`; acceptance `test_spec15_rendering_sweep_keeps_every_scene_coherent` |
| 5 | overlap and feet-based depth for the player and NPCs, foreground split from background | `port/graphics.lua`, `port/yellow_layers.lua`, `scripts/scr_depth.gml` path through `port/assetcompat.lua` | `tests/test_depth_sort.py`, `tests/test_boat_water.py`; acceptance named scenes (dock layering) |
| 6 | River Person's boat and water | `port/graphics.lua`, `tools/recover_sprite_offsets.py`, `port/sprite_offsets.json` | `tests/test_boat_water.py`, `tests/test_sprite_offsets.py`; acceptance named scenes |
| 7 | Snowdin shopkeeper: two eyes, seated mouth, no duplicated facial features | `tools/recover_asset_arrays.py`, `port/recovered_asset_arrays.json`, `tools/convert.py` | `tests/test_asset_arrays.py`; acceptance named scenes |
| 8 | no duplicated characters or sprite layers | `port/graphics.lua` (draw provenance), `port/merge.lua` (`double_named`), `port/runtime.lua` | `tests/test_duplicate_draws.py`; acceptance sweep (no instance draws a sprite twice in a frame, in ten rooms) |
| 9 | one authoritative architecture; no `undertaleLV`/`yellowLV`/`cloverInventory`-style forks | `port/player.lua`, `port/inventory.lua`, `port/controller.lua`, `port/save.lua`, `port/graphics.lua` | acceptance `test_spec16_no_duplicated_player_state_exists_in_the_port` (scan of `port/` and both conversions, one installer per shared system) |
| 10 | room/area transitions preserve the player | `port/travel.lua`, `port/player.lua` | `tests/test_unified_player_state.py`, `tests/test_yellow_merge.py`; acceptance journey; native `CORE PLAYER PASS` |
| 11 | one save structure (Player + World) for both worlds | `port/save.lua`, `port/storage.lua` | `tests/test_unified_save.py`; acceptance `test_spec15_both_worlds_save_points_write_and_load_the_one_document` |
| 12 | asset compatibility layer (origins, frames, speed, collision, hitboxes, anchors, scaling, sheet coordinates) | `port/assetcompat.lua`, `port/collision.lua`, `port/yellow_studio.lua`, `tools/convert.py`, `tools/yellow/assets.py` | `tests/test_asset_sizes.py` (6a), `tests/test_asset_frames.py` (6b), `tests/test_movement_speed.py` (6c), `tests/test_asset_collision.py` (6d) |
| 13 | no temporary visual hacks; fix the shared system | `port/graphics.lua`, `port/runtime.lua`, `port/collision.lua`, `port/assetcompat.lua` | every piece's "reverting X fails test Y" evidence in `docs/PORTING.md`; the room-specific exemptions §13 permits are listed there, and piece 8 adds none |
| 14 | game-specific mechanics preserved without a second player state | Yellow ammunition/accessories and Undertale gear through `port/inventory.lua`; battle composition in `port/controller.lua` | `tests/test_unified_inventory.py`, `tests/test_unified_controller.py`, `tests/test_yellow_merge.py` (Yellow's pause menu equipping) |
| 15 | the §15 test list, run rather than claimed | `tests/test_acceptance_matrix.py` | the six §15 acceptance tests plus the native `ACCEPTANCE PASS` probe in `port/smoke.lua` / `tools/native_smoke.sh` |
| 16 | one continuous player, inventory, LV/EXP, save, overworld, movement, ability set and rendering system | the whole tree | all of the above, plus §16's two audits; certified only with this piece's PR green (CI tests + native LÖVE gate) |

**What this matrix does not claim** (also stated per piece in `docs/PORTING.md`):
Android GPU behaviour, audio fidelity, touch latency, a played-through route or
battle, pixel-perfect parity with either original engine, and the Yellow rooms
whose source data is absent (they still stop by name — see `manifest.missing_rooms`
and `port/runtime.lua`'s `room_goto` stop).
