# Touch, keyboard, mouse and gamepad controls

## Normal play

| Touch | Keyboard / original action |
|---|---|
| D-pad | Arrow keys; supports diagonals and sliding |
| Z / CONFIRM | Z, mapped by the game's code to Enter; interact/confirm |
| X / CANCEL | X, mapped to Shift; cancel, skip text, slow movement where used |
| C / MENU | C, mapped to Ctrl; open in-game menu |
| KEYS | Open or close the extra-key panel; the game keeps running |
| PAUSE | Pause the port and open control settings |
| Android Back | Pause, rather than accidentally invoking game quit |
| Desktop F2 | Pause/settings; F2 is not used by the original source |

The original in-game name-entry grid works with the D-pad, Z and X. The letter
keys in KEYS supply actual keyboard keys; they do **not** replace the game's own
grid-based naming logic with a different name-entry system.

## Extra keys

**Actions:** Enter, Shift, Ctrl, Space, Esc, Backspace, Tab, Home, End, Page Up,
Page Down, Insert, Delete, Mouse L and Mouse R.

**ABC / 123:** A–Z and 0–9. Uppercase button labels correspond to the original
Windows virtual-key codes, not lowercase character ordinals.

**F / Numpad:** F1–F12 and numpad 0–9. Numpad 3 is deliberately included because
the source directly checks key code 99. Function keys are not confused with
lowercase ASCII letters.

Every detected concrete keyboard code is covered by a test. The source's
`vk_anykey` pseudo-key does not need its own button: pressing any actual keyboard
button satisfies it. Mouse buttons do not count as keyboard keys.

Opening KEYS or changing its page does not cancel a held D-pad thumb. Extra keys
already held when changing pages remain captured until that finger is released
(or slides outside its original button). This allows chords across pages. Closing
the panel releases its captured extra keys, not the other thumb's controls.

The two source mouse events are only in `obj_rainbowbolt_testgen`: global left
button down and global right button pressed. Touch the game image to aim and
hold/tap left mouse; Mouse R in KEYS uses the last aim location. Native mouse
movement/buttons also work. These debug/test actions are not needed for normal play.

## Multi-touch behavior

Each finger has its own source ID. Sources are combined before calculating held,
pressed and released edges. Consequently:

- Two fingers on Z still represent one held key; lifting either alone does not
  release it.
- Holding a hardware key while releasing the same touch key remains held.
- A quick tap entirely between two 30 Hz game ticks is stretched to one tick,
  with its release delivered on the next tick; it is not dropped.
- Moving a captured button finger to a different action releases the old action
  and presses the new one. Sliding out releases it; sliding back can reacquire it.
- The D-pad has a center dead zone, diagonal detection and diagonal-boundary
  hysteresis to reduce jitter. Sliding beyond the pad's capture margin releases
  movement.
- Resize/rotation cancels touch captures. Focus loss, app hiding and pause clear
  input and stop game updates, avoiding stuck controls and resume fast-forward.
- Synthetic touch-generated mouse events are filtered, avoiding duplicate input.

No control enables the source's debug mode. Debug-only buttons stay gated by the
original code. Esc retains the game's behavior: some scenes exit immediately,
others require a hold. Android Back is intentionally a safer pause action.

## Layout and settings

Landscape uses narrower, height-bounded side controls outside the game image;
portrait/4:3 reserves
a bottom deck. The game retains its aspect ratio. Aspect-preserving **Fit** scaling is the default and uses the whole available
area with nearest-neighbour filtering. PAUSE → SCALE switches to optional
integer-pixel scaling; small screens still downscale rather than crop. Safe-area insets are
included when LÖVE/Android reports them.

PAUSE offers size (80–125%), opacity (30–100%), left/right-handed layout, optional
vibration, reset and a control test screen. Settings are saved as validated plain
text in `touch-settings-v1.txt` in the app's save directory. No executable Lua is
loaded from settings/saves. Vibration is off by default.

A seventh PAUSE row, **COLLISION: ON/OFF**, exposes the game's own `phasing`
debug toggle (the keyboard equivalent lives on `obj_mainchara`): OFF walks
through walls. It is a testing aid rather than a setting, so it defaults to ON,
is never written to `touch-settings-v1.txt`, and is re-applied after an in-game
restart.

Extra-key panels temporarily cover the game picture; they are not intended to
replace the large D-pad/Z/X/C controls during normal battles. Very small windows
necessarily have smaller extra targets. Real-device reach, hit-target comfort,
latency and OS gesture conflicts have not yet been validated.

## Native gamepad mapping

| Gamepad | Key |
|---|---|
| Left stick / D-pad | Arrows |
| A | Z / confirm |
| B or X | X / cancel |
| Y or right shoulder | C / menu |
| Start | Enter |
| Back | Escape |
| Left shoulder | Shift |

Analog input uses 0.45 activation and 0.30 release thresholds to prevent drift.
Disconnect clears that controller's sources only. The Windows joystick poller is
reported unavailable to avoid duplicate events; the original joystick-config
screen is not used.

## Test on your device

Open **PAUSE → CONTROL TEST**, or run `love . --input-test` on desktop. Check held
key codes and edges while using two/three fingers, mixed hardware input, page
changes, quick taps, rotations, app switching and controller disconnects. Return
with BACK TO GAME. The tester does not advance gameplay.
