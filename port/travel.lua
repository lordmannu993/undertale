-- Cross-game travel for the merged build.
--
-- The two doors are the games' own hubs, so nothing is bolted on outside them:
--   * Undertale's River Person boat. Its destination choice already ends in
--     obj_dogboat_thing travelling to one of three dock rooms (70 Snowdin,
--     125 Waterfall, 140 Hotland). Holding X - the cancel button, on screen
--     for the touch controls - during the ride sends the same choice to the
--     matching Undertale Yellow landing spot instead. The native two-option
--     location chooser also gets a category/pager layer so Yellow's seven own
--     stops are selectable without changing obj_choicer.
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
--
-- Both services are open from the first frame, because the owner asked for
-- exactly that: the River Person is there before Hotland (the shipped boat
-- deletes itself below global.plot 122 - see openRiverService) and the UGPS
-- whale flies to every stop its own menu can hold, not only the ones the
-- player has walked past (see openWhaleService). Neither service invents a
-- destination: the stops and their landings stay the games' own data.
local Travel = {}
Travel.VERSION = 1
Travel.SAVE_FILE = "merge.sav"

local RIVER_DESTINATIONS = {
    [70] = {label = "Snowdin - Forest", room = "rm_snowdin_11_yellow", x = 200, y = 100},
    [125] = {label = "Dunes - West Mines", room = "rm_dunes_05", x = 510, y = 170},
    [140] = {label = "Hotland - Crossroads", room = "rm_hotland_02", x = 170, y = 120},
}
-- SCR_TEXT is one of the decompiler-repaired switches.  The branch that was
-- written as case 587 in the GMX source is dispatched as 770 after the audited
-- label repair; 771 is its two-dock menu and 772 commits the selected dock.
-- Keep these IDs here instead of changing SCR_TEXT.gml (the repair is hash
-- guarded and the original script remains the source of truth).
local RIVER_TEXT_GREETING = 770
local RIVER_TEXT_LOCATIONS = 771
local RIVER_TEXT_RESULT = 772
local RIVER_TEXT_CUSTOM_START = 773

local WHALE_DESTINATIONS = {
    {label = "Snowdin - Dock", room = 70},
    {label = "Waterfall - Dock", room = 125},
    {label = "Hotland - Dock", room = 140},
}
-- The cancel button, in both worlds' own spelling: Undertale's obj_screen runs
-- keyboard_set_map(88, 16), so a physical X reaches Undertale code as vk_shift,
-- while Yellow checks ord("X") itself. Holding either counts as holding X.
local X_BUTTONS = {88, 16}

-- AUTO RUN is Undertale Yellow's own option (obj_config case 4, ini
-- "Controls"/"autorun"), and it means exactly what the pause-menu label says:
-- scr_normal_state sprints whenever the player is moving and the run cluster
-- is untouched, so walking runs; holding the run cluster then walks instead.
-- The value is a number, exactly as ini_read_real produces it - Yellow's own
-- checks compare it against GML's true/false (1/0).
local AUTORUN_ON, AUTORUN_OFF = 1, 0

-- The River Person's boat removes itself in its own Create event while
-- global.plot is under 122, which is the value Undyne's Waterfall chase writes
-- (obj_undyne_ex, obj_undynea_chaser, obj_undyneboss, obj_undynefall and the
-- two undynetrigger objects). Until then no dock has a boat at all - the
-- owner's report that the River Person cannot be used before Hotland. The
-- port lifts that single guard for the duration of that single event: every
-- other line of the Create event, which is where the boat builds itself,
-- runs exactly as the game wrote it.
local RIVER_PLOT = 122

