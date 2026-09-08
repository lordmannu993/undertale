# Movement paths: what was missing, how it was recovered, what is claimed

Piece 1 of the path-recovery work. Recorded here because the previous behaviour was a
hard stop in the middle of the first scripted walk, and because recovered data is only
worth anything if its provenance and its semantics are written down.

## The problem

`projectA.project.gmx` in this checkout lists **zero** entries in every resource
section and has **no `paths` element at all**. The loose per-asset `.gmx` files
survived the decompile, the resource registry did not. The converter therefore learned
path *names* only from decompiler comments such as:

```
path_start(5/* path_torielwalk1 */, 0, 0, 1/* path_action_restart */);
```

38 referenced names, no point data. `Runtime:startPath` raised a compatibility stop on
every one of them, which is what a player in `room_ruins1` sees: Toriel's walk to the
ruins door begins with `path_start(5, ...)`.

## How the data was recovered

`tools/recover_paths.py` fetches each referenced path from a public GameMaker project
dump and writes `port/path_data.json`:

| field | value |
| --- | --- |
| upstream project | `kittibyte/UndertaleDecomp` |
| pinned commit | `249ffa27ee7e7eee0d7ce84b736c294458b38685` (never a branch name) |
| source layout | `paths/<name>/<name>.yy` (GMS2 GMPath record) |
| result | 38 of 38 referenced paths recovered, 19 KB |

Rules the tool enforces, and the reason it exists instead of hand-typed numbers:

- only paths **this repository's own code references** are fetched;
- nothing is interpolated, rounded or added — every stored coordinate is an integer,
  and `tests/test_paths.py` fails if a fractional point appears;
- a name with no upstream record stays absent so `path_start` keeps stopping;
- each path carries `source.upstream`, `source.ref` and `source.file`, so any single
  claim can be re-checked or reverted.

Rerun with `python3 tools/recover_paths.py` (needs `GITHUB_TOKEN` for the API rate
limit); verify the checked-in file with `python3 tools/recover_paths.py --check`.

## Playback semantics, and the evidence behind each choice

Implemented in `Runtime:startPath` / `Runtime:advancePath` / `Runtime:pathGeometry`:

- **`path_speed` is pixels per step.** `path_position` advances by
  `path_speed / total_length`, so the same fraction is the same place on the path at
  any speed. `obj_toroverworld2` sets `path_speed = 2/3/4` from the player's distance,
  which only behaves like Toriel pacing you if speed is measured in pixels.
- **The fourth argument is GameMaker's absolute flag, not a relative offset.**
  `room_ruins1` places `obj_toroverworld2` at `x=142 y=320`; the recovered
  `path_torielwalk1` starts at `140,320`. Read as absolute the path begins 2 px from
  where she stands; read as relative it would put her at `282,640`, outside a
  `320x480` room. `tests/test_paths.py` pins that comparison so the choice cannot rot.
- **One deliberate deviation from the upstream source: `obj_torhandhold1`'s three
  `path_start` calls pass the absolute flag, where the pinned decompile passes `0`.**
  The upstream `obj_torhandhold1` starts `path_torielwalk5_2` (and Toriel's
  `path_walkright` exit) with the *relative* flag; taken as offsets from the walk-in
  position near (768,110) the recovered points — which zig-zag across the spike maze
  in room-absolute coordinates ending at (1136,60) — would put the crossing at
  (1540,210)..(1904,170), outside the `1200x240` room, and the scene limps on
  off-camera with the player invisible (the reported "Toriel and player go missing"
  at the spike bridge). This checkout therefore passes `1/* absolute */` on all three
  calls, matching what sibling `obj_toroverworld6` already passes for
  `path_torielwalk5` in the same room. The evidence and the resulting scene flow
  (`path_position == 1` → restore visibility/`phasing`, create `obj_toroverworld4`,
  farewell dialogue to `plot = 8`) are pinned by
  `tests/test_paths.py::test_toriel_handhold_completes_scene_instead_of_walking_off_room`.
- **Start snaps onto the path.** GameMaker places the instance at the path position
  when the path begins, so `path_start` does the same instead of waiting a step.
