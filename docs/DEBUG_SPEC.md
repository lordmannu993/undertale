# Owner's debug & repair brief — Undertale ⊕ Undertale Yellow fusion (binding)

> **Provenance.** Issued by the owner on 2026-09-24, on the session branch
> `arena/01a0d3aa-undertale`, and it **replaces the finished unified-fusion queue**
> as the objective set behind the **"Proceed ❤️"** trigger (see `AGENTS.md`).
> This file is the requirement set; the living work queue, progress and the exact
> order of pieces are [`docs/DEBUG_QUEUE.md`](DEBUG_QUEUE.md). Where the two
> disagree on a requirement, **this file wins**.
>
> The wording below is the owner's, verbatim. The only normalisation is that the
> owner's `====` separators became Markdown section headings; no requirement text
> was changed. Anything added by an agent in this file must be marked as such.
>
> **Rule carried with the brief:** a piece/section of this plan is *complete*
> only when its fix, its failing-without-it test, its docs line and its scoped
> evidence exist; **the PR for that piece is opened and merged only then** — one
> piece/section per PR, never a partial one.

---

You are working on an existing LOVE2D game project that is a fan-made fusion/port inspired by Undertale and Undertale Yellow.

Your task is to thoroughly debug and fix the current game without unnecessarily rewriting working systems.

**IMPORTANT:**

- Do NOT rebuild the game from scratch.
- Do NOT replace working systems just because they are unfamiliar.
- First inspect the existing architecture, scene/state management, rendering pipeline, room transitions, entity spawning, fonts, and update/draw loops.
- Understand how the Undertale side and the Undertale Yellow side are currently separated and how the player transitions between them.
- Preserve existing gameplay, dialogue, rooms, mechanics, assets, and behavior wherever possible.
- Make targeted fixes.
- Avoid introducing duplicate systems when an existing system can be corrected.
- Do not "fake" a fix by hiding symptoms.
- Fix the underlying cause.
- Before modifying code, trace the relevant execution paths.
- After making changes, check for regressions on BOTH sides of the game.

The current project has several major problems.

## 1. UNDERTALE YELLOW FONT PROBLEMS

On the Undertale Yellow side of the game, fonts are incorrect.

There are two related problems:

1. The font being used is not the correct font/style for the Undertale Yellow portion of the game.
2. Some Undertale Yellow text is being rendered vertically instead of horizontally.

Investigate the entire text rendering pipeline.

Check:

- Font loading
- Font file paths
- Font initialization
- Font caching
- love.graphics.newFont usage
- love.graphics.setFont usage
- Any custom text renderer
- Text wrapping
- Text alignment
- Text scaling
- Text rotation
- Transform stacks
- love.graphics.push/pop
- love.graphics.translate
- love.graphics.rotate
- love.graphics.scale
- Any coordinate transforms inherited from room/camera rendering
- Dialogue rendering
- UI rendering
- Battle text rendering if applicable
- Menu text
- NPC dialogue
- Signs/interactions
- Any Undertale Yellow-specific rendering code

The vertical text issue is especially important.

Do NOT simply rotate the text back without understanding why it is being rotated.

Determine whether the vertical orientation is caused by:

- A graphics transform not being reset
- A room/camera transform
- A sprite/entity transform
- A dialogue renderer inheriting a rotation
- A coordinate system conversion
- A font rendering function
- Incorrect width/height parameters
- Incorrect text wrapping
- A mistaken love.graphics.printf configuration
- A custom renderer
- A transformation left active from drawing another object

Make sure every text rendering operation runs in the correct graphics state.

Use love.graphics.push() and love.graphics.pop() where appropriate so transformations do not leak between unrelated rendering operations.

If the Undertale Yellow side is supposed to have a specific font, identify the existing font assets in the repository and determine which one is actually intended.

Do not download random fonts or substitute a generic font unless the project genuinely has no appropriate asset.

Check the Undertale side as well after fixing this.

The final result should be:

- Undertale text remains correct.
- Undertale Yellow text uses its intended font.
- Undertale Yellow text renders horizontally.
- Dialogue is not rotated.
- Menus are not rotated.
- UI text is not rotated.
- Text wrapping remains correct.
- Text positioning remains correct.
- No graphics transform leaks into subsequent rendering.

## 2. UNDERTALE YELLOW SIDE HAS SEVERE LAG

The Undertale Yellow portion of the game currently experiences heavy performance problems.

Do NOT immediately optimize random code.

First identify what is actually causing the performance degradation.

Profile/inspect the relevant update and draw paths.

