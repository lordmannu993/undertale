# Undertale + Undertale Yellow — Unified Love2D Fusion Fixes

> **Status of this document:** owner-issued requirements, received 2026-09-19. It is the
> authoritative specification for the fusion. It is reproduced verbatim below so that the
> wording of the requirement, not a paraphrase of it, is what the work is judged against.
>
> This document **supersedes** the "Yellow merge: complete" framing in
> [YELLOW.md](YELLOW.md) and the merge section of [AGENTS.md](../AGENTS.md) wherever the
> two disagree. "All five pieces complete" described the *conversion* pipeline (assets,
> scripts, objects, rooms, merged manifest) and the travel hubs. It never established that
> the result plays as one game. The owner has now stated that it does not, and this
> document is the requirement set that defines what "does" means.
>
> Provenance: the owner asked for this to be treated as the binding brief for the
> repository. It cannot be installed as an agent system prompt (that is fixed by the
> platform and is not editable from inside a session), so it is committed here and
> referenced from `AGENTS.md` — which is this project's own first-read agent document —
> so that it survives the session and is picked up by every later one.

---

## 1. Create One Unified Inventory and Progression System

Undertale and Undertale Yellow currently have separate inventory/progression systems. This
is incorrect for the fusion.

The player should have **one shared inventory and one shared progression state** throughout
the entire game.

- Undertale and Undertale Yellow must use the **same inventory**.
- Items obtained in either portion of the game must remain available when entering the other
  portion.
- There must **not** be a separate "Clover's Inventory."
- There must **not** be an "Undertale Inventory" and an "Undertale Yellow Inventory."
- Equipment must be persistent and shared across the entire game.
- Weapons, armor, consumables, key items, and other relevant inventory state should carry
  over correctly.
- If an item is equipped, its equipped state must also persist when transitioning between
  areas/original game content.
- The player's **LV, EXP, HP, stats, equipment, inventory, money, and other relevant
  progression data must not reset** when entering Undertale Yellow content.
- Likewise, progress obtained from Undertale Yellow content must remain available when
  returning to Undertale content.

Treat the player's progression as belonging to **one continuous protagonist/game state**,
rather than belonging to either source game.

## 2. Fully Fuse Undertale and Undertale Yellow

The biggest issue with the current implementation is that it behaves as though there are
**two separate games placed inside one executable**.

That is not what I want.

The result should feel like a **single unified Undertale experience that incorporates
Undertale Yellow content**.

Do NOT implement the game as:

> Undertale → switch to Undertale Yellow → switch back to Undertale

Instead, integrate both games' mechanics, characters, abilities, assets, rooms, systems, and
relevant content into a common game architecture.

There should be:

- One player state.
- One inventory.
- One equipment system.
- One progression system.
- One save/progression structure.
- One overworld system.
- One battle system.
- One set of shared player mechanics.

## 3. Merge Frisk and Clover's Abilities

Do not treat Frisk and Clover as completely isolated player implementations.

Merge their compatible abilities into the unified player system.

For example:

- Clover's running ability should be available to the unified player.
- Clover's running/walking sprites and associated movement animations should work correctly
  within Undertale areas.
- Any other gameplay ability Clover has that Frisk does not have should be incorporated into
  the unified player where technically appropriate.
- Likewise, any relevant abilities or mechanics that Frisk has but Clover lacks should remain
  available.
- The player should not lose abilities simply because they entered content originating from
  the other game.

The player controller should ultimately support the **combined functionality of both
protagonists**, rather than swapping between two isolated character controllers.

If an ability is context-sensitive, implement it through the shared player/controller system
rather than creating a separate character state that effectively turns the game into two
games.

## 4. Fix Player and Overworld Sprite Rendering

There are currently significant overworld rendering problems where sprites overlap
incorrectly or appear on the wrong visual layer.

Fix the rendering/depth system so that **every overworld object is rendered at its correct
Z/depth position**.

Do not solve this by manually changing individual sprites whenever a problem appears.
Establish a consistent overworld layering system.

The rendering system should correctly account for:

- Ground/background layers.
- Water.
- Environmental objects.
- Props.
- NPCs.
- The player.
- Foreground objects.
- Objects that should appear behind the player.
- Objects that should appear in front of the player.
- Multi-part sprites/objects whose individual components require different depth ordering.

Use appropriate **Y-sorting/depth sorting or explicit Z layers** where necessary.

