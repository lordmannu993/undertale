# Undertale Yellow merge: one traversable world, five pieces

Goal, in the owner's words: **the whole of Undertale Yellow merged into this Undertale
port as a single game**, so one playthrough can walk between both games' areas. The two
worlds are joined by their own travel hubs rather than by bolted-on shortcuts:

- **Undertale's River Person** (`obj_dogboat_thing` / `obj_riverman`, dialogue in
  `SCR_TEXT` cases 587-585, destination in `global.flag[459]`) gains extra boat
  destinations that land in Undertale Yellow's areas.
- **Yellow's UGPS mail whale** (`obj_mail_whale` → `obj_fast_travel_menu`,
  `global.fast_travel_list` / `scr_fasttravel_add`) gains extra travel points that land
  in Undertale's areas.

The player is **Frisk** (`obj_mainchara`) everywhere. Clover is not a playable character:
Yellow's player object keeps its mechanics but is drawn as Frisk, and Clover's sprite set
supplies what Frisk's set does not have — most visibly a **run animation bound to the X
button**. Frisk keeps Undertale's weapons and armours, and gains Clover's **weapon
ammunition** (weapon modifier) and **accessories** (armour modifier) as two extra
equipment slots. Yellow items are *not* pushed into Undertale shops as a shortcut: they
are picked up in Yellow's world, the way Yellow gives them to you.

## Why this is five pieces

Yellow is a GameMaker **Studio 2 (2023.4.0.84)** project: 3 908 sprite folders
(37 398 frame PNGs), 3 224 objects, 1 155 script folders, 287 rooms, 673 sounds,
112 tilesets, 68 paths, 26 shaders, 35 sequences — about 580 MB of assets. This port's
existing pipeline converts a GameMaker **1.4 `.gmx`** checkout. Nothing in Yellow can be
used until a second front end exists, so the work is ordered: source pipeline → language →
objects → rooms → merged world. Each piece is one PR, merged before the next starts.

