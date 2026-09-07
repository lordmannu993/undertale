# Port status and implementation

## What is converted

The build translates **20,285 source units** (137,558 lines of extracted GML),
including empty event/creation units, with **zero parse failures**:

| Resource | Count | Treatment |
|---|---:|---|
| Scripts | 173 | Generated Lua functions |
| Objects | 1,703 | Metadata plus every event function |
| Rooms | 334 | Creation code, instances, backgrounds, views and tiles |
| Sprites | 2,472 / 7,505 frames | Original PNGs, origins, masks and animation metadata |
| Sounds | 439 | Original audio, recovered sound IDs |
| Backgrounds | 197 | Original PNGs and tile references |
| Fonts | 11 | Original bitmap atlases and repaired glyph metadata |

**“All source units translated” is not “the entire game is working.”** This is a
compatibility-layer port, not a hand-rewrite of every object into idiomatic Lua.
No GameMaker runner, compiler, Windows executable, or proprietary runtime is
bundled. The `.love` archive is self-contained once built.

## Known blockers — do not hide these

**An entire room is also absent:** original ID **159**, the Hotland
walk-and-branch connector between the hot-dog stand and subsequent rooms.
It is recorded in `missing_rooms`; attempting to enter it stops explicitly.
This omission must not shift the IDs of the 334 rooms that are supplied.


1. **38 referenced movement paths are absent.** The GMX project's `paths` section
   is empty. `path_start` fails with the missing path's name, rather than
   fabricating movement or falsely completing a cutscene. Path parsing/playback
   also needs implementing and validating against the recovered original point
   data; dropping files into a folder alone is not sufficient yet.
2. **Original numeric resource IDs were lost in the alphabetized export.** The
   converter recovers annotations, `with` comments, room instance order and music
   aliases. Unidentified *named* assets receive synthetic IDs outside the legacy
   range; it never assigns an arbitrary alphabetic asset to a numeric reference.
   The report currently lists **86 unresolved IDs in statically recognizable
   reference positions**. This is not an exhaustive dynamic data-flow analysis.
   Queries for an unknown object return no match with a warning; creation of an
   unknown object stops. Unknown image/audio cues warn and cannot be reproduced.
3. **External resources are absent**, including dynamically replaced boss images,
   `credits.txt`, and the unused `data/unused/dfb` background. Detailed paths and
   call sites are in `missing_external_files`. Missing external sprite loads stop
   explicitly. Animated GIF replacement and dynamic color-key removal still need
   work; static PNG replacement is supported in the limited single-frame case.
4. **Full GameMaker fidelity is unverified.** In particular, complex collision
   ordering, pixel-mask sampling under subpixel/rotated scales, persistence edge
   cases, camera behavior, gradient text, advanced battles, and every route/end
   sequence need comparison against a reference run. Gradient text currently
   warns and uses its first corner color. Path execution is explicitly unsupported.
5. **No Android device certification or APK build.** Python tests run the real
   generated Lua headlessly. The v0.1.1 release pipeline additionally runs the
   packaged game in native Linux LÖVE under Xvfb/software OpenGL, checks actual
   enemy/border/SOUL pixels and captures screenshots using touch callbacks.
   Audio uses a null output device. These checks still do not establish Android
   GPU compatibility, audible fidelity, physical touch latency or lifecycle
   behavior. The Android APK tooling remains unverified.

Steam services intentionally report unavailable. LÖVE gamepad input replaces the
legacy Windows joystick poller; the old in-game joystick configuration is not
used. All original debug keys remain available, but touch controls do **not**
enable `global.debug`.

## Reproducible pipeline

```text
projectA.project.gmx + GMX/GML files
              |
      tools/convert.py
      tools/gml.py (lexer, Pratt parser, Lua emitter)
              |
          generated/
              |
  port/runtime.lua + input/storage/graphics/audio/collision
              |
        tools/package.py
              |
  artifacts/undertale-love-experimental.love
              |
  tools/build_android.py (separate, pinned love-android dependency)
              |
  development APK, only when an Android toolchain actually builds it
```

Conversion rejects unknown syntax and drag-and-drop actions rather than dropping
code. Every generated Lua chunk is checked by the tests in both **Lua 5.1** and
**LuaJIT 2.1**. The large `SCR_TEXT` switch is partitioned by whole cases to avoid
LuaJIT's short-jump limit while preserving return, break and fall-through.

Generated files and build artifacts are ignored by Git. Edit the source,
converter, or runtime, not generated files. Packaging uses an explicit file list:
no `.git`, credentials, local saves, SDKs, Python packages, or GameMaker XML are
included. ZIP timestamps and permissions are normalized and a SHA-256 is emitted.

## Source repairs (export only)

The original GameMaker files have not been changed.

- The supplied decompiler bound switch labels in reverse to their branch bodies.
  `tools/source_repairs.py` repairs nine verified script tables, with exact source
  SHA-256 guards. `SCR_TEXT` keeps its terminal case 0 debug branch in place;
  the other 472 labels are reassigned to the ascending original IDs. For example,
  200 selects Flowey's greeting, 666 the SOUL tutorial, and 706 Undyne's chair
  question. Tests check the words, not merely the presence of drawn text.