-- Undertale Yellow registers its fast-travel stops as the player finds them:
-- four in the Dunes-42 whale scene (obj_mail_whale_dunes_42/Create_0.gml) and
-- one per room whose creation code calls scr_fasttravel_add (rm_hotland_02,
-- rm_steamworks_24, rm_steamworks_32). These are those seven labels, verbatim,
-- with the room each one flies to - the room numbers are the ones Yellow's own
-- obj_fast_travel_menu switch hands the whale, read through the merged ID
-- space, because Yellow's room 56 and the merged build's room 56 are two
-- different rooms. A test asserts both halves against the pinned source so a
-- typo cannot silently move a stop.
local YELLOW_TRAVEL_POINTS = {
    {label = "Dunes - Oasis Valley", room = "rm_dunes_30"},
    {label = "Dunes - West Mines", room = "rm_dunes_05"},
    {label = "Hotland - Crossroads", room = "rm_hotland_02"},
    {label = "Snowdin - Forest", room = "rm_snowdin_11_yellow"},
    {label = "Steamw. - C. Station", room = "rm_steamworks_32"},
    {label = "Steamw. - Commons", room = "rm_steamworks_24"},
    {label = "Wild East - Farm", room = "rm_dunes_42"},
}
-- Exposed for the merge tests, which pin every label and every room against
-- the pinned Yellow source rather than against this file.
Travel.YELLOW_TRAVEL_POINTS = YELLOW_TRAVEL_POINTS
-- The same Step_0 switch also supplies the landing coordinates.  Keep these
-- alongside (rather than inside) the label/room records so the native stop list
-- remains easy to audit and the River Person can use the exact same landings.
local YELLOW_TRAVEL_COORDINATES = {
    ["Dunes - Oasis Valley"] = {880, 720},
    ["Dunes - West Mines"] = {510, 170},
    ["Hotland - Crossroads"] = {170, 120},
    ["Snowdin - Forest"] = {200, 100},
    ["Steamw. - C. Station"] = {400, 290},
    ["Steamw. - Commons"] = {520, 120},
    ["Wild East - Farm"] = {600, 120},
}
Travel.YELLOW_TRAVEL_COORDINATES = YELLOW_TRAVEL_COORDINATES

-- Every UGPS whale ends its fly-in when fly_speed reaches exactly zero, and
-- the approach decrements it by 0.2 from 2 - a subtraction no binary float
-- lands on zero with (from 2.0 the tenth step is about 2.8e-16, the eleventh
-- is negative). The game's own next line, scene 2, is the Mail/Travel
-- dialogue; without it the whale hovers and the UGPS cannot be used at all.
-- The port reads that last step as the landing the game wrote it to be.
local WHALE_APPROACH_SCENE = 1
local WHALE_LANDING_SPEED = 0.2
local WHALE_OBJECTS = {
    "obj_mail_whale",
    "obj_mail_whale_arrive",
    "obj_mail_whale_dunes_42",
    "obj_mail_whale_snowdin_11",
    "obj_mail_whale_steamworks_32",
}

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
        riverDestination = nil,
        riverDialogue = nil,
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
        whaleObjects = {},
    }, {__index = Travel})
    for _, name in ipairs(WHALE_OBJECTS) do
        local id = yellowNames.objects and yellowNames.objects[name]
        if id then travel.whaleObjects[id] = name end
    end
    R.travel = travel
    travel:loadSave()
    travel.world = travel:worldOf(R.manifest.room_order and R.manifest.room_order[1] or 0)
    -- The boat's own gate is patched before any room can place one, and the
    -- UGPS switch is left alone until Yellow's world exists to hold it.
    travel:openRiverService()

    local gotoRoom = R.gotoRoom
    function R:gotoRoom(index)
        return gotoRoom(self, travel:resolve(index))
    end
    -- The location screen lives in the audited Undertale SCR_TEXT switch.  Its
    -- original chooser has two slots, so the merged River Person menu is layered
    -- after that script returns rather than changing the source switch or the
    -- generic obj_choicer.  Other scripts keep the exact Runtime:script path.
    local script = R.script
    function R:script(index, E, ...)
        local result = script(self, index, E, ...)
        if index == undertaleNames["SCR_TEXT"] then
            travel:afterRiverText(select(1, ...))
        end
        return result
    end
    -- The port's AUTO RUN setting, applied through the game's own global.
    function R:setAutorun(value)
        travel:setAutorun(value)
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

