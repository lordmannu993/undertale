# Experimental LÖVE build — not a fully functional game port

This prerelease makes the current `.love` package downloadable from GitHub. It
contains the converted Lua and the assets supplied in this repository. **It is
not a completed or native-device-verified game, and it is not an APK.**

## v0.1.8 fixes

- **Fix the crash on starting most battles outside the Ruins** (reported as:
  *unable to initiate battle with any enemy in Snowdin — "Port compatibility
  stop: instance_create Missing object ID 255" against `obj_snowdrake` in
  `room_battle`*). Every part-based monster spawns its artwork through a local
  variable holding a bare original object ID (`part2= 255; mypart2=
  instance_create(x, y, part2)`), and those literals carry no decompiler
  annotation — so the body-part objects stayed on synthetic IDs and
  `instance_create` stopped the moment the battle controller created the
  monster. The first Snowdin encounter (battlegroup 30, Snowdrake) stopped on
  255; Doggo, Dogamy & Dogaressa, Greater Dog, Gyftrot, Glyde, Papyrus, Shyren,
  Undyne the Undying, Mettaton EX/NEO, So Sorry and the True Lab amalgamates all
  hit the same wall on their own part IDs.
- **Recover the 22 missing part-object IDs with pinned, auditable provenance.**
  `tools/recover_parts.py` pairs each of this checkout's own numeric literals
  with the object name that the pinned upstream decompilation
  (`kittibyte/UndertaleDecomp` @ `249ffa27`, the same immutable commit already
  backing the registry and movement-path recoveries) uses for the *same
  statement* — accepting a pair only when both events assign the same `partN`
  variables in the same order, and taking **no number from the dump**: IDs come
  from this repository's own literals, only the names are paired. The sweep also
  re-validates the 38 part sites that already have decompiler annotations as
  anchors, refuses on any disagreement, and records per-site provenance in
  `port/recovered_parts.json` (fetched by script, committed, and imported by the
  converter). A `--check` mode re-verifies the file offline.
- All 59 monster part-spawn sites in the game now resolve, so part-based
  battles start and draw their monsters. This does **not** certify full battle
  fidelity: turn logic, ACT/FIGHT behaviour and attack patterns beyond the
  scripted regression coverage remain unverified.
- 16 new automated tests pin the fix (the suite grows from 163 to **179**): the
  provenance and no-invention checks, a static guard that every `partN` literal
  passed to `instance_create` resolves to a registered object, the reported
  crash case (ID 255 = `obj_drakebody`) explicitly, and end-to-end battle tests
  for every Snowdin battlegroup (Doggo, Lesser Dog, Dogamy & Dogaressa, Greater
  Dog, Papyrus, Gyftrot, Snowdrake, Ice Cap, Jerry, Glad Dummy, Glyde) plus a
  Waterfall Shyren spot check. Each was verified to fail on the unfixed build
  with the reported crash signature before passing after it.
- Updated the GitHub download to the v0.1.8 experimental LOVE archive.

## v0.1.7 fixes

- **Fix the Ruins spike-bridge softlock** ("Toriel and the player go missing").
  `obj_torhandhold1` started the recovered `path_torielwalk5_2` with GameMaker's
  *relative* path flag, but the recovered points are room-absolute coordinates
  that zig-zag across the spike maze. Read as offsets from the walk-in position
  near (768,110) the hand-in-hand crossing landed at (1540,210)..(1904,170) —
  outside the `1200x240` room — so the crossing, its follow-up dialogue and the
  hand-back of control all happened off-camera with the player invisible. All
  three `path_start` calls in that object now pass the absolute flag, exactly as
  sibling `obj_toroverworld6` already did for `path_torielwalk5` in the same room.
  The scene now ends in view at (1136,60), restores `phasing` and the player's
  visibility, creates `obj_toroverworld4`, and the farewell dialogue completes.
  This is a **listed deviation** from the pinned upstream decompile (which passes
  `0`); the room geometry makes relative coordinates impossible there, and the
  evidence is recorded in `docs/PATHS.md` under "Playback semantics".
- **Fix overlapping dialogue when skipping text.** `scr_textskip` (X/Shift) only
  fast-forwarded the character position, so a writer that had reached a halt state
  never ran its own confirm-key page advance or destroy event and stayed alive
  under the next bubble's writer. The script now branches on the writer's halt
  state the way the writer's own user event does: complete the page, advance it,
  or hand control back and destroy the stalled writer.
