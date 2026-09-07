# Experimental LÖVE build — not a fully functional game port

This prerelease makes the current `.love` package downloadable from GitHub. It
contains the converted Lua and the assets supplied in this repository. **It is
not a completed or native-device-verified game, and it is not an APK.**

## v0.1.3 fixes

- Fix the sprite-glitch softlock at the end of Flowey's tutorial fight. The
  damaged GMX export negated `obj_dialoguer`'s `obj_face` cleanup guards (its
  Destroy event and the no-face branch of its Step event), so dialogue face
  portraits leaked: Flowey's face followed the player out of the battle, stacked
  on top of Toriel's, and the leftover Toriel face then blocked
  `obj_floweytrigger`'s `!instance_exists(obj_torface)` check forever. Both
  guards are restored — verified against the shipped game's decompilation and
  applied as an audited, per-event SHA-256-guarded conversion repair. The
  original GameMaker files are unchanged.
- Restore Toriel's directional overworld sprite IDs (`spr_toriel_dt`/`_r`/`_l`/
  `_rt`/`_lt`), so her walk animations resolve to the correct original sprites.
- Add regression coverage that plays the full tutorial battle through its ending:
  it checks the faces are cleaned up, `obj_floweytrigger` advances, and player
  control is returned. An audit test verifies the repair report and rejects a
  different source export. **145 automated tests** now pass.
- Retain every v0.1.2 fix: reference-guided opening scenery, decompiler-reversed
  dialogue-label repairs, correct font IDs, the room-ID gap and proper Flowey/
  battle/game-over routing, and the larger phone Fit viewport.

Close the old running LÖVE game before opening the new versioned file; resuming an
old Android recent-app card will keep running the previous build. The same save
identity is retained. Flowey's alternate greetings on repeat attempts are normal
saved-history behaviour, not scrambled dialogue. Android's rotated/dimmed
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
