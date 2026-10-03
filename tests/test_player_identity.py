"""Debug piece D3 (brief §3, §5): exactly one Player, ever.

The merged build follows each game's own player architecture:

* **Undertale** places ``obj_mainchara`` in the room (278 of 334 rooms) and the
  object is *not* persistent, so the player is recreated by every room load.
* **Undertale Yellow** creates ``obj_pl`` once (``scr_initialize``) and the
  object *is* persistent, so one instance is carried from room to room; Yellow
  rooms never place it (their ``obj_pl`` reference is the view's follow object).

The seam between the two is the crossing, and it is the only place a world
changes. These tests pin that: the world being left is shut down when the
destination room actually loads — never earlier, because GameMaker defers
``room_goto`` to the end of the step and Yellow's own ``obj_transition`` keeps
running afterwards:

    room_goto(newRoom);
    if (instance_exists(obj_pl)) { obj_pl.x = xx; ... } else instance_create(xx, yy, obj_pl);

Tearing the world down inside ``room_goto`` made that ``else`` branch create a
second, persistent Clover which then rode into the Undertale room next to its
own ``obj_mainchara``: the owner's two identical players.

Not claimed: Android, native rendering, audio, or a hand-played route. Headless
converted flow only.
"""
import pytest

from test_yellow_merge import live, merged, vm, yellow_rooms  # noqa: F401


def boot(vm):
    assert vm.execute(
        "local ok,err=pcall(function() R:start() end) return ok and 'ok' or tostring(err)"
    ) == "ok"


#: Shared Lua helpers: the player census, and Yellow's own way of changing room.
CENSUS = '''
    FRISK = R.manifest.names["obj_mainchara"]
    CLOVER = R.manifest.yellow_names.objects["obj_pl"]
    CONTROLLER = R.manifest.yellow_names.objects["obj_controller"]
    DOCK = R.manifest.names["room_fire_dock"]
    YELLOW = R.manifest.yellow_names.rooms["rm_hotland_02"]
    function players()
        return countInstances(FRISK) + countInstances(CLOVER)
    end
    function anyScope()
        for _, i in ipairs(R.instances) do if i.alive then return i end end
    end
    -- Yellow changes room through its own obj_transition, which is what the
    -- UGPS whale hands the destination to (obj_mail_whale/Other_11.gml).
    function yellowTransitionTo(room, x, y, budget)
        R:call("scr_change_room", R:scope(anyScope()), room, x or 220, y or 160)
        local worst = players()
        for _ = 1, budget or 60 do
            tick(1)
            worst = math.max(worst, players())
            if R.travel.world == R.travel:worldOf(room) and R.vars.room == room then break end
        end
        tick(2)
        return math.max(worst, players())
    end
'''


@live
def test_a_room_goto_does_not_tear_down_the_world_being_left(vm):
    """The root cause, in isolation.

    ``room_goto`` only requests a room: in GameMaker the change happens at the
    end of the step, so every statement after it still runs in the old room.
    Before the fix the crossing ran inside ``R:gotoRoom``, so the persistent
    Yellow player was already gone on the next line.
    """
    boot(vm)
    assert vm.execute(CENSUS + '''
        crossTo(YELLOW)
        if countInstances(CLOVER) ~= 1 then return "Yellow did not start with one player" end
        R:gotoRoom(DOCK)
        -- Exactly where Yellow's obj_transition asks its question.
        if countInstances(CLOVER) ~= 1 then
            return "the Yellow player was destroyed inside room_goto: " .. countInstances(CLOVER)
        end
        if R.travel.world ~= "yellow" then return "the world changed before the room loaded" end
        R:applyTransitions(); tick(1)
        if R.travel.world ~= "undertale" then return "the room load did not cross" end
        if countInstances(CLOVER) ~= 0 then return "the Yellow player survived the crossing" end
        if countInstances(FRISK) ~= 1 then return "the dock did not place exactly one Frisk" end
        return "ok"
    ''') == "ok"


@live
def test_yellows_own_transition_does_not_leave_a_second_player(vm):
    """The owner's symptom: two identical players in the Undertale room.

    Both are drawn as Frisk (``port/frisk.lua`` remaps Clover), which is why the
    report says *identical copies*. Before the fix this returns frisk=1 clover=1.
    """
    boot(vm)
    assert vm.execute(CENSUS + '''
        crossTo(YELLOW)
        local worst = yellowTransitionTo(DOCK)
        if R.vars.room ~= DOCK then return "the transition did not reach the dock" end
        if countInstances(CLOVER) ~= 0 then
            return "a Yellow player rode into the Undertale room: clover=" .. countInstances(CLOVER)
        end
        if countInstances(FRISK) ~= 1 then return "frisk=" .. countInstances(FRISK) end
        if worst > 1 then return "two players were alive at once during the return: " .. worst end
        return "ok"
    ''') == "ok"