Compare:

UNDERTALE SIDE

vs

UNDERTALE YELLOW SIDE

Determine what systems are significantly more expensive on the Undertale Yellow side.

Investigate:

- love.update
- love.draw
- Room loading
- Tile rendering
- Tilemap generation
- Entity updates
- NPC updates
- Collision detection
- Player updates
- Particle systems
- Animations
- Dialogue systems
- Font rendering
- love.graphics.print
- love.graphics.printf
- Sprite drawing
- Repeated image loading
- Repeated font loading
- Repeated audio loading
- File I/O during gameplay
- JSON/data parsing during gameplay
- Pathfinding
- Collision loops
- Large nested loops
- Tables being recreated every frame
- Garbage collection
- Coroutines
- Timers
- Event systems
- Camera calculations
- Shader usage
- Canvas rendering
- Scaling
- Duplicate entities
- Accidental infinite loops
- Accidental recursive calls
- Excessive draw calls
- Excessive object creation
- Unbounded particle/entity creation
- Systems being registered multiple times

Pay particular attention to whether the River Person/River Man transition is causing duplicate entities or duplicated update loops.

Also investigate whether the Undertale Yellow room is:

- Being drawn multiple times
- Being updated multiple times
- Loaded multiple times
- Creating entities repeatedly
- Registering callbacks repeatedly
- Creating duplicate collision objects
- Creating duplicate NPCs
- Creating duplicate player objects
- Recreating fonts/images every frame
- Rebuilding tilemaps every frame

Do not optimize by simply lowering resolution, removing effects, reducing game logic, or disabling features.

The goal is to fix the underlying performance bug while preserving visual and gameplay behavior.

Use caching where appropriate.

For example:

- Load fonts once.
- Load images once.
- Cache room resources.
- Avoid recreating objects every frame.
- Avoid unnecessary allocations inside love.update/love.draw.
- Avoid repeated expensive calculations.
- Avoid duplicate event registration.
- Avoid rebuilding static geometry every frame.

If there is a specific runaway system, fix that system instead of adding arbitrary frame-rate caps.

The game should maintain a stable frame rate on the Undertale Yellow side comparable to the Undertale side.

## 3. RIVER MAN / RIVER PERSON DUPLICATES THE PLAYER

There is a serious bug involving the River Man/River Person transition.

When interacting with the River Man/River Person:

- Two identical copies of the Player character are created.
- The duplicate player appears to interfere with the transition.
- The Player cannot properly return to the Undertale side afterward.

This needs to be treated as a state/entity lifecycle bug.

Do NOT simply delete one of the players visually.

Find out why the second player exists.

Investigate:

- Player initialization
- Player constructor
- Room loading
- Room transitions
- Scene transitions
- River Person interaction
- Boat boarding
- Boat exit
- Player respawning
- Player persistence
- Save/load systems
- Global player references
- Local player references
- Entity manager
- Room entity lists
- Transition callbacks
- Teleport functions
- Spawn functions
- Game state initialization
- World switching
- Undertale <-> Undertale Yellow state management

Search the entire codebase for every place where the Player is instantiated.

For example, inspect every occurrence of:

- Player.new
- createPlayer
- spawnPlayer
- newPlayer
- player = ...
- entities:add(player)
- world:add(player)
- room:add(player)
- player initialization functions

Determine whether the Player is supposed to be:

A) persistent between rooms

or

B) destroyed and recreated on room transition.

Then follow that architecture consistently.

Do NOT mix both approaches.

A likely bug may be something similar to:

1. Existing Player survives the transition.
2. Destination room creates another Player.
3. Both are added to the entity/update/render lists.
4. Both receive input/update calls.
5. One or both become attached to the wrong room/state.

But do not assume this is the cause. Verify it in the actual code.

There must ultimately be exactly ONE active Player instance.

The fix must ensure:

- No duplicate Player.
- Only one Player receives input.
- Only one Player is updated.
- Only one Player is rendered.
- Only one Player participates in collisions.
- Player state is preserved appropriately.
- Player position is correct after transition.
- Player can board the boat.
- Player can leave the boat.
- Player can return to the Undertale side.
- Returning does not create another Player.
- Repeatedly using the River Person does not progressively create more Players.

Test repeated transitions specifically.

For example:

Undertale
→ River Person
→ Undertale Yellow
→ River Person
→ Undertale
→ River Person
→ Undertale Yellow

The number of active Player objects should never increase.

## 4. RIVER PERSON / RIVER MAN BOAT DESTINATION IS WRONG