| # | piece | state |
| --- | --- | --- |
| 1 | Pinned source pipeline + merged asset registry + every sprite, sound, font and tileset texture converted | **complete** |
| 2 | GMS2 GML: language support in the compiler, all 1 155 Yellow scripts converted, name→ID rewriting, GMS2 builtins in the runtime | **complete** |
| 3 | All 3 224 Yellow objects and their events, with parents, masks and collision-event targets | **complete** |
| 4 | All 287 Yellow rooms: instances, creation code, tile layers from tilesets, backgrounds, views; plus the 68 paths | **complete** — conversion, animation, tile transforms, layers and layer elements; 25 rooms whose layer effects or physics worlds have no equivalent stay named stops |
| 5 | One world: River Person + UGPS cross-game destinations, Frisk as the only player (Clover's run sprites on X), Frisk's weapons/armours plus Clover's ammo/accessories, saves, packaging, release | **complete** — published as `love-v1.2.0-fusion-experimental`; see the piece 5 section below |

## Rules this merge follows (same as the rest of the port)

1. **No invented data.** Yellow's numeric asset IDs come from two independent records
   inside the pinned decompilation — the project's own resource order
   (`Undertale_Yellow.yyp`) and the decompiler's dumped ID list
   (`notes/Asset_Order/Asset_Order.txt`) — and the converter *fails* if they disagree.
2. **Pinned, fetchable, never committed.** Yellow assets are ~580 MB. They are fetched by
   `tools/fetch_yellow.py` from one immutable commit into the git-ignored `yellow_src/`,
   verified by digest, and packaged at build time. Only the converter, its provenance
   record (`port/yellow_source.json`) and the tests live in Git.
3. **Unsupported means a visible stop.** Shaders, sequences, nine-slice sprites,
   rotated-rectangle masks (collisionKind 5; none in the pinned source), GMLive and the
   Steamworks/Steam hooks have no GameMaker 1.4
   equivalent in this runtime. They are enumerated in the conversion report and must stop
   with their own name, never be silently replaced.
4. **Undertale stays intact.** Undertale's recovered IDs are untouched; Yellow lives in a
   disjoint band (`YELLOW_BASE = 1 000 000`). Every existing test and the native LÖVE gate
   must still pass at every piece.

## ID space

| resource | Undertale | Yellow (merged) |
| --- | --- | --- |
| sprites | recovered original IDs, synthetic `20000+` where unrecoverable | `1000000 + Asset_Order sprite ID` |
| objects | recovered / synthetic | `1000000 + object ID` |
| rooms | reconstructed order with the documented slot-159 gap | `1000000 + room ID` |
| sounds | recovered / synthetic | `1000000 + sound ID` |
| backgrounds | recovered / synthetic | `1000000 + tileset (background) ID` |
| fonts | original | `1000000 + font ID` |
| paths | recovered point data | `1000000 + path ID` (piece 4) |
| scripts | recovered / synthetic | name-resolved; GMS2 has no runtime script index |

Ten sprite names, ten object names, twenty-one sound names and one font name exist in both
games (`spr_flowey`, `obj_alphys_npc`, `mus_shop`, `fnt_main`, …). The merged manifest
therefore keeps Undertale's `names` map as-is and stores Yellow's complete name→ID map
beside it as `yellow_names`; piece 2 resolves Yellow's code through `yellow_names`, so a
collision can never rebind an Undertale asset.

## Piece 1, in detail

- `tools/fetch_yellow.py` — download the pinned tarball, verify its SHA-256, extract into
  `yellow_src/`, then verify two pinned index files by digest. `--check` re-verifies an
  existing checkout with no network; `--tarball-cache` lets CI cache the 309 MB download.
- `port/yellow_source.json` — the provenance record: upstream, fork origin, immutable
  commit, tarball digest and size, index-file digests, documented asset counts.
- `tools/yellow/gms2.py` — string-aware reader for GMS2's JSON-with-trailing-commas.
- `tools/yellow/registry.py` — the two-source ID recovery, the merged ID band, the
  on-disk-vs-order discrepancy list, and the Undertale↔Yellow name-collision table.
- `tools/yellow/assets.py` — sprite/sound/font/tileset records in exactly the shape
  `port/graphics.lua` and `port/audio.lua` already consume, plus the GMS2-only facts
  (animation speed and type, custom origin, nine-slice, tile grid) kept in a `yellow`
  sub-record for later pieces instead of being thrown away.
- `tools/yellow_convert.py --stage assets` — writes `generated/yellow/assets/*.lua`,
  `generated/yellow/manifest.lua` and `generated/yellow/conversion-report.json`.

Known deviations recorded by piece 1 (all reported, none hidden):

| GMS2 fact | merged-game handling |
| --- | --- |
| `collisionKind` 4 = Precise (per frame) (74 sprites) | GM 1.4's precise `colkind` 0 with `sepmasks` 1 (piece 6d; earlier pieces misread it as a rotated rectangle); `collisionKind` 0 Precise stays one composite mask (`sepmasks` 0) |
| `nineSlice` on 14 UI sprites | runtime has no nine-slice drawing; reported |
| `playbackSpeedType` 0 = frames **per second** (1 456 sprites) | converted to a GameMaker 1.4 `image_speed` using Yellow's own 30 FPS game speed, recorded per sprite |
| `playbackSpeedType` 1 = frames per game frame (2 452 sprites) | `image_speed` = `playbackSpeed`, identical semantics to GM 1.4 |
| font `ascender` / `ascenderOffset` vertical metrics | captured in the record; text vertical placement is verified in piece 5, not assumed |
| 3 sprite IDs in the order list have no folder on disk (`_filter_*` shader textures) | reported as missing, never substituted |
| 112 `_decompiled_*_tileset` sprite folders are tileset texture pages, not sprites | mapped through their tileset's background ID, not the sprite list |

## Piece 2, in detail

Piece 2 adds the GMS2 script front end without changing the existing GMX front end:

- `tools/gml2.py` extracts named GMS2 functions with a string/comment-aware scanner,
  binds parameters and defaults to the existing GameMaker scope, removes enum
  declarations after recovering their integer values, and reuses the strict Pratt
  parser/emitter for arrays, loop declarations, compound/bitwise operators and the
  GMS2 `@'...'` pragma argument form. Unsupported syntax remains a conversion error;
  it is never turned into an empty function.
- `tools/yellow_convert.py --stage scripts` runs the complete asset stage, then
  emits one Lua module for each of the **1,155** project script folders. The pinned
  checkout produced **1,137** named function exports from **66,812** source lines.
  The 22 GMLive resources are emitted as named compatibility stops, so a live-editing
  call fails visibly instead of becoming a no-op.
- `generated/yellow/manifest.lua` keeps scripts name-resolved: `script_execute` and
  direct calls use Yellow script names, never the decompiler's 2,345-entry synthetic
  script audit list as invented runtime IDs. Asset/object/room/path names remain in
  the nested `yellow_names` namespace, while Undertale's flat `names` map is not
  rebound. Asset references are emitted in Yellow's disjoint `1000000+ID` band.
- `port/yellow_builtins.lua` supplies the GMS2 array, type, string, math, asset,
  instance, input and colour aliases used by the converted scripts. Studio facilities
  without a safe 1.4 equivalent retain their builtin name and stop through
  `Runtime:unsupported`; a generated script with the same name is never shadowed.
  `Runtime:script` also continues to honor injected numeric GMX functions before
  loading a generated module.

## Piece 3, in detail

Piece 3 converts all **3 224** Yellow objects and their **8 494** events
(**243 470** lines of Studio 2 GML) into the module shape `tools/convert.py`
already writes for Undertale, so `port/runtime.lua` loads either game without
knowing which one it is looking at:

- `tools/yellow/objects.py` reads each `objects/<name>/<name>.yy` and resolves
  `spriteId`, `spriteMaskId`, `parentObjectId` and every collision event's
  `collisionObjectId` to merged `1 000 000+ID` values. A collision event's
  runtime key becomes `4:<merged target ID>`, the same renumbering
  `tools/convert.py` applies to Undertale's `ename` targets, and its code file is
  named after the *other* object (`Collision_obj_arcade_bullet.gml`) with no
  subtype — the naming the pinned source actually uses.
- `tools/gml2.py`'s `compile_gml2_event` compiles an event body rather than a
  script resource. Studio 2 lets an event declare its own functions; Yellow has
  sixteen such declarations, two of them named `state_switch` in different
  objects. They are emitted into the event's own GML scope (`E._locals`) and
  `Runtime:call` resolves a scope-local function before any builtin or script, so
  no object can shadow another and a local still wins over a builtin, as in
  GameMaker.
- `tools/yellow_convert.py --stage objects` runs pieces 1-2, writes
  `generated/yellow/objects/*.lua`, and extends the manifest with the object
  modules, Yellow's keyboard keys (`27`) and the per-instance mouse subtypes its
  objects declare (`0`, `4`).
- The runtime grew the dispatches Yellow's events need. Every one is inert for
  Undertale, whose objects use none of them: **Clean Up** (after Destroy, and for
  the instances a room change drops, which now stop existing instead of lingering
  alive but unlisted), **Draw Begin / Draw / Draw End** as three passes over
  instances in depth order, **Draw GUI Begin / Draw GUI / Draw GUI End** in
  display space, **Pre-Draw** and **Post-Draw** around the frame, and
  **per-instance mouse events** (`0`-`9`) gated on the pointer being over the
  instance's mask. Invisible instances still skip every Draw event, as
  GameMaker's own manual says they must.
- Parent loops would hang `Runtime:isA`, so the converter walks every chain and
  refuses the build if one closes.

Studio 2 facts piece 3 records rather than reinterprets:

| GMS2 fact | merged-game handling |
| --- | --- |
| objects carry no depth; an instance takes its room layer's | every object is converted with `depth = 0` and `yellow.depth_source`, and piece 4 assigns the real depth |
| 10 physics objects (the seesaw and piston puzzles) | the whole Box2D record is kept in `yellow.physics`, and `Runtime:create` stops with the object's name instead of dropping it into a world that will not move it |
| object variables (`properties`) would have to become Create-event prologue code | Yellow declares none; an encounter is a hard conversion error, never a silent omission |
| Async HTTP (`7:62`, GMLive's own poll) and Broadcast Message (`7:76`, sprite frame events) | both are converted, and both are listed per object in the report as events nothing dispatches |
| No Button / Mouse Enter / Mouse Leave (`6:3`, `6:10`, `6:11`) and Resize (`8:65`) | no dispatch; no Yellow object uses them, and the report says why |
| Drag and Drop events | Yellow has none (`isDnD` is false on all 8 494 events); an encounter is a hard error |

Piece 3 converts and validates objects, but it does not make Yellow playable by
itself: rooms remain piece 4, so no converted object is ever placed, and the
Studio 2 builtins `port/yellow_builtins.lua` has not implemented still stop the
events that call them. Piece 4 supplies the rooms; piece 5 the merged world.

## Verification

```bash
python3 tools/fetch_yellow.py --check           # offline: is the pinned source really there?
python3 tools/yellow_convert.py --stage assets  # convert every sprite/sound/font/tileset
python3 tools/yellow_convert.py --stage scripts # convert assets plus all GMS2 scripts
python3 tools/yellow_convert.py --stage objects # convert assets, scripts and all 3 224 objects
.venv/bin/python -m pytest -q                   # offline unit tests + live gates when fetched
```

Live gates skip (never pass silently) when `yellow_src/` is absent, and CI fetches it, so
the full-asset conversion is proven on every pull request.

## Pieces 4–5 status (2026-09-14)

Piece 4 is complete. Piece 5 is **complete** and was published as
`love-v1.2.0-fusion-experimental`, gated on the native fused-world tests below
exactly as this document required.

### Piece 4: rooms, animation, transforms and layers

- `tools/yellow/rooms.py` converts all **287 rooms** and **68 paths**: 7 637 placed
  instances, 1 340 creation-code files, **199 454 drawables** across **3 006
  layers**, with tile RLE cardinality validated and every reference resolved
  through the pinned registry.
- Tile transform bits are decoded, not guessed: bits 0–18 are the tile index,
  bit 28 mirror, bit 29 flip, bit 30 a 90° clockwise rotation, and any other bit
  set is a conversion error. Mirror and flip are applied before rotation, which is
  the order GameMaker documents.
- `ts_steamworks_tileset` is the one animated tileset. Its `FrameData` rows are
  per-tile-index cycles driven by a single global tile clock, at the 5 FPS the
  texture page records, and a placed tile animates from its own index onwards.
- Sprite asset layers honour `GMRSpriteGraphic.animationSpeed` as a multiplier on
  sprite playback speed and `headPosition` as the starting frame; background layer
  animation converts `animationFPS` at the game's own 30 FPS.
- `port/yellow_layers.lua` implements the `layer_*` and `layer_background_*`
  families plus `layer_tilemap_get_id`, and `R:buildLayerElements()` gives scripts
  the element model they query (`layerelementtype_*`: background 1, instance 2,
  sprite 3, tilemap 4). Yellow's GameMaker 1.4 tile helpers compare
  `layer_get_element_type == 7`, which never matches a Studio 2 tilemap, so they
  stay faithful no-ops here exactly as they are in the shipped game.
- Tile, background and sprite drawable positions are **layer-relative**; the
  renderer adds the layer's own offset.
- 40 named room-feature stops remain, covering **38 layer effects** (`Effect_1`,
  sepia, pixelate, distort, twirl, flashback and similar) and **2 physics worlds**.
  The 25 rooms that need them are blocked rather than rendered without them.

### Yellow now starts

The startup blocker recorded earlier in this document is gone. Headlessly, the
converted Yellow manifest runs `rm_intro` (90 s of intro), takes a key press into
`rm_logos`, another into `rm_mmfirst`, and reaches **`rm_ruins00` with 24
instances**; 9 000 frames pass with no compatibility stop, and holding a direction
moves `obj_pl` 120 px in three seconds until geometry stops it. Getting there took
real implementations, not stubs:

- `display_set_gui_size`, the GUI/application-surface path and `draw_self`.
- **GMLive**: the pinned source is a shipped build whose GMLive is already inert
  (`live_call()` returns false, `live_init`/`live_update`/`live_room_start` are
  empty), so those 21 scripts now convert literally and behave as they do on a
  real device. Only the live-editing entry point itself, which uses Studio
  constructors this compiler cannot express, stays a named stop. Every Yellow
  event begins with `if (live_call()) return global.live_result;`, so this was the
  difference between a game that runs and one that stops in `obj_gmlive`.
- `port/yellow_studio.lua`: data structures (`ds_list`, `ds_map`, `ds_grid`),
  GPU blend modes, the extra drawing calls, primitives, cameras and viewports,
  gamepads, and the object/sprite/collision helpers.

Two documented deviations are reported on every run instead of being silent:

- **Texture groups do not exist here.** Assets are single files loaded on demand,
  so `texture_prefetch`/`texture_flush` have nothing to do, and the pinned
  decompilation carries no tag records for `asset_get_tags` to return.
- **Shaders are not converted.** `sh_palette_swap` and the other 16 shaders have
  no LÖVE equivalent, so a shader that would be set is reported and skipped and the
  scene keeps its original colours. `sprite_get_texture`/`texture_get_uvs` still
  return real values, because each sprite frame really is its own texture.

### Piece 5: what is implemented

- **One manifest, two worlds.** `tools/merge.py` writes
  `generated/merged/manifest.lua`, which `port/merge.lua` builds from the two
  conversions. Undertale keeps its recovered IDs below `YELLOW_BASE` (1 000 000)
  and Yellow keeps its band above it, and the merge *checks* that invariant rather
  than assuming it: Yellow's own numeric room references (`room_goto(56)`) only
  work because room IDs are `YELLOW_BASE + the project's own index`. Undertale's
  `names` stay authoritative; Yellow's names sit beside them in `yellow_names`,
  with the 4 colliding names resolved in Undertale's favour and listed in the
  report.
- **River Person → Yellow.** The boat already ends in `obj_dogboat_thing`
  travelling to one of three docks (70 Snowdin, 125 Waterfall, 140 Hotland).
  Holding **X** — the cancel button, on screen for touch — during the ride sends
  the same choice to the matching Yellow landing spot from Yellow's own fast-travel
  table: Snowdin dock → `rm_snowdin_11_yellow` (200, 100), Waterfall dock →
  `rm_dunes_05` (510, 170), Hotland dock → `rm_hotland_02` (170, 120). The
  native River Person dialogue is dispatched at repaired runtime label **770**;
  its three unused message slots are explicitly terminated so the writer cannot
  scan stale data. After Yes, `port/travel.lua` layers a category page over the
  native two-option chooser: **Yellow** pages through all seven Yellow labels with
  the coordinates from `obj_fast_travel_menu/Step_0.gml`, while **Undertale** keeps
  the original two dock choices. The native boat animation and `global.flag[459]`
  commit still perform the ride.
- **UGPS whale → Undertale.** `obj_fast_travel_menu` lists `global.fast_travel_list`
  and writes `global.fast_travel_newroom/newx/newy` for the highlighted entry, so
  the bridge adds three dock entries to that list with `ds_list_add` and fills the
  same three globals; Yellow's own whale code performs the trip. Frisk lands beside
  the dock room's own boat or player instance.
- **Initialization at both ends.** The first crossing into Yellow runs Yellow's
  own `scr_initialize()` before the room loads (its room creation code registers
  fast travel points, which needs the globals it creates), then makes sure exactly
  one `obj_controller` and one `obj_pl` exist. A later entry does not run that
  script again (piece 5d): it is a new-game reset. Persistent instances of the
  world being left are destroyed, so there is never a second player. Undertale
  needs no equivalent: the merged build boots through Undertale's own title flow.
- **Versioned merged saves.** Since piece 5d, `merge.sav` version 2 is the
  Player+World document (`docs/PORTING.md`). `[merge]` still carries `version`,
  `crossings`, `last_room`, `world`, `ammo` and `accessory`. `file0` and
  `Save.sav` stay as projections. A file with an unknown version is a named stop,
  not a guess. Version 1 is copied to `merge.sav.v1` and migrated; the copy is
  not deleted.
- **Packaging gate.** `tools/package.py --merged` refuses to build unless the
  Yellow conversion reached its rooms stage with no compile errors, and never
  regenerates Yellow itself.

### Piece 5, round 2: both travel services open (v1.2.1)

The owner reported that the River Person could not be used before Hotland and
asked for both services to be available from the start, reaching all of their
old and new stops. Four port-side rules do that; each one is reported on
startup under its own warning key.

- **`travel-river-service` — the boat's plot gate.** `obj_dogboat_thing`'s own
  Create event destroys the instance while `global.plot < 122` (set by the six
  `obj_undyne*` resources). `Travel:openRiverService()` wraps that one event:
  while it runs, `global.plot` reads 122; afterwards it is restored to whatever
  it was. Nothing else about the event changes. The separate River Person
  interaction repair adds only the three `%%%` terminators in the boat source;
  the audited `SCR_TEXT.gml` remains unchanged.
- **`travel-ugps` — the whale's own unlock.** `global.player_can_travel` is
  Yellow's switch for "this whale will carry you" (normally set by the
  Dunes-42 delivery scene). `Travel:openWhaleService()` sets the same switch
  after every Yellow-world initialization and re-asserts it each step, because
  `scr_initialize` resets it.
- **`travel-ugps` — the ten stops.** `Travel:offerWhaleDestinations()` adds the
  three Undertale docks and Yellow's seven own labels with Yellow's own
  `scr_fasttravel_add` (so de-duplication and Yellow's descending sort are
  Yellow's), memoized on the list handle and its size.
- **The merged ID space.** Yellow's menu writes its own project's room numbers
  (56, 81, 137, 175, 202, 211, 276). `Travel:beforeStep()` rewrites
  `global.fast_travel_newroom` for the highlighted or confirmed label to the
  merged room (`yellow_names.rooms`), because Undertale's room 56 is a
  different room from Yellow's. Dock labels keep the port's own landing read
  from the dock room's boat or player instance.
- **`travel-ugps-landing` — a whale's approach.** Every whale's fly-in ends
  when `fly_speed` compares equal to exactly zero; `fly_speed = 2` decremented
  by 0.2 never reaches zero in binary floating point (the tenth step is about
  2.8e-16, the eleventh is negative), so the whale hovered and the Mail/Travel
  dialogue never started. `Travel:landWhales()` reads that last step as the
  landing the next line expects — scene 1, still descending, speed below the
  decrement — and changes nothing else about the animation.
- **`view_camera` in the runtime.** `port/runtime.lua` now gives every viewport
  a camera and creates it when a room loads, because Yellow's code reads
  `view_camera[0]` directly (a mail station places its whale at
  `camera_get_view_y(view_camera[0]) - 40`). Before this, ringing any bell
  stopped the frame with *"Camera 0 does not exist"*.

### Piece 5, round 3: the particle system (v1.2.1)

Round 2 left one named stop: *"Snowdin - Forest"* lands in
`rm_snowdin_11_yellow`, whose `part_snow` needs GameMaker's particle system.
Round 3 implements it, so all ten UGPS stops and all three dock crossings
travel and land. 19 of Yellow's 32 Snowdin rooms place `part_snow` (an
earlier note said 20; the pinned source places it in 19).

- **`port/particles.lua` — the four families.** `part_system_*` (create,
  create_layer, destroy, exists, clear, draw_order, depth, position,
  automatic_update/draw, update, drawit), `part_type_*` (create, destroy,
  exists, clear, shape, sprite, size, scale, speed, direction, orientation,
  gravity, colour/color 1-3 and mix, alpha 1-3, blend, life, step, death),
  `part_emitter_*` (create, destroy, destroy_all, exists, clear, region,
  burst, stream) and `part_particles_create/clear` (plus the colour-tinted
  create). Systems tick once per game step after End Step and draw at their
  own depth among the instances and tiles; `part_snow`'s snowfall draws at
  −9999. Undertale calls none of these, so the family is inert there.
- **33 objects create systems** (37 reference the family; the other four only
  emit into or destroy systems owned elsewhere). A static test pins every
  `part_*` callee in the pinned source against the implemented set, so a new
  call site cannot slip past the suite.
- **Yellow's sprite numbers resolve through the merged band.**
  `part_type_sprite` sites pass the decompiler's raw numbers (636 for
  `spr_snowflake`, 665, 238, …). For a Yellow caller they resolve to
  `1000000 +` the number with a `particle-sprite:<n>` warning; a Yellow
  number with no banded sprite draws nothing and warns instead of drawing an
  unrelated Undertale sprite. Undertale callers keep exact IDs.
