# Debug & repair — the owner's ten-point final report (piece D6, brief §12)

> **Piece:** D6 of [`DEBUG_QUEUE.md`](DEBUG_QUEUE.md) — the both-side regression
> pass (TEST A–F, brief §11), the §12 cleanup, and this report. D0–D5 are
> merged; this piece runs their work end to end as one continuous session, on
> the headless probe and on the packaged archive through the CI native gate,
> and records what was found. **Two further return-side bugs were found and
> fixed by this pass itself** (point 4 below): a crossing used to leave the
> Undertale side permanently unable to move.

Everything here is verifiable in-repo:

```bash
.venv/bin/python tools/debug_probe.py --phases acceptance   # TEST A–F, one session
.venv/bin/python tools/debug_probe.py                       # full run, all phases
.venv/bin/python -m pytest -q                               # 625 passed / 1 skipped
bash tools/native_smoke.sh artifacts/check.love             # CI only (needs LOVE + xvfb)
```

---

## 1. Root cause of the Undertale Yellow font issue

Yellow's decompilation carries **raw compiled font numbers** wherever the
decompiler could not prove an asset: `obj_dialogue`'s Create sets
`dialogue_font = 9`, `scr_initialize_battle` sets `global.font_type_text = 1`.
In Yellow's own asset order those numbers mean `fnt_main` and `fnt_main_battle`;
in the merged build they were read through **Undertale's** ID band, where 9 is
`fnt_papyrus` — so Yellow's dialogue drew with Papyrus' face. Objects already
had a band re-mapper (`Runtime:resolveObjectIndex`); fonts had none.
**Fix (D1a):** `Runtime:resolveFontIndex`, consumed by `draw_set_font`
(`port/graphics.lua`), re-bands a raw number the same way when the caller is
Yellow. Yellow's `obj_dialogue` now draws with its own `fnt_main` (merged
1,000,009); Undertale's `draw_set_font(9/1/2)` still selects
papyrus/main/maintext. Evidence: `tests/test_yellow_fonts.py` (7 tests, 5 fail
without it); `obj_mainchara`'s faces and Undertale's opening text are unchanged
(TEST A below).

## 2. Root cause of the vertical text issue

Yellow's own dialogue deliberately calls
`draw_text_ext(xx, yy + 10, message, line_sep, -1)`. GameMaker reserves a
**non-positive wrap width for "no automatic wrapping"**, but the shared
renderer compared every accumulated word against `-1` and pushed each word onto
its own line: seven words became seven rows (a 55×126 px column — taller than
it is wide). It was never a leaked transform; the transform stack was audited
and is scoped (`push("all")`/`pop` around every text draw, guarded by
`tests/test_text_orientation.py`). **Fix (D1b):** `width <= 0` keeps only the
message's explicit `#`/newline breaks; positive widths keep the old word-wrap
loop. Evidence: `tests/test_text_orientation.py` (fails under the old loop),
and TEST D below — the same marker now lays out as a 344×36 px box, wider than
tall, and the native gate proves the glyph quads of `fnt_main` sit on at most
two rows (one per explicit break) with x advancing along each row.

## 3. Root cause of the Undertale Yellow performance problem

Several, all on the shared runtime rather than in Yellow's logic — each found
by profiling the actual update/draw paths (brief §2), never by lowering
resolution, cutting effects or capping the frame rate:

* **Per-frame allocation churn (D2).** `renderFrame` built a fresh draw-record
  table for every live instance and particle system on every frame. Reusing a
  room-local pool left draw count and event logic unchanged:
  Snowdin 160.70 → 149.04 KB/tick, 2,833.93 → 2,676.82 µs/tick at an unchanged
  805.90 draws/frame.
* **Texture re-decodes at every door (D5).** The per-room-load trim released
  the *whole* texture cache, so Frisk's own sprite and the next room's tile
  pages were re-decoded at every room change. Textures are now kept for one
  further room load (`newImage` per room change, Ruins 12→13→14→13→12:
  9/9/4/9/9 → 9/6/1/6/6; Yellow snowdin→dunes→snowdin→hotland: 10/4/10/3 →
  9/3/9/2), and `love.lowmemory` still frees everything.
* **One GPU mesh per coloured primitive (D5).** 75 primitives created 75
  meshes per frame; they now share one pooled stream mesh.
* **`require` in the draw path (D5).** The view pass required a module every
  frame; it is required once at load now.
* **A duplicate-entity/duplicate-update risk at the crossing (D3)** was
  removed with the duplicate-player fix below — the census in TEST F shows the
  instance count constant across three round trips (21 Yellow / 33 Undertale
  per hop, no growth).

