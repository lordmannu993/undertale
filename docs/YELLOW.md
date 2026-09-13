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
| 3 | All 3 224 Yellow objects and their events, with parents, masks and collision-event targets | not started |
| 4 | All 287 Yellow rooms: instances, creation code, tile layers from tilesets, backgrounds, views; plus the 68 paths | not started |
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

Piece 2 converts and validates scripts, but it does not make Yellow playable by
itself: objects and rooms remain pieces 3 and 4, so no Yellow room is entered yet.

## Verification

```bash
python3 tools/fetch_yellow.py --check          # offline: is the pinned source really there?
python3 tools/yellow_convert.py --stage assets # convert every sprite/sound/font/tileset
python3 tools/yellow_convert.py --stage scripts # convert assets plus all GMS2 scripts
.venv/bin/python -m pytest -q                  # offline unit tests + live gates when fetched
```

Live gates skip (never pass silently) when `yellow_src/` is absent, and CI fetches it, so
the full-asset conversion is proven on every pull request.
