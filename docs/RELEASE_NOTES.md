# Experimental LÖVE build — not a fully functional game port

This prerelease makes the current `.love` package downloadable from GitHub. It
contains the converted Lua and the assets supplied for both merged games. **It
is not a completed or native-device-verified game, and it is not an APK.**

## v1.2.1 — every stop travels

Two rounds of owner feedback. First: *"make sure that the River Person and
UGPS are always available to use"* and *"I can fast travel to all of their old
and new locations"* — neither service is locked behind story progress any
more, and both can be used in the first minutes of a run. Then, with one named
stop left: implement the particle system, the only blocker, leaving no travel
stop behind.

- **The River Person is at every dock from the first frame.** The boat's own
  Create event deletes itself while `global.plot` is under 122 — the value
  Undyne's Waterfall chase writes — which is why no dock had a boat before
  Hotland. That single guard is lifted for that single event and `global.plot`
  is restored immediately afterwards; the boat, the River Person, the
  destination choice and both rides (dock to dock, and the room-316 crossing)
  stay the game's own code.
- **The UGPS offers every stop it can fly to.** `global.player_can_travel` is
  the whale's own "this whale will fly you" switch; the port sets the same
  switch when Yellow's world is initialized, then registers the three
  Undertale docks and Yellow's own seven stops through Yellow's own
  `scr_fasttravel_add` — ten stops, whether or not the player has walked past
  them, listed by Yellow's own menu in Yellow's own order.
- **Yellow's stop numbers are read through the merged ID space.** Yellow's menu
  writes the room numbers of Yellow's own project (56 = its Snowdin forest,
  137 = Wild East). In a merged build those have to resolve to `1000000 + 56`,
  or the whale flies the player into Undertale's room of the same number; the
  bridge fills `fast_travel_newroom` with the merged room of the highlighted
  label.
- **A UGPS whale's approach now finishes.** Every whale ends its fly-in by
  comparing `fly_speed` to exactly zero, and its own `fly_speed -= 0.2` from 2
  cannot reach zero in binary floating point (the tenth step lands on about
  2.8e-16). The whale hovered, and the Mail/Travel dialogue — the only way into
  the fast-travel menu — never started. The port reads that last step as the
  landing the game's own next line expects, and reports it at startup.
- **Mail-station bells no longer stop the runtime.** A station asks for
  `view_camera[0]` to place its whale; that table had never been created, so
  ringing a bell stopped the frame with *"Camera 0 does not exist"*. Every
  visible viewport's camera now exists from room load.
- **The particle system is implemented, so Snowdin travels.** GameMaker's
  `part_*` builtins — systems, types, emitters, direct creation — run in a new
  `port/particles.lua`: `part_snow`'s snowfall draws at depth -9999 in all 19
  Snowdin rooms that place it, and the Snowdin-forest whale stop plus
  Undertale's Snowdin boat crossing land instead of stopping. All ten UGPS
  stops and all three dock crossings travel and land.
- **The same landing needed three small rules, all reported.** The forest's
  shadow system passes Yellow's raw object numbers where the merged build
  needs the banded ones, so Yellow callers get their numbers banded
  (`object-band`) in `with`, `instance_create` and `instance_create_depth`;
  `object_get_parent` answers Yellow callers in Yellow's number space; and
  `texture_set_stage` joins the report-and-skip shader flow, since the
  palette-shader path binds through it on every shaded actor.
- **309 automated tests** pass on this branch (fifteen new: eleven particle
  unit tests, two static pins against the pinned Yellow source, and the two
  Snowdin landing tests — whale stop and boat crossing — plus a native gate
  that screenshots snowfall drawn in the forest).

## v1.2.0 — the Undertale ⊕ Undertale Yellow fusion build

One `.love` archive carries **both games as a single traversable world**: the
whole of this repository's Undertale port and the whole of the pinned Undertale
Yellow v1.2.1 decompilation, joined by the games' own travel hubs. You play one
playthrough, as **Frisk in both worlds**.

### What is new in v1.2.0

- **Both games in one archive.** 287 Yellow rooms (with 199 454 layer
  drawables), 3 224 Yellow objects with their 8 494 events, 1 155 Yellow
  scripts, 3 796 sprites, 673 sounds and 11 fonts convert into the same runtime
  as Undertale, in a disjoint ID band (`1000000 +` the pinned Asset_Order ID)
  so no Undertale ID moves. The merge *checks* that invariant instead of
  assuming it.
- **The River Person now sails to Undertale Yellow.** Hold **X** — the cancel
  button, on screen for touch — during a River Person boat ride, and the
  destination you chose lands in Yellow instead: Snowdin's dock → the Snowdin
  forest, Waterfall's dock → the Dunes, Hotland's dock → Yellow's Hotland.
  Every destination and landing coordinate is the games' own data; no
  recovered script or object was edited.