Where it stands after D6 (headless, this run, same machine class as the D0
baseline): UT corridor 1,754–2,148 µs/tick at 48 draws/frame (D0 baseline:
2,033 µs/tick at 48 — structurally identical, the difference is machine
noise); Yellow hotland 433 µs/tick at 137 draws/frame; Yellow snowdin
2,217 µs/tick at 805.96 draws/frame and 6.45 KB/tick. The machine-independent
facts are the draws/frame and allocation numbers, and the soak (TEST C) shows
them flat across an extended stay: hotland 137 → 137 draws/frame, instances
21 → 21, memory 41,140 → 41,064 KB, and the native gate's counter proves a
steady room decodes **zero** textures per window. What is *not* claimed: a
device FPS number — the owner's phone remains the authority for that (the CI
native gate renders through software GL).

## 4. Root cause of the duplicate Player problem

**The reported duplicate (fixed in D3):** the fused crossing ran synchronously
inside `room_goto`, but GameMaker defers the room change to the end of the
step. Yellow leaves rooms through its own `obj_transition`, whose Step is
`room_goto(newRoom); if (instance_exists(obj_pl)) … else instance_create(xx,
yy, obj_pl);` — the object the UGPS whale hands its destination to. Because the
crossing had already destroyed the persistent Clover, the `else` branch built a
**second, persistent** player that rode into the Undertale room beside its own
`obj_mainchara`; both are drawn as Frisk (piece 4's pixels-only remap), which
is the owner's "two identical copies". **Fix (D3):** the crossing happens when
the destination room *loads* (`Travel:beforeLoadRoom`), exactly where
GameMaker performs a `room_goto`; the teardown is the named
`Travel:retireOtherWorld`, also applied on the save-restore path. Evidence:
`tests/test_player_identity.py` — 3× round trips with the census taken every
tick never exceed one player.

**Two further return-side bugs found by this piece's TEST E** (the "cannot
properly return to the Undertale side" half of the same report — the player
count was already 1, but the returned-to side was dead):

