# Debug baseline — architecture map + reproduction harness (piece D0)

> **Piece:** D0 of [`DEBUG_QUEUE.md`](DEBUG_QUEUE.md) (brief §9). This file is the
> architecture map and the captured output of the reproduction harness
> [`tools/debug_probe.py`](../tools/debug_probe.py). **D0 changes no behaviour.**
> Every fix belongs to pieces D1–D5, each of which must add a test that fails
> without its change. The numbers below are the baseline those pieces must beat.

Everything here is verifiable in-repo: boot the merged build headlessly exactly
like the test suite does and run the probe. Commands:

```bash
python3 tools/fetch_yellow.py --tarball-cache .yellow-cache      # once
python3 tools/convert.py && python3 tools/yellow_convert.py --stage rooms && python3 tools/merge.py
python3 tools/debug_probe.py            # full run (plays the Undertale opening)
python3 tools/debug_probe.py --quick    # reduced budget; tests/test_debug_probe.py runs this
```

The probe boots `generated/merged/manifest.lua` with `{headless=true, trace=true,
memorySaves=true, seed=42}` (same recipe as `tests/conftest.py` and
`port/smoke.lua`), so draws are recorded in `R.drawLog` instead of a GPU and two
runs agree. It refuses to run unless the Yellow conversion is at the `rooms`
stage, because the suite's own tests re-run earlier stages on `generated/yellow/`.

---

## 1. The architecture map (the traced path)

The trace below follows one fused play session: **GAME START → room init →
player init → Undertale play → River Person → boat → transition → Yellow room →
player update/draw → dialogue draw → return transition → Undertale room.**
File/function names are the ones that own each step.

### 1.1 Boot and GAME START

| step | owner | notes |
| --- | --- | --- |
| LÖVE callbacks | `main.lua` | `love.update` accumulates real time and runs whole game ticks at `1/vars.room_speed`; one tick = `input:beginFrame → R:step → R:renderFrame → R:finishFrame → input:endFrame`. `love.draw` only presents the cached `game.canvas`. |
| manifest choice | `main.lua` (`boot`) | A merged build ships `generated/merged/manifest.lua` (built by `tools/merge.py` from `generated/manifest.lua` + `generated/yellow/manifest.lua` through `port/merge.lua`); a single-game build uses `generated/manifest.lua`. |
| runtime construction | `port/runtime.lua` `Runtime.new` | Installs, in order: builtins, storage, audio, **graphics**, collision, **yellow_studio** (Studio-2 cameras/views/surfaces), **yellow_layers**, particles, **yellow_builtins**, then the fusion bridges: **`port/player.lua`** (shared progression), **`port/inventory.lua`**, **`port/save.lua`** (`merge.sav` v2), **`port/travel.lua`** (world crossings), **`port/frisk.lua`** (Frisk-only rendering), **`port/controller.lua`** (one controller). |
| GAME START | `Runtime:start → loadRoom(manifest.room_order[1])` | Undertale's own title flow; `SCR_GAMESTART` runs when `obj_time` recreates on Undertale's side. `travel.world` is seeded from the band of `room_order[1]` (`worldOf`). |

### 1.2 Room init and player init

* **Rooms** — one system for both games: `Runtime:gotoRoom(index)` sets
  `pendingRoom`; `applyTransitions` drains it through `Runtime:loadRoom`.
  `loadRoom` runs Room End, stores/restores persistent rooms, seeds
  `vars.view_*`/`background_*`, creates the room's editor instances
  (`Runtime:create`, deferred), runs Create events, instance creation code,
  then the room's own creation code. Studio-2 (Yellow) rooms additionally carry
  `room.layers`, and `Runtime:buildLayerElements` (from `port/yellow_layers.lua`)
  materialises tile/asset/sprite layer elements; Yellow drawables are drawn by
  the closure `port/yellow_graphics.lua` installs.
* **World separation** — purely by **ID band**: Undertale keeps its recovered
  GameMaker 1.4 indices; Yellow sits at `YELLOW_BASE = 1,000,000` and above
  (`port/merge.lua` enforces both bands and records every same-name pair as
  `double_named`: 10 sprites, 10 objects, 21 sounds, **1 font — `fnt_main`**).
  `manifest.objects/scripts/rooms/paths` are read-through proxies (Undertale
  first, then Yellow); `Runtime:callerIsYellow(E)` and `assetOwnerIsYellow(E)`
  decide which world a running script or a dynamic asset lookup belongs to;
  `Runtime:resolveObjectIndex` re-bands Yellow's raw decompiler object numbers.