For objects that are supposed to be sorted dynamically based on their position in the world,
use their world-space Y coordinate or an equivalent depth value rather than relying entirely
on hard-coded draw order.

For objects that contain both background and foreground portions, allow the object to be
split into separate render layers where necessary. For example, a large environmental object
may need one portion rendered behind the player and another portion rendered in front of the
player.

The important thing is that the final result should visually match the intended
original-game layering.

## 5. Fix Overworld Sprite Overlap and Z-Axis Issues

Inspect the overworld rendering pipeline as a whole.

Sprites should not:

- Randomly appear in front of objects they should be behind.
- Appear behind objects they should be in front of.
- Overlap other sprites incorrectly.
- Render multiple depth layers simultaneously in the wrong order.
- Flicker or visually pop between incorrect layers.
- Have their feet/body positioned incorrectly relative to environmental objects.

Pay particular attention to the player's feet/base position. The player's **logical position
and sprite's visual bottom point** should be used when determining depth, rather than simply
sorting based on the top-left corner of the sprite.

Apply the same principle to NPCs and other world entities.

If an NPC is standing behind a counter, tree, wall, table, or other foreground object, the
foreground portion must be capable of rendering over the NPC while the rest of the
environment remains behind it.

## 6. River Person's Boat and Water Rendering

There is a specific rendering bug involving the River Person's boat.

The boat and water/waves currently render in the wrong order.

The intended result is:

- The water/waves should be rendered at their appropriate background/environment depth.
- The River Person's boat should be positioned correctly relative to the water.
- The boat should not incorrectly render as though it is simply placed above every
  water/wave layer.
- Any portions of the boat or character that are supposed to overlap the water should use the
  correct depth.
- Water effects/waves should not incorrectly appear over portions of the boat that should be
  visible.
- The boat should not appear to float at an incorrect Z position relative to the river.

Use the original games' visual layering as the reference for the intended result.

Do not just move the entire boat to a higher or lower global render layer if that causes
other portions of the scene to become incorrect. If necessary, separate the boat into
appropriate visual components/layers.

## 7. Fix Snowdin Shopkeeper Sprite

The Snowdin Shopkeeper currently renders incorrectly.

The sprite appears to have:

- Four eyes instead of two.
- A floating/separated mouth.
- Incorrectly composited facial features.

This suggests that the sprite layers, sprite sheet coordinates, animation frames, or texture
composition are being handled incorrectly.

Fix the sprite so that the Snowdin Shopkeeper renders as intended:

- Exactly two eyes.
- Correct mouth position.
- Correct facial proportions.
- No duplicated facial features.
- No floating facial components.
- Correct sprite-sheet/frame selection.
- Correct animation behavior.

Check whether this is caused by:

- Incorrect sprite-sheet coordinates.
- Incorrect frame dimensions.
- Incorrect source rectangles.
- Incorrect texture offsets.
- Incorrect scaling.
- Multiple animation frames being drawn simultaneously.
- Duplicate sprite layers.
- Incorrect sprite origin/anchor points.
- Incorrect transparency handling.
- Undertale and Undertale Yellow assets being composited together accidentally.

Fix the **underlying cause** rather than simply hiding the duplicated features.

## 8. Do Not Duplicate Characters or Sprite Layers

Because this is a fusion project, be especially careful about accidentally rendering the same
character more than once.

A character should have one authoritative world entity and one appropriate visual
representation unless the original scene specifically requires multiple visual layers.

Do not render an Undertale version and Undertale Yellow version of the same NPC
simultaneously.

Do not accidentally draw:

- The base sprite twice.
- Two animation frames at once.
- Duplicate facial overlays.
- Duplicate shadows.
- Duplicate character bodies.
- Separate Undertale and Undertale Yellow versions of the same character.

If assets from both games are required for different animations or states, select the
appropriate asset rather than drawing both.

## 9. Establish a Proper Shared Architecture

Refactor the implementation where necessary instead of continuing to patch individual
symptoms.

The architecture should have shared systems such as:

```text
Game State
├── Player
│   ├── HP
│   ├── LV
│   ├── EXP
│   ├── Stats
│   ├── Inventory
│   ├── Equipment
│   ├── Abilities
│   └── Movement
│
├── World
│   ├── Undertale Areas
│   ├── Undertale Yellow Areas
│   ├── NPCs
│   ├── Objects
│   └── Collision
│
├── Rendering
│   ├── Background Layers
│   ├── World Objects
│   ├── Y/Z Sorting
│   ├── NPCs
│   ├── Player
│   └── Foreground Layers
│
└── Battle/System State
    ├── Stats
    ├── Inventory
    ├── Equipment
    └── Abilities
```

Do not duplicate these systems for Undertale and Undertale Yellow unless there is a genuine
technical reason to do so.

The game should have one authoritative source of truth for player progression.

For example, there should not be separate variables such as:

```text
undertaleLV
yellowLV
undertaleEXP
yellowEXP
undertaleInventory
yellowInventory
cloverInventory
friskInventory
```

Instead, use a unified state concept such as:

```text
player.level
player.exp
player.inventory
player.equipment
player.stats
player.abilities
```

The exact implementation is up to you, but the important requirement is that the underlying
state is **shared rather than duplicated**.

## 10. Room and Area Transitions Must Preserve State

Changing rooms, regions, or content originating from either game must not recreate the player
from scratch.

When transitioning between areas:

1. Save the current unified player state.
2. Load the destination room/world data.
3. Place the existing player entity into the destination.
4. Preserve inventory.
5. Preserve equipment.
6. Preserve LV.
7. Preserve EXP.
8. Preserve abilities.
9. Preserve appropriate stats.
10. Preserve any other persistent progression data.

Do not initialize a fresh Undertale Yellow player when entering Yellow content.

Do not initialize a fresh Undertale player when returning to Undertale content.

The room transition should change the **world**, not replace the **player's progression
state**.

## 11. Save/Load Must Use the Unified State

The save system must serialize the unified game state.

A save should be able to contain, as appropriate:

```text
Player
├── LV
├── EXP
├── HP
├── Max HP
├── Stats
├── Inventory
├── Equipment
├── Abilities
└── Other persistent state

World
├── Current Area
├── Story Progress
├── NPC State
├── Event State
└── Other persistent state
```

Loading a save must restore the same unified player regardless of which game's content the
player was previously exploring.

Do not have separate save structures for Undertale and Undertale Yellow.

## 12. Maintain Correct Asset Compatibility

Undertale and Undertale Yellow may use different sprite dimensions, animation systems,
coordinate systems, or asset conventions.

Where those systems differ, create a compatibility layer rather than allowing each game to
maintain its own completely separate player/world framework.

Normalize things such as:

- Sprite origins.
- Animation frame handling.
- Movement speed.
- Collision boxes.
- Hitboxes.
- Render anchors.
- World coordinates.
- Depth values.
- Scaling.
- Sprite-sheet coordinates.

Do not assume that two sprites with visually similar dimensions have identical origins or
collision geometry.

## 13. Do Not Fix Bugs With Temporary Visual Hacks

Avoid solutions such as:

```text
if room == "snowdin_shop" then moveSprite(...)
if character == "river_person" then drawLater(...)
if yellowMode then resetInventory(...)
```

unless the behavior is genuinely required by the game.

Prefer fixing the shared system causing the problem.

For example:

- If all sprites have incorrect depth, fix the depth-sorting system.
- If all room transitions reset progression, fix player-state persistence.
- If sprites are duplicated, fix entity/animation rendering.
- If sprite-sheet frames are wrong, fix frame selection and source rectangles.
- If equipment disappears, fix the shared inventory/equipment state.

Individual room-specific overrides should only exist when the original scene genuinely
requires unique behavior.

## 14. Preserve Game-Specific Mechanics Without Creating Separate Games

Some mechanics may originate specifically from Undertale or Undertale Yellow.

Preserve those mechanics where appropriate, but integrate them into the shared architecture.

The rule should be:

> **Different content does not mean different player state.**

A Yellow-specific mechanic can still exist, but it should interact with the same player,
inventory, equipment, world, and progression systems whenever appropriate.

Likewise, Undertale-specific mechanics should remain available when appropriate rather than
disappearing simply because the player entered Yellow-derived content.

## 15. Testing Requirements

After making the changes, thoroughly test the fusion rather than only checking that the game
launches.

Test at minimum:

**Player State**

- Enter Undertale Yellow content with an existing inventory.
- Confirm all appropriate items remain.
- Equip an item.
- Transition to Yellow content.
- Confirm the equipment remains equipped.
- Gain EXP.
- Transition between content.
- Confirm EXP remains.
- Confirm LV remains.
- Confirm HP/stats behave correctly.
- Confirm abilities remain available.