-- The original obj_choicer is deliberately a two-option object.  River Person
-- gets a small pager instead of a third-party menu: one page offers a Yellow
-- stop and More (the last page offers Back), and the next page is written only
-- after the player chooses More.  This keeps the game's own chooser, input,
-- cursor and dialogue animation intact while making all seven Yellow stops
-- reachable.
local RIVER_UNDERTALE_CHOICES = {
    [70] = {{label = "Waterfall", flag = 2}, {label = "Hotland", flag = 3}},
    [125] = {{label = "Snowdin", flag = 1}, {label = "Hotland", flag = 3}},
    [140] = {{label = "Snowdin", flag = 1}, {label = "Waterfall", flag = 2}},
}

function Travel:riverBoat()
    local id = self.ids.undertale.boat
    if not id then return nil end
    for _, instance in ipairs(self.runtime.instances) do
        if instance.alive and instance.v.object_index == id then return instance end
    end
    return nil
end

function Travel:setRiverMessage(text)
    local R = self.runtime
    local messages = R.global.msg
    if type(messages) ~= "table" then
        messages = R.defaults("%%")
        R.global.msg = messages
    end
    messages[0] = text
    -- OBJ_WRITER stops at %%%.  Clear every slot the native River Person uses
    -- so a previous long dialogue can never leak a line into this pager.
    for index = 1, 8 do messages[index] = "%%%" end
end

function Travel:setRiverChoice(prompt, left, right)
    if #left > 10 then
        self:setRiverMessage("* " .. prompt .. "&  " .. left .. "&         Ride        " .. right .. "\\C")
    else
        self:setRiverMessage("* " .. prompt .. "& &         " .. left .. "         " .. right .. "\\C")
    end
end

function Travel:holdRiverBoat()
    local boat = self:riverBoat()
    if boat then boat.v.con = 0 end
end

function Travel:riverUndertalePage()
    local choices = RIVER_UNDERTALE_CHOICES[self.runtime.vars.room]
    if not choices then
        choices = {{label = "Snowdin", flag = 1}, {label = "Waterfall", flag = 2}}
    end
    self:setRiverChoice("Where will we go today?", choices[1].label, choices[2].label)
    self.riverDialogue.undertaleChoices = choices
end

function Travel:riverYellowPage(page)
    local destination = YELLOW_TRAVEL_POINTS[page]
    if not destination then
        self.riverDialogue = nil
        return
    end
    local nextLabel = page < #YELLOW_TRAVEL_POINTS and "More..." or "Back"
    self:setRiverChoice("Where will we go today?", destination.label, nextLabel)
    self.riverDialogue.page = page
end

function Travel:finishRiverChoice(flag, destination)
    local R = self.runtime
    local flags = R.global.flag
    if type(flags) ~= "table" then
        flags = R.defaults(0)
        R.global.flag = flags
    end
    flags[459] = flag
    self.riverDestination = destination
    -- An explicit Yellow selection is a destination choice, not the old
    -- hold-X shortcut.  resolve() consumes this record at the boat's own
    -- room_goto, after the native ride animation has finished.
    self.riverLatch = destination ~= nil
    local boat = self:riverBoat()
    if boat then boat.v.con = 0.1 end
    self:setRiverMessage("* Then we're off.../%%")
    self.riverDialogue = nil
end