* **Player init** — Undertale: the room places `obj_mainchara` (Frisk). Yellow:
  rooms place `obj_pl` (Clover's mechanics, drawn as Frisk by `port/frisk.lua`).
  Progression is **one `R.player` record** (`port/player.lua`): every spelling
  (`hp`/`current_hp_self`, `lv`/`player_level`, …) is a metatable view on it, so
  neither world's initializer can create a second protagonist; Yellow's
  `scr_initialize` runs under `playerBridge:withDefaults` on first entry.
* **Controllers** — `port/controller.lua` installs one `R.player.controller`
  shared by both adapters (one facing, one run rule, one movement speed).

### 1.3 Undertale play

`Runtime:step` runs the GameMaker event order over a snapshot of
`R.instances`: Begin Step → alarms → keyboard → mouse → Step → movement →
collision events → Outside/Intersect → End Step → particles → `compact` →
`applyTransitions` → `updateViews` (camera follow). `travel:beforeStep` is
wrapped around every step (X-hold boat latch on the Undertale side; AUTO RUN,
whale landing and fast-travel globals on the Yellow side). `renderFrame`
paints one canvas per tick: sorted depth list of tiles + instances + particle
systems, view transforms, Draw Begin/Draw/Draw End passes, then the GUI passes
(`8:74/8:64/8:75`) in display space.

### 1.4 River Person → boat → transition (Undertale → Yellow)

1. The boat is `obj_dogboat_thing` (Undertale). Its own Create deletes it below
   `global.plot < 122`; `Travel:openRiverService` lifts that guard for that one
   event so every dock has a boat from the first frame.
2. Interacting drives Undertale's own `SCR_TEXT` switch (repaired labels
   770–773). `Runtime:script` is wrapped so `Travel:afterRiverText` sees the
   switch value and layers the fused pager (world choice + Yellow stops) over
   the native two-slot chooser. A choice calls `Travel:finishRiverChoice`,
   which writes `global.flag[459]` (the boat's own dock flag) and, for a Yellow
   stop, sets `riverDestination` + `riverLatch` and resumes the boat (`con=0.1`).
3. The boat's Step machine (converted `generated/objects/obj_dogboat_thing.lua`)
   then calls `room_goto(316)` (boarding/ride room) and later
   `room_goto(70/125/140)` by `flag[459]`.
4. **Every `room_goto` passes `Travel:resolve`** (the wrapper installed in
   `Travel.install`). With the latch armed it swaps the dock for the mapped
   Yellow room (`RIVER_DESTINATIONS` for hold-X, `riverDestination` for the
   pager) and calls `Travel:beginCrossing`: destroys the *other* world's
   persistent instances, clears `flag[0..29]` (crossing scratch), runs
   `scr_initialize` once (first Yellow entry only; re-entry recreates only the
   controller via `ensureYellowController`), publishes the landing spot to
   `global.player_x/y`, saves `merge.sav`, then lets `loadRoom` run.
5. `Travel:afterLoadRoom` places the player if the room did not spawn one and
   applies the pending coordinates.

### 1.5 Yellow room → player update/draw → dialogue draw

* Yellow runs on the **same** `Runtime:step`/`renderFrame`; its Studio-2
  extras come from `port/yellow_studio.lua` (cameras, view_get/set, surfaces,
  layers) and `port/yellow_layers.lua`. `obj_pl`'s events (converted from the
  pinned source) do movement/state; `port/controller.lua` publishes the shared
  decisions; `port/frisk.lua` remaps Clover's walk sprites to Frisk's at draw.
