# Experimental LÖVE build — not a fully functional game port

This prerelease makes the current `.love` package downloadable from GitHub. It
contains the converted Lua and the assets supplied in this repository. **It is
not a completed or native-device-verified game, and it is not an APK.**

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

1. Download **`undertale-love-v0.1.3-experimental.love`** from the assets below
   (approximately 124 MB). Do not download GitHub's automatic “Source code” ZIP
   if you want to try the packaged game.
2. Install the official **LÖVE 11.5 runtime** for your platform:
   https://github.com/love2d/love/releases/tag/11.5
3. Open the `.love` file with LÖVE on desktop or Android. Python and GameMaker are
   not required for the downloaded archive.

Touch controls include the D-pad, Z/X/C, extra key pages, pause/settings,
handedness, size/opacity adjustment, and a control tester. Actual touchscreen
behavior still needs device validation.

## Validation and limitations

The automated tests check Lua 5.1/LuaJIT syntax, the converted opening/title,
naming, initial movement, menu/cancel, first doorway, save/load, persistence,
input handling, and reproducible packaging. **The separate native smoke test checks Linux rendering with software OpenGL and
null audio; neither test suite establishes Android GPU compatibility, audible
fidelity, physical touch latency, or full-game playability. No Android APK has
been compiled or installed as part of this prerelease.**

Missing movement paths and external resources, unresolved numeric asset IDs,
and remaining GameMaker compatibility work prevent a complete game. Path playback
also needs implementation and validation against recovered data. Some scenes
will stop with a diagnostic; missing resources have not been fabricated or
silently replaced. Some of the missing external files are optional/debug assets.

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