function Travel:afterRiverText(message)
    if self.world ~= "undertale" or type(message) ~= "number" then return end
    local R = self.runtime
    if message == RIVER_TEXT_GREETING then
        -- SCR_TEXT 770 is only made by the boat interaction in this service.
        -- Replacing an old pending pager here also makes a second conversation
        -- start cleanly after a completed ride.
        if self:riverBoat() then
            self.riverDestination = nil
            self.riverDialogue = {stage = "initial"}
        end
        return
    end
    local dialogue = self.riverDialogue
    if not dialogue then return end

    if message == RIVER_TEXT_LOCATIONS then
        if R.global.choice == 0 then
            dialogue.stage = "world"
            self:holdRiverBoat()
            self:setRiverChoice("Where will we go?", "Yellow", "Undertale")
        else
            -- The native No branch already filled the final dialogue.
            self.riverDialogue = nil
        end
        return
    end

    if message == RIVER_TEXT_RESULT and dialogue.stage == "world" then
        self:holdRiverBoat()
        if R.global.choice == 0 then
            dialogue.stage = "yellow"
            self:riverYellowPage(1)
        else
            dialogue.stage = "undertale"
            self:riverUndertalePage()
        end
        return
    end

    if message < RIVER_TEXT_CUSTOM_START then return end
    if dialogue.stage == "undertale" then
        local choices = dialogue.undertaleChoices or RIVER_UNDERTALE_CHOICES[R.vars.room]
        local selected = choices and choices[(R.global.choice or 0) + 1]
        if selected then self:finishRiverChoice(selected.flag, nil) end
        return
    end
    if dialogue.stage == "yellow" then
        local page = dialogue.page or 1
        if R.global.choice == 0 then
            self:finishRiverChoice(1, YELLOW_TRAVEL_POINTS[page])
        elseif page < #YELLOW_TRAVEL_POINTS then
            self:holdRiverBoat()
            self:riverYellowPage(page + 1)
        else
            -- Back returns to the native Undertale two-dock list without
            -- adding a third chooser slot or inventing a separate menu.
            dialogue.stage = "undertale"
            self:holdRiverBoat()
            self:riverUndertalePage()
        end
    end
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
    if self.world == "undertale" and self.riverLatch then
        -- A pager selection takes precedence over the old X-held mapping.  If
        -- there is no explicit Yellow selection, retain the original bridge:
        -- holding X during the native ride maps dock 70/125/140 to the existing
        -- three River destinations.
        local destination = self.riverDestination or RIVER_DESTINATIONS[index]
        if destination then
            target = self:yellowRoom(destination.room)
            if self.riverDestination then
                local coordinates = YELLOW_TRAVEL_COORDINATES[destination.label]
                if coordinates then
                    self.pendingCoordinates = {coordinates[1], coordinates[2]}
                else
                    local x, y = self:landingSpot("yellow", target)
                    self.pendingCoordinates = {x, y}
                end
            else
                self.pendingCoordinates = {destination.x, destination.y}
            end
            self.riverLatch = false
            self.riverDestination = nil
        end
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
    -- Both games reuse flag[0..29] with different meanings. The fusion queue
    -- reserves this range as crossing scratch space, never player storage.
    -- Clear it in BOTH directions; scr_initialize used to clear it only when
    -- entering Yellow. Leave all other flags/story globals to their content.
    local flags = R:array(R.global, "flag")
    for index = 0, 29 do flags[index] = 0 end
    -- Before the room loads: Yellow's own room creation code registers fast
    -- travel points, which needs the globals scr_initialize creates. Shared
    -- Player fields remain authoritative throughout this initialization.
    self:initialize(world, scope)
    if world == "yellow" then
        -- Piece 5b: the ammo/accessory slots are live shared equipment now
        -- (port/inventory.lua), and content initialization cannot reset them,
        -- so no snapshot is re-applied here.  What the player equipped simply
        -- survives the crossing.
        -- ...and it resets Yellow's own options with them, AUTO RUN included.
        self:applyAutorun()
        -- ...and it resets the UGPS switch and its list with them too.
        self:openWhaleService()
    end
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
    -- Initialize content, not a second protagonist. The aliases in
    -- port/player.lua reject replacement defaults only for already-present
    -- Player fields, while every world-specific initializer statement runs.
    R.playerBridge:withDefaults(function()
        return R:script(name, R:scope(scope))
    end)
end

-- AUTO RUN, as the pause menu's setting. Nil means "whatever the game itself
-- has", which is how a single-game build and a merged build that never touched
-- the toggle both stay out of the way. The global only exists once Yellow's own
-- initializer has run, so the value is remembered until then and re-applied at
-- every crossing afterwards.
function Travel:setAutorun(value)
    self.autorun = value and true or false
    if self.autorun then
        self.runtime:warn("travel-autorun",
            "AUTO RUN is on: moving in Yellow's world runs, and holding the run button (X) walks.")
    end
    self:applyAutorun()
    self:saveAutorun()