1. **Undertale's boot controllers never came back.** `room_start`
   (room_order[1], the boot room) places exactly two persistent instances —
   `obj_time` (the movement gates `obj_mainchara`'s Step reads, plus the
   alarms that spawn every room's collision solids and markers) and
   `obj_screen` (`keyboard_set_map`, the Z/X/C maps the boat latch also
   honours). The outbound crossing retires them with the rest of the
   Undertale world, and nothing recreated them on the way back: after one
   round trip the returned-to room had **no collision geometry** and the
   player could never move again. **Fix:** `Travel:ensureUndertaleControllers`
   in the same `afterLoadRoom` seam that already restores Yellow's controller —
   it recreates `room_start`'s persistent placements when an Undertale room
   loads without them. Only their Create events run (obj_time's Create resets
   its direction flags; obj_screen's re-applies the key maps); the Game Start
   event that calls SCR_GAMESTART fires on the first room load alone.
2. **A stale interaction lock froze the player anyway.** `global.interact` is
   set to 1 by the world being left (its open dialogue, boat-ride text or
   whale menu) and every instance that would release it is retired by the
   crossing — while `obj_mainchara` only moves at `interact == 0`. **Fix:** the
   crossing releases the lock alongside the existing `flag[0..29]` crossing
   scratch, in both directions. In the games' own flows any post-`room_goto`
   release still runs before the room change is carried out, so this only
   removes what nothing else would.

Evidence: the three new D6 tests in `tests/test_player_identity.py` (each fails
without its fix), plus TEST E/F below — after the return the player walks
240 px across the four directions with zero Yellow-side events, and three
round trips keep `obj_time`/`obj_screen` at exactly one each.

## 5. Root cause of the incorrect River Person boat destination

The River Person's boat machine (`obj_dogboat_thing`, converted unchanged)
boards through **room 316** and only later disembarks with
`room_goto(70/125/140)` chosen by `global.flag[459]`. The fused bridge treated
the X-held latch as a general room switch, so the **boarding** `room_goto(316)`
could consume the committed Yellow destination — teleporting the player and
skipping the ride — and the hold-X latch could silently flip an Undertale dock
into a Yellow stop. **Fix (D4):** room 316 is an explicit boarding/ride
pass-through; the committed destination (pager selection or hold-X mapping) is
preserved until the boat's own `con=18` disembark request; source dock IDs and
landing data are unchanged (no invented coordinates — the landings are read
from the dock rooms' own boat instances). All six packaged cases land as
documented, including the full interactive ride after a pager choice and the
whale return. Evidence: `tests/test_boat_destination.py` plus the interactive
travel tests; TEST B/E/F below re-drive the packaged crossings.

## 6. Files changed (per piece)

| piece | files |
| --- | --- |
| D0 (merged) | new `docs/DEBUG_BASELINE.md`, new `tools/debug_probe.py`, `tests/test_debug_probe.py` — no behaviour change |
| D1a (merged) | `port/runtime.lua` (`Runtime:resolveFontIndex`), `port/graphics.lua` (`draw_set_font`), `tests/test_yellow_fonts.py` |
| D1b (merged) | `port/graphics.lua` (`draw_text_ext` no-auto-wrap), `tests/test_text_orientation.py`, `tools/debug_probe.py` |
| D2 (merged) | `port/graphics.lua` (room-local draw-record pool), `tests/test_yellow_performance.py` |
| D3 (merged) | `port/travel.lua` (`beforeLoadRoom`/`retireOtherWorld`/`afterLoadRoom`), `tools/debug_probe.py`, `tests/test_player_identity.py` |
| D4 (merged) | `port/travel.lua` (room-316 pass-through, committed destination), `tests/test_boat_destination.py` |
| D5 (merged) | `port/graphics.lua`, `port/yellow_studio.lua` (`pr_*` kinds, pooled mesh), `main.lua` (`love.lowmemory`), `tests/test_graphics_state.py` |
| **D6 (this piece)** | `port/travel.lua` (boot-controller restore + interaction-lock release), `port/inventory.lua` (dead `setEquipment` removed), `tools/debug_probe.py` (acceptance phase), `port/smoke.lua` (native TEST C/D/F), `tools/native_smoke.sh` (requires the acceptance outputs), `tests/test_player_identity.py` (+3), new `tests/test_debug_acceptance.py` (5), this report, `docs/PORTING.md`, `docs/DEBUG_QUEUE.md`, `AGENTS.md` |

## 7. What was changed in each file (D6)

* **`port/travel.lua`** — `Travel:ensureUndertaleControllers`: recreates
  `room_start`'s persistent placements (`obj_time`, `obj_screen` — the set is
  read from the boot room's own data, not hand-picked) when an Undertale room
  loads without them, from the same `afterLoadRoom` seam that restores Yellow's
  controller. `Travel:beginCrossing` releases `global.interact` with the rest
  of the crossing scratch, with a warning line when it was held.
* **`port/inventory.lua`** — removed the unused local `setEquipment` (piece 5b
  draft; the real guard lives in the equipment view path) — the §12 dead-code
  sweep found nothing else in `port/`, `main.lua` or `tools/` (353 definitions
  scanned; no debug prints, TODO markers or temporary hacks remained from
  D0–D5 — the probe and its tests are committed deliverables, not scaffolding).
* **`tools/debug_probe.py`** — the `acceptance` phase: TEST A–F as one fresh,
  continuous session (opening → crossing → soak → dialogue → return → repeated
  crossings), with an event census by world band proving the old world never
  updates, per-tick player census, and per-scenario PASS lines ending in
  `DEBUG ACCEPTANCE PASS: A B C D E F`.
* **`port/smoke.lua`** — the native gate's D6 sections: a `newImage` counter
  (file loads only) with a two-window soak that must decode 0 textures in a
  steady room; the dialogue proof (intercepts `fnt_main`'s glyph quads for one
  frame: ≤ 2 rows, ≥ 6 glyphs on the widest row, > 60 px span) with a
  `native-yellow-text` capture; two more packaged round trips with an
  every-tick player census, the boot-controller and interaction-lock checks;
  writes `native-debug-acceptance.txt`.
* **`tools/native_smoke.sh`** — requires `DEBUG ACCEPTANCE PASS`, the
  acceptance file and the new capture; the wall timeout is raised 600 s → 720 s
  for the added sections (the tick budget already covered them).
* **Tests** — `tests/test_player_identity.py` +3 (boot controllers, movement
  after return, interaction lock — each fails without its fix);
  `tests/test_debug_acceptance.py` new (runs the acceptance phase; asserts the
  six PASS lines, the D0-baseline pin, the two text symptoms re-answered, the
  TEST F census, and the native gate's wiring — the last fails without the
  smoke/native-smoke change).

## 8. Architectural changes

**None new in D6.** Both fixes are the existing architecture applied
symmetrically: the boot-controller restore mirrors `ensureYellowController` in
the one seam that owns world lifetime (`Travel:afterLoadRoom`), and the
interaction lock joins `flag[0..29]` as crossing scratch cleared by
`beginCrossing`. The certified fusion invariants are re-asserted unchanged by
the acceptance run: one `R.player` record, one inventory/equipment, one
controller, one `merge.sav`, Frisk-only rendering in Yellow, and the Undertale
side intact (TEST A pins its corridor to the D0 baseline). The plan's one
architectural move was D3's (crossing at the destination room's load), already
merged and now guarded end to end by TEST F.

## 9. Remaining known issues

* **86 unresolved static numeric asset references** and 3 unrecoverable pinned
  IDs (recorded in `conversion-report.json`); room 159 is absent from the
  export and stops by name; external resources (dynamically replaced boss
  images, `credits.txt`) are missing. See `PORTING.md` → "Known blockers".
* **Yellow's battle and story systems are unclaimed** (the shipped scope is the
  overworld crossing); shaders are not converted (scenes keep original
  colours); 25 rooms have named stops.
* **Not verified by this plan:** Android device FPS/latency, audio fidelity,
  touch latency, and a hand-played route on the owner's phone. The native gate
  renders through software GL in CI; it proves draw facts, not device speed.
* **Scoped out of TEST D:** dialogue and NPC text are driven directly
  (`obj_dialogue`); menus, signs and battle text were not individually driven
  — every text draw in the acceptance frames is asserted to be a Yellow-band
  font record while in Yellow, and the shared renderer's orientation semantics
  are unit-tested, but no menu/sign/battle screen was opened by the harness.
* **`global.entrance` is left as-is:** a crossing can leave the leaving world's
  entrance mode set. It is inert (consumed only alongside `interact == 3`,
  which the crossing releases, and every door/boat sets its own pair), so no
  failure is provable from it; recorded here rather than patched speculatively.

## 10. Tests performed and their results

* **TEST A (Undertale)** — played opening → naming → `room_area1` →
  `room_area1_2`; scripted walk moved the player 510 px; Flowey's "Howdy"
  dialogue present; 42 text draws, all Undertale font records
  (`fnt_maintext`); corridor **48 draws/frame (D0 baseline: 48)**,
  1,754 µs/tick (D0: 2,033). **PASS** (headless; native gate covers the same
  opening with pixel assertions).
* **TEST B (enter Yellow)** — dock 140 + X held → `rm_hotland_02`; one player,
  shared Player record kept; landed at Yellow's own 170,120; per-direction
  legs moved 120+120+10+48 px inside the 520×240 room; the 320×240 camera view
  contains the player. **PASS**.
* **TEST C (Yellow soak)** — 150-tick windows, hotland → snowdin → dunes →
  hotland; one player at every tick; instances 21 → 21; hotland draws/frame
  137 → 137 (snowdin 809, dunes 2,576); allocations ~0 KB/tick; memory
  41,140 → 41,064 KB; natively: **0 texture decodes per steady window**
  (snowdin 0+0 after warm-up, hotland 0), heap 20,276 → 20,343 KB.
  **PASS**.
* **TEST D (Yellow text)** — `obj_dialogue` drew the marker with Yellow's own
  `fnt_main` (merged 1,000,009); every text draw in the frame is a
  Yellow-band record; the one explicit break lays out as a 344×36 box, wider
  than tall (D0 symptom: 55×126). Natively the glyph quads form at most 2
  rows. **PASS**.
* **TEST E (return)** — `fast_travel_point="Waterfall - Dock"` →
  `room_water_dock`; one player at the dock room's own placement 140,100 (the
  boat is placed 67 px away); Undertale movement resumed (240 px across the
  four legs) with **zero Yellow-side events**; no transition stuck.
  **PASS** (after this piece's two fixes; it froze before them).
* **TEST F (repeated transitions)** — UT → Y → UT → Y → UT → Y → UT (three
  round trips, six crossings, census every tick): max 1 player at any tick,
  world/room as expected at every hop, instances 21/33 per hop with no growth,
  allocations flat. **PASS**.
* **Full local suite:** `625 passed, 1 skipped` (PORT_REQUIRE_YELLOW off in
  the sandbox; CI runs it with the Yellow gates required). **CI:** the PR's
  workflow run carries `pytest` with `PORT_REQUIRE_YELLOW=1`, the merged
  packaging check and the native LÖVE gate, which now also requires
  `DEBUG ACCEPTANCE PASS` (linked in the PR body).
* **Real build path:** `tools/package.py --merged --no-convert` builds the
  389.8 MiB archive (SHA-256
  `a27ae2831b11a03e598770508ee7f8a82a49a79924f9a24f43b34945b67d4a3c`); the
  native gate runs TEST A–F against that archive in CI.

**Scope of all evidence above:** headless converted flow + traced draw log +
CI software-GL native gate, fixed seed, one machine class. It does not claim
Android GPU behaviour, audio fidelity, or a hand-played route.