- **Documented particle deviations:** `part_system_create` ignores the extra
  argument two Yellow sites pass (`particles-create-args`); destroy/clear on
  a gone handle are lenient no-ops as in GameMaker, while burst/stream/create
  on one warn once per builtin (`particles-missing:<builtin>`);
  inverse-gaussian sampling is min/max-of-two-uniforms edge bias; shape pixel
  sizes are approximate (sprite particles are exact); fractional burst/stream
  counts are floored; particle ids start at 1 so a stored handle stays truthy
  in GML.
- **The same room needed three more rules, all riding along reported.** Its
  shadow system (`obj_shadow_master`, spawned by `obj_shadow_collider`)
  switches `object_get_parent()` against raw Yellow numbers (1130 for
  `obj_npc_base`, 1133, 1191) and creates `with(drawer_object)` /
  `instance_create_depth(..., 829/obj_shadow_drawer)` through them, so (1)
  `Runtime:resolveObjectIndex` bands any small object number a Yellow caller
  passes to `with`/select, `instance_create` and `instance_create_depth`
  (`object-band:<n>`; stale instance ids and Undertale callers are untouched),
  (2) new `object_get_parent` answers a Yellow caller in Yellow's number
  space so those switches match (both call sites are pinned by test), and (3)
  `texture_set_stage` joins the documented report-and-skip shader flow —
  `scr_draw_palette_shader` binds its palette through it on every shaded
  actor, and stopping there while `shader_set` is a skip was incoherent.
  `part_snow` itself, the shadow drawers and the palette binding are all
  proven in the Snowdin landing tests, headless and native.

