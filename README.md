# UNDERTALE — experimental LÖVE / Android port

This checkout now includes a **GML-to-Lua converter, a LÖVE compatibility runtime,
and multi-touch controls**. The original GameMaker files are preserved.

**This is not a finished, full-game Android port.** Every source unit translates,
but the decompiled checkout is incomplete: 38 referenced movement paths are
absent, some original numeric asset IDs are unresolved, and external resources
are missing. Those problems, plus remaining runtime fidelity work, prevent a
full-game compatibility claim. No native Android APK has been built or tested in
this workspace. See [port status](docs/PORTING.md) and [validation](docs/VALIDATION.md).

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
coverage. That is not GPU, audio-device, Android, or full-playthrough testing.

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

## Conversion and tests

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

The converter processes **173 scripts, 1,703 objects, and 334 rooms**, including
all event and instance-creation code. It preserves zero-based GML arrays,
instance contexts, script arguments, numeric booleans, and original room order.
Generated code lives in `generated/`; it is reproducible, intentionally not
committed, and may be discarded after packaging to avoid duplicating the archive. The archive includes the generated code, so Python is not needed on
the phone.

`generated/conversion-report.json` records translation coverage, resource-ID
evidence, source repairs, every detected input key, and missing resources.
Unsupported syntax fails conversion. Missing movement paths/external sprite
loads stop with a diagnostic rather than inventing substitute gameplay.

### Source provenance

The original README described this as “Undertale src code,” said it was “most
likely decompiled,” and stated that the repository owner is not Toby Fox. No
permission to redistribute the original game or its assets is implied by this
port. Only package or distribute material you have the right to use.
