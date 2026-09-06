# Experimental LÖVE build — not a fully functional game port

This prerelease makes the current `.love` package downloadable from GitHub. It
contains the converted Lua and the assets supplied in this repository. **It is
not a completed or native-device-verified game, and it is not an APK.**

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

1. Download **`undertale-love-v0.1.2-experimental.love`** from the assets below
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