- **Add a touch COLLISION toggle for testing.** PAUSE gains a seventh row,
  `COLLISION: ON/OFF`, mapped onto the game's own `phasing` debug global (the
  keyboard toggle on `obj_mainchara`): OFF walks through walls. It is a testing
  aid, not a setting — it is never written to the persisted touch settings, it
  defaults to ON, and it is re-applied after an in-game restart.
- Three new regressions pin these fixes (the suite grows from 160 to **163
  automated tests**), and each was verified to fail on the unfixed code with the
  bug's own signature before passing after it.
- Updated the GitHub download to the v0.1.7 experimental LOVE archive, and this
  page's "Download and try" section, which still named the v0.1.5 asset.
- Corrected a stale limitation count: `README.md` and `docs/PORTING.md` claimed
  **44** unresolved numeric asset IDs, but the conversion report that ships inside
  the archive has listed **86** ever since v0.1.6 made the pinned upstream
  registry dump audit-only (no IDs imported). `docs/CONTROLS.md` now documents the
  new PAUSE COLLISION row.

## v0.1.6 fixes

- Toriel now faces the tangent while following paths, including reverse travel; stopped paths preserve the scripted facing.
- Voided the incompatible upstream registry import and restored all 13 verified Toriel dialogue-face sprite IDs, preventing disco-ball and unrelated portraits.
- Alarm timers now fire when they cross zero, so the first Froggit encounter starts normally.

## v0.1.5 fixes

- **Restore the missing Toriel/Asriel directional and talking sprite IDs.** The
  decompiler only annotated a handful of the directional sprite IDs, so Toriel's
  up-talking pose (`utsprite`/`usprite` = 1111) and the hand-hold down/up poses
  (1113/1117) fell through to synthetic IDs or were absent entirely, and the
  Toriel/Asriel overworld reveal (`obj_torinteractable7`,
  `obj_asriel_overworldanim`) drew Asriel's side/up/talking poses blank. Restored
  in `port/resource_overrides.json`: `spr_toriel_ut` 1111,
  `spr_toriel_handhold_d` 1113, `spr_toriel_handhold_u` 1117, `spr_asriel_dt`
  2418, `spr_asriel_ut` 2420, `spr_asriel_rt` 2422, `spr_asriel_l` 2424,
  `spr_asriel_lt` 2425.
- A new regression (`tests/test_toriel_sprites.py`) asserts every
  directional/talking sprite ID a Toriel or Asriel overworld object assigns
  resolves to a real, non-empty sprite, and that the restored IDs are not
  synthetic.
- Corrected the v0.1.4 release page, whose "Download and try" section named the
  v0.1.3 asset and whose limitations text still described movement paths as
  missing although that archive contains all 38 recovered paths and their
  playback.
- Updated the GitHub download to the v0.1.5 experimental LOVE archive.

## v0.1.4 fixes

- Added pinned exact-name resource-registry evidence, The upstream registry is audit-only; its conflicting candidates are retained, and the honest unresolved count remains 86.
- Recovered the missing Hotland room 159 source from the pinned upstream dump and included its provenance in the archive. The runtime continues to stop explicitly until a tested GMS2-to-GMX adapter is available.
- Recovered point data for all 38 referenced movement paths from one pinned upstream GameMaker project dump and played them back at GameMaker's pixels-per-step speed. Per-path provenance and the coordinate-semantics evidence are in docs/PATHS.md.
- The release was gated on a native Linux LÖVE run asserting Toriel is actually drawn displaced along her recovered path, plus a route test that drives the real scripted fight and dialogue into room_ruins1.
- Updated the GitHub download to the v0.1.4 experimental LOVE archive.

## v0.1.3 fixes

- **Fix the end-of-battle sprite glitch and permanent softlock after Flowey's
  tutorial fight.** The damaged GameMaker export negated `obj_dialoguer`'s
  `obj_face` cleanup guards in two events (its Destroy event and the no-face
  branch of its Step event), so dialogue face portraits were never destroyed.
  Flowey's face survived into and out of the tutorial battle and stacked on top
  of Toriel's at nearly the same coordinates, and the leftover Toriel face then
  blocked `obj_floweytrigger`'s `!instance_exists(obj_torface)` wait forever:
  control never returned and Toriel never led you to the ruins door. Both guards
  are restored to match the shipped game's decompilation, each behind its own
  per-event source-hash guard, and recorded in the conversion report.