@live
def test_repeated_crossings_never_grow_the_player_count(vm):
    """Undertale → Yellow → Undertale → Yellow → ... never adds a player.

    The brief asks for exactly this sequence, through both doors: the boat's own
    ``room_goto`` on the way out and Yellow's transition object on the way back.
    The census is taken on every tick, not only at the landings.
    """
    boot(vm)
    assert vm.execute(CENSUS + '''
        local worst, census = 0, {}
        for round = 1, 3 do
            R:gotoRoom(YELLOW); R:applyTransitions()
            for _ = 1, 4 do tick(1); worst = math.max(worst, players()) end
            census[#census + 1] = ("round %d yellow frisk=%d clover=%d controllers=%d")
                :format(round, countInstances(FRISK), countInstances(CLOVER), countInstances(CONTROLLER))
            if countInstances(CLOVER) ~= 1 then return census[#census] end
            if countInstances(CONTROLLER) ~= 1 then return census[#census] end
            worst = math.max(worst, yellowTransitionTo(DOCK))
            census[#census + 1] = ("round %d undertale frisk=%d clover=%d")
                :format(round, countInstances(FRISK), countInstances(CLOVER))
            if countInstances(FRISK) ~= 1 or countInstances(CLOVER) ~= 0 then return census[#census] end
        end
        if worst > 1 then return "player count reached " .. worst .. ": " .. table.concat(census, " | ") end
        return "ok"
    ''') == "ok"


@live
def test_loading_a_save_recorded_in_the_other_world_leaves_one_player(vm):
    """A restore is not a crossing, but the entity rule still holds.

    ``Save:enter`` deliberately suppresses the crossing (no scratch-flag clear,
    no content initialization, no travel save over the document it just read).
    The world being left must still be retired, or the restored Undertale room
    gets the persistent Clover as well as its own Frisk.
    """
    boot(vm)
    assert vm.execute(CENSUS + '''
        crossTo(YELLOW)
        if countInstances(CLOVER) ~= 1 then return "Yellow did not start with one player" end
        -- A save point recorded in Undertale, read back while the player is in Yellow.
        R.saveBridge:write({ area = DOCK, world = "undertale", x = 220, y = 160 })
        R:call("scr_load", R:scope(anyScope()))
        R:applyTransitions(); tick(2)
        if R.vars.room ~= DOCK then return "the load did not place the saved room" end
        if countInstances(CLOVER) ~= 0 then
            return "the Yellow player survived the restore: " .. countInstances(CLOVER)
        end
        if countInstances(FRISK) ~= 1 then return "frisk=" .. countInstances(FRISK) end
        return "ok"
    ''') == "ok"


@live
def test_the_crossing_keeps_the_one_shared_player_record(vm):
    """One Player, not one player entity per world.

    The entity is each world's own adapter, but the progression record, the
    controller and the inventory are the fusion's single Player (pieces 5a-5d).
    A crossing must move it, not replace it — and the world being left must stop
    (no persistent instance of it is left alive to update or draw).
    """
    boot(vm)
    assert vm.execute(CENSUS + '''
        crossTo(DOCK)
        local record, controller, inventory = R.player, R.player.controller, R.player.inventory
        R.player.hp = 11
        R.player.inventory[1] = "Butterscotch Pie"
        crossTo(YELLOW)
        if R.player ~= record then return "the crossing replaced the Player record" end
        if R.player.controller ~= controller then return "the crossing replaced the controller" end
        if R.player.inventory ~= inventory then return "the crossing replaced the inventory" end
        if R.player.hp ~= 11 then return "hp became " .. tostring(R.player.hp) end
        if R.player.inventory[1] ~= "Butterscotch Pie" then return "the inventory was reset" end
        for _, i in ipairs(R.instances) do
            if i.alive and i.v.persistent and R.travel:worldOf(i.v.object_index) ~= "yellow" then
                return "an Undertale persistent instance is still alive in Yellow: " .. tostring(i.v.object_index)
            end
        end
        yellowTransitionTo(DOCK)
        if R.player ~= record then return "the return replaced the Player record" end
        if R.player.hp ~= 11 then return "hp became " .. tostring(R.player.hp) .. " on the way back" end
        for _, i in ipairs(R.instances) do
            if i.alive and i.v.persistent and R.travel:worldOf(i.v.object_index) ~= "undertale" then
                return "a Yellow persistent instance is still alive in Undertale: " .. tostring(i.v.object_index)
            end
        end
        return "ok"
    ''') == "ok"