- **Yellow's UGPS mail whale sails back.** Yellow's own fast-travel menu lists
  the three Undertale docks. Choosing one runs Yellow's own whale travel code
  and Frisk steps out beside the dock's own boat.
- **Frisk everywhere.** Yellow's player object keeps all of its mechanics
  (movement, states, masks, collisions — nothing about the rooms or battles
  changes), but the body you see is drawn from Undertale's Frisk sprites:
  28 of Clover's walk-cycle poses (including the route, water, Snowdin and
  roof recolours) draw Frisk's matching direction.
- **Clover's run animation on the X button.** Hold X while walking in Yellow's
  world and you sprint at Yellow's own run speed, with Clover's
  `spr_pl_run_*` cycle — the one pose family Frisk's set does not have, kept
  Clover's on purpose. Gun poses, the Steamworks goggles, the dance and lying
  poses also stay Clover and are reported by name at startup.
- **Clover's ammunition and accessories as two extra equipment slots, beside
  Frisk's own gear.** Frisk keeps Undertale's weapons and armours untouched.
  In Yellow's world, its own pause menu equips Clover's ammunition (weapon
  modifier) and accessories (armour modifier) into two additional slots that
  feed Yellow's own attack/defense math. Equipping swaps with the inventory
  slot exactly as Yellow does, and the loadout persists in the merged save,
  restored after every crossing with Yellow's own stat scripts.
- **A versioned merged save.** `merge.sav` records version, crossings, last
  room, world and the two equipment slots. It is additive: each game keeps the
  save files it already writes, a single-game save is never rewritten, and an
  unknown version stops with its own name instead of being guessed at.
- **Native fused-world release gate.** The LÖVE/xvfb gate now plays the Undertale
  opening, then crosses into Yellow natively: the boat ride lands one player in
  `rm_hotland_02` drawn as Frisk, the whale brings them back to exactly one
  Frisk at the Waterfall dock, and `merge.sav` records both crossings and the
  equipment slots. Screenshots are kept as the release run's artifacts.
- **A larger automated suite.** 285 automated tests pass for this release (was 255 at the last validation),
  including the Frisk remap, the X-run, the menu-driven equips, the merged
  save restore, and packaging gates that refuse to ship a merged archive
  missing any of the ~19 400 referenced pinned asset files.

### What this release still does not claim