### Piece 5: what shipped

- **Frisk-only rendering.** `port/frisk.lua` installs a draw-time sprite remap
  for merged manifests: 28 of Clover's walk-cycle poses (the four base
  directions plus Yellow's route, water, Snowdin and Steamworks-roof variants —
  Clover's up-walk has no recolours, which the pinned name list confirms) draw
  Undertale's `spr_maincharau/d/l/r`. The remap is pixels-only: sprite records,
  masks, `image_number` and every gameplay lookup keep resolving to Clover, so
  no room geometry or battle math changes, and Undertale's own sprite IDs are
  never in the table. Poses Frisk's set does not have stay Clover and are
  reported by name at startup (see below).
- **The X-run.** Yellow's own `scr_normal_state` already sprints while its
  `keyboard_multicheck(1)` cluster — X or Shift — is held; `scr_initialize`
  sets `global.player_can_run`, and `scr_determine_player_sprites` selects
  Clover's `spr_pl_run_*` cycle. No runtime change was needed: the merged build
  only had to prove it (speed 5 px/step against 3 walking, run sprites selected
  while held) and keep those run poses out of the remap, which is what the
  owner asked for.
- **Clover's ammunition and accessories as two extra slots.** Frisk's
  `global.weapon`/`global.armor` are untouched; Yellow's own pause menu equips
  its ammunition (weapon modifier) and accessories (armour modifier) through
  `scr_item_use`, swapping with `global.item_slot` and re-running Yellow's own
  determine scripts — the merged runtime adds nothing to that flow.
  `port/travel.lua` carries the loadout in `merge.sav` (`ammo`, `accessory`).
  That release re-applied it after every crossing, because `scr_initialize`
  reset both slots; piece 5b removed the re-apply (the slots are live shared
  equipment) and piece 5d skips `scr_initialize` on re-entry. The derived
  `player_weapon_modifier_attack` /
  `player_armor_modifier_defense` are recomputed through Yellow's own scripts,
  the same assignment `scr_initialize` itself makes.
