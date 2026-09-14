-- Cross-game travel for the merged build.
--
-- The two doors are the games' own hubs, so nothing is bolted on outside them:
--   * Undertale's River Person boat. Its destination choice already ends in
--     obj_dogboat_thing travelling to one of three dock rooms (70 Snowdin,
--     125 Waterfall, 140 Hotland). Holding X - the cancel button, on screen
--     for the touch controls - during the ride sends the same choice to the
--     matching Undertale Yellow landing spot instead.
--   * Yellow's UGPS mail whale. obj_fast_travel_menu lists global.fast_travel_list
--     and writes global.fast_travel_newroom/newx/newy for the entry the player
--     highlighted. The bridge adds three Undertale dock entries to that list and
--     fills the same three globals for them, so Yellow's own whale code performs
--     the travel.
--
-- Every destination room and every landing coordinate comes from the games' own
-- data: the docks are obj_dogboat_thing's three room_goto targets, and the
-- Yellow spots are the room/x/y triples in obj_fast_travel_menu's switch.
-- Undertale dock landings are read from the dock room's own boat instance.
local Travel = {}
Travel.VERSION = 1
Travel.SAVE_FILE = "merge.sav"

local RIVER_DESTINATIONS = {
    [70] = {label = "Snowdin - Forest", room = "rm_snowdin_11_yellow", x = 200, y = 100},
    [125] = {label = "Dunes - West Mines", room = "rm_dunes_05", x = 510, y = 170},
    [140] = {label = "Hotland - Crossroads", room = "rm_hotland_02", x = 170, y = 120},
}
local WHALE_DESTINATIONS = {
    {label = "Snowdin - Dock", room = 70},
    {label = "Waterfall - Dock", room = 125},
    {label = "Hotland - Dock", room = 140},
}
-- The cancel button, in both worlds' own spelling: Undertale's obj_screen runs
-- keyboard_set_map(88, 16), so a physical X reaches Undertale code as vk_shift,
-- while Yellow checks ord("X") itself. Holding either counts as holding X.
local X_BUTTONS = {88, 16}

function Travel.install(R)
    if R.manifest.game ~= "merged" then return nil end
    local base = R.manifest.yellow_base or 1000000
    local yellowNames = R.manifest.yellow_names or {}
    local undertaleNames = R.manifest.names or {}
    local B = R.builtins

    local travel = setmetatable({
        runtime = R,
        base = base,
        crossings = 0,
        riverLatch = false,
        pendingInit = nil,
        world = nil,
        ids = {
            undertale = {player = undertaleNames["obj_mainchara"], boat = undertaleNames["obj_dogboat_thing"], controller = nil},
            yellow = {
                player = yellowNames.objects and yellowNames.objects["obj_pl"],
                controller = yellowNames.objects and yellowNames.objects["obj_controller"],
                whaleMenu = yellowNames.objects and yellowNames.objects["obj_fast_travel_menu"],
            },
        },
        riverDestinations = RIVER_DESTINATIONS,
        whaleDestinations = WHALE_DESTINATIONS,
    }, {__index = Travel})
    R.travel = travel
    travel:loadSave()
    travel.world = travel:worldOf(R.manifest.room_order and R.manifest.room_order[1] or 0)

    local gotoRoom = R.gotoRoom
    function R:gotoRoom(index)
        return gotoRoom(self, travel:resolve(index))
    end
    local loadRoom = R.loadRoom
    function R:loadRoom(...)
        local results = {loadRoom(self, ...)}
        travel:afterLoadRoom((...))
        return unpack(results)
    end
    local step = R.step
    function R:step(...)
        travel:beforeStep()
        return step(self, ...)
    end
    return travel
end

function Travel:worldOf(room)
    return (type(room) == "number" and room >= self.base) and "yellow" or "undertale"
end

function Travel:exists(object)
    if not object then return false end
    for _, instance in ipairs(self.runtime.instances) do
        if instance.alive and instance.v.object_index == object then return true end
    end
    return false
end

function Travel:yellowRoom(name)
    local rooms = (self.runtime.manifest.yellow_names or {}).rooms or {}
    local id = rooms[name]
    if not id then
        self.runtime:unsupported("travel:" .. tostring(name), "Merged travel destination is missing from the converted Yellow manifest.")
    end
    return id
end