- It is **not a finished full-game port of either game**. Undertale's known
  gaps remain (86 unresolved static numeric asset references in recognizable
  positions, missing external files, absent original room 159, the 38
  recovered paths' frame-level parity uncertified). See the attached
  conversion reports for both games.
- **Yellow's battles and deeper systems are unclaimed.** Walking and crossing
  are proven; fighting Yellow's enemies, its story flags, palette shaders
  (reported and skipped — the scene keeps its original colours) and the 25
  rooms whose layer effects or physics worlds have no equivalent here (they
  stop with their own names) are not certified.
- **No Android device certification or APK.** The native gate is Linux
  LÖVE/xvfb with software GL and null audio. Android GPU behaviour, audio
  fidelity, touch latency and lifecycle behavior remain outstanding, as do
  full-game playthroughs of either world.
- Clover is not a playable character; the player is Frisk in both worlds, as
  the merge specifies.

## v0.1.10 features

- **Glyde encounters are 20× faster.** `obj_encounterer_glyde`'s `scr_steps`
  timers are cut to 1/20 of stock: first encounter `3600 + random(150)` →
  `180 + random(7.5)` steps, repeat encounters `840 + random(680)` →
  `42 + random(34)` steps. Expected wait is exactly 1/20 of vanilla in both
  phases; the area population factor is untouched.
- **A "709 EXP" button in the STAT menu.** The STAT screen gains one
  heart-selected row, **"709 EXP"**. Confirming it runs
  `global.xp += 709` and then the game's own `scr_levelup`, so LOVE/HP/AT/DF
  rise immediately and exactly as if the EXP were earned in battle
  (709 → LV 8). The EXP is real `global.xp`: displayed, saved normally, and
  repeatable with every press. `scr_levelup` itself is byte-identical to
  stock — no masking, no accounting flags.
- **Zero route impact.** The button touches **only** `global.xp`. The kill
  counter `global.kills` stays 0, so every pacifist gate (`kills == 0` in
  `obj_endflowey` / `obj_asgoreb` / `obj_dogfoodbag`) still passes, genocide
  flag 27 never moves, and neutral runs stay neutral. No save-format change:
  nothing new is persisted.
- **Sans's Last Corridor judgment notices a bloodless LV rise.** In
  `obj_lastsans_trigger`, when LOVE has risen with zero kills (a state only
  reachable via the button), Sans gives his usual "EXP = execution points /
  LOVE = Level of Violence" explanation, then seriously questions how your
  LOVE went up — and ambiguously lets it go: *"... but you didn't hurt
  anyone. not a single monster got hurt this time. so where'd all that exp
  come from? some other life, maybe? heh. honestly? it doesn't really
  matter. ... i'm still rooting for you. good luck."* He never says how he
  knows. True LV-1 pacifists get the unchanged original "you never gained any
  LOVE" speech.
- **185 automated tests** (was 181), with four new cases in
  `tests/test_statmenu_cheats.py`: Glyde timer values (conversion artifact +
  live `steps` bound), vanilla leveling math, a player-driven menu run of the
  button (EXP 709/LV 8/kills 0, stacking on repeat), and the Sans judgment
  branching verified end-to-end through the real converted scene (classic
  speech preserved at LV 1, custom speech at LV 8 with 0 kills).
- The GitHub download now points at the v0.1.10 experimental LOVE archive.

## v0.1.9 fixes

- **Fix the Snowdin tile-puzzle softlock** (reported as: *after solving
  Papyrus's puzzles the game softlocks and Papyrus's overworld sprite doesn't
  move*). GameMaker alarms are one-shot — they reset to −1 when they fire —
  but the runtime left them armed, so every alarm event ran twice.
  `obj_papyrus4` advances its cutscene with `alarm[4]++`: the double-fire
  incremented 51→52→53 in two frames, skipping the wait for the tiles to
  finish randomizing and never setting the next alarm, so the scene stalled at
  conversation 53 with `interact=1` (player frozen, Papyrus frozen). The
  runtime now resets each alarm to −1 before running its event, matching
  GameMaker; events may still re-arm recurring alarms.
- **Fix every doubled text, enemy and dialogue** (reported as: *every single
  text, enemy and dialogue is doubled and overlaps on itself*). The same
  double-fire created two overlapping copies of everything an alarm spawns —
  enemy speech bubbles, damage numbers, bullets, dialogue boxes — across the
  whole game. One-shot alarms spawn exactly one instance now (verified:
  one-shot spawns 1, a 10-step recurring alarm spawns 3 in 35 ticks, and the
  Flowey fight contains exactly one of each object).
- Two new regressions pin the fix (the suite grows from 179 to **181**): an
  alarm one-shot unit test (fires exactly once, resets to −1, re-arming works)
  and a headless Papyrus4 playthrough that answers the intro, waits out the
  tiles, and asserts plot 58 with control restored. Each was verified to fail
  on the unfixed code with the reported signature before passing after it.
- Updated the GitHub download to the v0.1.9 experimental LOVE archive.

## v0.1.8 fixes

- **Fix the crash on starting most battles outside the Ruins** (reported as:
  *unable to initiate battle with any enemy in Snowdin — "Port compatibility
  stop: instance_create Missing object ID 255" against `obj_snowdrake` in
  `room_battle`*). Every part-based monster spawns its artwork through a local
  variable holding a bare original object ID (`part2= 255; mypart2=
  instance_create(x, y, part2)`), and those literals carry no decompiler
  annotation — so the body-part objects stayed on synthetic IDs and
  `instance_create` stopped the moment the battle controller created the
  monster. The first Snowdin encounter (battlegroup 30, Snowdrake) stopped on
  255; Doggo, Dogamy & Dogaressa, Greater Dog, Gyftrot, Glyde, Papyrus, Shyren,
  Undyne the Undying, Mettaton EX/NEO, So Sorry and the True Lab amalgamates all
  hit the same wall on their own part IDs.
- **Recover the 22 missing part-object IDs with pinned, auditable provenance.**
  `tools/recover_parts.py` pairs each of this checkout's own numeric literals
  with the object name that the pinned upstream decompilation
  (`kittibyte/UndertaleDecomp` @ `249ffa27`, the same immutable commit already
  pinned for the registry audit) shows for the same statement, after checking
  that both of a monster's events assign the same part variables in the same
  order. Per-site provenance and the 38 already-annotated anchor sites are
  committed in `port/recovered_parts.json`; nothing is imported from the
  registry dump, whose incompatible ID space stays audit-only.
- **179 automated tests** (was 163), including 16 new regressions: per-site
  provenance and no-invention checks, a static guard over all 59 part spawn
  sites, and an end-to-end battle for every Snowdin battlegroup. Each was
  verified to fail on the unfixed code with the reported crash signature
  before passing after it.
- Updated the GitHub download to the v0.1.8 experimental LOVE archive.

## Older versions

`love-v0.1.0` through `love-v0.1.7-experimental` remain downloadable, renamed
with a "Superseded —" prefix. Every published release is immutable; none is
republished over.