* **Fonts/text ownership (this is where the reported font bugs live):**
  * `draw_set_font(v)` (`port/graphics.lua`) stores `state.font = v` — a bare
    number, no world check.
  * Text draws (`draw_text*`, `draw_text_ext`) read
    `R.assets.fonts[state.font]` (bitmap glyph atlases converted per world:
    Undertale from `fonts/*.font.gmx`, Yellow from `yellow_src/fonts/*.yy` at
    merged IDs) and render glyph-by-glyph; a missing record falls back to a
    generic 14 px LÖVE font.
  * Yellow's converted code resolves **static** font references to merged IDs
    (e.g. `draw_set_font(E, 1000005)`), but the decompilation also carries
    **raw compiled font numbers** wherever the decompiler could not prove an
    asset: `obj_dialogue/Create_0.gml` sets `dialogue_font = 9`,
    `scr_initialize_battle` sets `global.font_type_text = 1`. In Yellow's own
    asset order (pinned `notes/Asset_Order/Asset_Order.txt`) **1 =
    `fnt_main_battle`, 9 = `fnt_main`**; in the merged build those raw numbers
    read through Undertale's band (**UT 1 = `fnt_main`, UT 9 =
    `fnt_papyrus`**). Objects have a re-band (`resolveObjectIndex`); fonts do
    not. See §3, symptom 1.
  * `draw_text_ext(x, y, str, sep, width)` wraps by word whenever
    `measureLine > width` — including when `width` is negative, which
    GameMaker defines as *no wrapping*. Yellow's dialogue calls it with
    `width = -1` (`obj_dialogue/Draw_64.gml`). See §3, symptom 2.

### 1.6 Return transition (Yellow → Undertale)

* Packaged return: Yellow's own UGPS whale. `obj_fast_travel_menu` writes
  `global.fast_travel_newroom/newx/newy`; `Travel:beforeStep` fills the same
  globals for the three Undertale dock entries (`WHALE_DESTINATIONS`) using
  landings read from the dock rooms' own boat instances (`landingSpot`), and
  Yellow's own whale code performs the `room_goto`. `resolve` sees the band
  change and runs `beginCrossing` in the other direction (destroying Yellow's
  persistent instances, recreating Undertale's `obj_time` etc. via the normal
  room load).
* The River Person boat also returns the player (docks are Undertale rooms;
  going to one from Yellow crosses back the same way).

### 1.7 State that changes at a crossing (the complete list)

`Travel:beginCrossing` + `loadRoom`: other-world persistent instances
destroyed; `flag[0..29]` zeroed; `travel.world`, `travel.crossings`,
`pendingInit` updated; `global.player_x/y` published (Yellow); `merge.sav`
written (reason `travel`, leaving position); then `loadRoom` resets
`vars.room*`, view/background arrays, `roomState`, non-persistent instances.
**Not** changed: `R.player`, inventory/equipment, `travel.yellowReady`,
story flags outside 0–29, graphics state (`port/graphics.lua`'s `state` is
runtime-global and survives crossings — relevant to piece D5).

---

## 2. The reproduction harness (`tools/debug_probe.py`)