The River Person's boat currently does not lead to the correct destination.

Investigate the transition logic rather than simply changing coordinates until it appears correct.

Find:

- The River Person interaction code.
- Boat interaction code.
- Boat movement code.
- Transition trigger.
- Destination room/state.
- Destination spawn coordinates.
- World/side selection.
- Any teleport/warp functions.
- Any room ID or map ID associated with the boat.
- Any Undertale vs Undertale Yellow world-switching logic.

Determine the intended route.

The River Person should reliably transport the player to the correct destination.

Make sure the following are logically separated:

SOURCE ROOM
PLAYER
RIVER PERSON
BOAT
TRANSITION
DESTINATION ROOM
DESTINATION SPAWN POINT

The transition should explicitly define its destination rather than relying on accidental current state.

For example, conceptually:

River Person interaction
→ board boat
→ transition animation
→ change world/room
→ load destination room
→ place existing Player at destination spawn
→ remove/disable old room entities
→ resume gameplay

Do not create a new Player unless the architecture explicitly requires it.

If the game has a room registry, world registry, scene manager, or transition manager, use the existing system rather than creating a parallel transition system.

## 5. STATE MANAGEMENT

Because multiple bugs appear to happen around the Undertale / Undertale Yellow boundary, carefully inspect the game's state architecture.

Determine how the project represents:

- Current game
- Current world
- Current room
- Current scene
- Current player
- Active entities
- Persistent entities
- Room-specific entities
- Transition state
- Dialogue state
- Boat state
- Camera state

Look for global variables or references that may become stale.

Pay special attention to:

- Old room references
- Old entity arrays
- Old Player references
- New Player references
- Camera references
- Collision world references
- Event listeners
- Timers
- Coroutines
- Transition callbacks

When switching worlds, make sure the old world does not continue updating in the background.

There should not be:

World A update
+
World B update
+
World A draw
+
World B draw

unless that is explicitly required.

The active world should be unambiguous.

## 6. GRAPHICS STATE SAFETY

Because there is a vertical text problem and potentially different rendering systems between the two games, inspect all graphics state management.

Look for code using:

- love.graphics.push
- love.graphics.pop
- love.graphics.translate
- love.graphics.rotate
- love.graphics.scale
- love.graphics.origin
- love.graphics.setFont
- love.graphics.setColor
- love.graphics.setShader
- love.graphics.setCanvas
- love.graphics.setScissor
- love.graphics.setBlendMode

Make sure temporary rendering changes do not leak into unrelated systems.

For example:

push
→ transform
→ draw rotated object
→ pop

rather than:

transform
→ draw rotated object
→ forget to reset transform
→ all later text becomes rotated.

Pay special attention to the Undertale Yellow renderer because its text appears vertically.

## 7. RESOURCE MANAGEMENT

Inspect whether the Undertale Yellow side repeatedly loads assets.

Fonts, images, sounds, music, shaders, and maps should generally be loaded once and reused rather than loaded every frame or every interaction.

Look for patterns like:

```lua
function draw()
  local font = love.graphics.newFont(...)
end
```

or:

```lua
function update()
  local image = love.graphics.newImage(...)
end
```

or repeated:

require(...)
JSON decoding
file reading
asset creation

inside frequently executed functions.

Correct these where appropriate.

Do not over-engineer an asset manager if the project already has one.

## 8. DO NOT BREAK THE EXISTING UNDERTALE SIDE

This is extremely important.

The Undertale side currently works well enough that the primary goal is to fix the Undertale Yellow side and the bridge between both games.

After every significant change, verify that:

- Undertale rooms still load.
- Undertale player movement still works.
- Undertale collisions still work.
- Undertale dialogue still works.
- Undertale fonts still work.
- Undertale rendering still works.
- Undertale music/audio still works.
- Existing transitions still work.
- The River Person still works.
- The player does not duplicate.
- Returning from Undertale Yellow does not break the Undertale side.

Do not replace Undertale's existing systems merely to make the Yellow side easier.

## 9. DEBUGGING APPROACH

Before changing code, create a mental map of the relevant architecture.

Trace this path:

GAME START
→ WORLD/ROOM INITIALIZATION
→ PLAYER INITIALIZATION
→ UNDERTALE GAMEPLAY
→ RIVER PERSON INTERACTION
→ BOAT
→ TRANSITION
→ UNDERTALE YELLOW ROOM
→ PLAYER UPDATE
→ PLAYER DRAW
→ TEXT/DIALOGUE DRAW
→ RETURN TRANSITION
→ UNDERTALE ROOM
→ PLAYER RESTORATION