-- Landing spots come from the room's own instance list: Undertale's docks carry
-- the boat that would have brought Frisk there, and a Yellow room carries its
-- own player start. Only when a room has neither does the bridge fall back to
-- the room's centre, and it says so.
function Travel:landingSpot(world, roomId, coordinates)
    if coordinates then return coordinates[1], coordinates[2] end
    local path = self.runtime.manifest.rooms[roomId]
    local room = path and require(path) or nil
    local ids = self.ids[world] or {}
    if room and room.instances then
        for _, wanted in ipairs({ids.boat, ids.player}) do
            if wanted then
                for _, instance in ipairs(room.instances) do
                    if instance.object == wanted then return instance.x, instance.y end
                end
            end
        end
    end
    self.runtime:warn("travel-landing:" .. tostring(roomId),
        "Room " .. tostring(roomId) .. " has no boat or player instance to land beside; arriving at its centre instead.")
    return (room and room.width or 320) / 2, (room and room.height or 240) / 2
end

function Travel:resolve(index)
    local target = index
    if self.world == "undertale" and self.riverLatch and RIVER_DESTINATIONS[index] then
        local destination = RIVER_DESTINATIONS[index]
        target = self:yellowRoom(destination.room)
        self.riverLatch = false
        self.pendingCoordinates = {destination.x, destination.y}
    end
    local world = self:worldOf(target)
    if world ~= self.world then self:beginCrossing(world, target) end
    return target
end

function Travel:beginCrossing(world, room)
    local R = self.runtime
    local scope = nil
    for _, instance in ipairs(R.instances) do
        if instance.alive then scope = instance break end
    end
    -- Persistent instances belong to the world they were created in. Leaving
    -- them alive would put a second player and a second set of controllers in
    -- the room, so the world being left is shut down here and the world being
    -- entered is initialised once its room has loaded.
    for _, instance in ipairs(R.instances) do
        if instance.alive and instance.v.persistent and self:worldOf(instance.v.object_index) ~= world then
            R:destroy(instance, true)
        end
    end
    -- Before the room loads: Yellow's own room creation code registers fast
    -- travel points, which needs the globals scr_initialize creates.
    self:initialize(world, scope)
    if world == "yellow" and self.pendingCoordinates then
        -- Yellow's rooms spawn their own player from these globals while the
        -- room loads, and scr_initialize has just reset them to its defaults,
        -- so the landing spot is published here, before the room is entered.
        R.global.player_x = self.pendingCoordinates[1]
        R.global.player_y = self.pendingCoordinates[2]
    end
    self.world = world
    self.crossings = self.crossings + 1
    self.pendingInit = {world = world, room = room, coordinates = self.pendingCoordinates}
    self.pendingCoordinates = nil
end

-- Yellow initialises its own world from a menu with scr_initialize(), which
-- creates global.encounter_list, global.fast_travel_list and the rest. Entering
-- a Yellow room without it would leave those globals at zero, so the crossing
-- runs the game's own initializer first - the same call obj_mainmenu_debug makes
-- before room_goto. Undertale needs no equivalent here: the merged build boots
-- through Undertale's own title flow, which runs SCR_GAMESTART itself.
function Travel:initialize(world, scope)
    if world ~= "yellow" then return end
    local R = self.runtime
    local name = "scr_initialize"
    if not (R.manifest.scripts or {})[name] then
        R:unsupported("travel:" .. name, "Yellow's world initializer is missing from the merged manifest.")
    end
    if not scope then
        -- Every instance of the world being left can already be gone. The
        -- initializer only reads the caller's position, so it runs from a
        -- documented stand-in at the room origin instead of failing.
        R:warn("travel-scope", "scr_initialize ran from a stand-in scope at 0,0: no instance of the world being left was alive.")
        scope = {_instance = true, id = -1, alive = true, active = true, v = R.defaults(0)}
        scope.v.x, scope.v.y, scope.v.object_index = 0, 0, -1
    end
    R:script(name, R:scope(scope))
end

