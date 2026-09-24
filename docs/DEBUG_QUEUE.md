# Debug & repair — living work queue (the "Proceed ❤️" source of truth)

This file is the **single, authoritative, GitHub-readable record** of the
debug-and-repair work that the user trigger **"Proceed ❤️"** now continues. It
exists so that a brand-new session — with no memory of any chat — can read
`AGENTS.md` → here and know *what is done, what is pending, in what order and
exactly how to continue*.

**Binding requirement set:** [`DEBUG_SPEC.md`](DEBUG_SPEC.md) — the owner's
12-section debug & repair brief, verbatim. Where this file and the brief
disagree on a requirement, **the brief wins**.

**History (frozen):** [`FUSION_STATUS.md`](FUSION_STATUS.md) is the *finished*
unified-fusion queue (pieces 1–8, all merged; the fusion is certified). It is
kept as the historical record and its §7 acceptance matrix is still the map of
the 16 spec requirements → code → evidence. It is **not** the live queue any
more; this file is.

> **If the user says "Proceed ❤️", do exactly this** (the full protocol is in
> `AGENTS.md` → "Standing instruction: 'Proceed ❤️'"):
> bring the current head onto your branch, set up the pipeline, run the suite
> green, then do the **next pending piece, top-to-bottom** from §3. If a piece is
> split into sub-pieces, finish its next pending sub-piece before advancing.
> **A PR is opened and merged only after that one piece/section is complete**
> (§2 rule 8, §5, §6) — never a partial one. One piece per session is fine.

---

## 1. Where completed work lives (read this first)

Every completed piece is **merged to `master`** as it goes green. A fresh session
is branched from `master`, so it **already has every merged piece** — no extra
step. Do the next ⬜ piece from §3.

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
| most recent merged piece | **none yet** — this queue was installed 2026-09-24 replacing the finished fusion queue; the fusion itself is complete (`FUSION_STATUS.md`, merge `43aa57f`) |
| in-flight piece | **none** |
| next ⬜ piece | **D0** — architecture map + reproduction harness (brief §9) |
| in-flight open PR | **none** |
| published build | `love-v1.2.5-fusion-experimental` (source `c16fb9b`) is still the newest downloadable archive. This queue is **source-only** until the owner asks for a release build; do not publish a version unless a piece list says a release is due (`FUSION_STATUS.md` → "To publish a version") |

---

## 2. Non-negotiable rules (do not re-litigate, do not weaken)

1. **Fix the root cause, never the symptom.** No "fake" fixes (hiding, drawing
   over, clamping a symptom, rotating text back without knowing why it rotated).
   Every piece's PR states the root cause it proved and how it was proved.
2. **Smallest reasonable change; reuse existing systems.** Do **not** rebuild the
   game, do not replace working systems because they are unfamiliar, do not add
   a second manager for something that already has one (rooms, transitions,
   scenes, entities, assets, fonts, input, saves). No parallel transition or
   player system.
3. **Preserve the certified fusion invariants:** one `R.player` record, one
   inventory/equipment, one controller, one `merge.sav` Player+World document,
   one installer per shared system (`FUSION_STATUS.md` §2, §7). Pieces 1–8's
   guarantees must still hold after every change.
4. **The Undertale side must not regress** (brief §8): rooms, movement,
   collisions, dialogue, fonts, rendering, audio, transitions, and returning from
   Yellow all stay working. Never replace an Undertale system to make Yellow
   easier.
5. **Performance work is measured, not guessed.** Profile/inspect the actual
   update and draw paths, compare Undertale vs Yellow, then fix the runaway
   system. Forbidden as "fixes": lowering resolution, deleting effects, cutting
   game logic, disabling features, arbitrary frame-rate caps. Record before/after
   numbers (ticks, allocations, entity/draw counts) in the PR.
6. **Do not recreate per-frame work.** Fonts, images, sounds, music, shaders,
   maps and catalogs are loaded once and cached. No `newFont`/`newImage`/file
   reads/JSON parses/`require`s inside `update`/`draw`/event paths.
7. **Every behaviour change needs evidence in the repo:** a test that **fails
   without it**, a line in `docs/PORTING.md` (a new "Debug fixes" section) or the
   relevant doc, and a **scoped claim** about what was *not* verified. Never leave
   a red test; never delete one.