end

function Travel:applyAutorun()
    if self.autorun == nil then return end
    local R = self.runtime
    if R.global.option_autorun == nil then return end
    local wanted = self.autorun and AUTORUN_ON or AUTORUN_OFF
    if R.global.option_autorun ~= wanted then
        R.global.option_autorun = wanted
    end
end

-- The same key Yellow's own scr_savecontrols writes, so the game's config and
-- the port's menu cannot disagree: whoever opens Yellow's controls next reads
-- the value the pause menu shows here.
function Travel:saveAutorun()
    if self.autorun == nil then return end
    local B = self.runtime.builtins
    B.ini_open(nil, "Controls.sav")
    B.ini_write_real(nil, "Controls", "autorun", self.autorun and AUTORUN_ON or AUTORUN_OFF)
    B.ini_close()
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
    -- Yellow's controller re-reads its ini whenever it is created (the
    -- Steamworks vents recreate it), which would silently drop AUTO RUN; the
    -- pause menu is this build's menu for that option, so it is asserted here.
    self:applyAutorun()
    self:openWhaleService()
    self:landWhales()
    -- The whale menu only knows its own seven entries; fill the travel globals
    -- for ours so Yellow's own whale code carries out the trip. Yellow's menu
    -- writes the room numbers of Yellow's own ID space for its own stops, and
    -- a merged build has to read those through the merged space: the menu's
    -- room 56 is Yellow's Snowdin forest, not Undertale's room 56.
    local docks, yellowStops = {}, {}
    for _, destination in ipairs(WHALE_DESTINATIONS) do docks[destination.label] = destination.room end
    local yellowRooms = R.manifest.yellow_names and R.manifest.yellow_names.rooms or {}
    for _, destination in ipairs(YELLOW_TRAVEL_POINTS) do
        local room = yellowRooms[destination.room]
        if room then yellowStops[destination.label] = room end
    end
    local selected, confirmed = nil, R.global.fast_travel_point
    for _, instance in ipairs(R.instances) do
        if instance.alive and instance.v.object_index == self.ids.yellow.whaleMenu then
            selected = instance.v.point_selected
        end
    end
    local chosen = docks[selected] or docks[confirmed]
    local yellowStop = yellowStops[selected] or yellowStops[confirmed]
    if chosen then
        local x, y = self:landingSpot("undertale", chosen)
        R.global.fast_travel_newroom = chosen
        R.global.fast_travel_newx = x
        R.global.fast_travel_newy = y
    elseif yellowStop then
        -- A Yellow stop keeps the x/y Yellow's own menu wrote for it; only the
        -- ID space of the room changes.
        R.global.fast_travel_newroom = yellowStop
    end
end

function Travel:offerWhaleDestinations()
    local R = self.runtime
    local list = R.global.fast_travel_list
    if not list or type(list) ~= "number" or not R.truth(R.builtins.ds_exists(nil, list, 2)) then return end
    -- Seeding is idempotent, but it is also pointless to repeat once the list
    -- has not moved since the last pass; rooms and the menu only ever add.
    local size = R.builtins.ds_list_size(nil, list)
    if self.whaleList == list and self.whaleListSize == size then return end
    local scope = nil
    for _, instance in ipairs(R.instances) do
        if instance.alive then scope = instance break end
    end
    -- Yellow's own registration script refuses duplicates and keeps the list
    -- sorted, which is exactly the order its menu draws and walks.
    for _, destination in ipairs(WHALE_DESTINATIONS) do
        R:call("scr_fasttravel_add", R:scope(scope), destination.label)
    end
    for _, destination in ipairs(YELLOW_TRAVEL_POINTS) do
        R:call("scr_fasttravel_add", R:scope(scope), destination.label)
    end
    self.whaleList, self.whaleListSize = list, R.builtins.ds_list_size(nil, list)