function Travel:afterLoadRoom(roomId)
    local pending = self.pendingInit
    if not pending or pending.room ~= roomId then return end
    self.pendingInit = nil
    local R = self.runtime
    local ids = self.ids[pending.world]
    if ids.controller and not self:exists(ids.controller) then R:create(ids.controller, 0, 0) end
    if ids.player and not self:exists(ids.player) then
        local x, y = self:landingSpot(pending.world, roomId, pending.coordinates)
        if pending.world == "yellow" then
            -- Yellow's own player spawns from these globals (scr_initialize sets
            -- them, and the whale travel writes the same pair), so the landing
            -- spot has to be published there too, not only to instance_create.
            R.global.player_x = x
            R.global.player_y = y
        end
        R:create(ids.player, x, y)
    end
    if pending.coordinates and ids.player then
        -- Yellow's own whale crossing hands the landing spot to its transition
        -- object, which a boat crossing does not involve, so the bridge places
        -- the player itself once the room has loaded.
        for _, instance in ipairs(R.instances) do
            if instance.alive and instance.v.object_index == ids.player then
                instance.v.x, instance.v.y = pending.coordinates[1], pending.coordinates[2]
                instance.v.xstart, instance.v.ystart = instance.v.x, instance.v.y
                instance.v.xprevious, instance.v.yprevious = instance.v.x, instance.v.y
            end
        end
    end
    self:offerWhaleDestinations()
    -- Saved once the crossing has actually landed, so last_room is the room the
    -- player is standing in and not the one they left.
    self:save()
end

function Travel:beforeStep()
    local R = self.runtime
    if self.world == "undertale" then
        -- Holding X during the boat ride aims the same choice at Yellow.
        local held = false
        for _, code in ipairs(X_BUTTONS) do
            if R.input:check(code) then held = true break end
        end
        if self:exists(self.ids.undertale.boat) and held then
            if not self.riverLatch then
                R:warn("travel-river",
                    "Cross-game boat ride: X is held, so this River Person destination goes to Undertale Yellow instead.")
            end
            self.riverLatch = true
        end
        return
    end
    self:offerWhaleDestinations()
    -- The whale menu only knows its own seven entries; fill the travel globals
    -- for ours so Yellow's own whale code carries out the trip.
    local labels = {}
    for _, destination in ipairs(WHALE_DESTINATIONS) do labels[destination.label] = destination.room end
    local selected = nil
    for _, instance in ipairs(R.instances) do
        if instance.alive and instance.v.object_index == self.ids.yellow.whaleMenu then
            selected = instance.v.point_selected
        end
    end
    local chosen = labels[selected] or labels[R.global.fast_travel_point]
    if chosen then
        local x, y = self:landingSpot("undertale", chosen)
        R.global.fast_travel_newroom = chosen
        R.global.fast_travel_newx = x
        R.global.fast_travel_newy = y
    end
end

function Travel:offerWhaleDestinations()
    local R = self.runtime
    local list = R.global.fast_travel_list
    if not list or type(list) ~= "number" or not R.truth(R.builtins.ds_exists(nil, list, 2)) then return end
    for _, destination in ipairs(WHALE_DESTINATIONS) do
        if R.builtins.ds_list_find_index(nil, list, destination.label) == -1 then
            R.builtins.ds_list_add(nil, list, destination.label)
        end
    end
    R.builtins.ds_list_sort(nil, list, false)
end

-- A merged save layer of its own. Each game keeps the save files it already
-- writes (Undertale's INIs, Yellow's Save.sav), so an existing save from a
-- single-game build is never rewritten: the merged layer is additive and
-- versioned, and reading a file without a version stamps it as migrated.
function Travel:loadSave()
    local R, B = self.runtime, self.runtime.builtins
    B.ini_open(nil, Travel.SAVE_FILE)
    local version = B.ini_read_real(nil, "merge", "version", 0)
    if version == 0 then
        self.migrated = true
        B.ini_write_real(nil, "merge", "version", Travel.VERSION)
        B.ini_write_real(nil, "merge", "crossings", 0)
    elseif version ~= Travel.VERSION then
        B.ini_close()
        R:unsupported("merge.sav version " .. tostring(version),
            "This build reads merged save version " .. Travel.VERSION .. "; nothing was guessed at.")
    end
    self.crossings = B.ini_read_real(nil, "merge", "crossings", 0)
    self.lastRoom = B.ini_read_real(nil, "merge", "last_room", -1)
    B.ini_close()
end

function Travel:save()
    local B = self.runtime.builtins
    B.ini_open(nil, Travel.SAVE_FILE)
    B.ini_write_real(nil, "merge", "version", Travel.VERSION)
    B.ini_write_real(nil, "merge", "crossings", self.crossings)
    B.ini_write_real(nil, "merge", "last_room", self.runtime.vars.room)
    B.ini_write_string(nil, "merge", "world", self.world or "undertale")
    B.ini_close()
    self.runtime:flushSaves()
end

return Travel
