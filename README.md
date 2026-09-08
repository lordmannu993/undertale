# UNDERTALE — experimental LÖVE / Android port

This checkout now includes a **GML-to-Lua converter, a LÖVE compatibility runtime,
and multi-touch controls**. The original GameMaker files are preserved.

**This is not a finished, full-game Android port.** Every source unit translates,
but the decompiled checkout is incomplete: the 38 referenced movement paths had
no point data in the export — their coordinates are now recovered from a pinned
upstream dump ([docs/PATHS.md](docs/PATHS.md)) and played back — while some
original numeric asset IDs (44 in statically recognizable reference positions)
and external resources remain unresolved or missing. Those problems, plus
remaining runtime fidelity work, prevent a full-game compatibility claim. No
native Android APK has been built or tested in this workspace. See [port status](docs/PORTING.md) and [validation](docs/VALIDATION.md).

## Download the experimental `.love` file

[**Download `undertale-love-v0.1.6-experimental.love` (~124 MB)**](https://github.com/lordmannu993/undertale/releases/download/love-v0.1.6-experimental/undertale-love-v0.1.6-experimental.love)

[Release notes, SHA-256 checksum, and conversion report](https://github.com/lordmannu993/undertale/releases/tag/love-v0.1.6-experimental)

Download the **`.love` asset**, not GitHub's automatic “Source code” ZIP. It
contains the generated Lua and supplied assets; you do not need Python or
GameMaker to use it. Open it with **LÖVE 11.5** on desktop or Android. It is not an
APK and requires the LÖVE runtime.

**This is an experimental prerelease, not a fully functional game port.** The
missing resources and native-testing limitations described above still apply.
The large archive is hosted as a GitHub Release asset rather than committed to
Git. To regenerate it yourself, follow the build instructions below.

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
- Recover and ship pinned exact-name resource registry evidence, reducing unresolved static references from 86 to 44.
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
Android recent-app card will keep running v0.1.0. Your save identity is unchanged.
The original flower tiles and gameplay collision layout are retained. v0.1.2 adds
reference-guided backdrop artwork only to the two incomplete opening rooms;
other rooms are not replaced by a generic background. Movement path point data
is recovered and played back from v0.1.4 (docs/PATHS.md); frame-level fidelity
against the original engine is not yet certified.

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
  vibration, reset, and a control tester.
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
built on. The per-claim detail for recovered data is in [docs/PATHS.md](docs/PATHS.md).

## Conversion and tests

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
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