Identify where state changes at every step.

Then inspect the actual code responsible for each stage.

For the duplicate Player bug, log or otherwise inspect:

- Player object creation count
- Player object identity/reference
- Current room
- Current world
- Entity count
- Active Player count

For example, temporarily add diagnostic information such as:

PLAYER CREATED
PLAYER ID
CURRENT ROOM
CURRENT WORLD

Do this only while debugging. Remove noisy debug output once the problem is understood.

For the performance issue, identify what is consuming excessive update/draw work.

Do not blindly optimize.

For the font issue, identify exactly where the rotation/transform originates.

For the boat issue, identify exactly where the destination is determined.

## 10. IMPLEMENTATION REQUIREMENTS

When fixing the code:

1. Make the smallest reasonable architectural changes.
2. Reuse existing systems.
3. Avoid duplicate managers.
4. Avoid duplicate Player objects.
5. Avoid duplicate event handlers.
6. Avoid unnecessary rewrites.
7. Preserve existing assets.
8. Preserve existing gameplay behavior.
9. Preserve Undertale functionality.
10. Keep Undertale Yellow functionality intact while correcting its bugs.

If you discover that several symptoms share the same root cause, fix the root cause rather than applying several unrelated patches.

For example:

If duplicate Player instances are caused by room initialization running twice, fix the room initialization lifecycle rather than adding:

```lua
if playerAlreadyExists then return end
```

in several unrelated locations.

Likewise, if vertical text is caused by a leaked transform, fix the graphics state rather than rotating every individual text call.

## 11. TESTING CHECKLIST

After implementing the fixes, test the following scenarios.

**TEST A: UNDERTALE**

- Start game.
- Enter normal Undertale gameplay.
- Move Player.
- Interact with NPCs.
- Display dialogue.
- Verify text orientation.
- Verify fonts.
- Verify rendering.
- Verify no performance regression.

**TEST B: ENTER UNDERTALE YELLOW**

- Approach River Person.
- Start boat interaction.
- Board boat.
- Transition.
- Verify destination room.
- Verify only one Player exists.
- Verify Player position.
- Verify camera.
- Verify collisions.
- Verify movement.

**TEST C: UNDERTALE YELLOW PERFORMANCE**

Remain in the Undertale Yellow area for an extended period.

Check for:

- FPS drops.
- Increasing memory usage.
- Increasing entity count.
- Increasing Player count.
- Increasing draw/update workload.
- Repeated asset loading.

Move between multiple rooms if possible.

**TEST D: UNDERTALE YELLOW TEXT**

Check:

- Dialogue
- NPC text
- Menus
- Signs
- UI
- Battle text if present

All text should be:

- Correctly oriented.
- Correctly scaled.
- Correctly positioned.
- Using the intended Undertale Yellow font.

**TEST E: RETURN TO UNDERTALE**

Use the River Person/boat to return.

Verify:

- Correct destination.
- Correct spawn position.
- Exactly one Player.
- No duplicate Player sprite.
- No duplicate collisions.
- No stuck transition.
- Undertale gameplay resumes normally.

**TEST F: REPEATED TRANSITIONS**

Repeat the transition multiple times.

Example:

Undertale
→ Yellow
→ Undertale
→ Yellow
→ Undertale
→ Yellow
→ Undertale

After every transition verify:

- Player count = 1
- Active world = expected world
- Active room = expected room
- Old room is not updating
- No duplicate entities
- No accumulating performance degradation

## 12. FINAL CODE QUALITY CHECK

Once the bugs are fixed:

Search the codebase for related duplicate logic and temporary debugging code.

Remove:

- Debug prints
- Temporary hacks
- Unused variables
- Dead transition code
- Duplicate Player creation paths
- Duplicate event registrations
- Temporary performance workarounds
- Unused font loading
- Unused rendering transforms

Do not remove legitimate systems simply because they look unused without verifying their purpose.

Finally, provide a concise report containing:

1. Root cause of the Undertale Yellow font issue.
2. Root cause of the vertical text issue.
3. Root cause of the Undertale Yellow performance problem.
4. Root cause of the duplicate Player problem.
5. Root cause of the incorrect River Person boat destination.
6. Files changed.
7. What was changed in each file.
8. Any architectural changes.
9. Any remaining known issues.
10. Tests performed and their results.

Most importantly:

DO NOT just patch symptoms.

Understand the existing LOVE2D architecture first, identify the underlying causes, then implement targeted fixes that preserve the existing Undertale and Undertale Yellow gameplay.