8. **One piece/section per PR, merged only when complete.** A piece may be split
   into declared sub-pieces (like the old queue's 5a–5d); each sub-piece is
   itself a piece. The PR is opened once that piece is done and **merged once it
   is green** (local suite + CI + native LÖVE gate). Never merge an unfinished
   piece "to keep moving", never force-push `master`, never delete a release.
9. **Missing resources stop by name** (`Runtime:unsupported`), recovered/pinned
   data stays script-derived (never hand-typed), Yellow assets are never
   committed (~580 MB — fetch with `tools/fetch_yellow.py`).
10. **Debug scaffolding is temporary.** Diagnostics added while investigating
    (prints, counters, overlays) are removed before the piece merges (brief §12)
    — except what a committed test legitimately needs.
11. **Issues are disabled** on this repo. Evidence goes into PR bodies and
    `docs/`.

---

## 3. Ordered piece list

Status: ✅ done & evidenced · ⬜ pending · 🚧 in progress. Work top-to-bottom.
Split a piece into sub-pieces (declared in this table, e.g. `D1a`/`D1b`) when one
green increment is too large.

| # | brief § | Piece | Status | Primary files (inspect → change) | Evidence (PR / test) |
| --- | --- | --- | --- | --- | --- |
| **D0** | §9 | **Architecture map + reproduction.** Trace GAME START → room init → player init → Undertale play → River Person → boat → transition → Yellow room → player update/draw → dialogue draw → return transition → Undertale room; write down where state changes, how the two worlds are separated, and which code owns fonts, text, rooms, entities and transitions. Stand up one repeatable headless reproduction harness that prints the four reported symptoms (Yellow font, vertical text, Yellow lag, duplicate player at the crossing, boat destination) so every later piece starts from evidence. No behaviour change. | ⬜ | new `docs/DEBUG_BASELINE.md`, new `tools/debug_probe.py`; read `main.lua`, `port/runtime.lua`, `port/graphics.lua`, `port/travel.lua`, `port/player.lua`, `port/merge.lua`, `port/yellow_*.lua`, `tools/convert.py`, `tools/yellow/*.py` | pending |
| **D1a** | §1 (font identity) | **Yellow uses its intended font.** Trace font loading → record → ID → `draw_set_font` → renderer for both worlds; find why a Yellow caller gets the wrong face. Fix the shared resolution (caller's world / band / name map — reuse `Runtime:assetName`, `manifest.double_named`, the merged `fonts` records); never substitute a downloaded or generic font. Undertale's fonts verified unchanged. | ⬜ | `port/graphics.lua`, `port/runtime.lua`, `port/merge.lua`, `port/yellow_builtins.lua`, `tools/convert.py`, `tools/yellow/assets.py`; new `tests/test_yellow_fonts.py` | pending |
| **D1b** | §1 (orientation), §6 | **Yellow text renders horizontally.** Prove *why* it is vertical (leaked transform? view/camera rotation? wrapping/measure bug? surface/canvas state? GUI pass?) before changing anything; then fix that root cause and make the graphics state safe (push/pop around every temporary transform). No per-call "rotate it back" patches. | ⬜ | `port/graphics.lua` (`text()`, `draw_text_ext`, view push, GUI pass), `port/yellow_studio.lua` (cameras/views), `port/yellow_graphics.lua`, `port/opening_backdrops.lua`; new `tests/test_text_orientation.py` | pending |
| **D2** | §2, §7 | **Yellow-side performance.** Profile and compare both sides on the same machine/CI; find the runaway system (duplicate updates/draws, duplicated entities/callbacks, per-frame allocations, repeated loads, unbounded particles, rebuilding static geometry) and fix it — caching where the project already caches, not a new asset manager. Record before/after numbers; keep all effects and logic. | ⬜ | `port/runtime.lua` (`step`, dispatch, room lifecycle), `port/graphics.lua` (draw list, per-frame allocation), `port/particles.lua`, `port/collision.lua`, `port/yellow_layers.lua`, `port/travel.lua`, `port/storage.lua`; new `tests/test_yellow_performance.py` | pending |
| **D3** | §3, §5 | **Exactly one Player, ever.** Enumerate every place a Player instance is created/kept/destroyed; decide the architecture (persistent player *or* recreated per room — follow the one the code already uses) and make it consistent. Old world stops updating/drawing after a crossing; the destination places the *existing* player. Include the repeated-transition test (UT → Yellow → UT → Yellow → …) asserting the count never grows. | ⬜ | `port/player.lua`, `port/controller.lua`, `port/travel.lua`, `port/save.lua`, `port/runtime.lua` (`room_goto`, instance create/destroy, persistent instances), `port/merge.lua`, `port/frisk.lua`; new `tests/test_player_identity.py` | pending |
| **D4** | §4, §5 | **River Person boat destination is right.** Trace interaction → board → ride → transition trigger → destination room → spawn point for both directions and make the destination explicit (no reliance on accidental current state / stale globals / "hold X" ambiguity that silently picks the other world). Keep the games' own destinations and landings; no invented coordinates. | ⬜ | `port/travel.lua`, `scripts/SCR_TEXT.gml` (cases 585–587 / repaired labels 770–773), `objects/obj_dogboat_thing.object.gmx`, rooms 70/125/140/316 (+ the dock room's own spawn data), Yellow `obj_fast_travel_menu`; new `tests/test_boat_destination.py` | pending |
| **D5** | §6, §7 | **Graphics-state and resource hygiene sweep.** Audit the whole port for leaked `translate/rotate/scale/origin/setFont/setColor/setShader/setCanvas/setScissor/setBlendMode` and for load-once violations, and fix what is actually wrong — no speculative rewrites. Add a guard test so a leak or a per-frame load cannot come back silently. | ⬜ | `port/graphics.lua`, `port/opening_backdrops.lua`, `port/touch.lua`, `port/audio.lua`, `port/storage.lua`, `port/yellow_studio.lua`, `port/yellow_graphics.lua`, `tools/convert.py`; new `tests/test_graphics_state.py` | pending |
| **D6** | §8, §11, §12 | **Both-side regression pass + cleanup + the final report.** Run TEST A–F (below) on the real build path, delete leftover debug scaffolding and dead code, re-run the full suite + native gate, write `docs/DEBUG_REPORT.md` with the owner's ten points, and update the queue (`AGENTS.md`, this file) to "complete" (or to the newly found scope). A release build only if the owner asks for one. | ⬜ | new `docs/DEBUG_REPORT.md`, `AGENTS.md`, this file, `docs/PORTING.md`, `docs/FUSION_STATUS.md`, `port/smoke.lua`, `tools/native_smoke.sh`, `tests/test_acceptance_matrix.py` | pending |

### Sub-pieces and shared root causes (read before starting a piece)

- **D1 may split into D1a/D1b.** They are listed separately because "wrong face"
  and "vertical text" are different symptoms that may have different causes. If
  they turn out to share one root cause, fix it **once** and record it in both
  rows — do not write two fixes for one cause.
- **D3/D4 and the D2 lag investigation overlap at the crossing.** The brief
  explicitly asks whether the River Person crossing creates duplicate entities or
  duplicated update loops (a lag cause *and* a duplicate-player cause). If one
  root cause explains both, fix it in the earlier piece, note it in the other
  row's evidence, and keep the other piece's tests as the guard.
- **D1b/D5 overlap on graphics state.** If the vertical text is a leaked
  transform in shared code, D1b carries that fix; D5 then owns the *general*
  audit and the guard test, and must not re-fix the same site.
- **D0 changes nothing.** Its deliverable is the map plus a working reproduction
  harness; its "test" is that the harness runs and its captured output is quoted
  in the doc/PR. Every later piece brings its own failing-without-the-fix test.

---

## 4. Setup (run this in every new session before coding)

```bash
cd /home/user/undertale
git fetch origin
# Already-merged pieces are inherited from master. Only merge an open PR's
# branch when §1 records unfinished work there.

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
  the sandbox. Authoritative rendering evidence is the CI native gate plus the
  headless draw log (`R.drawLog`; see `FUSION_STATUS.md` §4 for the offline probe
  recipe). Any FPS or GPU claim that cannot be measured in CI is **scoped out**
  until it is measured on the owner's device.
- `PORT_REQUIRE_YELLOW=1` makes the Yellow gates fail instead of skip; CI sets it
  and caches the tarball in `.yellow-cache/`.
- Visual/FPS numbers for D2 come from this harness (ticks per second of game
  time, `collectgarbage("count")`, instance and draw-call counts per tick), so
  the before/after claim is reproducible in CI, not "feels faster".

---

## 5. Definition of a finished piece (gate before you push)

A piece (or a declared sub-piece) is not done until **all** of these hold:

1. The **root cause is identified and written down** (what it was, how it was
   proved, what was rejected) — brief §9.
2. A **test that fails without the change** is added (and passes with it); for
   D0, a reproduction harness whose captured output is quoted.
3. A **line in `docs/PORTING.md`** (new "Debug fixes" section) or the relevant doc
   records what changed, the evidence, and its scope.
4. The claim is **scoped** to what was actually run (headless converted flow +
   draw log + CI native smoke). It does not claim Android GPU behaviour, audio
   fidelity, or pixel-perfect original parity unless that was verified.
5. `.venv/bin/python -m pytest -q` is **green locally** and **CI is green**
   (`PORT_REQUIRE_YELLOW=1` + the native LÖVE gate).
6. `docs/DEBUG_QUEUE.md` (this file) — status flipped to ✅, evidence column
   filled, §1 "most recent merged piece"/"next ⬜ piece" advanced — and
   `AGENTS.md` are updated **in the same commit**.
7. Both sides were re-checked (brief §8): Undertale rooms/movement/collisions/
   dialogue/fonts/rendering/audio/transitions and the return trip, not just the
   side that was edited.
8. Temporary debug output from the investigation is removed (brief §12).

**Then, and only then,** the PR is opened; once CI is green it is merged (rule 8).

---

## 6. How a session records its progress

1. Mark the piece's row ✅ in §3 and fill the evidence column (PR + test names +
   measured numbers where relevant).
2. Set it as the **most recent merged piece** in §1 and advance **next ⬜ piece**
   to the first remaining pending row.
3. Update `AGENTS.md` "Current state" so a new session can find the queue state,
   and keep the verification-commands section accurate.
4. One commit: `git add -A docs AGENTS.md <piece files> && git commit`. Push on
   the session branch (`arena/<id>-undertale` — never rename it).
5. Open the PR with a body that says: **piece N done — root cause, evidence
   (test + CI run), what it does *not* prove, and what piece N+1 is.** The owner
   prefers that over option menus.
6. **Merge the PR once CI is green** (`gh pr merge N --merge`) so the piece lands
   on `master` for the next session. Only complete pieces are merged.

---

## 7. Brief § → piece map (so nothing in the brief is dropped)

| brief § | subject | piece(s) |
| --- | --- | --- |
| 1 | Yellow fonts + vertical text | D1a, D1b |
| 2 | Yellow lag | D2 (with D3 where the crossing is the cause) |
| 3 | River Person duplicates the Player | D3 |
| 4 | Boat destination wrong | D4 |
| 5 | State management (worlds, stale references) | D0 (map), D3, D4 |
| 6 | Graphics state safety | D1b (the leak), D5 (the sweep + guard) |
| 7 | Resource management | D2, D5 |
| 8 | Do not break the Undertale side | every piece's gate (§5.7) + D6 |
| 9 | Debugging approach (trace first, instrument, remove output) | D0, and the "root cause written down" gate in every piece |
| 10 | Implementation requirements | §2 rules |
| 11 | Testing checklist (TEST A–F) | each piece's own tests + the D6 acceptance run |
| 12 | Final quality check + the ten-point report | D6 |

---

## 8. The D6 acceptance run (brief §11, run rather than claimed)

D6 repeats the owner's checklist end-to-end on the built archive/native gate and
records the result in `docs/DEBUG_REPORT.md`:

- **TEST A (Undertale):** start the game, play Undertale, move, talk to an NPC,
  show dialogue, confirm text orientation/fonts/rendering and no performance
  regression against the D0 baseline.
- **TEST B (enter Yellow):** approach the River Person, start the interaction,
  board, transition; verify destination room, exactly one Player, position,
  camera, collisions, movement.
- **TEST C (Yellow performance):** stay in Yellow, then move between rooms;
  watch for FPS drops, rising memory, rising entity/Player counts, rising
  draw/update workload, repeated asset loading.
- **TEST D (Yellow text):** dialogue, NPC text, menus, signs, UI (and battle text
  if reachable) — orientation, scale, position, intended font.
- **TEST E (return):** use the boat to return; verify destination, spawn
  position, exactly one Player, no duplicate sprite or collisions, no stuck
  transition, Undertale resumes.
- **TEST F (repeat):** UT → Y → UT → Y → UT → Y → UT; after every transition
  Player count = 1, active world/room as expected, old room not updating, no
  duplicate entities, no accumulating degradation.

Anything that cannot be run in CI (Android device FPS, audio fidelity, a played
route) is listed as **not verified** in the report, not implied.

---

## 9. The final report's shape (brief §12)

`docs/DEBUG_REPORT.md` answers, in order:

1. Root cause of the Undertale Yellow font issue.
2. Root cause of the vertical text issue.
3. Root cause of the Undertale Yellow performance problem.
4. Root cause of the duplicate Player problem.
5. Root cause of the incorrect River Person boat destination.
6. Files changed.
7. What was changed in each file.
8. Any architectural changes.
9. Any remaining known issues.
10. Tests performed and their results.
