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
| 4 | All 287 Yellow rooms: instances, creation code, tile layers from tilesets, backgrounds, views; plus the 68 paths | **in progress** — complete source conversion, partial static rendering; animation/transform parity remains |
| 5 | One world: River Person + UGPS cross-game destinations, Frisk as the only player (Clover's run sprites on X), Frisk's weapons/armours plus Clover's ammo/accessories, saves, packaging, release | not started |

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
   rotated-rectangle masks, GMLive and the Steamworks/Steam hooks have no GameMaker 1.4
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
| `collisionKind` 4 = rotated rectangle (74 sprites) | no GM 1.4 equivalent; recorded and reported, resolved in piece 3 where the masks are used |
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

## Pieces 4–5 work in progress (2026-09-13)

**This is not completion of the requested combined chunks. Do not merge or release
it as a connected game.** Piece 5 has not been implemented. Existing Undertale
packaging and release links remain unchanged, and do not include Yellow.

Implemented so far:

- `tools/yellow_convert.py --stage rooms` builds the earlier stages plus all
  **287 rooms**, **68 paths**, **7,637 placed instances**, **1,340 room/instance
  creation-code files**, and **199,258 static/animated drawable records**.
- `tools/yellow/rooms.py` validates tile RLE cardinality, resolves references
  through the pinned registry, uses `RoomOrderNodes` for traversal order and
  `instanceCreationOrder` for creation order, and retains original layer records.
  Path coordinates/speeds/kind/closure/precision are copied, not inferred.
- Editor instance IDs are explicitly **port handles**, reversibly encoded as
  `2**32 + hexadecimal inst_ suffix`. They are not claimed to be recovered numeric
  GameMaker runtime instance IDs. The band does not overlap runtime-created or
  Undertale editor instances.
- Room layer depth, instance transform/colour/alpha/image fields and numeric view
  target IDs reach the runtime. Static sprite asset layers and static sprite
  backgrounds can render without rebinding Undertale's asset names.
- Unsupported room features stop **before** the old room receives Room End or
  Clean Up. The generated report enumerates **506 feature findings across 107
  rooms**: animated tiles/sprite assets, tile transform flags, moving backgrounds,
  depth-sorted colour layers, effects and physics. Some findings refer to hidden
  layers; these are conservatively blocked rather than silently losing features
  when game scripts later enable them.
- Fixed `fetch_yellow.py` deleting its non-cached tarball *before* extraction.
  Both cached and temporary download paths have regression tests.

Validation: the full local headless suite passed **272 tests**, including the
**15-test** focused room suite. The live gates compile every generated room and its manifest in
Lua 5.1 and LuaJIT, assert the pinned counts, and compare all 68 paths directly
against their `.yy` source. These tests do **not** establish native Yellow pixels,
working Yellow gameplay, or cross-game travel.

Concrete startup blocker: starting the generated Yellow manifest headlessly reaches
`obj_controller [Create] in rm_intro`, then stops at **`display_set_gui_size`**.
No GUI-size handler has been silently stubbed. Getting past this one call would
not prove the remaining game works.

Remaining before completing pieces 4–5:

1. Implement and verify animation timing, transformed tile drawing, layer
   visibility/mutation and colour-depth behavior; add native Yellow render gates.
   Check Studio instance image-speed multipliers against sprite playback speed.
2. Resolve the startup and reachable-room runtime builtin gaps, preserving named
   stops for explicitly unsupported effects/physics instead of claiming parity.
3. Implement and test River Person ↔ UGPS routing and game initialization at both
   ends, with no duplicate persistent controller/player instances.
4. Add Frisk-only rendering plus X-run, ammo/accessory equipment integration, and
   versioned shared saves with old-save migration and round-trip tests.
5. Add an opt-in merged manifest/package with collision-safe script/asset
   namespaces, build gates and native travel/save tests. Only then publish a new
   immutable experimental release and update download links.