# --- D6: the return side of the crossing (found by the acceptance run) -------
#
# The both-side regression pass (piece D6, brief section 8/11) found the
# "cannot properly return" half of the owner's report: two independent locks
# froze the Undertale side after ONE round trip, even though the player count
# stayed at one. Both are return-side state the outbound crossing retires and
# nothing restored.


@live
def test_the_return_restores_room_starts_boot_controllers(vm):
    """room_start's persistent controllers come back with their world.

    room_start (room_order[1], the boot room) places exactly two persistent
    instances: obj_time and obj_screen. The outbound crossing retires them with
    the rest of the Undertale world (Travel:retireOtherWorld), and before the
    fix nothing brought them back. obj_time is what obj_mainchara's Step reads
    for its direction gates and its alarms spawn the rooms' collision solids
    and markers; obj_screen owns keyboard_set_map (the Z/X/C maps the boat
    latch also honours). After one round trip both were gone: the returned-to
    room had no collision geometry and the player could never move again.
    Travel:ensureUndertaleControllers now recreates room_start's persistent
    placements when an Undertale room loads without them (their Create alone -
    the Game Start event that runs SCR_GAMESTART fires on the first room load
    only, never there).
    """
    boot(vm)
    assert vm.execute(CENSUS + '''
        local TIME = R.manifest.names["obj_time"]
        local SCREEN = R.manifest.names["obj_screen"]
        if countInstances(TIME) ~= 1 or countInstances(SCREEN) ~= 1 then
            return "boot did not place room_start's controllers"
        end
        crossTo(YELLOW)
        if countInstances(TIME) ~= 0 then return "obj_time survived into Yellow" end
        if countInstances(SCREEN) ~= 0 then return "obj_screen survived into Yellow" end
        yellowTransitionTo(DOCK)
        if countInstances(TIME) ~= 1 then return "the return left obj_time at " .. countInstances(TIME) end
        if countInstances(SCREEN) ~= 1 then return "the return left obj_screen at " .. countInstances(SCREEN) end
        crossTo(YELLOW); yellowTransitionTo(DOCK)
        if countInstances(TIME) ~= 1 or countInstances(SCREEN) ~= 1 then
            return "repeated crossings stacked or lost the boot controllers"
        end
        return "ok"
    ''') == "ok"


@live
def test_the_returned_undertale_side_still_moves(vm):
    """Movement survives the round trip (both return-side root causes).

    With obj_time restored, a stale ``global.interact`` still froze the player:
    the interaction lock is set by the world being left (its open dialogue,
    boat-ride text or whale menu) and every instance that would release it is
    retired by the crossing, while Undertale's obj_mainchara only moves at
    ``interact == 0``. The crossing now releases the lock with the rest of the
    crossing scratch (brief section 5). Before the two fixes every leg of this
    walk moved 0 px. Each leg is measured on its own: symmetric holds cancel
    out in net displacement.
    """
    boot(vm)
    assert vm.execute(CENSUS + '''
        crossTo(YELLOW)
        yellowTransitionTo(DOCK)
        if R.travel.world ~= "undertale" then return "never returned to Undertale" end
        local moved, legs = 0, {}
        for _, key in ipairs({37, 39, 38, 40}) do
            local p = R:select(FRISK)[1]
            local x0, y0 = p.v.x, p.v.y
            hold(key, 20)
            p = R:select(FRISK)[1]
            local d = math.abs(p.v.x - x0) + math.abs(p.v.y - y0)
            legs[#legs + 1] = d
            moved = moved + d
        end
        if moved == 0 then return "the player cannot move after the round trip" end
        return "ok"
    ''') == "ok"


@live
def test_a_crossing_releases_the_leaving_worlds_interaction_lock(vm):
    """The stale lock itself, in isolation, in both directions.

    In the games' own flows any post-room_goto release still runs before the
    room change is carried out (the change is deferred to the end of the step),
    so releasing it at the crossing only removes what nothing else would.
    """
    boot(vm)
    assert vm.execute(CENSUS + '''
        R.global.interact = 1
        crossTo(YELLOW)
        if R.global.interact ~= 0 then
            return "entering Yellow kept the lock: interact=" .. tostring(R.global.interact)
        end
        R.global.interact = 1
        crossTo(DOCK)
        if R.global.interact ~= 0 then
            return "returning to Undertale kept the lock: interact=" .. tostring(R.global.interact)
        end
        return "ok"
    ''') == "ok"