- **Native fused-world gates.** `port/smoke.lua` now ends the LÖVE/xvfb gate
  with a fused section (merged archives only; a single-game archive stops by
  design and still passes): the placed dock boat with `global.plot=122` (the
  boat's own Create gate), X held through the ride, `gotoRoom(140)` — the call
  `obj_dogboat_thing` itself makes — landing exactly one `obj_pl` at Yellow's
  own 170,120 in `rm_hotland_02`, Frisk proven in the renderer's draw log and
  Clover's four walk sprites proven absent, then the whale's own travel globals
  bringing back exactly one `obj_mainchara` to the Waterfall dock, and
  `merge.sav` asserting version 1, both crossings and the equipment record.
  `tools/native_smoke.sh` requires the two new screenshots and refuses a merged
  gate that never ran the fused section.
- **Packaging.** `tools/package.py --merged` derives, from the converted
  records themselves, every pinned `yellow_src/` file the archive must carry
  (~19 400 asset files, ~280 MB) and stops the build if any is absent — a
  merged archive without them would draw nothing and play no sound.
- **The release.** `love-v1.2.0-fusion-experimental` publishes through the same
  draft-then-flip workflow as every earlier release, packaging with `--merged`
  and attaching both games' conversion reports.

### Piece 5: what stays Clover, and what is still unclaimed

1. **Poses without a Frisk equivalent** stay Clover: the `spr_pl_run_*` cycle
   (deliberately — it is the X-run the owner asked for), the revolver
   (`*_geno_shoot`, `goggleless_shoot`), the Steamworks goggles, the dance and
   the lying poses. Each is listed in the startup warning.
2. **Yellow's battles, shops, mail and story systems are unclaimed.** The
   travel hubs, one player per world and the equipment flow are proven
   headlessly and natively; fighting Yellow's enemies is not.
3. **Shaders stay reported-and-skipped** (the scene keeps its original
   colours), and the 25 rooms needing layer effects or physics worlds still
   stop with their own names.
4. **No Android-device certification.** The native gate is Linux LÖVE/xvfb
   with software GL and null audio; device GPU/audio/touch behaviour remains
   outstanding, for both worlds.

Both games also share one `global` namespace in a merged build. Names used by both
games refer to the same variable; crossing re-runs Yellow's own initializer, which
is what keeps its side consistent.