- **End actions follow the constants this runtime declares** (`path_action_stop = 0`,
  `restart = 1`, `continue = 2`, `reverse = 3`): stop ends the path on the last point,
  restart wraps to the next lap, continue holds the end without ending the path,
  reverse flips the speed sign and bounces at both ends. The GameMaker 1.4 numbering is
  0/1/2 for stop/continue/reverse, so a *future* export that passes 1 or 2 means
  something different; Undertale itself only ever passes `0` here, which is
  unambiguous in either table. Recorded as an open question, not settled.
- **`kind` 0 is the polyline through the authored points; `kind` 1 is a Catmull-Rom
  spline sampled `precision` times per span**, with open paths repeating their
  endpoints as phantom control points. Undertale's recovered paths mix both kinds and
  some are closed, so `pathGeometry` adds the return segment only for closed paths.
- **Deliberate deviations.** `path_orientation` is only honoured when negative (follow
  the tangent); instances default to `0` here and Undertale sets `direction` and its
  own facing state explicitly, so overwriting it every step would be a behaviour change
  with no evidence behind it. `path_scale` is not applied at all: nothing in this
  repository's code sets it.

## What this makes possible, and what it does not claim

Covers the whole Toriel corridor/house/basement walk family, Flowey's battle hands
(`path_hand1`, `path_hand2`), `path_bedjump`, `path_unbed`, the Papyrus walks,
`path_waterglass`, `path_icecube_water1`, `path_goofyrock`, the dog walks, froghead and
the `path_walkup`/`path_walkdown`/`path_whimsun` set.

Not claimed:

- no frame-for-frame comparison against the original engine's path stepping; the timing
  model is documented GameMaker behaviour plus the source code's own speed usage;
- no Android device run, and the spline sampling for `kind 1` is the standard
  Catmull-Rom formula, not a byte-identical reproduction of GameMaker's sampler;
- the route gate proves the walk renders on Linux software GL. It does not prove the
  ruins door transition, and it does not exercise the other 36 recovered paths.

## Pieces

- [x] Piece 1 — recover point data with provenance; implement playback; tests; docs.
- [x] Piece 2 — native gate: `port/smoke.lua` now plays Flowey's tutorial fight, follows
      Toriel into `room_ruins1`, and asserts the renderer actually drew her displaced
      along the recovered path: every `spr_toriel*` draw call observed during the walk is
      accumulated and the furthest must be more than 20 px from her room placement, with
      the sample count, sprite name, furthest drawn position and `path_position` recorded
      in `native-toriel-walk.txt` alongside the `native-toriel-walk.png` capture.
      `tools/native_smoke.sh` fails unless both exist. Budget raised to 9000 frames and
      420 s because the route is genuinely longer.
      First CI attempt gated on the single frame the screenshot landed in, where she is
      not guaranteed to be inside the view; that is why the check is a per-walk
      accumulation now, and it is green on run 34149357546.
- [x] Piece 3 — route harness: `tests/test_paths.py::test_the_reported_scene_now_walks_instead_of_stopping`
      drives the real scripted battle, dialogue and triggers into `room_ruins1`, then
      asserts `path_position` advances and she leaves her placement behind. No teleporting.
- [x] Piece 4 — import the safe registry evidence with `tools/recover_registry.py`.
      The pinned dump is recorded in `port/recovered_registry.json`; exact local-name
      matches reduce the statically recognizable unresolved-ID count from 86 to 44.
      Conflicting names are retained as conflicts rather than guessed. The 68 external
      files and the remaining ambiguous IDs are still explicit limitations.
- [x] Piece 5a — recover the missing room source from the same pinned dump.
      `tools/recover_missing_room.py` verifies the checked-in SHA-256 and the source is
      packaged as `port/recovered_rooms/room_fire_walkandbranch.yy` with provenance.
      The source is GMS2 `.yy`, while this port consumes GMX; the explicit adapter remains
      open, so the runtime still stops at slot 159 rather than pretending the formats are
      interchangeable. A release is not claimed until that adapter is tested.
