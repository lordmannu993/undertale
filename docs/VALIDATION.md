# Validation record and remaining device checklist

## Executed in this workspace

Validation date: **2026-09-06**.

- Converted all **20,285** source units with **zero parse failures**.
- Compiled every generated Lua chunk, runtime module, `main.lua` and `conf.lua`
  with both **LuaJIT 2.1** and **Lua 5.1** (through Lupa).
- **101 tests passed** in the automated pytest suite; it covers:
  - GML expressions, strings/comments, numeric booleans, zero-based/2D arrays,
    post-increment, loops, break/continue, switch fall-through and large-switch
    partitioning, `with`/`other`, locals, inheritance and script arguments.
  - The actual converted opening story, title, naming grid, initial overworld
    movement, C menu, X cancel, first doorway, and original save/load scripts.
  - Input ownership, two fingers plus a hardware key, auto-repeat suppression,
    between-tick taps, key remapping/direct checks, cancellation, gamepad drift,
    disconnect, mouse isolation, D-pad sliding, and cross-page held keys.
  - Safe-area layout bounds at eight window/inset configurations, three control
    sizes and both handedness settings (**48 layout combinations**).
  - Every detected concrete keyboard key has a touch target; the two detected
    mouse event types also have targets.
  - INI/text save round trips, full-heal-on-load behavior retained from the
    original scripts, path traversal rejection, audio-handle state/fades,
    collision geometry, room persistence restoration/invalidation, asset reset
    on restart, and explicit errors for missing path/external resources.
- Built the `.love` archive twice in the packaging test and verified identical
  SHA-256 digests, root entry points, normalized timestamps, CRCs, bundled assets,
  and exclusion of scratch code, GameMaker XML, saves and repository metadata.
- Android preflight correctly reports that **JDK 17 is absent**. No Android SDK,
  Gradle native compilation, signing, installation, or device playtest occurred.

Run the current suite and see its live test count:

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

**These are headless engine/input tests.** Sprite pixels, GPU drawing, codecs,
physical speakers, touchscreen events and Android OS callbacks are not exercised
by the headless tests. Collision pixel masks fall back to bounding geometry in
that mode. Passing them must not be presented as full native or game-route QA.

## Unchecked: native LÖVE

- [ ] Launch the packaged `.love` in LÖVE 11.4/11.5, not just an unpacked folder.
- [ ] Compare intro/title/menu glyphs, sprite origins, colors and transparency
      with a reference recording.
- [ ] Compare music volume, text voices, loops, pitch, seeking and fades.
- [ ] Check rectangle/pixel collisions, diagonal walls and moving bullet patterns.
- [ ] Confirm 30 game ticks per second on 30/60/90/120 Hz displays; redraws must
      not accelerate Draw-driven gameplay.
- [ ] Verify every room transition, camera, inherited event and persistent room.
- [ ] Recover the missing source assets/IDs and validate every path/boss/route.

## Unchecked: Android

Suggested matrix (not devices already tested): small 16:9 phone, tall notched
phone, 4:3 tablet, arm64 low-memory device, and a newer 16 KB-page device with an
appropriately rebuilt runner.

- [ ] Build the debug APK with the pinned toolchain and verify the embedded
      archive/package ID/orientation. Do not treat the supplied workflow as a
      completed build.
- [ ] Install and cold-launch offline, including after force-stop/reboot.
- [ ] Hold movement + Z/X/C with two/three fingers; test repeated quick taps and
      opposite-direction changes under load.
- [ ] Try every extra-key page and chord, including Space, Enter, Ctrl, Shift,
      Escape hold, Backspace, F4, letter/number shortcuts and numpad 3.
- [ ] Use the original naming screen, battle controls and every puzzle/minigame.
- [ ] Mix keyboard, gamepad and touch without premature releases or duplication.
- [ ] Swipe between buttons, off a button, through the D-pad center, and back.
- [ ] Test Android Back, app switch, notification shade, lock/unlock, calls,
      rotation, multi-window resize and controller disconnect while holding keys.
- [ ] Confirm no stuck keys, delayed ghost presses or battle fast-forward on resume.
- [ ] Verify both landscape orientations, notch/gesture safe areas, portrait in the
      general LÖVE runner, left-handed mode, size/opacity settings and optional
      vibration. Assess reach and touch-target comfort on physical screens.
- [ ] Save/relaunch/load in app-private storage; simulate interrupted writes and
      verify the old save survives. Verify cache eviction/low-memory recovery.
- [ ] Measure sustained frame time, memory, temperature and audio latency.
- [ ] Validate current Android permissions, SDK target and native page-size support
      before any public release.

## Reporting a failure

Include the room/object/event from `last-port-error.txt`, the conversion report,
steps to reproduce, route/save state, LÖVE version, device model, Android version,
screen size/insets, and whether a physical keyboard/gamepad was connected.
Do not attach credentials. Never replace a missing path with a no-op to make a
smoke test pass; report and recover the missing source data instead.
