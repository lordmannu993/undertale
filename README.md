# UNDERTALE ⊕ UNDERTALE YELLOW — experimental LÖVE / Android port

This checkout now includes a **GML-to-Lua converter, a LÖVE compatibility runtime,
and multi-touch controls**. The original GameMaker files are preserved. Since
v1.2.0 it also merges **the whole of Undertale Yellow** into the same runtime as
one traversable world — see [docs/YELLOW.md](docs/YELLOW.md).

**This is not a finished, full-game Android port.** Every source unit translates,
but the decompiled checkout is incomplete: the 38 referenced movement paths had
no point data in the export — their coordinates are now recovered from a pinned
upstream dump ([docs/PATHS.md](docs/PATHS.md)) and played back — while some
original numeric asset IDs (86 in statically recognizable reference positions;
the pinned upstream registry dump is audit-only since v0.1.6, so no ID is
imported from it; the variable-mediated monster battle-part spawns are
recovered since v0.1.8 with per-site provenance) and external resources remain
unresolved or missing. Those
problems, plus remaining runtime fidelity work, prevent a full-game
compatibility claim. No native Android APK has been built or tested in this
workspace. See [port status](docs/PORTING.md) and [validation](docs/VALIDATION.md).

## Download the experimental `.love` file

[**Download `undertale-yellow-fusion-v1.2.2-experimental.love` (~390 MB)**](https://github.com/lordmannu993/undertale/releases/download/love-v1.2.2-fusion-experimental/undertale-yellow-fusion-v1.2.2-experimental.love)

[Release notes, SHA-256 checksum, and both conversion reports](https://github.com/lordmannu993/undertale/releases/tag/love-v1.2.2-fusion-experimental)

Download the **`.love` asset**, not GitHub's automatic “Source code” ZIP. It
contains the generated Lua and supplied assets for **both games**; you do not
need Python or GameMaker to use it. Open it with **LÖVE 11.5** on desktop or
Android. It is not an APK and requires the LÖVE runtime.

**This is an experimental prerelease, not a fully functional game port.** The
missing resources and native-testing limitations described above still apply —
to Undertale, and to Yellow's unclaimed battle and story systems (see the
release notes). The large archive is hosted as a GitHub Release asset rather
than committed to Git. To regenerate it yourself, follow the build instructions
below.

### Added in v1.2.2 — Snowdin Inn HP and River Person destinations

- **Snowdin Inn restores HP to at least the current maximum +10 at every LV.**
  The bonus is temporary current HP, not a permanent maximum-HP increase.
  Repeat stays do not stack it, and an existing higher HP value is preserved.
  Examples: LV 1 → 30/20 HP, LV 8 → 58/48 HP, LV 20 → 109/99 HP.
  This replaces the original low-level-only bonus table as requested.
- **The River Person Yellow destination fix is now in the download.** PR #27's
  corrected dialogue dispatch and terminated message slots make the Yellow
  destination selector reachable; all seven Yellow choices use their own
  landing coordinates. v1.2.1 was built before this fix and does not contain it.
- **A fresh, versioned fusion archive**, published only after the automated
  suite, merged packaging checks and native Linux LÖVE gate pass. Android
  device validation and full-game compatibility remain unclaimed.

### Added in v1.2.1 — every stop travels

- **Both travel services are open from the first frame.** The River Person's
  boat waits at every dock before Hotland (its plot guard is lifted for its
  own Create event only), and the UGPS whale offers all ten stops — Yellow's
  seven plus the three Undertale docks — visited or not. Whales finish their
  landing approach, and mail-station bells no longer stop the runtime.
- **The particle system, so Snowdin travels.** GameMaker's `part_*` builtins
  run in the runtime: `part_snow`'s snowfall draws over the forest, and the
  Snowdin-forest whale stop plus Undertale's Snowdin boat crossing land
  instead of stopping. All ten stops and all three dock crossings travel.
- **The forest's shadows and palettes come with it.** The room's shadow
  system resolves Yellow's raw object numbers through the merged ID band,
  `object_get_parent` answers Yellow callers in Yellow's number space, and
  palette-shader bindings join the reported-and-skipped shader flow.
- **Native Snowdin gate.** The release's LÖVE/xvfb gate lands in the forest
  natively and screenshots snowfall drawn there, on top of both crossings.
- **309 automated tests** passed for this release (was 285), including
  eleven particle unit tests, static pins against the pinned Yellow source,
  and both Snowdin landings proven headless and native.

### Added in v1.2.0 — the Undertale ⊕ Undertale Yellow fusion

- **Both games in one world.** The whole of the pinned Undertale Yellow v1.2.1
  decompilation — 287 rooms, 3,224 objects, 1,155 scripts, 3,796 sprites,
  673 sounds — converts into this port's runtime alongside Undertale, in a
  disjoint ID band so no Undertale ID moves. One boot, one save layer, one
  playthrough.
- **The River Person sails to Yellow.** Hold **X** (the on-screen cancel
  button) during a River Person boat ride and your destination lands in
  Undertale Yellow instead: Snowdin's dock → the Snowdin forest, Waterfall's
  dock → the Dunes, Hotland's dock → Yellow's Hotland. Yellow's UGPS mail
  whale lists the three Undertale docks and runs its own travel code to bring
  you back beside the dock's boat. **Both services are open from the start of
  a run**: the River Person's boat waits at every dock before Hotland, and the
  UGPS lists every stop it can fly to, visited or not.
- **Frisk everywhere.** Yellow's player keeps its own mechanics but is drawn
  as Frisk; holding **X** while walking runs at Yellow's run speed with
  Clover's `spr_pl_run_*` animation — the pose family Frisk's set doesn't
  have. Gun poses, goggles and dance poses stay Clover, reported by name.
- **Clover's ammunition and accessories join Frisk's equipment.** Frisk keeps
  Undertale's weapons and armours; Yellow's own pause menu equips Clover's
  ammo (weapon modifier) and accessories (armour modifier) into two extra
  slots that feed Yellow's attack/defense math, and the loadout persists in
  the versioned merged save (`merge.sav`) across crossings.
- **Native fused-world gate.** The release's LÖVE/xvfb gate plays the Undertale
  opening, then crosses into Yellow and back natively: one player per world,
  Frisk rendered in Yellow, and `merge.sav` recording both crossings.
- **285 automated tests** passed for this release (was 255 at the last validation), including the
  Frisk remap, the X-run, menu-driven equips, save restore across crossings,
  and packaging gates that refuse to ship a merged archive missing any of the
  ~19,400 referenced pinned asset files.

### Added in v0.1.10

- **Glyde encounters are 20× faster.** The ice-cave encounterer's step timers
  are cut to 1/20 of stock (`scr_steps` 3600+random(150) → 180+random(7.5)
  first, 840+random(680) → 42+random(34) on repeats), so farming Glyde no
  longer means walking in circles for ages. The population factor is
  untouched.
- **A "709 EXP" button in the STAT menu.** The STAT screen shows one
  heart-selected row, **"709 EXP"**; confirming it adds 709 real EXP and runs
  the game's own `scr_levelup`, so LOVE and stats rise exactly as if the EXP
  came from battle. It touches only `global.xp`: the kill counter and every
  route flag stay untouched, so pacifist runs still complete and neutral runs
  stay neutral. Repeatable.
- **Sans's judgment notices a bloodless LV rise.** If you reach the Last
  Corridor with raised LOVE but zero kills, Sans questions how your LOVE went
  up after his usual EXP/LOVE explanation — then lets it go ("... but you
  didn't hurt anyone... it doesn't really matter... i'm still rooting for
  you"). True LV-1 pacifists still get the untouched classic speech.
- **185 automated tests** passed for this release (was 181), including four new
  cases: Glyde timer values, vanilla leveling math, a player-driven menu run
  of the button, and the Sans judgment branching verified end-to-end through
  the real converted scene.

### Fixed in v0.1.9

- **Alarms no longer fire twice — fixing the Snowdin tile-puzzle softlock and
  every doubled text, enemy and dialogue.** GameMaker alarms are one-shot:
  they reset to −1 when they fire. The runtime left them armed, so every alarm
  event in the game ran twice. `obj_papyrus4` advances its cutscene with
  `alarm[4]++`, so the double-fire skipped the tile-wait state and the scene
  stalled with the player frozen and Papyrus standing still; every
  alarm-spawned speech bubble, damage number, bullet and dialogue box was also
  created twice, drawn overlapping itself.
- The runtime now resets each alarm to −1 before running its event, matching
  GameMaker; events may still re-arm recurring alarms.
- **181 automated tests** passed for this release (was 179), including two new
  regressions — an alarm one-shot unit test and a headless Papyrus4
  playthrough to plot 58 with control restored — each verified to fail on the
  unfixed code.

### Fixed in v0.1.8

- **Starting battles outside the Ruins no longer crashes with "Port
  compatibility stop: instance_create Missing object ID 255."** Part-based
  monsters spawn their artwork through variables holding bare original object
  IDs (`part2= 255;` then `instance_create(x, y, part2)`); without decompiler
  annotations those IDs stayed synthetic and every such battle stopped the
  instant it began — including *every* enemy encounter in Snowdin (Snowdrake,
  Doggo, Dogamy & Dogaressa, Greater Dog, Gyftrot, Glyde, Papyrus) and the
  part-based Waterfall, Hotland and True Lab battles.
- The 22 missing part-object IDs are recovered by `tools/recover_parts.py`:
  each ID is this checkout's own numeric literal, paired with the object name
  the pinned upstream decompilation uses for the same statement, with the 38
  already-annotated part sites re-validated as anchors and per-site provenance
  committed in `port/recovered_parts.json`. All 59 part spawn sites now resolve.
- **179 automated tests** passed for this release (was 163), including 16 new
  regressions: provenance/no-invention checks, a static guard over every part
  spawn site, and end-to-end battle tests for every Snowdin battlegroup. Each
  was verified to fail on the unfixed code with the reported crash signature.

### Fixed in v0.1.7

- Toriel's hand-in-hand crossing of the Ruins spike maze no longer walks her and
  the player off-camera (`obj_torhandhold1` started the recovered
  `path_torielwalk5_2` with GameMaker's *relative* flag while the recovered points
  are room-absolute, so the crossing, its dialogue and the hand-back of control
  happened outside the 1200x240 room). The scene now ends in view, control
  returns, and the farewell dialogue completes. The deliberate deviation from the
  pinned decompile is listed with its evidence in [docs/PATHS.md](docs/PATHS.md).
- Holding **X**/Shift to skip text no longer leaves a stalled text writer alive
  under the next bubble: `scr_textskip` now runs the same halt-state handling as
  the writer's own confirm key, including handing control back and destroying the
  stale writer. Overlapping dialogue is gone.
- **PAUSE** gains a seventh row, **COLLISION: ON/OFF**, exposing the game's own
  phasing debug toggle to touch: OFF walks through walls. It is a testing aid —
  runtime-only, never saved to the touch settings, and it defaults to ON.
- **163 automated tests** passed for this release (was 160), including three new
  regressions that were each verified to fail on the unfixed code.
- Corrected a stale limitation count: this README and `docs/PORTING.md` claimed
  **44** unresolved numeric asset IDs, while the conversion report inside the
  archive has listed **86** since v0.1.6 made the pinned upstream registry dump
  audit-only. `docs/CONTROLS.md` now documents the new PAUSE COLLISION row.

### Fixed in v0.1.6

- Toriel now faces the path tangent while following movement paths, including
  reverse travel; stopped paths preserve the scripted facing.
- Void the incompatible upstream registry import and restore all 13 verified
  Toriel dialogue-face sprite IDs, so dialogue portraits no longer show
  placeholder or unrelated sprites.
- Alarm timers now fire when they cross zero, so the first Froggit encounter
  starts normally.
- **160 automated tests** passed for this release.

### Fixed in v0.1.5

- Restore the missing Toriel/Asriel directional and talking sprite IDs
  (`spr_toriel_ut` 1111, `spr_toriel_handhold_d` 1113, `spr_toriel_handhold_u`
  1117, `spr_asriel_dt` 2418, `spr_asriel_ut` 2420, `spr_asriel_rt` 2422,
  `spr_asriel_l` 2424, `spr_asriel_lt` 2425): Toriel's up/hand-hold poses and
  Asriel's overworld reveal no longer draw blank.
- Regression coverage now asserts every directional/talking sprite ID the
  Toriel/Asriel overworld objects assign resolves to a real, non-empty sprite,
  and that the restored IDs are not synthetic.

### Fixed in v0.1.4

- Recover point data for all 38 referenced movement paths from one pinned
  upstream GameMaker project dump (per-path provenance in
  [docs/PATHS.md](docs/PATHS.md)) and play them back at GameMaker's
  pixels-per-step speed: Toriel's walk to the ruins no longer stops the scene.
- The packaged build is gated on a native Linux LÖVE run that asserts Toriel is
  actually drawn displaced along the recovered path, plus a route test that
  drives the real scripted fight and dialogue into `room_ruins1`.
- Recover and ship pinned exact-name resource registry evidence, the registry is audit-only; unresolved static references remain 86.
- Recover the missing Hotland room 159 source with provenance and include it in the archive; the GMS2-to-GMX adapter remains experimental and the runtime still stops explicitly at that slot.
- Preserve reproducible conversion reports and source provenance in the downloadable archive.

### Fixed in v0.1.3

- End-of-battle sprite glitch and permanent softlock after Flowey's tutorial
  fight are gone. The damaged export negated `obj_dialoguer`'s `obj_face`
  cleanup guards in two events, so dialogue face portraits were never destroyed:
  Flowey's face followed the player out of the battle, stacked on Toriel's, and
  the leftover Toriel face blocked `obj_floweytrigger`'s
  `!instance_exists(obj_torface)` wait forever. Both guards are restored against
  the shipped game's decompilation, each with its own source-hash guard.
- Restore the verified Toriel directional sprite IDs (`spr_toriel_dt/r/l/rt/lt`
  = 1105, 1107–1110) in the resource overrides, keeping the existing anchors.
- New regression plays the whole tutorial fight like a player and checks that no
  face leaks, play returns to `room_area1_2`, Toriel speaks and starts leading to
  the ruins door, control is restored, and every face is cleaned up.
- **145 automated tests** now pass.

### Also fixed in v0.1.2

- Restore the missing opening chamber floor, light rings, corridor and doorway
  using the supplied reference views, palette and room coordinates. These are
  explicitly reconstructed backdrops, not recovered original tile records.
- Repair the damaged export's reversed switch-label bindings: Flowey now says
  the SOUL tutorial, not Undyne's chair prompt. Verified item/phone/encounter and
  Papyrus-call tables are repaired too, with source-hash guards.
- Correct original font IDs and malformed text-setup spacing arguments.
- Check the actual dialogue words and bubble bounds, plus native floor/ring/door
  pixels and five scene screenshots; **143 automated tests** passed at that release.

### Also fixed in v0.1.1

- Flowey now enters the tutorial room, rather than an empty test battle: the
  converter preserves missing original room ID 159 instead of shifting later IDs.
  Normal battles, game-over, and other later room references are corrected too.
- The phone play area is larger: narrower side rails and full-area **Fit** scaling.
  Optional **SCALE: INTEGER** remains available in PAUSE settings.
- Regression coverage now includes the actual Flowey transition and a native Linux
  LÖVE smoke test with touch callbacks and pixel checks, required before publishing.

Close the old running game and open the new, versioned download; resuming the old
Android recent-app card will keep running the older build (v0.1.6 or earlier).
Your save identity is unchanged.
The original flower tiles and gameplay collision layout are retained. v0.1.2 adds
reference-guided backdrop artwork only to the two incomplete opening rooms;
other rooms are not replaced by a generic background. Movement path point data
is recovered and played back from v0.1.4 (docs/PATHS.md); frame-level fidelity
against the original engine is not yet certified.

## Undertale Yellow merge — complete

A second game is merged into this port: **Undertale Yellow v1.2.1**, from the
pinned public decompilation
[`lordmannu993/UnderTale-Yellow`](https://github.com/lordmannu993/UnderTale-Yellow).
The result is **one traversable world**, not two builds side by side: Undertale's
River Person and Yellow's UGPS mail whale each carry destinations into the other
game's areas, Frisk is the only playable character (Clover's sprite set supplies
what Frisk's does not have, including a run animation on the X button), and Frisk
keeps Undertale's weapons and armours beside Clover's ammunition and accessory
slots.

Yellow is a GameMaker **Studio 2** project, so it needed its own front end before
any of it could run. That work was split into five pieces, tracked in
[docs/YELLOW.md](docs/YELLOW.md), each landed as its own pull request.

| piece | what it delivers | state |
|---|---|---|
| 1 | Pinned source pipeline; every Yellow sprite, sound, font and tileset converted into the port's asset records, with Yellow's own numeric IDs recovered from two records inside the pinned source | **complete** |
| 2 | GameMaker Studio 2 GML in the compiler; all 1,155 Yellow scripts converted with name-resolved calls and GMS2 runtime adapters | **complete** |
| 3 | All 3,224 Yellow objects and their 8,494 events, with parents, masks and collision-event targets, plus the event dispatches they need (Clean Up, Draw Begin/End, Draw GUI, per-instance mouse) | **complete** |
| 4 | All 287 Yellow rooms, tile layers and paths, with tile transforms, animation and the `layer_*` families | **complete** |
| 5 | The connected world: cross-game travel through both hubs, Frisk-only rendering with Clover's X-run, Clover's ammo/accessory slots, versioned merged saves, packaging and the fused native release gate | **complete** (v1.2.0; both services open and the particle system in v1.2.1) |

Yellow's ~580 MB of assets are fetched from the pinned commit at build time
(`python3 tools/fetch_yellow.py`) and are never committed to this repository;
the v1.2.0 `.love` carries every referenced file inside the archive. What stays
unclaimed is documented in the release notes: Yellow's battle system, palette
shaders (reported and skipped), the 25 rooms whose layer effects or physics
worlds have no GameMaker 1.4 equivalent (they stop with their own names), and
any Android-device certification.

## Run with LÖVE

Install **LÖVE 11.4 or 11.5** and **Python 3.10+**. No GameMaker installation or
Python dependencies are needed to convert/package the game.

```sh
python3 tools/convert.py
love .
```

Windows: use `python` instead of `python3`, and your installed `love.exe`.

```sh
love . --touch          # show the mobile layout on a desktop
love . --input-test     # test multi-touch/keyboard/gamepad input without advancing the game
```

The original opening, title, naming screen, initial movement, menu/cancel,
first room transition, and save/load scripts have automated **headless LuaJIT**
coverage. The release pipeline also checks native Linux rendering. Neither constitutes
Android hardware, audio-device, or full-playthrough validation.

## Build the Android-loadable archive

```sh
python3 tools/package.py
```

Output:

- `artifacts/undertale-love-experimental.love`
- `artifacts/undertale-love-experimental.love.sha256`
- `artifacts/undertale-love-experimental.conversion-report.json`

A `.love` file is a ZIP containing the converted Lua and existing assets, with
`main.lua` at its root. It is **not an APK**. Open it with the official LÖVE Android
runner, or follow [Android APK instructions](docs/ANDROID.md) to embed it in a
standalone **development** APK.

```sh
# Requires JDK 17 + the Android SDK/NDK described in docs/ANDROID.md.
python3 tools/build_android.py --allow-experimental
```

There is also a manual **Experimental Android APK** GitHub Actions workflow.
It has not been executed as part of this change.

## Touch controls

- Eight-way **D-pad**, with sliding and a center dead zone.
- **Z** confirm/interact, **X** cancel/slow movement, **C** in-game menu.
- **KEYS** opens Enter, Shift, Ctrl, Space, Escape, Backspace, navigation keys,
  A–Z, 0–9, F1–F12, numpad keys, and the two mouse buttons used in a test room.
- **PAUSE** provides size/opacity adjustment, left-handed layout, optional
  vibration, reset, a control tester, and (from v0.1.7) a runtime-only
  **COLLISION** toggle for testing.
- **AUTO RUN** (merged build): PAUSE also shows **AUTO RUN: ON/OFF**, saved with
  the other settings. It drives Undertale Yellow's own option of that name —
  moving runs, and the run button (**X**) walks instead.
- Android **Back** pauses. Desktop **F2** opens the same pause screen.
- Simultaneous fingers, gamepads, and physical keys have independent ownership;
  lifting one source does not cancel another. Short taps survive between ticks.
- Layouts respect the screen safe area, preserve aspect ratio, and reserve a
  control area outside the game image. Portrait uses a bottom control deck.

See [all mappings and behavior](docs/CONTROLS.md). “Perfect” controls are not
claimed: real-device comfort, latency, OS interruptions, and different Android
screens still need testing.

## For agents continuing this port

Start at [AGENTS.md](AGENTS.md): current state, the open piece list, sandbox gotchas
(no LOVE in the sandbox, so the native gate runs in CI) and the rules this repo is
built on. The per-claim detail for recovered data is in [docs/PATHS.md](docs/PATHS.md),
and the Undertale Yellow merge has its own piece list in
[docs/YELLOW.md](docs/YELLOW.md).

## Conversion and tests

```sh
python3 -m pip install -r requirements-dev.txt
python3 tools/fetch_yellow.py                 # optional: the pinned Yellow source (~309 MB)
python3 tools/yellow_convert.py --stage objects # optional: pieces 1-3 of the Yellow merge
python3 -m pytest -q                           # 255 tests; Yellow live gates skip without the fetch
```

The converter processes **173 scripts, 1,703 objects, and 334 rooms**, including
all event and instance-creation code. It preserves zero-based GML arrays,
instance contexts, script arguments, numeric booleans, and original room order.
Generated code lives in `generated/`; it is reproducible, intentionally not
committed, and may be discarded after packaging to avoid duplicating the archive.
The archive includes the generated code, so Python is not needed on the phone.

`generated/conversion-report.json` records translation coverage, resource-ID
evidence, source repairs, every detected input key, and missing resources.
Unsupported syntax fails conversion. Missing movement paths/external sprite
loads stop with a diagnostic rather than inventing substitute gameplay.

### Source provenance

The original README described this as “Undertale src code,” said it was “most
likely decompiled,” and stated that the repository owner is not Toby Fox. No
permission to redistribute the original game or its assets is implied by this
port. Only package or distribute material you have the right to use.
