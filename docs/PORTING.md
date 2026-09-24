# Port status and implementation

> **Debug & repair work is recorded in this file too.** The owner's reported bugs on
> the Undertale Yellow side and at the world crossing (wrong font, vertical text,
> heavy lag, a duplicated Player at the River Person, the wrong boat destination) are
> being fixed piece by piece against the binding [`DEBUG_SPEC.md`](DEBUG_SPEC.md); the
> live order and progress are in [`DEBUG_QUEUE.md`](DEBUG_QUEUE.md). Each finished
> piece adds a **"Debug fixes"** entry (root cause, change, evidence, scope), the way
> the fusion pieces each added their own section in this file.

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


1. **All 38 referenced movement paths were absent from this export; their point data is
   now recovered, not reconstructed.** The GMX project's `paths` section is empty, so
   `port/path_data.json` carries the coordinates pinned to one upstream GameMaker
   project commit, and `port/runtime.lua` plays them back at GameMaker's
   pixels-per-step speed. A path without a recovered record still stops with its name
   instead of fabricating movement. Provenance, the coordinate-semantics evidence and
   the open questions are in [PATHS.md](PATHS.md); device and route validation is not
   finished.
2. **Original numeric resource IDs were lost in the alphabetized export.** The
   converter recovers annotations, `with` comments, room instance order and music
   aliases. Unidentified *named* assets receive synthetic IDs outside the legacy
   range; it never assigns an arbitrary alphabetic asset to a numeric reference.
   The report currently lists **86 unresolved IDs in statically recognizable
   reference positions**. Since v0.1.6 the pinned `kittibyte/UndertaleDecomp`
   registry dump is **audit/conflict-only**: it numbers resources in its own ID
   space, which is incompatible with this export, so no numeric ID is imported
   from it and `registry_import` is recorded as voided. v0.1.6 voided that import
   after it assigned unrelated sprites to Toriel's dialogue faces; the 13 verified
   face IDs are restored by hand in `port/resource_overrides.json` instead. The
   dump's 1,535 disagreeing rows are retained in `registry_conflicts` as
   evidence; they are not silently assigned. This is not an exhaustive dynamic
   data-flow analysis.
   One class the static audit cannot see — monster events that spawn battle
   artwork through variables holding bare original IDs (`part2= 255; mypart2=
   instance_create(x, y, part2)`) — is now recovered instead of left synthetic:
   every such battle used to stop with `instance_create Missing original object
   ID`, which is what broke all part-based Snowdin encounters. `tools/recover_parts.py`
   pairs each of this checkout's literals with the object name the pinned
   upstream decompilation uses for the same statement, after checking both events
   assign the same part variables in the same order; per-site provenance and the
   38 already-annotated sites it re-validates as anchors are in
   `port/recovered_parts.json` (see `tests/test_monster_parts.py`).
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
   warns and uses its first corner color. Path playback is implemented for the
   38 recovered paths (docs/PATHS.md); frame-level parity with the original
   engine's stepping is not yet certified.
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

## Undertale Yellow merge (all five pieces)

A second GameMaker project is merged in: **Undertale Yellow v1.2.1**, a
GameMaker **Studio 2 (2023.4.0.84)** decompilation fetched from one pinned commit
(`port/yellow_source.json`) into the git-ignored `yellow_src/`. Piece list,
architecture and the recorded deviations live in [YELLOW.md](YELLOW.md). The
fused build ships as `love-v1.2.0-fusion-experimental`.

What the merge adds to the pipeline, and what it deliberately does not claim:

| resource | Yellow count | treatment in the merged build |
|---|---:|---|
| Sprites | 3,799 IDs / 3,796 converted | Frame PNGs, origins, masks and animation metadata as GameMaker 1.4 records; 3 pinned IDs have no folder upstream and are listed, not substituted. Yellow's 28 player walk-cycle poses draw Frisk at render time (mechanics stay Clover's records) |
| Sounds | 673 | Original audio files, volumes, durations |
| Fonts | 11 | Bitmap atlases and every glyph, including the default-character glyph 9647 |
| Tilesets | 112 | Texture page as a background plus the tile grid (`tile_width`, `out_columns`, `tile_count`, animation frames) |
| Objects | 3,224 | Metadata, parents, masks and all 8,494 events, with collision targets renumbered to merged IDs. Studio 2 has no object depth (room layers supply it) and 10 physics objects stop with their own name |
| Rooms / paths | 287 / 68 | All converted: instances, creation code, tile layers with mirror/flip/rotate transforms, backgrounds, views, and the one animated tileset; 40 named room-feature stops (layer effects, physics worlds) stay blocked rather than rendered without equivalents |
| Scripts | 1,155 | All resources converted; calls remain name-resolved and the 22 GMLive resources convert literally (the shipped build's GMLive is inert) with one explicit stop |
| Shaders / sequences | 26 / 35 | No GameMaker 1.4 equivalent; enumerated for a visible stop, never substituted |

Yellow's numeric IDs are recovered from two independent records inside the pinned
source — `Undertale_Yellow.yyp`'s resource order and the decompiler's
`notes/Asset_Order/Asset_Order.txt` — and the converter refuses to run if they
disagree. Merged IDs are `1000000 + the Yellow ID`, so Undertale's recovered IDs
(which reach 22,471) are untouched. Output goes to `generated/yellow/` with its
own `conversion-report.json`.

Piece 2 also adds `tools/gml2.py`, which adapts named GMS2 functions, enums, default
parameters, array literals and loop declarations to the existing strict compiler;
`port/yellow_builtins.lua` handles the GMS2 array/type/string/math/asset aliases and
leaves unsupported Studio facilities as named `Runtime:unsupported` stops. The
script manifest uses names rather than inventing a numeric GMS2 script index, and
keeps Yellow names under `yellow_names` so a collision cannot rebind an Undertale
name.

`port/yellow_studio.lua` implements the Studio 2 facilities Yellow's converted code
calls for real: `ds_list`/`ds_map`/`ds_grid`, GPU blend modes, primitives and the
extra drawing calls, cameras and viewports (GameMaker gives every viewport a
camera, which is how Yellow's 1.4 compatibility shim reads `view_xview`), and a
gamepad family that reports "not connected" because this port feeds touch and
keyboard through the same key events. `port/yellow_layers.lua` implements the
`layer_*` families and the element model rooms are built from.

Two deviations are reported on every run rather than hidden: texture groups do not
exist here (assets are single files loaded on demand, and the pinned
decompilation carries no tag records), and Yellow's 17 shaders are not converted,
so a shader that would be set is reported and skipped and the scene keeps its
original colours.

A merged build adds `port/merge.lua`, which builds one manifest out of both
conversions and checks the ID bands instead of assuming them, and `port/travel.lua`,
which connects Undertale's River Person boat and Yellow's UGPS mail whale,
initialises each world with its own scripts, and (since piece 5d) writes one
`merge.sav` Player+World document beside the `file0` / `Save.sav` projections
each continue menu still reads.
`port/frisk.lua` draws Yellow's player as Frisk (pixels only; run poses, gun
poses, goggles, the dance and lying poses stay Clover and are reported). The
native LÖVE/xvfb gate plays the Undertale opening and then crosses into Yellow
and back: one player per world, Frisk drawn in `rm_hotland_02`, and both
crossings recorded in `merge.sav`. See `docs/YELLOW.md`.

Piece 3 adds `tools/yellow/objects.py`, which writes each Yellow object in the same
module shape `tools/convert.py` uses for Undertale (metadata plus
`object.events["kind:number"]`), and `compile_gml2_event`, which compiles an event
body and binds an event's own local functions into that event's scope instead of the
shared script namespace. The runtime grew the dispatches those events need — Clean
Up, Draw Begin/End, Draw GUI Begin/GUI/GUI End, Pre/Post-Draw and per-instance
mouse events — each unused by every Undertale object. Rooms still require piece 4.

## Reproducible pipeline

```text
projectA.project.gmx + GMX/GML files       yellow_src/ + GMS2/GML files
              |                                      |
      tools/convert.py                    tools/yellow_convert.py
      tools/gml.py (lexer, Pratt parser,   tools/gml2.py + tools/gml.py
      Lua emitter)                         (GMS2 adapter + shared emitter)
              |                                      |
          generated/                         generated/yellow/
              |                                      |
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

## Merged archive must ship the item catalog (v1.2.5)

v1.2.4's download stopped on boot with `module 'generated.merged.items' not
found`. `tools/merge.py` writes that module next to
`generated/merged/manifest.lua`, and `port/inventory.lua` loads it whenever
`manifest.game == "merged"`. `tools/package.py` listed only the manifest. The
native gate stayed green because `require` searches `./` after the archive, and
CI's working directory contained the file `merge.py` had just written. A
downloaded `.love` has no such neighbour.

`merged_files()` now refuses to package unless both modules exist and returns
both, plus any later `generated/merged/*.lua`. The zip is checked for those two
names before it replaces the output. `Inventory.loadCatalog` loads through
`love.filesystem` when LÖVE is present, so a cwd copy cannot satisfy a packaged
launch. `tools/native_smoke.sh` rejects a merged archive that lacks the catalog
before launching LÖVE. Headless tests still `require` the generated file; they
have no `love.filesystem`.

Evidence: `tests/test_packaging.py::test_merged_package_ships_the_item_catalog_and_stops_without_it`
fails if the file list drops the catalog; `tests/test_unified_inventory.py::test_catalog_load_uses_the_archive_and_ignores_a_cwd_copy`
fails if a cwd copy can satisfy a LÖVE load. Not claimed: that v1.2.4's
already-published archive was rewritten (published assets stay immutable),
Android behaviour, or any change to item rules.

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
- The export negated `obj_dialoguer`'s `obj_face` cleanup guards (its Destroy
  event and the no-face branch of its Step event). The shipped game destroys the
  dialogue face portraits when the dialoguer ends; with the guard negated they
  leak, so Flowey's portrait followed the player out of the tutorial battle,
  stacked on top of Toriel's, and the leftover Toriel face then blocked
  `obj_floweytrigger`'s `!instance_exists(obj_torface)` check forever — the
  sprite-glitch softlock at the end of Flowey's fight. Both guards are restored,
  verified against the shipped game's decompilation and hash-guarded per event.

- Editor instance IDs give relative room order, **not contiguous original IDs**.
  Version 0.1.0 incorrectly compacted missing room slot **159**; all later numeric
  room references were shifted. The exporter now preserves that hole and checks
  independent elevator/battle/game-over anchors in `resource_overrides.json`.
  Thus normal battle is 306, Flowey is 307, and game-over is 310. Adjacency does not
  silently skip the missing Hotland room (`room_fire_walkandbranch`).
- Original asset IDs are recovered from numeric decompiler annotations and
  adjacent `// object_name` / `with(id)` comments.
- Monster body-part spawns are recovered from variable-mediated references:
  the decompiled events hold bare literals in `partN` variables that no
  annotation covers, so `tools/recover_parts.py` pairs each literal with the
  object name the pinned upstream decompilation uses for the same statement
  (structural agreement required, no number taken from the dump) and the
  converter imports the result from `port/recovered_parts.json`. All 59 part
  spawn sites now resolve; the 22 previously-unresolved IDs cover every
  part-based battle from Snowdin through the True Lab (Doggo, Dogamy &
  Dogaressa, Greater Dog, Gyftrot, Glyde, Papyrus, Snowdrake, Shyren, Undyne,
  Mettaton EX/NEO, So Sorry, the amalgamates and their True Lab mimics).
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
- Create/Destroy, Begin/Normal/End Step, alarms, keyboard and mouse events
  (global and per-instance), inherited events, room events, animation-end, Clean
  Up and the Draw Begin/Draw/Draw End, Draw GUI and Pre/Post-Draw passes are
  dispatched. `tests/test_yellow_objects.py` drives one probe object through every
  one of them, so the dispatch list is checked rather than claimed.
- Fixed game ticks respect `room_speed`. **Draw executes once per game tick**,
  not once per monitor refresh: much of this game updates menus/dialogue in Draw.
- Rendering uses a cached, nearest-filtered canvas, sprite origins/transforms,
  bitmap glyphs, tile depths, backgrounds and viewports. UI draws afterward in
  device coordinates and cannot alter the game's virtual coordinates.
- GameMaker's particle system (systems, types, emitters, direct creation) runs
  in `port/particles.lua`: systems tick once per game step, after End Step, and
  draw at their own depth among the instances and tiles. Undertale never calls
  it, so the family is inert outside Yellow.
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

1. Recover the remaining referenced external files from an export you are
   authorized to use. Path points are already recovered with pinned provenance
   (docs/PATHS.md); speed/closed/smooth parity still needs reference validation.
2. Recover the complete original asset index tables, resolving reported IDs rather
   than guessing from alphabetical order. The manifest includes evidence per ID.
3. Certify path playback against reference runs on every route/boss, and add
   regression fixtures for the remaining flagged behavior (collision ordering,
   persistence, camera, gradient text, advanced battles).
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

## Snowdin Inn HP rule (v1.2.2)

Owner-requested gameplay deviation, not a general runtime or decompiler repair:
`obj_townnpc_innlady`'s Begin Step wake-up branch (`conversation == 6`) now sets
`global.hp = max(global.hp, global.maxhp + 10)`. The checked-in source previously
healed to maxhp, then mapped HP 20/24/28/32/36 to 30/32/34/36/38; that gave smaller
bonuses at LV 2–5 and none at higher levels. The new rule uses the actual maximum
from `scr_levelup`, including LV 20's 99 HP, without changing `maxhp`, LV or EXP.
Damage can consume the excess normally; staying again refreshes rather than
stacks the bonus, and HP already above the target is not reduced. No other
healing, save-point or combat behavior is changed.

`tests/test_snowdin_inn.py` exercises all 20 levels at five initial HP values
through the real room, wake-up alarm and converted Begin Step event. It also
checks repeat stays, leveling between stays, no healing before the alarm or on
an ordinary visit, and no continuous regeneration after waking.

## Sprite crop offsets (fusion requirement 12, first piece)

This checkout's sprite PNGs are **cropped to their collision bbox** while the events
that draw them keep using the original canvas: `spr_shopkeeper1`'s image is 61×111
inside a 64×120 frame whose origin is the canvas origin. Drawing the exported pixels
with the canvas origin therefore shifted every such sprite up/left by the crop — the
Snowdin shopkeeper's face landed 9 rows above the eyes and mouth overlays, which is
the owner-reported "four eyes, floating mouth", and the River Person's boat cover
floated off the waterline.

`tools/recover_sprite_offsets.py` recovers the missing canvas offset per sprite from
one pinned upstream record — `sprites/<name>/<name>.yy` frame metadata in
`kittibyte/UndertaleDecomp` at `249ffa27ee7e7eee0d7ce84b736c294458b38685`, the same
dump docs/PATHS.md uses. **Offsets only; no artwork is imported.** A sprite is
accepted only when all of these hold:

1. the local `<sprite>.sprite.gmx` bbox equals the upstream frame bbox,
2. both disagreeing canvas edges imply the same offset (`bbox_left - art_left` and
   `bbox_top - art_top` agree with the canvas size),
3. the canvas contains the exported image, and
4. the offset is non-zero.

There is one **anchored** extension (added for the River Person's dog boat,
piece 3): when the export's crop keeps the art pinned to its top-left corner,
spans the crop's full width, and the crop spans the bbox width exactly, both
horizontal edges agree *without* upstream metadata, so
`offset = (bbox_left, bbox_top)` follows from the local export alone. The
vertical component additionally uses the no-trim invariant — the export never
trims transparent rows *above* the art, which holds for every one of the
upstream-verified records — so the crop top equals the bbox top. Because no
upstream bbox is available to check against, the anchored path accepts only
when a canvas can be pinned from records already verified upstream in this
same file and sharing the sprite's draw call site
(`CANVAS_CORROBORATION` in the tool; currently just the boat's own siblings
`spr_regboat`/`spr_dogboat_cover`). The record carries
`canvas_source: "sibling-pinned"` and `up_bbox: null` so its provenance stays
auditable, and `--check` re-verifies it offline (re-derivation plus the
sibling gate).

**448 of the 1,428 candidates verify; the other 980 are listed in
`port/sprite_offsets.json` `unresolved[]` with one of four reasons**
(two-sided-disagreement 972, bbox-differs-from-upstream 6, canvas-too-small 1,
not-in-upstream 1). They are drawn unshifted rather than guessed at, and
`tests/test_sprite_offsets.py` fails if a regenerated file drops one without a
reason. Accepted examples: `spr_shopkeeper1` (1,9) 64×120→61×111,
`spr_dogboat` (3,3) 91×40→85×31 (anchored — the upstream vertical edges
disagree, 3 vs 8, because the export trimmed transparent rows below the hull
art), `spr_dogboat_cover` (7,25) 91×40→78×15, `spr_riverman` (1,0) 29×42→27×42,
`spr_maincharad` 20×30→19×29; `spr_shopkeeper1_face0..6`, the eyes/mouth
overlays, `spr_heart` and `spr_shop1_bg` are already full-canvas and stay at
(0,0).

Pipeline: `convert.py` refuses to run without the file and carries `ox`/`oy` into
`generated/assets/sprites_N.lua`; `port/graphics.lua` subtracts them from the origin
in both the whole-image and `draw_sprite_part` paths (the crop rect too) and appends
them to the draw log, so a probe can replay the shifted draw. `tools/pngalpha.py` is
a stdlib-only PNG reader used to measure the exported alpha bounds without Pillow;
it was validated against Pillow on 25 sprites with 0 mismatches.

Regenerate with `python3 tools/recover_sprite_offsets.py --cache <upstream metadata>`
(offline `--check` re-derives every row from the local tree alone; the recovery
tools fetch nothing at test time).

Recorded limitations for this piece (the size half is **superseded** by
"Sprite canvas and size compatibility" below — piece 6a, which pins 553 more
canvases and points every size read at the canvas):

- the candidates no route can shift are still drawn with their exported origin, so
  a cropped one keeps a cosmetic offset. They are now named individually under
  `canvas` with the axis that is unproven (553 of them) instead of all 980 being
  listed as unresolved — the reason they are not nudged is unchanged;
- `sprite_get_width`/`sprite_get_height` reported the **exported** image
  dimensions, not the original canvas (95 call sites). Piece 6a replaces this with
  one accessor that answers in canvas pixels for both games;
- this is the asset-compatibility half of spec requirement 12 (origins, sheet
  coordinates, render anchors). Per-frame origins, movement speed, collision boxes
  and Yellow's GMS2 sprites are separate pieces and are not claimed here.
  Y-sorting from the sprite's visual bottom point was a separate piece too and is
  now claimed by "Depth / Y-sort" below.

## Instance-array asset IDs (spec §7, §12 — second piece)

The crop-offset recovery above fixed where the shopkeeper's sprites *land*; this
piece fixes that the emotion faces *draw at all*. The Snowdin shopkeeper keeps its
seven emotion faces inside an instance array and selects them by a computed index:

    facespr[1]= 881;                              # obj_shopmouth1 / obj_shop1 Create
    ...
    draw_sprite(facespr[global.faceemotion], ...) # obj_shopmouth1 Draw

No decompiler annotation covers a bare literal stored in an array, so the converter
left the seven `spr_shopkeeper1_face*` sprites on synthetic IDs and every emotional
line stopped with `Unresolved sprite ID 881` — the face never drew, leaving the mouth
floating over the default two-eye frame. The same class hides five sibling sites:
`obj_shop1`'s own (unreferenced) `facespr`, the Asgore body's eight `part` sprites
(`draw_sprite_ext(part[i], ...)`), and three `background_index` slots
(`obj_backgrounder_core` / `obj_backgrounder_tundra` / `obj_gameshake`) that the GM1.4
decompile spells `background_index[i]= <id>;` while the GMS2 dump spells
`background_index_set(i, <bg>)`.

`tools/recover_asset_arrays.py` pairs each local literal with the asset name the
pinned upstream decompilation (`kittibyte/UndertaleDecomp` at
`249ffa27ee7e7eee0d7ce84b736c294458b38685`, the same ref as every other recovery)
uses for the same statement — same variable, same subscript, same block. **IDs come
only from this checkout's own literals; the dump contributes names, never numbers.**
All 18 IDs (7 shopkeeper faces, 8 Asgore body parts, 3 backgrounds) across 32
statement sites verify; `port/recovered_asset_arrays.json` records the local
file+event+subscript and the upstream file+statement for every pair, and
`tools/recover_asset_arrays.py --check` re-derives the sweep from the local tree
alone (no network).

Pipeline: `convert.py` imports the file in `recover_ids` (raising on a category or ID
conflict) and registers the references so a dropped site shows up in
`unresolved_numeric_references`. `tests/test_asset_arrays.py` pins the fix: the
manifest maps each name to its original ID, each recovered ID indexes a real asset
record, and in room 311 the shopkeeper's emotion faces for `faceemotion` 1-6 draw —
which fails (and logs `Unresolved sprite ID 881`…`877`) without the converter import.

Recorded limitations for this piece:

- the **scalar** form of the same bug is out of scope: `obj_torielbody` assigns
  `facespr= 2285;` (a plain variable, not an array) to nine Toriel faces
  (`2282`-`2290`) that no annotation covers and which this sweep deliberately does
  not touch; they remain `Unresolved sprite ID` stops;
- this is the *frame-selection* half of spec §7. The crop-offset piece owns the
  *position*; together they make the shopkeeper render as intended, and
  `tests/test_sprite_offsets.py` + `tests/test_asset_arrays.py` cover the two halves.

## Depth / Y-sort (spec §4, §5 — unified-fusion piece 2)

Both worlds Y-sort and both were broken, each in its own way:

- **Undertale** sorts its overworld through `scr_depth`
  (`depth = 50000 - y*10 + sprite_height*10`, called every step by 181 objects
  including the player), but `sprite_height` read the *exported* (cropped)
  image size while the game's arithmetic assumes the original canvas. Two
  actors whose crops differ could draw in the wrong relative order.
- **Yellow** sorts by assigning `depth = -y` every step (the player, every NPC
  on `obj_npc_base`, every actor with `npc_dynamic_depth`), but the renderer
  drew each room-placed (layered) instance at its *authored layer* depth and
  ignored the assignment, so same-layer actors drew in creation order. In
  Dalv's room the chest (y=148) drew behind the player (y=140).

The fix keeps each world's own `scr_depth` routing (each world still calls its
own copy, as the shared-script split established) and repairs the two systems:

1. Recovered sprites carry their pinned canvas size (`cw`/`ch` from the same
   `port/sprite_offsets.json` record that owns `ox`/`oy`; `convert.py` refuses
   a record without one). The `sprite_width`/`sprite_height` instance reads
   use it; sprites without a verified canvas (the 980 unresolved, e.g. Frisk's
   own walk set) keep reporting their exported size — never a guess.
2. Assigning `depth` to a layered instance moves it onto a managed
   `Compatibility_Instances_Depth_N` layer at that depth — one layer per depth
   value, reused across steps — which is what GameMaker Studio 2 itself does
   with runtime depth assignment. Managed actors detach from their authored
   layer (visibility, destroy, `layer_depth` no longer follow it); `layer_depth`
   mirrors the new depth onto the members that stay. `instance_create` and
   `instance_create_depth` paths are unchanged.
3. Depth ties across layers resolve by the room's own layer-list slot (the
   layer nearer the front of the list draws later), with a managed actor
   comparing by its home slot. Unlayered GameMaker 1.4 entries keep creation
   order. The draw list is therefore deterministic frame to frame: no flicker
   or popping between layers.

Evidence: `tests/test_depth_sort.py` (11 tests — every behaviour test fails
without the change, verified by stash). Live pins: the Waterfall statue
(`spr_statue`, 59px exported / 80px canvas) sorts from 80 in
`room_water_statue`, and `rm_dalvsroom` draws diary → player → chest →
gramophone, behind to front. Per-world `scr_depth` routing is still pinned by
`tests/test_yellow_merge.py::test_shared_script_names_resolve_to_each_worlds_own_copy`.

Recorded limitations for this piece (updated by piece 6a, which landed the
builtins and pinned 553 more canvases):

- `sprite_get_width`/`sprite_get_height` now report the same canvas the instance
  reads do, through `port/assetcompat.lua`: the two no longer disagree, and both
  answer in original-canvas pixels for the 1,367 candidates whose canvas is
  pinned;
- the 61 candidates with no pinned canvas sort from their exported dims, for the
  same no-guessing rule (the 553 canvas-only ones now sort from their canvas);
- the cross-layer tie rule (room list order) is best-available: GameMaker
  Studio 2 draws by depth and its exact-tie order is undocumented. Distinct
  depths — the common case — never reach the tie-break.
## River Person's boat and water (spec §6 — unified-fusion piece 3)

Spec §6 asks for the River Person's boat and water to render as separate visual
components with the original layering — not a blanket global render layer. The
merged build already carried the original layering (authored room depths 49330
hull / 49320 riverman in the water and fire docks, 950000 boat in the tundra
dock, 900000 during the ride, the water pillar at −1 in front of everything —
and the player, which no room authors, at `scr_depth`'s key: 49310 in the dock
at y=100 once piece 6a pinned the 30px canvas its cropped export read as 29);
this piece pins that reference from the draw log and repairs the two pixel
defects inside it:

1. **The dog boat hull floated above its waterline.** `spr_dogboat` was the one
   boat sprite whose crop offset never recovered: the upstream vertical edges
   disagree (3 vs 8) because the export trimmed transparent rows *below* the
   hull art, so the original rule's two-sided gate rejected it and the 85×31
   hull drew at (0,0) — 3 px up and left of its canvas place, paws dangling off
   the boat rim its waterline cover (7,25) sits on. The anchored recovery path
   (above) pins (3,3) with the 91×40 canvas corroborated by the sibling hull
   and cover, which are upstream-verified and share the draw call. The
   constrained `spr_dogboat` (84×34 second frame) still fits that canvas at
   (3,3), which the record's frame list pins.
2. **The waterline ripple snapped to hard steps.** The boat's draw event
   animates the cover with a fractional sub-index (`cc += 0.1` per draw,
   `draw_sprite(1529, cc, x, y)`), and GameMaker interpolates the fraction
   between the two frames; `port/graphics.lua` floored it, stepping the 2-frame
   ripple in discrete jumps. `sprite()` now draws the base frame, then the next
   frame at the fractional amount (a crossfade; GM's per-pixel lerp differs
   only where the frames differ in transparency at their edges). Integer
   sub-indices log and draw exactly as before; the draw log appends the blend
   frame and amount (fields 13/14) so the semantics are pinned.

Evidence: `tests/test_boat_water.py` (10 tests). The offset test fails without
the anchored record (the hull logs (0,0)), the ripple test fails without the
crossfade (no blend fields), and the layering tests pin the original reference:
water behind the boat → hull → cover → riverman → player in rooms 125/140/70,
the regulated boat (flag 461 = 0) sharing the same layering, the original
room-data depths, and the ride in room 316 (340 → 330 at 2 px/tick → 118, depth
900000, water pillar in front). `tests/test_sprite_offsets.py` gains the
(3,3) pin plus the anchored-provenance test, and the full suite is 474 passed,
1 skipped.

Recorded limitations for this piece:

- the layering is pinned from the headless draw log against the decompiled
  room data; parity with the original game's *pixels* is a CI-only visual
  claim (the native smoke crosses the fire dock and plays the ride) and is not
  claimed here;
- the crossfade is a compositing crossfade (base frame, then next frame at the
  fractional amount), not GM's exact per-pixel lerp: where the two frames
  differ in transparency at their edges the result can differ by a fraction of
  a pixel's alpha;
- the anchored path currently corroborates one sprite (the dog boat hull), and
  the candidates the anchored geometry alone cannot gate are listed by name
  rather than nudged: piece 6a pins their canvases from the pinned upstream
  metadata (553 of them) and leaves the unprovable axes unproven, so their drawn
  position is unchanged until a route proves it;
- the boat's depth is event-assigned in every state (the original room data
  carries no instance depth), so the recovered 91×40 canvas cannot move it;
  the sprite's own draw uses the canvas origin, not `scr_depth`.

## No duplicated characters or sprite layers (spec §8 — unified-fusion piece 4)

Spec §8 asks for one authoritative entity and one visual representation per
character — never an Undertale copy and a Yellow copy of the same thing on screen
at once — and it asks for the audit to start from the merged name tables rather
than a hand-written list. Two things were wrong, one per half of that.

**1. The base sprite was drawn twice.** In Yellow's Snowdin the player's body was
issued twice in the same frame. The room carries a separate `obj_shadow_drawer`
instance whose Draw event (`generated/yellow/objects/obj_shadow_drawer.lua`,
event `8:0`) opens a `with (shadow_actor)` scope over the player and draws it
there — the player itself is `visible` 0 and never enters the normal draw loop.
Inside that scope three draws happen in a row: line 137 `draw_self()` paints the
actor with the original palette; line 139 `scr_draw_palette_shader(palette_index)`
paints **the same actor again** under `sh_palette_swap`
(`generated/yellow/scripts/scr_draw_palette_shader.lua:12` is
`shader_set(sh_palette_swap) → draw_self() → shader_reset()`, gated on the actor's
own `shader_on`); line 141 `draw_sprite_ext(…, c_black, other.draw_alpha*image_alpha)`
adds the shadow overlay as a separate layer (in this room at alpha 0, i.e.
invisible). This port reports shaders as unconverted and keeps the original
colours (`port/yellow_studio.lua`), so the "recoloured" pass paints the same
pixels of the same frame at the same position, scale, angle, tint and alpha — a
pixel-identical second draw, which is exactly §8's "do not draw the base sprite
twice".

The draw log proved it before the fix: two identical actor entries per frame, the
first from `obj_shadow_drawer.lua:137` with no shader active, the second from
`scr_draw_palette_shader.lua:12` with `R.shaderState.active` set and the actor's
`shader_on` = 1 (probes `probe_frame.py`, `probe_trace.py`, `probe_shader_state.py`;
the whole event dispatches once, so this is one event drawing one character
twice, not two entities). `port/graphics.lua` now drops that repeat: while an
unconverted shader is active, a draw whose sprite, frame, fraction, position,
scale, angle, tint, alpha, owning instance *and* blend state all equal the
previous draw's is not issued, is counted in `R.shaderRedraws`, logged as
`sprite-suppressed` and reported once as `shader-redraw`. Everything else still
draws — a draw under a shader that is not a repeat, and a repeat whose blend
state changed (the same pixels added on top of themselves are how the original
asks for a glow) — so nothing disappears from a scene, and the shadow overlay
beside the body keeps its own tint and is untouched.

**2. The 42 names both games use resolved to one game's asset for every caller.**
At the pinned revisions the two games name 42 assets the same way while shipping
different files. Undertale's flat name map is the merged `names`/`constants`
table, so before this piece *every* caller — Yellow's own scripts included — got
**Undertale's** Flowey sprite, `obj_floweytrigger`, `mus_shop`, `fnt_main`, …:

| category | names | examples |
| --- | --- | --- |
| sprites (10) | `spr_dustcloud`, `spr_fakewaterl`, `spr_fakewateropenl`, `spr_fakewateropenm`, `spr_fakewaterr`, `spr_flowey`, `spr_fridge`, `spr_quittingmessage`, `spr_switch`, `spr_waterice` | `spr_flowey` = UT 1095 / Yellow 1000243 |
| objects (10) | `obj_alphys_npc`, `obj_chairiel`, `obj_fakewater`, `obj_fakewaterl`, `obj_fakewaterm`, `obj_fakewateropenl`, `obj_fakewateropenm`, `obj_floweytrigger`, `obj_interactable`, `obj_solidparent` | `obj_floweytrigger` = UT 20598 / Yellow 1001312 |
| sounds (21) | `mus_barrier`, `mus_birdnoise`, `mus_cymbal`, `mus_elevator`, `mus_f_laugh`, `mus_f_newlaugh`, `mus_intronoise`, `mus_shop`, `mus_vsasgore`, `mus_wind`, `snd_ehurt1`, `snd_fall2`, `snd_heavydamage`, `snd_hurtbeef`, `snd_hurtbig`, `snd_hurtbuzz`, `snd_hurtdragon`, `snd_hurtloox`, `snd_hurtsmall`, `snd_screenshake`, `snd_splash` | `mus_shop` = UT 239 / Yellow 1000126 |
| fonts (1) | `fnt_main` | UT 1 / Yellow 1000009 |

`port/merge.lua` now builds that list from the two manifests themselves
(`manifest.double_named`, one `{name, category, undertale, yellow}` per pair; a
new shared name appears by itself) and feeds it into
`name_collisions_with_undertale`. `Runtime:assetName(name, E)` resolves a shared
name by the caller's world — Yellow's own asset for a Yellow caller, Undertale's
for everyone else — and `Runtime:assetOwnerIsYellow(E)` decides that from the
*calling instance's own ID band*, falling back to the room band only for a caller
with no instance (a global script or a room's creation code). An asset belongs to
the content its caller came from, not to the room it is standing in: an Undertale
character carried into Yellow keeps Undertale's Flowey. The scope read (`E["name"]`
inside generated code) and `asset_get_index` both go through it, and
`Runtime:reportNameSplit` warns once per shared name, naming both IDs.

`tools/merge.py` also printed the collision count as `len()` of the report's
per-category mapping (4 — the number of categories); it now sums the entries
(`assets both games name: 42 (fonts 1, objects 10, sounds 21, sprites 10)`).

**What can actually reach a colliding name.** The audit was checked against the
converted code, not assumed: no generated Undertale file calls `asset_get_index`
at all and none of the 32 shared sprite/sound/font names appears in it as a
string — Undertale's conversion resolves assets numerically, so the split cannot
change Undertale. The 10 shared *object* names do appear in Undertale's code as
its own `with`-style selectors (`E["obj_alphys_npc"]`, `E["obj_fakewater"]`, …),
which is why the scope read honours the caller's world rather than a room's.
Yellow's side is the dynamic one: 20 `asset_get_index` call sites in 18 source
files (`spr_crayon_*`, `spr_size_crayon_*`, `hotland_background_*`, room names
from `global.current_room_overworld`, script names built at run time). Yellow's
`__global_object_depths` — the only other place that would turn object *names*
into IDs (`asset_get_index(global.__objectNames[i])`) — is generated but never
runs in this port: nothing calls it, and its entry pragma
`gml_pragma("global", …)` is a reported-unsupported builtin, so
`global.__objectID2Depth` stays empty (nothing is silently filled with the wrong
game's object). Should it ever be wired up, it goes through the same
world-aware `asset_get_index`, so a Yellow caller gets Yellow's object.

Evidence: `tests/test_duplicate_draws.py` (11 tests) — the audit's shape and the
42-entry ID pairing read from the merged manifest; per-world resolution of all 42
names through `asset_get_index`, a scope read and the flat constant; the concrete
twins; an Undertale visitor in a Yellow room keeping Undertale's assets; the
"no scene shows both copies of one name" sweep over five Undertale and four
Yellow rooms; the duplicate-draw sweep over the same rooms (sprite ID + owning
instance provenance from the draw log, with the fractional-sub-index crossfade
and a differently tinted shadow allowed); the palette shader's dropped redraw;
an unrelated draw under the same shader still drawn; and an additive repeat of
identical pixels still drawn.

Fails without the change (each verified by reverting that file alone):
`port/graphics.lua` → the duplicate sweep reports `sprite draw without
provenance: spr_regboat` (and the body-draw test fails); `port/merge.lua` → the
audit test reports `the flat collision list disagrees with the audit: 0 vs 32`
and `double_named` disappears; `port/runtime.lua` + `port/yellow_builtins.lua` →
`spr_flowey gave 1095, not Yellow's 1000243; … fnt_main gave 1, not Yellow's
1000009`; `tools/merge.py` → the count test reports the old
`name collisions with Undertale: 4`. Full suite: 485 passed, 1 skipped.

Recorded limitations for this piece:

- this is the headless converted flow plus the draw log; the CI LÖVE gate renders
  the same rooms, but no pixel-level or Android claim is made here;
- the suppression covers the *duplicate*, not the shader's recolour: shaders
  remain reported and unconverted, so a palette-swapped pass keeps the original
  colours and is drawn once instead of twice;
- the duplicate-draw gate only audits draws that belong to an instance; particle
  systems, tile layers and backgrounds legitimately repeat one sprite and carry
  owner −1 (Yellow's snow and dust systems do this thousands of times per frame);
- "no scene shows both copies" was swept over the five Undertale and four Yellow
  rooms the merged tests already drive, not every room in both games;
- the 42 shared names are pinned to the two manifests' revisions; a rebuilt
  conversion regenerates the list instead of patching it.

## Shared core Player progression (spec §1, §9, §10 — unified-fusion piece 5a)

This is the first **sub-piece**, not completion of piece 5. Previously, entering
Yellow ran `scr_initialize` with LV 1 / EXP 0 / HP 20 / gold 0 / name Clover,
while Undertale's corresponding globals retained an unrelated set of values.
Returning did not carry Yellow's earned progression back.

`port/player.lua`, installed before gameplay initialization in merged builds,
now owns one live `R.player` record. The converted globals are compatibility
**views**, not values copied on each frame or snapshots parked per world:

| Player field | Undertale spelling | Yellow spelling |
| --- | --- | --- |
| `hp` | `hp` | `current_hp_self` |
| `maxHp` | `maxhp` | `max_hp_self` |
| `level` | `lv` | `player_level` |
| `exp` | `xp` | `player_exp` |
| `gold` | `gold` | `player_gold` |
| `name` | `charname` | `player_name` |
| `stats.attack` | `at` | `player_attack` |
| `stats.defense` | `df` | `player_defense` |

Both spellings read/write the same field through the global table's metatable;
there is no raw copy of either alias in `global`. `Runtime:get/set/increment`
and directly assigned Lua globals use the same path. Non-player globals and
single-game manifests keep their old behavior. The existing source initializers
supply starting values — this adapter introduces no new table of stat numbers.

Travel runs its content initializer inside `Player:withDefaults`: existing
Player fields cannot be replaced with new-game defaults, but genuinely absent
fields may be initialized and all non-player initialization still runs. Nested
scripts see the existing HP/stats *during* initialization, not a temporarily
reset character followed by a restore. Zero and negative HP are not mistaken
for absent fields; crossing neither heals nor clamps overheal nor recalculates
stats from LV. The guard unwinds on errors and does not intercept explicit
new-game, load, damage or reward writes outside content initialization.

The queue's crossing-scratch policy is now explicit in both directions:
`global.flag[0..29]` is cleared; shared progression is never stored there.
Higher flags and `plot` are not cleared by this adapter. This is **not** a claim
that the games' story/route flags are unified.

Evidence: `tests/test_unified_player_state.py` (23 tests) covers all eight live
alias pairs through direct writes and compiled GML; LV 1/8/20 crossings with
injured/full/overhealed HP; updates from Yellow and a repeat entry; the real
naming flow and Yellow pause header; Yellow's converted reward/level-up alarm;
flag isolation; error unwinding; explicit new-game reset; and single-game
inertness. The pre-change regression fails with `crossing reset field 1: 1 ~= 8`.
Removing just the defaults guard reproduces that failure; removing just the
flag clear fails with `cross-world scratch flag survived: 0`. All changes are
restored before the green run. Full local suite: **508 passed, 1 skipped**
with `PORT_REQUIRE_YELLOW=1 .venv/bin/python -m pytest -q`.

The packaged Linux LÖVE gate (`port/smoke.lua`) now carries a scripted LV-8,
709-EXP, 58/48-HP player through the existing native boat/whale crossings,
mutates HP/EXP/gold through Yellow's aliases, and asserts the same record and
values on return. `tools/native_smoke.sh` requires its
`native-unified-player.txt` / `CORE PLAYER PASS` evidence. It is a state probe
after the scripted opening, not a played-through Yellow battle or an Android
certification. [PR #41](https://github.com/lordmannu993/undertale/pull/41) merged
as `33ae6c9` after [CI run 35708911107](https://github.com/lordmannu993/undertale/actions/runs/35708911107)
passed the suite, merged packaging and native gate on source `68eecca`.
GitHub's checks/step statuses confirm the pass; sandbox downloads of its log
and artifacts were blocked by TLS EOF, so no independent screenshot inspection
is claimed.

Still pending, explicitly:

- **Inventory and primary equipment are unified as piece 5b** (merged after 5a):
  `port/inventory.lua` holds one shared 8-slot inventory and one four-slot
  equipment set on `R.player`; `global.item`/`global.item_slot` and the
  weapon/armor/modifier globals are live views with working numeric/string
  adapters (paired ids 1/7/13/41/58 resolve per spelling, empty = 0 in
  Undertale's view and `"Nothing"` in Yellow's), and `generated/merged/items.lua`
  (`tools/item_catalog.py`, written by `tools/merge.py`) carries both games'
  extracted item rows - 64 Undertale items (repaired switch labels), 78 Yellow
  items (GMS2 sources), 5 name pairs; nothing hand-typed. Foreign items run the
  catalog's use/equip/desc/name/value/stat actions in either content set;
  Yellow's initializer can fill empty slots (its Missing Poster starter) but no
  longer resets the shared inventory or equipment on re-entry. Still not
  claimed: the STAT panel's hard-coded `"Clover"` heading and gear labels.
- **The shared controller is piece 5c**, documented in the next section. 5a
  did not merge the entities or pick a level-up rule; 5c does the second of
  those and leaves the entities as the rooms place them.
- **Persistence is piece 5d**, documented after the controller section. 5a did
  not claim a save format, a migration, or a restart-resume, and no new
  downloadable release was published for 5a.

## Shared player controller (spec §3, §15 — unified-fusion piece 5c)

One `R.player.controller`, installed only when `manifest.game == "merged"`,
after `port/frisk.lua`. `obj_mainchara` and `obj_pl` stay the entities their
rooms place. Crossing still leaves exactly one of them. There is no third
player object and no per-room swap of controllers.

**Run.** Yellow's compiled rule is unchanged: `option_autorun` XOR (the run
button AND `player_can_run`). That button is `keyboard_multicheck(1)` — Shift
(16) or 120, and physical X once `obj_screen` maps 88 to 16. Undertale does
not read AUTO RUN. While `player_can_run` is 1, holding that cluster adds a
bonus step on the Undertale adapter only, and only on an axis whose net delta
from the frame-start `xprevious`/`yprevious` is already exactly ±3 (piece 5c
made that bonus ±3; piece 6c, below, made it Yellow's ±2).
The bonus is the start of End Step (`3:2`), before the camera follows `x`.
Collision runs with `xprevious` set to the walked spot, then `xprevious` is
restored to the frame start so a blocked bonus does not look like the walk
never happened. `image_speed` becomes Yellow's `1/3` after the original End
Step, and only if the player actually moved and `image_speed` was not already
0. Yellow gets no extra step; its `is_sprinting` is copied onto
`R.player.movement`. `player_can_run` is the shared `abilities.run` flag,
stored as 1/0 (a Lua boolean would fail Yellow's `== true`), default 1.
`withDefaults` does not replace a value that is already set.

**Draw.** While the live `obj_mainchara` is sprinting, the four base walk
sprites (`spr_maincharad/u/l/r`) draw `spr_pl_run_down/up/left/right`. The
mask stays the walk sprite. A nil draw owner is identity, which is what the
older remap tests pin. Umbrella and other costumes have no Clover run pair;
none is invented. Yellow's 24 run poses stay out of the walk remap.

**Facing.** Captured on `gotoRoom`, before `scr_initialize` creates `obj_pl`
at `direction = 270`. Published to `global.facing` before the room's Create
events, then applied after the load: Undertale 0/1/2/3 is Yellow 270/0/90/180.
Nil until the first capture, so a fresh game is not forced to face down.

**Abilities.** Menu (17/67/99) and interact (13/90/122/89) are
`R.player.abilities`, checked through a frame-local `Input.suppressed` that
is cleared at the end of the step. 88 and 16 are never suppressed, and the
gate does not call `Input:clear` (that would drop the boat latch and the
single-game `hold(39, 20)` ⇒ +60 probe).

**Progression.** Yellow's fade alarm still grants EXP and gold. If that write
changed LV, max HP, AT or DF, the controller snapshots current HP, sets LV to
-1, calls Undertale's `scr_levelup`, and restores HP (and a leftover -1).
That script is the shared rule: LV 20 is 99/99/99 and EXP caps at 99999.
Yellow's `*_next` tables are not a second rule and are not edited. A grant
that does not change those stats does not call the script, so a custom AT
survives; the EXP cap still calls it when EXP is already at least 99999,
without forcing LV to -1. Crossing does not reconcile. Current HP is not a
level-up output.

**Battle consumers.** Standing views stay what 5b pinned: ammo is not in
`wstrength` (Real Knife + temy armour is 109, not 112) and accessory defense
is not in `adef`. For the duration of one script, `battleCompose` adds ammo
inside Undertale's `scr_attackcalc` / `scr_mercystandard`, the armour's weapon
bonus inside Yellow's five attacking-damage scripts, and accessory defense
inside `scr_damagestandard`. The wrappers are injected `R.scripts` entries
(Undertale by index, Yellow by name). Item, init and Martlet scripts are not
wrapped. Save scripts are piece 5d, below. Target-bar weak/strong scaling is
not honored.

Evidence: `tests/test_unified_controller.py` (5 tests). Uninstalling the
controller fails all five (no sprint, no solid-probe sprint, no controller,
LV 2 max HP 20 instead of 24, fight power 119 instead of 122). Skipping only
the bonus collision check fails the wall test with a 6px step.
Full local suite: **526 passed, 1 skipped** with
`PORT_REQUIRE_YELLOW=1 .venv/bin/python -m pytest -q`.

Not claimed: Android, audio, pixel-perfect origins, piece 6's cropped sizes
and exact speeds, a native X-run (CI still runs the existing
`CORE PLAYER PASS` crossing probe only), or that the fusion is complete.
The unified save is the next section.

## Player + World save (spec §11 — unified-fusion piece 5d)

One `merge.sav` version 2, installed only when `manifest.game == "merged"`
(`port/save.lua`, before travel so the boot read is the migration). `[Player]`
is LV, EXP, current HP, max HP, gold, name, base AT/DF, all eight inventory
slots, the four equipment slots, run/menu/interact, and the phone and Yellow
PP/SP/RP globals. `[World]` is the world name, current area, position, facing,
story (`plot` and Yellow's `story` stay distinct), route, the regional flag
arrays, NPC and talk maps, and the encounter/steal/fast-travel/box lists.
`[merge]` keeps the version, crossing count, last room, and the ammo/accessory
strings the earlier tests read. `file0` and `Save.sav` are projections so each
continue menu still sees a save; `scr_save`'s own writer still emits `file9`.
They are not a second structure: when `Player.LV` is present, load does not
read them.

Save points in either world write that document. `scr_save` still runs
Undertale's own writer, then one unified write. `scr_savegame` does not run
Yellow's script: that script deletes `Save.sav` and stops on `ds_grid_write`,
which this runtime does not implement (a named stop). The save point warns once
and writes the unified document instead, including `global.story`, which
Yellow's script never stored. `scr_load` and `scr_loadgame` both restore it and
`room_goto` the saved room. Injured HP stays injured. Undertale's own `scr_load`
heals to max HP, and that heal is what a legacy `file0` migration records; a
version-2 load does not heal.

Version 1 is travel metadata. The bytes are copied to `merge.sav.v1` (one path
segment; the copy is not deleted) and the file is rewritten as version 2 with
`migrated_from=1` and the old travel fields. No LV, HP or story is invented.
A missing file is not stamped. Version 99 stops with `merge.sav version 99`
and is not rewritten. A `Save.sav` whose encounter or NPC blob is not a list
this port wrote stops with `Not a save string this port wrote` and is not
deleted. A legacy `file0` is loaded by the original script (while `obj_time`
still exists) and the bytes are left in place.

Re-entering Yellow does not run `scr_initialize`. That script is a new-game
reset. The first entry still runs it. A later entry keeps story, route, flags,
NPC maps and fast-travel labels, recreates a missing `obj_controller` /
`obj_radio`, and puts `saveroom` and `tinypuzzle` back after the controller's
Create hard-codes them. `SCR_GAMESTART` is still an explicit reset. A crossing
writes the document before the destination room's Create, because returning to
Undertale recreates `obj_time` and that Create runs `SCR_GAMESTART`. Landing
then updates only the `[merge]` travel fields, so that reset is not the save.

Evidence: `tests/test_unified_save.py` (8 tests). Without the re-entry guard,
story, route, item stock, `saveroom`, `tinypuzzle` and the NPC map reset.
Without the save-point wrapper, `scr_savegame` stops on `ds_grid_write`.
Without the version check, version 99 is rewritten. Full local suite:
**534 passed, 1 skipped** with `PORT_REQUIRE_YELLOW=1 .venv/bin/python -m pytest -q`.

Not claimed: Android, audio, a played save-point menu, pixel-perfect original
parity, piece 6 speeds, or that the fusion is complete. The native gate still
does not drive a save point; it only asserts `merge.sav` version 2 after its
existing crossing probe.

## Sprite canvas and size compatibility (spec §12 — unified-fusion piece 6a)

Spec §12 asks for a compatibility layer wherever the two games' asset
conventions differ, instead of two separate frameworks. Sprite **size** was the
clearest case. Undertale's checkout exported many PNGs *cropped*, so
`sprite_get_width`/`sprite_get_height` and the `sprite_width`/`sprite_height`
instance reads answered with the cropped pixels — while every event that reads
them, and `scripts/scr_depth.gml`, which turns the height into Undertale's Y-sort
key, was written against the original canvas. Yellow's GMS2 records are not
cropped, so the same call meant the canvas there. One game, two meanings for the
same number.

**One accessor.** `port/assetcompat.lua` answers in original-canvas pixels for
both worlds: `port/graphics.lua`'s size builtins, `port/yellow_studio.lua`'s
copies of them, the `sprite_width`/`sprite_height`/origin instance reads in
`port/runtime.lua`, and the `sprite_get_xoffset`/`sprite_get_yoffset` builtins all
go through it. A cropped Undertale export and an uncropped Yellow sprite now
answer in the same units, and a sprite whose canvas is not pinned answers with its
exported size — never a guess.

**The recovery had stopped reproducing itself.** `tools/recover_sprite_offsets.py`
read the pinned upstream record with GameMaker 1.4 GMX (XML) patterns, but the
pinned ref serves GameMaker Studio 2 `.yy` files (and those carry trailing commas,
so they do not load as JSON either). A re-run therefore fetched nothing: every
candidate came back `missing-fields`, so the checked-in 448 offsets could not be
re-derived by the tool that claims to own them. The pinned numbers are now fetched
once (`--refresh`, `GITHUB_TOKEN`) into `port/recovered_sprite_metadata.json` —
1,427 of the 1,428 candidates, with `spr_pressz` genuinely absent upstream (HTTP
404, named as such) — and `port/sprite_offsets.json` is derived from that metadata
plus this checkout by a pure function, so `--check` re-derives the **whole file**
offline instead of re-checking rows against numbers embedded beside them.

**Three lists and a proof per axis.** The file (format 2) separates:

- `sprites` — 814 records whose crop offset is *proven*. The 448 earlier records
  are unchanged (their `symmetric-bbox-edges` route, plus the sibling-pinned dog
  boat), and 366 are new: their export **is** the canvas (`canvas-span`), so their
  offset is exactly (0, 0) — a proven no-op instead of a guess.
- `canvas` — 553 records whose original canvas is pinned while at least one axis
  of the offset is not provable. They are **never shifted** (the exported position
  stays, exactly as before) and carry the canvas so every size read is right:
  Frisk's walk sprite `spr_maincharad` 19×29 → canvas 20×30, which moves the
  player's own `scr_depth` key by 10; `spr_5_coffeeline` 8×7 → 13×10;
  `spr_adate_arm` 48×31 → 77×71 (491 of the 553 change height).
- `unresolved` — 61 candidates with no pinned canvas (54 whose pinned bbox does
  not fit the pinned canvas, 6 whose bbox disagrees with this checkout's, 1 absent
  upstream). They keep the exported size for every read and stay named with their
  reason.

The routes, and why each is evidence rather than a guess: `canvas-span` (the
export spans the whole canvas on that axis, so a crop of that size starts at 0);
`bbox-interval` (the art fills the export and the export's span equals the pinned
bbox's span on that axis — with an *automatic* bbox, `bboxmode` 0, the art must
then start at the bbox edge; a manual box is a collision rectangle and proves
nothing about where the art sits, so those stay unproven); the earlier
`symmetric-bbox-edges` rule and the `sibling-pinned` anchored path are kept as
they were. Upstream contributes numbers only — no artwork is fetched or imported,
and every gate is re-derived offline.

Evidence: `tests/test_asset_sizes.py` (12 tests). `sprite_get_width` answering
14×15 for `spr_5_mouth2` rather than 13×14, the canvas-only sprite answering 13×10
rather than 8×7, `sprite_width`/`sprite_height` following the instance scale, and
Frisk's `scr_depth` key using 30 rather than 29 each fail without their part of the
change (accessor, recovery, converter carry, instance read).
`test_canvas_only_sprites_are_never_shifted` and
`test_sprite_with_no_pinned_canvas_keeps_its_exported_size` pin the no-guess side;
`test_one_accessor_backs_every_size_read` walks all 2,203 sprite records that carry
a canvas; `test_recovery_tool_re_derives_everything_offline` runs `--check` with an
empty environment. `tests/test_depth_sort.py` and `tests/test_sprite_offsets.py`
were updated for the stronger evidence (Frisk's canvas is now pinned and still not
shifted; the offsets file now has three lists), and piece 3's two dock pins in
`tests/test_boat_water.py` moved by exactly one canvas pixel (+10 depth units) for
the player — the boat and riverman pins, whose canvases were already pinned, did
not move. Regenerate with
`python3 tools/recover_sprite_offsets.py` (offline, from the checked-in metadata)
or renew the metadata with `--refresh`.

Not claimed: the 553 canvas-only sprites are still **drawn** at their exported
position, so one whose art was trimmed by the crop can sit a pixel or two off until
a route proves its offset — deliberate, and they are named rather than nudged. The
61 unresolved candidates keep cropped sizes. Per-frame origins, movement speed
(Undertale's 3 px step vs Yellow's +2 autorun), hitboxes/collision boxes, scaling
and GMS2 sheet coordinates are still open piece-6 sub-pieces, as are pixel-perfect
parity with the original engine (a CI-only visual claim) and Android.

## Frame selection, animation rate and render anchors (spec §12 — unified-fusion piece 6b)

Spec §12 names sprite origins, animation frame handling and render anchors as
things one compatibility layer must normalise. Piece 6b found four places where
the two worlds meant different things by the same animation state, and fixes each
in the shared system (`port/assetcompat.lua`, `port/graphics.lua`,
`port/runtime.lua`), with no per-room or per-character branch:

1. **Frame selection.** GameMaker draws the sub-image `image_index` rounds *down*
   to — the manual's own words for `image_index` are "it is always rounded down to
   obtain the subimage that is drawn", and YoYo's runner truncates the index the
   same way in `Sprite.Draw`. Piece 3 had replaced that with a crossfade of the two
   neighbouring frames, which drew every animating sprite in *both* worlds as two
   stacked frames (walk cycles run at `image_speed` 0.2 or 1/3, so almost every
   step is fractional), and — because the boat cover's `cc += 0.1` never wraps —
   drew the cover's second frame at a blend "amount" above 1 (4.1 after forty
   ticks, fully opaque) once `cc` passed 2. The renderer now draws one sub-image;
   the draw log's blend fields (13/14) stay `nil`. The ripple steps one frame
   every ten draws, as the original does.
2. **Animation rate.** Studio 2 made `image_speed` a *multiplier* on the sprite's
   own playback speed; GameMaker 1.4's `image_speed` is frames per step. The Yellow
   converter already recorded the per-step rate (`yellow.image_speed`, FPS types
   divided by Yellow's own 30 FPS game speed), but the runtime advanced every
   instance by the bare `image_speed`: of Yellow's 2,039 multi-frame sprites, 1,265
   author one frame per step and were right by coincidence, 772 author a slower
   rate (10 fps at 30 steps/s is 1/3 frame per step, 5 fps is 1/6) and animated
   up to six times too fast, and 2 author a faster one. `Runtime:finishFrame` now advances
   `image_speed × AssetCompat.playbackRate(sprite)`; the rate is 1 for every
   Undertale record, so Undertale is unchanged. The converter also stops coercing
   an authored `playbackSpeed` of 0 to 1 (19 pinned sprites hold their frame until
   code sets `image_index`).
3. **Render anchor.** Frisk's sprites put the origin at the canvas corner (0,0),
   Clover's at his body (`spr_pl_down` 9,16). The Frisk-only remap
   (`port/frisk.lua`) drew the replacement at its *own* origin, so Yellow's player
   was drawn 9px right and 15px down of Clover's body — away from the collision
   mask it walks with — and Undertale's running Frisk (Clover's run cycle) 10px
   left and 15px up of the walk pose. A remapped draw now stands on the requested
   sprite's feet: `AssetCompat.anchor` aligns the two canvases' bottom centres —
   the point the depth rule already sorts by — and part draws move their source
   rectangle by the same amount. The draw log records the anchored origin
   (fields 17/18).
4. **Frame count.** A remap draws the replacement at the same *phase* of its own
   cycle (`AssetCompat.remapFrame`). Clover's six-frame run over Frisk's two-frame
   side walk used to show frames 0 and 1 only; it now shows all six. The shared
   controller's run rate is expressed in the run pose's own frames
   (`runImageSpeed`: 1/3 × walk frames / run frames on the record), so the drawn
   pose advances exactly Yellow's 1/3 frame per step (`scr_normal_state`).

Evidence: `tests/test_asset_frames.py` (6 tests). Reverting the renderer fails
four of them (the fractional draw logs `0/1/0.5 1/2/0.7 0/1/4.1`, the Frisk and
run-pose anchors, the identity check); reverting the runtime rate fails the Yellow
rate test (`spr_mail_station_steamworks`, 10 fps, advances 3 frames in 3 steps
instead of 1); reverting the controller's run rate fails the run-cycle test (each
run frame shows for 1 step, not 3). Two earlier pins were updated with the
rationale in their docstrings: piece 3's
`test_cover_ripple_interpolates_between_frames` became
`test_cover_ripple_steps_one_frame_every_ten_draws` (30 draws, 3 frame changes,
no blend — it fails on the crossfade renderer), and piece 5c's sprint-rate check
now measures the drawn pose's rate (1/3) instead of the record's. Full local suite
553 passed, 1 skipped (`PORT_REQUIRE_YELLOW=1`).

Not claimed: pixel-perfect parity with either engine (a CI-only visual claim),
Android, or a played-through scene. The anchor aligns canvas bottom centres; it
does not claim the two artists drew the feet at the same pixel inside their
canvases. Sprites the offset recovery could not pin keep their exported frames.

## One movement speed (spec §12 — unified-fusion piece 6c)

Spec §12 lists movement speed among the things one compatibility layer
normalises, and §3 asks for Clover's running to belong to the unified player.
Both games walk 3px a step — `obj_mainchara`'s own `x+= 3`/`y+= 3` and
`obj_pl`'s `plspd = 3` — and Yellow runs `pl_spd = plspd + 2`
(`scr_normal_state`). Piece 5c ran Undertale at an extra 3px lattice step, so the
same button ran 6px a step in one world and 5px in the other.

The controller now owns one speed (`Controller.WALK_STEP` 3, `Controller.RUN_BONUS`
2). Yellow's own compiled step already runs 3+2 and is untouched; Undertale's walk
step is followed by a +2 bonus in the direction it walked, collided through
Undertale's own collision events exactly as the 5c step was (a blocked bonus rolls
back to the walked spot, and `xprevious` is restored so the walk still counts).
The bonus is not snapped to the 3px lattice: `obj_mainchara`'s Create snaps
*before* it moves the player to the entrance marker, and 498 of Undertale's 568
markers are off that lattice, so the original already walks off it.

Evidence: `tests/test_movement_speed.py` (3 tests). The constants are re-read
from both pinned sources (`obj_mainchara`'s Step, `obj_pl`'s Create,
`scr_normal_state`), so they cannot drift from either game; Undertale runs
5px a step in every direction (6 without the change) while its walk stays 3 and
Yellow's own run stays 3+2; and running into room_area1's east wall from each of
the five 5px phases never enters it (without the bonus collision the phases at
x=231/232 end inside the wall at x=261/262). Piece 5c's controller pins were
updated with the rationale in their docstrings: two run steps are 10, not 12,
and the solid probe's 4px gap now separates a 3px walk from a 5px run.
Full local suite 556 passed, 1 skipped (`PORT_REQUIRE_YELLOW=1`).

Not claimed: a played-through route, input latency, or Android. Undertale's
diagonal wall-slide objects (`obj_sur` and friends) still slide in their own ±3
steps once a run touches them, which is the original's own behaviour for a walk.

## Collision boxes, hitboxes, scaling and sheet coordinates (spec §12 — unified-fusion piece 6d)

The last sub-piece of spec §12. Five places where the two worlds answered a
collision or size question differently, each fixed in the shared system
(`port/collision.lua`, `port/graphics.lua`, `port/yellow_studio.lua`,
`port/yellow_builtins.lua`, `tools/yellow/assets.py`), with no per-room or
per-character branch:

1. **Precise masks in canvas pixels.** `R:maskPoint` transforms the probe point
   into *canvas* coordinates, then read the exported PNG at those coordinates.
   A cropped Undertale export starts at its recovered offset (the renderer
   draws it at `ox, oy`), so every cropped sprite's pixel hitbox sat
   `(ox, oy)` away from its art — 448 recovered sprites have a non-zero offset,
   and 136 objects collide with one of them (`spr_adate_body` is 10px right and
   17px down of its crop corner). The mask is now read at `canvas - (ox, oy)`,
   through one `R:maskPixel`.
2. **Composite vs per-frame masks.** GameMaker's *Precise* mask is "a composite
   of the edges of all the sub-images placed over each other" (GameMaker manual,
   Sprite Editor); only separate masks (1.4 `sepmasks`, Studio 2 *Precise (per
   frame)*) follow the current frame. The runtime used frame 0 as the whole
   mask when masks were not separate; it now takes the union of every frame.
3. **Studio 2's `collisionKind` 4 is Precise (per frame).** The GMS2 sprite
   schema numbers the kinds 0 Precise, 1 Rectangle, 2 Ellipse, 3 Diamond,
   4 PrecisePerFrame, 5 RectangleWithRotation (the `SpriteCollisionKind` enum in
   bscotch/stitch's `YySprite.ts` and NPC-Studio's `yy-typings` agree). The
   converter read 4 as a rotated rectangle and hard-coded `sepmasks` 0, so the
   74 per-frame masks (every one of them multi-frame: Big Frog's knight, Ceroba's
   bullets, Flowey's hands) collided as composites. Kind 4 now converts to
   GameMaker 1.4's precise `colkind` 0 with `sepmasks` 1; kind 0 stays one
   composite mask; kind 5 (none in the pinned source) is reported by name. The
   conversion report's finding is now `precise-per-frame-mask: 74`.
4. **`place_meeting`/`instance_place` test the caller's collision box.**
   GameMaker moves the caller to (x, y), checks *its mask* against the target,
   and moves it back — precise only when both masks are (GameMaker manual,
   `place_meeting`). The port checked the single point (x, y), so Yellow's 313
   `place_meeting` and 34 `instance_place` calls (the diagonal wall slides in
   `scr_normal_state`, battle hitboxes, platforms) missed anything the caller's
   origin had not reached. `R:placeMeeting` is the one test behind both, and
   `instance_place_list` collects every instance the same test meets.
5. **Scaling and sheet coordinates in canvas pixels.** `draw_sprite_stretched`,
   Yellow's `draw_sprite_stretched_ext` and `draw_sprite_tiled(_ext)` scaled or
   stepped by the *exported* size, so a cropped sprite stretched past the
   rectangle it was asked to fill (`spr_adate_body` over 154×142 drew at
   2.30×2.63 instead of 2×2). They now go through `AssetCompat.width/height`.
   `sprite_get_uvs` — a named compatibility stop that four *placed* Yellow
   reflection objects hit every draw (`rm_snowdin_04_yellow`,
   `rm_snowdin_10_yellow`, `rm_hotland_complex_1`/`1c`) plus four spawned
   backgrounds — now answers from the frame: in this port every frame is its own
   texture (UVs 0..1), and the trim fields are exactly the recovered crop
   (`[4]/[5]` = `ox, oy`, `[6]/[7]` = exported/canvas size), so an uncropped
   Yellow frame answers `0, 0, 1, 1, 0, 0, 1, 1`.

Evidence: `tests/test_asset_collision.py` (6 tests), with mask pixels supplied by
a stand-in `love.image` so the headless run exercises the precise path.
Reverting `port/collision.lua` fails three (the cropped mask hits
`00000` instead of `11000` at canvas (10,17)/(76,70); the composite reads
`1000` instead of `1001`; `place_meeting` answers 0 for a box whose edge crosses
the target); reverting `port/graphics.lua` fails the stretch (`2.2985, 2.6296`
instead of `2, 2`); reverting `port/yellow_studio.lua` alone fails
`sprite_get_uvs` with `attempt to call field 'sprite_get_uvs' (a nil value)`
(the builtin is registered there, and 6d removed it from the compatibility-stop
list in `port/yellow_builtins.lua` — reverting both Yellow files together
reproduces the quoted `Compatibility stop: sprite_get_uvs`); reverting the
converter (`tools/yellow/assets.py`, with `tools/yellow_convert.py`'s finding
count and `port/yellow_studio.lua`'s per-frame reading) fails the kind-4 test —
all 74 per-frame sprites convert wrongly, the first being
`spr_battle_flowey_yarn_lhand_1` (the test reports the first of the 74;
`spr_attack_thorns` is among them). Piece 1's Yellow-assets pin
`test_a_rotated_rectangle_mask_keeps_its_original_value_and_is_counted` became
`test_a_per_frame_precise_mask_is_precise_with_separate_masks_and_counted`, with
the schema reference in its docstring. Full local suite 562 passed, 1 skipped
(`PORT_REQUIRE_YELLOW=1`).

Not claimed: pixel-perfect parity with either engine (a CI-only visual claim),
Android, or a played-through battle. Particle sprites keep drawing at their
exported origin (a cropped particle sprite can sit its crop offset away, as
before); Studio 2's nine-slice drawing and rotated-rectangle masks (kind 5, none
in the pinned source) stay reported rather than emulated.

## Snowdin shopkeeper visual sweep (spec §7 — unified-fusion piece 7)

The owner's original screenshot — four eyes, a floating mouth — was the
shopkeeper's three face layers losing their alignment. Room 311 composites the
keeper from three layers whose positions were authored against the *original
canvas*:

| layer | drawn by | position | pixels land at |
| --- | --- | --- | --- |
| `spr_shopkeeper1` body (61×111 in a 64×120 canvas) | `obj_shop1` Draw | `(shx, 0)`, `shx=130` | `(131, 9)` — the recovered crop offset `(1, 9)` |
| `spr_shopkeeper1eyes` blink strip (26×7, 4 frames) | auto draw of `obj_shopeyes1`, spawned at `(18 + shx, 40)` | `(148, 40)` | `(148, 40)` (uncropped) |
| `spr_shopkeeper1mouth` (9×7, 2 frames) | `obj_shopmouth1` Draw while `faceemotion == 0` | `(shx + 27, 50)` | `(157, 50)` (uncropped) |
| `spr_shopkeeper1_face0..6` (25×25, origin `(1, 4)`) | `obj_shopmouth1` Draw while `faceemotion > 0` | `(shx + 20, 36)` | `(149, 32)` |

The body's painted eyes sit at bitmap rows 31–36 and its mouth at rows 42–45.
With the carriage correct, the eyes strip covers rows 31–37 of those same
columns, the mouth covers the painted mouth exactly, and an emotion face's
bitmap (18, 23 into the body's bitmap, 25×25) covers the whole painted face —
its own eyes band (face rows 9–14) and mouth (rows 19–24) land on the body's,
so exactly one pair of eyes shows and the painted mouth is seated on the
muzzle, for `faceemotion` 0–6. The mouth layer does not draw while an emotion
face is up (the Draw event swaps them), and the blink strip keeps animating
underneath, as in the original. Before the crop-offset piece drew the body's
exported pixels at `(130, 0)`, every overlay kept its canvas position, and the
body's own eyes and mouth rode 9 rows up and 1 column left — the four eyes and
the floating mouth. Before the instance-array piece the emotion faces did not
draw at all (`Unresolved sprite ID 881`).

Piece 7 is the sweep that pins the whole composition in the draw log.
`tests/test_asset_arrays.py` gained two tests:
`test_shopkeeper_default_face_layers_seat_exactly` (emotion 0 draws body, eyes
and mouth exactly once each, at the positions above, with the seat equations
`+17, +31` and `+26, +41` against the body's bitmap) and
`test_shopkeeper_emotion_faces_cover_the_default_face_and_swap_out_the_mouth`
(emotions 1–6 each draw exactly one face at `(150, 36)` with origin `(1, 4)`,
the mouth layer is absent, the face covers the strip's dark eye pixels and its
whole band, and no `Unresolved sprite ID` warning is raised). The seat test
fails if the crop carriage is removed (the offset assertion reads `(0, 0)`
instead of `(1, 9)`, and the seat equations follow); the emotion test fails
without the recovered array IDs. Draw-log evidence for the PR: emotion 0 draws
`spr_shopkeeper1 x=130 y=0 ox=1 oy=9`, `spr_shopkeeper1eyes x=148 y=40`,
`spr_shopkeeper1mouth x=157 y=50`; emotion 3 draws the same body and eyes plus
`spr_shopkeeper1_face3 x=150 y=36 originX=1 originY=4`; the `faceemotion` 1–6
sweep draws each face exactly once.

Not claimed: pixel-perfect parity against a captured original frame (a CI-only
visual claim), the blink/talk animation *rates* beyond the layers' own
`image_speed` handling (piece 6b's frame selection), or any other shop room —
`obj_shopmouth1` destroys itself outside room 311, and the other shops were not
swept.

## Acceptance matrix (spec §15, §16 — unified-fusion piece 8)

Piece 8 is the last piece of the fusion: spec §15's test list and §16's
acceptance criteria, run as **one suite** rather than as more per-piece probes,
and the matrix that maps every requirement to its code path, its test and its
evidence (`docs/FUSION_STATUS.md` §7).

`tests/test_acceptance_matrix.py` (7 tests) drives §15 as one continuous
session — Undertale, then Undertale Yellow, then home — instead of separate
fixtures per feature:

| §15 checklist | test | what it drives |
| --- | --- | --- |
| Player state | `test_spec15_one_journey_keeps_inventory_equipment_and_progression` | `scr_itemget` grants a weapon, `scr_weaponeq` equips it (swapping the Stick back into the slot), a Monster Candy stays carried, `scr_levelup` sets LV 8 / 48 max HP / AT 24 / DF 11, HP is left injured; the crossing into `rm_hotland_02` must keep every slot, the equipped weapon (Yellow reads it as "Toy Knife"), LV/EXP/HP/stats/gold/name and the shared `run`/`menu`/`interact` abilities; Yellow's own pause menu equips Silver Ammo (slot swap back to Rubber Ammo) and a Yellow-only Lemonade rides in a slot; the whale crossing home keeps both — proved through Undertale's `global.item` spelling of the same slot |
| Inventory (one inventory, no Clover/Frisk inventory) | same test + `test_spec16_one_player_one_inventory_one_controller_one_save` | both spellings are live views of `R.player.inventory[1..8]` in both directions of a write; `global.item[8]` stays Undertale's own scratch |
| Movement | `test_spec15_movement_and_its_animations_match_in_both_worlds` | 3px/step walking in both worlds, 5px/step running in both (Undertale's collided +2), and the drawn pose per frame: walk poses while walking, `spr_pl_run_right` — Clover's run cycle — while sprinting in **either** world (spec §3) |
| Rendering | `test_spec15_rendering_sweep_keeps_every_scene_coherent`, `test_spec15_named_scenes_keep_their_original_layering` | ten rooms (five Undertale, five Yellow) rendered after a real crossing: no instance draws the same sprite twice in a frame, every owned draw belongs to a live instance, and the sweep covers the player in both worlds, 2260+ particle draws, 500+ background draws and the shopkeeper's multi-layer composite; then the three named scenes — the dock's water < hull < cover < riverman < player order, room 311's body/eyes/mouth exactly once each, and the Snowdin forest drawing the visiting Frisk (never Clover's walk sprites) with its snow |
| Save/load | `test_spec15_both_worlds_save_points_write_and_load_the_one_document` | `scr_save` in Undertale, mangled, restored by `scr_load`; `scr_savegame` at a Yellow save point, mangled, restored by **Undertale's** loader while standing in the Yellow room (injured HP kept, room kept); `merge.sav` version 2 with `n:8`/`s:Lemonade` in the `Player` block, and `R.saveMemory` holding no third `.sav` document |
| §16 one system | `test_spec16_no_duplicated_player_state_exists_in_the_port`, `test_spec16_one_player_one_inventory_one_controller_one_save` | the port and both conversions are scanned for the separate-state spellings spec §9 forbids (`cloverInventory`, `friskInventory`, `undertaleLV`, `yellowLV`, …) and for a second `*.install` of the shared systems; then identities: `R.player` (and `R.playerBridge.state`, `R.inventoryBridge.state`) is one record across two crossings, one controller object, one inventory/equipment table, every progression spelling round-trips through the other, and `merge.sav` stays version 2 |

Each mechanism the suite relies on was reverted one at a time (file edited
back, the acceptance test run, the file restored) so the tests are known to
fail without the pieces they certify:

| reverted mechanism | observed failure |
| --- | --- |
| `port/inventory.lua`: the content-initialization slot guard (`if guarding() and normalize(state.inventory[index]) ~= UT_EMPTY`) | `inventory after crossing: Missing Poster,0` — Yellow's own `scr_initialize` wipes the carried slot |
| `port/player.lua`: the alias write guard `if bridge.defaultsDepth == 0 or owner[field.key] == nil` | `LV/EXP lost` — destination defaults replace the live record |
| `port/controller.lua`: `RUN_BONUS = 2` → `0` | `Undertale run distance: 3,3,3,3` |
| `port/frisk.lua`: the sprint remap condition `movement and movement.sprinting and owner and owner.v` | `Undertale run drew spr_maincharar` — the run cycle stops being Clover's |
| `port/graphics.lua`: the draw-list comparison `a.depth > b.depth` reversed | the dock draws `spr_maincharad, spr_riverman, spr_dogboat, spr_dogboat_cover, bg_watertiles_supplement, …` — the water in front of the hull |

The native gate carries the same inventory/equipment claim through the
**packaged** archive: `port/smoke.lua` now puts a Yellow-only item in slot 3 and
equips Silver Ammo before the River Person crossing, asserts both on arrival in
`rm_hotland_02` through Yellow's and Undertale's spellings, asserts them again
after the whale has carried the player home, requires `merge.sav`'s `ammo` to be
that same "Silver Ammo", and writes `port-test-output/native-acceptance.txt`
with an `ACCEPTANCE PASS` line — which `tools/native_smoke.sh` now requires
rather than merely logging (the same shape as piece 5a's `CORE PLAYER PASS`).

This certifies the fusion's *systems* headlessly plus the packaged crossings in
the native gate. Not claimed by piece 8: Android behaviour, audio fidelity,
touch latency, a played-through route or battle, pixel-perfect parity with
either original engine, or the Yellow rooms that still stop by name (25 rooms
have no converted source data; piece 8 does not add any). The room-specific
exemptions §13 allows stay listed where they were listed; piece 8 adds none.