**Inventory**

- Obtain an Undertale item.
- Transition into Yellow content.
- Confirm the item is still present.
- Obtain a Yellow item.
- Return to Undertale content.
- Confirm the item is still present.
- Confirm there is only one inventory.
- Confirm there is no Clover-specific inventory.

**Movement**

- Confirm walking works everywhere it should.
- Confirm running works in Undertale areas.
- Confirm Clover-derived movement functionality does not disappear in Undertale content.
- Confirm Frisk-derived functionality remains available where appropriate.
- Confirm movement animations correctly match movement state.

**Rendering**

Check multiple rooms and situations for:

- Player/NPC overlap.
- Player/environment overlap.
- NPC/environment overlap.
- Foreground objects.
- Background objects.
- Water.
- Props.
- Shadows.
- Multi-layer sprites.
- Animation frames.
- Sprite origins.
- Y/Z sorting.

Specifically verify:

- River Person's boat.
- River Person.
- River water/waves.
- Snowdin Shopkeeper.
- Snowdin Shop environment.
- Player sprites.
- NPC sprites.

**Save/Load**

- Save while using Undertale content.
- Load the save.
- Save while using Yellow content.
- Load the save.
- Confirm inventory, equipment, LV, EXP, abilities, and other persistent state remain
  consistent.

## 16. Final Acceptance Criteria

Do not consider this task complete merely because both games can be accessed from the same
executable.

The finished result must behave as **one unified game**.

The player should experience:

- One continuous player character/state.
- One inventory.
- One equipment system.
- One LV.
- One EXP value.
- One progression state.
- One save system.
- One overworld framework.
- One movement system.
- One combined ability set.
- One coherent rendering/depth system.

Undertale Yellow should not feel like a separate game embedded inside Undertale.

The final implementation should instead make its content feel like it belongs to the **same
unified Love2D game**.

Before declaring the task finished, inspect the relevant code and verify that the fixes are
actually implemented at the system level. Do not simply claim that the issues are fixed.

If you find duplicated player state, duplicated inventories, separate game-mode logic, or
separate rendering pipelines that are responsible for these problems, refactor them so that
the shared systems become the authoritative implementation.

**Most importantly: do not preserve the current "two games in one" architecture. The
objective is an actual fusion, not a launcher, selector, or transition between two
independently functioning games.**

This version completes the cutoff and also makes the **architecture requirement much more
explicit**, especially around preventing separate `undertaleLV`, `yellowLV`,
`cloverInventory`, etc. from continuing to exist underneath the UI.

---

## How this spec binds work in this repository

Every numbered requirement above must be satisfied *and evidenced*, following this repo's own
hard rules (`AGENTS.md` → "Hard rules, and why"): no fabricated data, visible stops rather
than silent substitution, and behaviour claims that are scoped to what was actually run.

| spec § | where it lands in this repo |
| --- | --- |
| 1, 9, 10, 11 | player/progression/inventory/equipment/save state — `port/storage.lua`, `port/merge.lua`, Undertale's `global.*` progression variables and Yellow's `global.*` equivalents, and the `merge.sav` layer |
| 2, 14 | world/room traversal and game-mode branching — `port/runtime.lua`, `port/travel.lua`, `tools/merge.py` |
| 3, 12 | unified player controller and the Undertale↔Yellow asset compatibility layer — `port/frisk.lua`, `port/yellow_studio.lua`, `port/collision.lua`, sprite origin/mask/`image_speed` normalisation in `tools/yellow/assets.py` |
| 4, 5, 6, 8 | depth/Y-sort and duplicate-draw — `port/graphics.lua`, `port/yellow_layers.lua`, `port/yellow_graphics.lua`, per-room layer data in `tools/yellow/rooms.py` |
| 7 | Snowdin Shopkeeper frame selection/source rectangles — sprite conversion (`tools/convert.py`, `tools/yellow/assets.py`) and the shop's instance/layer data |
| 15, 16 | `tests/` (offline) plus the native LÖVE/xvfb gate (`port/smoke.lua`, `tools/native_smoke.sh`, CI only) |

Acceptance is the list in §15 and §16, not "the game launches". A claim that a section is
done needs the command that demonstrated it recorded in the PR.