One harness, five evidence sections, no repository code changed (all
instrumentation — the `gotoRoom` recorder, the `draw_set_font` tap, the event
and draw counters — is installed in the probe's own Lua VM):

| section | what it does |
| --- | --- |
| `[boot]` | merged manifest boots, world seeded `undertale`. |
| `[opening]` | (full mode) plays title → naming → Flowey's corridor with the smoke test's own input script; captures Undertale's text draws and measures the corridor. The UT baseline. |
| `[font-text]` | packaged crossing to `rm_hotland_02`, opens Yellow's own `obj_dialogue` the way Yellow's NPCs do, records every `draw_set_font` value and every text draw, resolves what the font numbers mean in both worlds, and recomputes the `draw_text_ext` layout the shared renderer produces. |
| `[performance]` | per-tick CPU time, garbage growth, event dispatches and draw-log entries for one Undertale room and two Yellow rooms, same run. |
| `[player-identity]` | Frisk/Clover/controller counts across repeated packaged crossings. |
| `[boat-destination]` | the boat's **own** disembark state (`con=18`, `flag[459]`) and the packaged crossings, recorded by the `gotoRoom` wrapper: requested room, latch state, landing room — plus the full interactive ride after a pager choice. |

Exit code 0 means the harness ran to completion; the sections print their own
evidence either way. `tests/test_debug_probe.py` runs the `--quick` budget.

---

## 3. Captured baseline (full run, 2026-09-24, this repository's CI image)

Quoted verbatim from `python3 tools/debug_probe.py` (port warnings elided):

```text
== [boot] ==
manifest: merged yellow_base: 1000000 first room: room_introstory world: undertale
boot stable: room=room_introstory instances=3

== [opening] ==
Undertale played to room_area1_2 | writer present: true | UT text draws in current frame: 6
  UT font in use: 2 -> fnt_maintext (undertale side) e.g. "*"
UT room_area1_2            world=undertale instances=48    players=1 us/tick=2032.64   KB/tick=83.74    events/tick=187.50  draws/frame=48

== [font-text] ==
crossed to rm_hotland_02 | world: yellow
obj_dialogue alive after 46 ticks: true | marker drawn: true
Yellow text draws captured: 1
  draw_set_font: 9 -> fnt_papyrus (undertale side) | raw Yellow number 9 means Yellow's own font fnt_main (merged id 1000009)
  text drawn with font 9 -> fnt_papyrus (undertale side) x1
layout of the marker under active font 9 -> fnt_papyrus (undertale side): 7 lines from 7 words, box 55x126 px -> VERTICAL COLUMN
layout under a 320px wrap width for comparison: 2 lines
glyph coverage of the marker: active font 100% | Yellow's own fnt_main (merged 1000009) 100%
SYMPTOM FONT: Yellow dialogue is drawn with an UNDERTALE font (fnt_papyrus); Yellow's dialogue_font=9 is Yellow's own raw font number (fnt_main), which the merged build reads through Undertale's ID band.
SYMPTOM VERTICAL: draw_text_ext(..., width=-1) wraps at every word, so the box is taller than it is wide: text stacks as a column. GameMaker treats a negative width as 'no wrapping'; the shared renderer does not.

== [performance] ==
tick budget per room: 300 (quick=false)
Y rm_hotland_02            world=yellow    instances=21    players=1 us/tick=411.61    KB/tick=47.35    events/tick=88      draws/frame=137
Y rm_snowdin_11_yellow     world=yellow    instances=22    players=1 us/tick=2268.63   KB/tick=19.09    events/tick=93      draws/frame=805.96
Yellow/Undertale tick-cost ratio vs the corridor baseline above: 0.20x (hotland), 1.12x (snowdin)

== [player-identity] ==
start (Undertale dock)                 world=undertale room=room_fire_dock             frisk=1 clover=0 controllers=1 total=32
round 1 -> Yellow                      world=yellow    room=rm_hotland_02              frisk=0 clover=1 controllers=1 total=21
round 1 -> back to Undertale           world=undertale room=room_fire_dock             frisk=1 clover=0 controllers=1 total=32
round 2 -> Yellow                      world=yellow    room=rm_hotland_02              frisk=0 clover=1 controllers=1 total=21
round 2 -> back to Undertale           world=undertale room=room_fire_dock             frisk=1 clover=0 controllers=1 total=32
round 3 -> Yellow                      world=yellow    room=rm_hotland_02              frisk=0 clover=1 controllers=1 total=21
round 3 -> back to Undertale           world=undertale room=room_fire_dock             frisk=1 clover=0 controllers=1 total=32
max simultaneous player instances across all crossings: 1
scripted packaged crossings keep exactly one Player; the owner's duplicate must come from the interactive boat flow - checked next.

== [boat-destination] ==
native flag=1 (Snowdin), no X                  requested=70        latch=false landed=room_tundra_dock           expected=room_tundra_dock           OK
native flag=2 (Waterfall), no X                requested=125       latch=false landed=room_water_dock            expected=room_water_dock            OK
native flag=3 (Hotland), no X                  requested=140       latch=false landed=room_fire_dock             expected=room_fire_dock             OK
X held, flag=1 -> Yellow stop                  requested=70        latch=true  landed=rm_snowdin_11_yellow       expected=rm_snowdin_11_yellow       OK
pager -> Dunes - West Mines                    requested=70        latch=true  landed=rm_dunes_05                expected=rm_dunes_05                OK
full ride after pager: 217 ticks, landed=rm_dunes_30 world=yellow goto sequence:
    room_goto(316) from 140 latch=true dest=Dunes - Oasis Valley
  players after full ride: frisk=0 clover=1 (total instances 126)
whale return fast_travel_point=Waterfall       requested=125       landed=room_water_dock            expected=room_water_dock            OK
boat destination cases: 6 mismatches: 0

== [summary] ==
probe completed: phases=all quick=false perf_ticks=300 frames=2041 crossings=14
Evidence above feeds docs/DEBUG_BASELINE.md; pieces D1-D5 own the fixes.
```

Notes on reading this:

* The full-mode `[opening]` corridor measurement includes Flowey's cutscene
  scripting (187 events/tick), so the two "ratio vs corridor" numbers understate
  the Undertale side; the quick-mode run measures a quiet Undertale room instead
  (`room_fire_dock`: 913 µs/tick, 135 events/tick, 128 draws/frame), giving
  1.02× (hotland) and 2.89× (snowdin) there. Piece D2 must pick its own stable
  comparison rooms and beat its own before/after numbers.
* `rm_snowdin_11_yellow` stands out either way: ~806 draw-log entries per frame
  with only 22 instances — the snow particles and tile layers dominate. That is
  a *candidate* runaway for D2, not a verdict.

---

## 4. Symptom status after D0

| symptom | headless status | evidence / leading root cause |
| --- | --- | --- |
| 1. Yellow font wrong | **fixed in D1a** | D0 reproduced: `obj_dialogue` (and 10 more `obj_dialogue*` Creates) sets `dialogue_font = 9`, and `scr_initialize_battle` sets `global.font_type_text = 1` — Yellow's own compiled font numbers (pinned Asset_Order: 1 = `fnt_main_battle`, 9 = `fnt_main`). The merged build read them through Undertale's band: **9 = `fnt_papyrus`, 1 = `fnt_main`**. Static references (`draw_set_font(E, 1000005)` etc.) already resolved; only the *raw-number* spellings were broken. **D1a** added `Runtime:resolveFontIndex` (sibling of `resolveObjectIndex`) and consumes it in `draw_set_font`. Evidence: `tests/test_yellow_fonts.py`; see [`PORTING.md`](PORTING.md) "Debug fixes — D1a". |
| 2. Yellow text vertical | **reproduced** | `obj_dialogue/Draw_64.gml` calls `draw_text_ext(xx, yy+10, message, line_sep, -1)`. GameMaker: negative width = no wrapping. The shared renderer wraps whenever `measureLine(line) > width`, so `-1` wraps at **every word**: the 7-word marker becomes 7 lines, a 55×126 px box — a vertical column. **D1b's job:** fix the shared `draw_text_ext` wrap contract (negative/zero width = no wrap), prove the fix against the same layout math, and check whether any other Yellow caller relied on the broken reading. The two symptoms are independent causes (wrong record vs wrong wrap contract) — no shared fix is currently known. |
| 3. Yellow lag | **quantified, cause not yet proven** | Headless CPU shows hotland at parity and snowdin ~2.9× a quiet Undertale room with ~806 draws/frame (particles + tile layers). Device-side FPS is out of scope until measured (§2 rule 5). D2 profiles from these numbers and must find the runaway system, not lower quality. |
| 4. Duplicate Player | **not reproduced by the packaged crossings** | 14 crossings in one run (3 scripted round trips + the boat cases + the full ride), max simultaneous Players = 1; controllers = 1 throughout. The duplicate the owner sees is therefore on the **interactive** boat path (dialogue-driven boarding) or device-specific input — D3 must drive that path, not relax this gate. |
| 5. Boat destination | **packaged matrix consistent; two traps recorded** | All six packaged cases land where `port/travel.lua` documents (0 mismatches). But (a) the hold-X latch silently flips an Undertale dock into a Yellow stop — the "hold X" ambiguity the brief names, and (b) on the full interactive ride the pager's latch is **consumed by the boarding `room_goto(316)`**, so the ride animation is skipped and the player teleports to the Yellow stop. Both are D4's to resolve: make the destination explicit at the moment the ride commits, without inventing coordinates. |

**Scope of this evidence:** headless converted flow + traced draw log, one
machine, fixed seed. It does **not** cover native LÖVE rendering, the Android
device, audio, or a hand-played route; CI's native gate and the owner's device
remain the authorities for those (queue §4 notes).

---

## 5. What D1–D5 inherit

* Reproduce first: every later piece can re-run the probe against its branch
  and diff its section of the output; the `gotoRoom` recorder and the
  `draw_set_font` tap are ready-made instruments.
* Baseline numbers (quick mode, quiet rooms, one 2026-09-24 sandbox run —
  re-measure on the piece's own branch): UT dock 913 µs/tick · 131 KB/tick
  · 135 events/tick · 128 draws/frame; Y hotland 933 µs/tick · 84 KB/tick · 88
  events/tick · 137 draws/frame; Y snowdin 2640 µs/tick · 198 KB/tick · 93
  events/tick · 806 draws/frame.
* The fusion invariants held throughout the probe: one `R.player` record, one
  controller, one `merge.sav`, Frisk-only rendering, Undertale's rooms/text
  untouched (opening played to Flowey with the smoke test's own assertions).