- Verified inventory/phone/encounter/Papyrus-call tables receive the same scoped
  repair, preserving their bodies and fall-through. This is not a general GML
  rule or an unchecked rewrite of arbitrary switches.
- Malformed decimal-comma shake values in `SCR_TEXTTYPE` and `_f` are repaired so
  the ten text-setup arguments do not shift into sound/spacing fields.

- Editor instance IDs give relative room order, **not contiguous original IDs**.
  Version 0.1.0 incorrectly compacted missing room slot **159**; all later numeric
  room references were shifted. The exporter now preserves that hole and checks
  independent elevator/battle/game-over anchors in `resource_overrides.json`.
  Thus normal battle is 306, Flowey is 307, and game-over is 310. Adjacency does not
  silently skip the missing Hotland room (`room_fire_walkandbranch`).
- Original asset IDs are recovered from numeric decompiler annotations and
  adjacent `// object_name` / `with(id)` comments.
- Music IDs are recovered from `scr_getmusindex` and explicit, documented
  exceptions. `port/resource_overrides.json` records additional reconstructed
  font, interaction-parent, default-dialogue and menu IDs. Font anchors now include
  Wingdings=0, main=1, damage=6, HUD/Courier=7, Comic Sans=8 and Papyrus=9, matching
  the Gaster/Sans/Papyrus typer and glyph-spacing call sites. These inferences need
  reference validation; annotations and overrides are distinguished in the report.
- Glyph labels such as `320, 321, ... 3210` are the malformed concatenation of
  `"32"` and an index. When the entire atlas matches that pattern, the export uses
  **32 + index**, preserving the atlas pixels and glyph positions.
- Exact malformed backslash comparisons in the three dialogue writer objects
  become `chr(92)`. Only these known source tokens are repaired; five event units
  contain the affected comparisons.
- The absent `testlines.txt` *debug override* in `SCR_TEXT` case 0 is guarded with
  `file_exists`; inline story/dialogue supplied by callers is retained.
- `abc_123_a` metadata names an absent MP3, but the actual sound is an OGG. The
  exporter records and uses the unique existing file with the same basename.
- GMX boolean metadata (`-1` for true) is normalized separately from GML numeric
  truth testing. The original project disables uninitialized-variable errors;
  uninitialized GML fields therefore retain its zero-default behavior.

## Runtime design

- Explicit GML scopes keep instance fields, `global`, `self`, `other`, locals and
  script arguments separate. `with` iterates a snapshot, including descendants.
- Create/Destroy, Begin/Normal/End Step, alarms, keyboard and mouse events,
  inherited events, room events and animation-end events are dispatched.
- Fixed game ticks respect `room_speed`. **Draw executes once per game tick**,
  not once per monitor refresh: much of this game updates menus/dialogue in Draw.
- Rendering uses a cached, nearest-filtered canvas, sprite origins/transforms,
  bitmap glyphs, tile depths, backgrounds and viewports. UI draws afterward in
  device coordinates and cannot alter the game's virtual coordinates.
- Collision queries use a bounding-box broad phase and transformed mask tests.
  Exact parity, especially the collision-event response/order, remains unverified.
- Audio resource IDs and playback handles are separate, with gain/pitch,
  looping, pause, seek and fades. Music streams; short effects are cached/cloned.
- Static image, mask, quad and sound-template caches are released on room changes
  and low-memory notifications. Runtime-generated sprites are retained as needed.
- INI/text saves live in LÖVE's application save directory, not the repository or
  the original desktop game's save folder. Writes replace saves atomically;
  absolute paths and traversal are rejected. Saves are never evaluated as Lua.

## Finishing the port

1. Recover the original path points/speeds/closed/smooth settings and referenced
   external files from an export you are authorized to use.
2. Recover the complete original asset index tables, resolving reported IDs rather
   than guessing from alphabetical order. The manifest includes evidence per ID.
3. Implement path playback and remaining flagged behavior, adding regression tests
   with actual cutscene/battle fixtures.
4. Run the native LÖVE and Android device checklist in `VALIDATION.md`, including
   every route/boss/save/ending. Fix behavior against reference recordings.
5. Only then remove the experimental designation and prepare release signing,
   current Android SDK/NDK/page-size compatibility, icons and distribution rights.

## Reference-guided opening backdrops (v0.1.2)

The supplied `room_area1` has eight disabled background layers and 20 tile records;
only the flowerbed-related records fall inside its initial camera view. The next
room has no tile records. The user's reference screenshots establish the missing
chamber/platform and light rings, and the corridor's arched doorway.

`port/opening_backdrops.lua` reconstructs these two opening backdrops using those
references, the existing collision/door coordinates and the exact supplied palette
(floor 58/57/72, rings 95/94/119 and 200/194/226, green 34/177/76). The original flower
tiles and gameplay collision remain untouched. The doorway ornament is reconstructed
line art, not a claimed pixel-identical recovery of an absent source image. The
second chamber follows its supplied stepped collision boundaries.

The report explicitly lists `reconstructed_backdrops`. The exporter refuses to
apply this reconstruction if these rooms gain background layers or a different
layout, so a future complete export will not silently be painted over. Other rooms
retain their own original tiles/backgrounds. Full-game scenery fidelity is still
not certified. Android's recent-app thumbnail is also scaled, rotated and dimmed;
judge the new rendering inside the running app.