end

-- The River Person, open from the first frame. The boat's own Create event is
-- wrapped rather than rewritten: while it runs, global.plot reads as the value
-- that lets the boat exist, and every other line of that event - the sprite
-- choice, the riverman instance, the room-316 ride setup - is the game's own.
function Travel:openRiverService()
    local R = self.runtime
    local boat = self.ids.undertale.boat
    if not boat or self.riverOpened then return end
    local record = R:object(boat)
    local events = record and record.events
    local create = events and events["0:0"]
    if type(create) ~= "function" then
        R:warn("travel-river-service",
            "obj_dogboat_thing has no Create event in this build, so the River Person keeps the game's own plot gate.")
        return
    end
    self.riverOpened = true
    events["0:0"] = function(runtime, scope)
        local plot = runtime.global.plot
        if type(plot) == "number" and plot < RIVER_PLOT then
            runtime.global.plot = RIVER_PLOT
        end
        local ok, result = pcall(create, runtime, scope)
        runtime.global.plot = plot
        if not ok then error(result, 0) end
        return result
    end
    R:warn("travel-river-service",
        "The River Person's boat is at every dock from the start: its own " ..
        "global.plot < 122 guard is lifted while that one Create event runs.")
end

-- The landing step of every whale's approach (see WHALE_APPROACH_SCENE).
-- Only scene 1 is touched, only while the whale is still descending, and only
-- on the value the game's own decrement left behind, so every other frame of
-- the animation - including the takeoff and the delivery - is untouched.
function Travel:landWhales()
    local R = self.runtime
    for _, instance in ipairs(R.instances) do
        local v = instance.alive and instance.v or nil
        if v and self.whaleObjects[v.object_index]
            and v.scene == WHALE_APPROACH_SCENE
            and type(v.fly_speed) == "number"
            and v.fly_speed > 0 and v.fly_speed < WHALE_LANDING_SPEED then
            R:warn("travel-ugps-landing",
                "A UGPS whale's approach ends when its fly_speed reaches exactly zero; the " ..
                "game's 0.2 decrement from 2 leaves about 2.8e-16 instead, so the last step " ..
                "is read as the landing and the Mail/Travel dialogue opens as written.")
            v.fly_speed = 0
        end
    end
end

-- The UGPS whale, open from the first frame. global.player_can_travel is the
-- game's own switch for "this whale will fly you" (obj_mail_whale's menu only
-- shows Travel when it is set, and the Dunes-42 scene normally sets it), so
-- the port sets the same switch and then offers every stop.
function Travel:openWhaleService()
    local R = self.runtime
    if not self.ids.yellow.whaleMenu then return end
    if not R.truth(R.global.player_can_travel) then
        R.global.player_can_travel = 1
        R:warn("travel-ugps",
            "UGPS fast travel is open from the start: ringing any mail station's bell offers " ..
            "Travel to all " .. tostring(#WHALE_DESTINATIONS + #YELLOW_TRAVEL_POINTS) .. " stops, visited or not.")
    end
    self:offerWhaleDestinations()
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
    local R, B = self.runtime, self.runtime.builtins
    B.ini_open(nil, Travel.SAVE_FILE)
    B.ini_write_real(nil, "merge", "version", Travel.VERSION)
    B.ini_write_real(nil, "merge", "crossings", self.crossings)
    B.ini_write_real(nil, "merge", "last_room", self.runtime.vars.room)
    B.ini_write_string(nil, "merge", "world", self.world or "undertale")
    -- The modifier slots only mean something once Yellow's world created them;
    -- before that the record stays empty rather than inventing a default.
    B.ini_write_string(nil, "merge", "ammo",
        type(R.global.player_weapon_modifier) == "string" and R.global.player_weapon_modifier or "")
    B.ini_write_string(nil, "merge", "accessory",
        type(R.global.player_armor_modifier) == "string" and R.global.player_armor_modifier or "")
    B.ini_close()
    self.runtime:flushSaves()
end

return Travel