- **Restore the verified Toriel directional sprite IDs** (`spr_toriel_dt` 1105,
  `spr_toriel_r` 1107, `spr_toriel_l` 1108, `spr_toriel_rt` 1109,
  `spr_toriel_lt` 1110) in `port/resource_overrides.json`, preserving the
  existing ID anchors.
- A new regression plays the entire tutorial fight like a player (steering the
  SOUL into Flowey's pellets and advancing his dialogue) and then asserts that no
  face leaks, the game returns to `room_area1_2`, Toriel appears and speaks, her
  face is cleaned up, `obj_floweytrigger` advances past the stuck state, player
  control returns, and Toriel starts walking toward the ruins door. A second test
  audits the repair itself: both events are reported, the generated Lua carries the
  restored guard, and a different source export is rejected by the hash guard.
- **145 automated tests** now pass (was 143).

## v0.1.2 fixes

- Restore reference-guided opening scenery: the chamber floor, light rings,
  corridor and doorway. Original flower tiles and collision are unchanged.
  This is an explicit reconstruction, not a claim of recovered original tiles.
- Correct decompiler-reversed dialogue labels: Flowey now explains the SOUL,
  rather than showing Undyne's chair question. Repair the verified item/phone/
  encounter/Papyrus-call tables with exact source-hash guards as well.
- Fix font IDs for the main/damage/HUD/Sans/Papyrus/Wingdings roles and malformed
  decimal-comma arguments that shifted text speed/sound/line spacing.
- Require exact dialogue-content and text-bounds assertions, plus native floor,
  light-ring and doorway pixels and five scene screenshots.
- Retain the v0.1.1 room-ID gap, proper Flowey/battle/game-over routing and larger
  phone Fit viewport.

Close the old running LÖVE game before opening the new versioned file. The same
save identity is retained. Flowey's alternate greetings on repeat attempts are
normal saved-history behaviour, not scrambled dialogue. Android's rotated/dimmed
recent-app thumbnail is not an in-game rendering setting.

## Download and try

1. Download **`undertale-love-v0.1.7-experimental.love`** from the assets below
   (approximately 124 MB). Do not download GitHub's automatic “Source code” ZIP
   if you want to try the packaged game.
2. Install the official **LÖVE 11.5 runtime** for your platform:
   https://github.com/love2d/love/releases/tag/11.5
3. Open the `.love` file with LÖVE on desktop or Android. Python and GameMaker are
   not required for the downloaded archive.

Touch controls include the D-pad, Z/X/C, extra key pages, pause/settings,
handedness, size/opacity adjustment, a control tester, and (from v0.1.7) a
runtime-only COLLISION toggle for walking through walls while testing. Actual
touchscreen behavior still needs device validation.

## Validation and limitations

The automated tests check Lua 5.1/LuaJIT syntax, the converted opening/title,
naming, initial movement, menu/cancel, first doorway, save/load, persistence,
input handling, and reproducible packaging. **The separate native smoke test checks Linux rendering with software OpenGL and
null audio; neither test suite establishes Android GPU compatibility, audible
fidelity, physical touch latency, or full-game playability. No Android APK has
been compiled or installed as part of this prerelease.**

All 38 referenced movement paths were recovered with pinned provenance
(docs/PATHS.md) and are played back by the runtime, but frame-level parity with
the original engine's stepping is not yet certified. Missing external
resources, the remaining unresolved numeric asset IDs, the missing Hotland
room's GMS2-to-GMX adapter, and remaining GameMaker compatibility work
prevent a complete game. Some scenes will stop with a diagnostic; missing
resources have not been fabricated or silently replaced. Some of the missing
external files are optional/debug assets.

See the bundled `docs/PORTING.md`, `docs/ANDROID.md`, and `docs/VALIDATION.md`, plus
the attached conversion report. This release must not be presented as a finished
game or as having “perfect” touch controls.

## Rebuild and provenance

Rebuild from the source commit listed below with `python3 tools/package.py`.
The archive is a Release asset, not a Git-tracked binary. ZIP output is repeatable
for the same source and Python/zlib toolchain; check the attached checksum for
this particular build.

The original repository describes its source as likely decompiled and does not
grant redistribution rights. No ownership of or license to the original game is
claimed by this port; only use or distribute material you have the right to use.
