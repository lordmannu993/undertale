-- One Player + World save for the merged game (fusion piece 5d, spec §11).
--
-- merge.sav version 1 was travel metadata (crossings, last room, ammo,
-- accessory). Version 2 is the save: a [Player] block and a [World] block.
-- Undertale's scr_save and Yellow's scr_savegame both write it; scr_load and
-- scr_loadgame both read it, whichever world the menu is in. file0, file9 and
-- Save.sav stay on disk as projections so each game's continue screen still
-- sees a save. They are not a second structure: when version 2 has a Player
-- record, load does not read them.
--
-- Version 1 is migrated explicitly. The bytes are copied to merge.sav.v1 and
-- left there; the copy is never deleted. A version this build does not know
-- stops by name and is not rewritten. A Save.sav this port did not write
-- stops by name the same way the ds reader already does.
--
-- Yellow's own scr_savegame calls ds_grid_write, which this runtime does not
-- implement (a named stop). The save point therefore does not run that script.
-- The fields it would have written are snapshotted here, from the live globals,
-- plus global.story, which scr_savegame never stored and scr_initialize resets.
local Save = {}
Save.__index = Save
Save.VERSION = 2
Save.LEGACY_VERSION = 1
Save.FILE = "merge.sav"
Save.LEGACY_COPY = "merge.sav.v1"

local DS_MAP, DS_LIST, DS_GRID = 1, 2, 5

-- Closed on purpose. Transient battle/menu globals are not world progress.
local STORY_GLOBALS = { "plot", "story", "route", "kills", "area", "currentsong" }
local OTHER_GLOBALS = {
    "currentroom", "saveroom", "player_area", "player_area_value",
    "last_room_overworld", "lastroom", "factory_code", "factory_code_3",
    "sworks_robot_count", "tinypuzzle", "mail_count", "mail_pinned",
    "elapsed_seconds", "fun_value", "current_room_overworld", "flowey_death_pop",
    "fighting_flowey", "flowey_save_number", "save_count", "menu_sprite",
    "gold_amount_total", "gold_spent", "hit_tracker", "death_count_total",
    "meta_flowey_fight_count", "meta_flowey_introduction_count",
    "game_finished_pacifist", "game_finished_pacifist_kill", "game_finished_murder",
    "interaction_count_wardrobe", "interaction_count_broom",
    "interaction_count_mini_fridge", "interaction_count_painting",
    "interaction_count_dalvsroom_chest", "interaction_count_flower_pot",
    "interaction_count_doorway_dalvshouse", "interaction_count_dalvroomhall_door",
    "dalv_house_enter_count", "interaction_count_books",
}
local EVENT_ARRAYS = {
    "flag", "menuchoice", "ruins_flag", "snowdin_flag", "dunes_flag",
    "dunes_flag_ext", "sworks_flag", "hotland_flag", "flowey_flag", "extra_flag",
    "mail_flag", "item_stock", "geno_complete", "kill_number", "sideNpc",
    "fun_event", "death_count", "encounter_flag", "sworks_robot_sprite",
    "sworks_robot_x", "sworks_robot_y", "sworks_robot_depth", "sworks_robot_scale",
    "sworks_robot_angle",
}
local EVENT_ARRAYS_2D = { "kill_area" }
local LISTS = {
    "encounter_list", "steal_list", "fast_travel_list", "box_slot_list",
    "mail_list", "mail_unclaimed_list", "mail_list_read", "factory_code_2",
}
local MAPS = { npc_map = "NPC.map", talk_map = "NPC.talk" }
local PLAYER_OTHER = {
    "maxen", "sp", "asp", "current_pp_self", "max_pp_self", "current_sp_self",
    "max_sp_self", "current_rp_self", "max_rp_self", "player_sprites",
    "player_has_satchel", "player_can_travel",
}

local SAVE_SCRIPTS = { "scr_save", "scr_saveprocess" }
local LOAD_SCRIPTS = { "scr_load" }
local YELLOW_SAVE = "scr_savegame"
local YELLOW_LOAD = "scr_loadgame"

local function trim(s)
    return (s:match("^%s*(.-)%s*$"))
end

function Save.install(R)
    if R.manifest.game ~= "merged" then return nil end
    if R.saveBridge then return R.saveBridge end
    local bridge = setmetatable({ runtime = R, restoring = false }, Save)
    R.saveBridge = bridge
    bridge:wrapScripts()
    return bridge
end

function Save:encode(value)
    local R = self.runtime
    if value == R.UNDEFINED then return "u:" end
    if type(value) == "number" then return "n:" .. string.format("%.15g", value) end
    if type(value) == "boolean" then return value and "b:1" or "b:0" end
    if type(value) == "string" then
        if value:find("[\r\n\\]") then
            R:unsupported("save string",
                "A Player/World string contains a newline or backslash; nothing was stripped: "
                .. value:sub(1, 40))
        end
        return "s:" .. value
    end
    return nil
end

function Save:decode(text)
    if text == nil or text == "" then return nil end
    local kind, rest = text:sub(1, 2), text:sub(3)
    if kind == "n:" then return tonumber(rest) or 0 end
    if kind == "s:" then return rest end
    if kind == "b:" then return rest == "1" end
    if kind == "u:" then return self.runtime.UNDEFINED end
    return nil
end

function Save:escapeBlock(text)
    return (text:gsub("\\", "\\b"):gsub("\r", "\\r"):gsub("\n", "\\n"))
end

function Save:unescapeBlock(text)
    return (text:gsub("\\n", "\n"):gsub("\\r", "\r"):gsub("\\b", "\\"))
end

function Save:parse(text)
    local doc, section = {}, ""
    for line in ((text or "") .. "\n"):gmatch("([^\n]*)\n") do
        line = trim(line)
        local header = line:match("^%[(.-)%]$")
        if header then
            section = header
            doc[section] = doc[section] or {}
        elseif line ~= "" and line:sub(1, 1) ~= ";" and line:sub(1, 1) ~= "#" then
            local key, value = line:match("^([^=]+)=(.*)$")
            if key then
                doc[section] = doc[section] or {}
                doc[section][trim(key)] = trim(value)
            end
        end
    end
    return doc
end

function Save:document()
    return self:parse(self.runtime:readSaveFile(Save.FILE))
end

function Save:mergeNumber(key, default)
    local B = self.runtime.builtins
    B.ini_open(nil, Save.FILE)
    local value = B.ini_read_real(nil, "merge", key, default)
    B.ini_close()
    return value
end

function Save:playerRecorded()
    local player = self:document().Player
    return player ~= nil and player.LV ~= nil and player.LV ~= ""
end

function Save:open()
    local R = self.runtime
    local version = self:mergeNumber("version", 0)
    if version == 0 then return end
    if version == Save.LEGACY_VERSION then
        self:migrateV1()
        return
    end
    if version ~= Save.VERSION then
        R:unsupported("merge.sav version " .. tostring(version),
            "This build reads merged save version " .. Save.VERSION .. "; nothing was guessed at.")
    end
    local travel = R.travel
    if travel then
        travel.crossings = self:mergeNumber("crossings", 0)
        travel.lastRoom = self:mergeNumber("last_room", -1)
    end
end

-- Version 1 has no Player and no World. Do not invent LV, HP or story from
-- the travel fields. Copy the file aside first; a later write must not be the
-- only copy of those bytes.
function Save:migrateV1()
    local R = self.runtime
    local raw = R:readSaveFile(Save.FILE)
    if raw and R:readSaveFile(Save.LEGACY_COPY) == nil then
        R:writeSaveFile(Save.LEGACY_COPY, raw)
    end
    local B = R.builtins
    B.ini_open(nil, Save.FILE)
    local crossings = B.ini_read_real(nil, "merge", "crossings", 0)
    local last = B.ini_read_real(nil, "merge", "last_room", -1)
    local world = B.ini_read_string(nil, "merge", "world", "")
    local ammo = B.ini_read_string(nil, "merge", "ammo", "")
    local accessory = B.ini_read_string(nil, "merge", "accessory", "")
    B.ini_close()
    B.file_delete(nil, Save.FILE)
    B.ini_open(nil, Save.FILE)
    B.ini_write_real(nil, "merge", "version", Save.VERSION)
    B.ini_write_real(nil, "merge", "crossings", crossings)
    B.ini_write_real(nil, "merge", "last_room", last)
    B.ini_write_string(nil, "merge", "world", world)
    B.ini_write_string(nil, "merge", "ammo", ammo)
    B.ini_write_string(nil, "merge", "accessory", accessory)
    B.ini_write_string(nil, "merge", "migrated_from", "1")
    if ammo ~= "" then B.ini_write_string(nil, "Player", "Equipment.ammo", "s:" .. ammo) end
    if accessory ~= "" then B.ini_write_string(nil, "Player", "Equipment.accessory", "s:" .. accessory) end
    if world ~= "" then B.ini_write_string(nil, "World", "World", "s:" .. world) end
    if last ~= -1 then B.ini_write_string(nil, "World", "Current Area", self:encode(last)) end
    B.ini_close()
    R:flushSaves()
    if R.travel then
        R.travel.crossings = crossings
        R.travel.lastRoom = last
        R.travel.migrated = true
    end
    R:warn("save-migrate-v1",
        "merge.sav version 1 was travel metadata. It was copied to merge.sav.v1 and migrated to Player+World version 2. The copy was not deleted, and no LV/HP/story was invented from it.")
end

function Save:encodeGrid(id)
    local R = self.runtime
    local B = R.builtins
    local width = B.ds_grid_width(nil, id)
    local height = B.ds_grid_height(nil, id)
    local cells = {}
    for y = 0, height - 1 do
        for x = 0, width - 1 do
            local value = B.ds_grid_get(nil, id, x, y)
            if value ~= nil and value ~= 0 and value ~= false then
                local encoded = self:encode(value)
                if not encoded or encoded:find("[;{}]") then
                    R:unsupported("save grid",
                        "A grid cell cannot be stored in the unified save; nothing was dropped.")
                end
                cells[#cells + 1] = x .. "," .. y .. "," .. encoded
            end
        end
    end
    return width .. "x" .. height .. "{" .. table.concat(cells, ";") .. "}"
end

function Save:encodeDs(kind, id)
    local B = self.runtime.builtins
    if type(id) ~= "number" or not self.runtime.truth(B.ds_exists(nil, id, kind)) then return nil end
    if kind == DS_LIST then return "l:" .. B.ds_list_write(nil, id) end
    if kind == DS_MAP then return "m:" .. B.ds_map_write(nil, id) end
    if kind == DS_GRID then return "g:" .. self:encodeGrid(id) end
end

function Save:playerEntity()
    local R = self.runtime
    local travel = R.travel
    if not travel or not travel.ids then return nil end
    local world = travel.world or "undertale"
    local id = travel.ids[world] and travel.ids[world].player
    if not id then return nil end
    return R:select(id)[1]
end

function Save:timeValue()
    local id = (self.runtime.manifest.names or {}).obj_time
    local instance = id and self.runtime:select(id)[1]
    if instance and type(instance.v.time) == "number" then return instance.v.time end
    return nil
end

function Save:putArray(put, prefix, name, value)
    if type(value) ~= "table" then return end
    for index, cell in pairs(value) do
        if type(index) == "number" and type(cell) ~= "table" then
            local encoded = self:encode(cell)
            if encoded then put(prefix .. name .. "." .. index, encoded) end
        end
    end
end

function Save:write(opts)
    opts = opts or {}
    local R = self.runtime
    local B = R.builtins
    local prior = self:document()
    local migrated = opts.migrated_from or (prior.merge and prior.merge.migrated_from)
    B.file_delete(nil, Save.FILE)
    B.ini_open(nil, Save.FILE)
    local function put(section, key, value)
        B.ini_write_string(nil, section, key, value)
    end
    local travel = R.travel
    local area = opts.area or R.vars.room
    local worldName = opts.world or (travel and travel.world) or "undertale"
    local player = R.player or {}
    local stats = player.stats or {}
    local equipment = player.equipment or {}
    local abilities = player.abilities or {}
    local ammo = type(equipment.ammo) == "string" and equipment.ammo or ""
    local accessory = type(equipment.accessory) == "string" and equipment.accessory or ""
    B.ini_write_real(nil, "merge", "version", Save.VERSION)
    B.ini_write_real(nil, "merge", "crossings", travel and travel.crossings or 0)
    B.ini_write_real(nil, "merge", "last_room", type(area) == "number" and area or -1)
    B.ini_write_string(nil, "merge", "world", worldName)
    B.ini_write_string(nil, "merge", "ammo", ammo)
    B.ini_write_string(nil, "merge", "accessory", accessory)
    if migrated and migrated ~= "" then
        B.ini_write_string(nil, "merge", "migrated_from", migrated)
    end

    local function playerPut(key, value)
        local encoded = self:encode(value)
        if encoded then put("Player", key, encoded) end
    end
    playerPut("LV", player.level)
    playerPut("EXP", player.exp)
    playerPut("HP", player.hp)
    playerPut("Max HP", player.maxHp)
    playerPut("Gold", player.gold)
    playerPut("Name", player.name)
    playerPut("Attack", stats.attack)
    playerPut("Defense", stats.defense)
    for index = 1, 8 do
        playerPut("Inventory." .. index, (player.inventory or {})[index] or 0)
    end
    for _, field in ipairs({ "weapon", "armor", "ammo", "accessory" }) do
        playerPut("Equipment." .. field, equipment[field] or 0)
    end
    for _, field in ipairs({ "run", "menu", "interact" }) do
        if abilities[field] ~= nil then playerPut("Abilities." .. field, abilities[field]) end
    end
    local phone = rawget(R.global, "phone")
    if type(phone) == "table" then
        for index, cell in pairs(phone) do
            if type(index) == "number" then playerPut("Other.phone." .. index, cell) end
        end
    end
    for _, name in ipairs(PLAYER_OTHER) do
        local value = rawget(R.global, name)
        if value ~= nil then playerPut("Other." .. name, value) end
    end

    put("World", "World", self:encode(worldName))
    if type(area) == "number" then put("World", "Current Area", self:encode(area)) end
    local areaName = R.roomState and R.vars.room == area and R.roomState.name or nil
    if not areaName and type(area) == "number" then
        local path = R.manifest.rooms[area]
        areaName = type(path) == "string" and path:match("([^%.]+)$") or nil
    end
    if areaName then put("World", "Current Area Name", self:encode(areaName)) end
    local entity = self:playerEntity()
    local px = entity and entity.v.x or opts.x
    local py = entity and entity.v.y or opts.y
    if px ~= nil then put("World", "X", self:encode(px)) end
    if py ~= nil then put("World", "Y", self:encode(py)) end
    local facing = player.movement and player.movement.facing
    if facing ~= nil then put("World", "Facing", self:encode(facing)) end
    local time = self:timeValue()
    if time ~= nil then put("World", "Story.time", self:encode(time)) end
    for _, name in ipairs(STORY_GLOBALS) do
        local value = rawget(R.global, name)
        if value ~= nil then put("World", "Story." .. name, self:encode(value)) end
    end
    for _, name in ipairs(OTHER_GLOBALS) do
        local value = rawget(R.global, name)
        if value ~= nil then put("World", "Other." .. name, self:encode(value)) end
    end
    local party = rawget(R.global, "party_member")
    if party ~= nil then put("World", "NPC.party", self:encode(party)) end
    for _, name in ipairs(EVENT_ARRAYS) do
        self:putArray(function(key, value) put("World", "Event." .. key, value) end, "", name, rawget(R.global, name))
    end
    for _, name in ipairs(EVENT_ARRAYS_2D) do
        local grid = rawget(R.global, name)
        if type(grid) == "table" then
            for row, cells in pairs(grid) do
                if type(row) == "number" and type(cells) == "table" then
                    for col, cell in pairs(cells) do
                        if type(col) == "number" then
                            local encoded = self:encode(cell)
                            if encoded then put("World", "Event." .. name .. "." .. row .. "." .. col, encoded) end
                        end
                    end
                end
            end
        end
    end
    for _, name in ipairs(LISTS) do
        local encoded = self:encodeDs(DS_LIST, rawget(R.global, name))
        if encoded then put("World", "List." .. name, encoded) end
    end
    for name, key in pairs(MAPS) do
        local encoded = self:encodeDs(DS_MAP, rawget(R.global, name))
        if encoded then put("World", key, encoded) end
    end
    local grid = self:encodeDs(DS_GRID, rawget(R.global, "sworks_id_grid"))
    if grid then put("World", "Other.sworks_id_grid", grid) end
    local ini = R:readSaveFile("undertale.ini")
    if ini then put("World", "Other.undertale_ini", "s:" .. self:escapeBlock(ini)) end
    B.ini_close()
    if opts.project then self:project(ammo) end
    R:flushSaves()
end

-- A crossing lands, then the destination's Create can reset the live record
-- (Undertale's obj_time runs SCR_GAMESTART). That must not replace the
-- Player/World document just written. Only the travel fields move.
function Save:touch(opts)
    opts = opts or {}
    local R = self.runtime
    local B = R.builtins
    local travel = R.travel
    B.ini_open(nil, Save.FILE)
    B.ini_write_real(nil, "merge", "version", Save.VERSION)
    B.ini_write_real(nil, "merge", "crossings", travel and travel.crossings or 0)
    local area = opts.area or R.vars.room
    if type(area) == "number" then B.ini_write_real(nil, "merge", "last_room", area) end
    local worldName = opts.world or (travel and travel.world)
    if worldName then B.ini_write_string(nil, "merge", "world", worldName) end
    B.ini_close()
    R:flushSaves()
end

-- Projections, not authorities. Undertale's title checks file_exists("file0");
-- Yellow's title reads Save.sav for the room name, menu sprite and route.
-- A real file0 written by scr_save is left alone. A Yellow save point cannot
-- run scr_save (obj_time was destroyed on the crossing), so it writes a marker
-- file0 plus the General keys the save-point menu displays.
function Save:project(ammo)
    local R = self.runtime
    local B = R.builtins
    if not R.truth(B.file_exists(nil, "file0")) then
        local id = B.file_text_open_write(nil, "file0")
        B.file_text_write_string(nil, id, "unified")
        B.file_text_writeln(nil, id)
        B.file_text_close(nil, id)
    end
    local player = R.player or {}
    B.ini_open(nil, "undertale.ini")
    if player.name ~= nil then B.ini_write_string(nil, "General", "Name", player.name) end
    if player.level ~= nil then B.ini_write_real(nil, "General", "Love", player.level) end
    local time = self:timeValue()
    if time ~= nil then B.ini_write_real(nil, "General", "Time", time) end
    local kills = rawget(R.global, "kills")
    if type(kills) == "number" then B.ini_write_real(nil, "General", "Kills", kills) end
    if type(R.vars.room) == "number" then B.ini_write_real(nil, "General", "Room", R.vars.room) end
    B.ini_close()
    local roomName = R.roomState and R.roomState.name or ""
    local menu = rawget(R.global, "menu_sprite")
    local menuName = "bg_ruins02"
    if type(menu) == "number" then
        local named = B.sprite_get_name(nil, menu)
        if type(named) == "string" and named ~= "" and named ~= "<undefined>" then menuName = named end
    end
    local route = rawget(R.global, "route")
    B.ini_open(nil, "Save.sav")
    B.ini_write_string(nil, "Save1", "room", roomName)
    B.ini_write_string(nil, "Save1", "Menu", menuName)
    if player.hp ~= nil then B.ini_write_real(nil, "Save1", "HP", player.hp) end
    if player.level ~= nil then B.ini_write_real(nil, "Save1", "LV", player.level) end
    if ammo ~= nil then B.ini_write_string(nil, "Save1", "Ammo", ammo) end
    if type(route) == "number" then B.ini_write_real(nil, "Route", "00", route) end
    B.ini_close()
end

function Save:assignGlobal(name, value)
    if value == nil then return end
    self.runtime.global[name] = value
end

function Save:restoreArray(name, entries)
    local arr = self.runtime:array(self.runtime.global, name)
    for key in pairs(arr) do arr[key] = nil end
    for index, value in pairs(entries) do arr[index] = value end
end

function Save:restoreList(name, text)
    local R = self.runtime
    if text:sub(1, 2) ~= "l:" then
        R:unsupported("save list " .. name, "Not a list this port wrote: " .. text:sub(1, 40))
    end
    local id = R.builtins.ds_list_create(nil)
    R.builtins.ds_list_read(nil, id, text:sub(3))
    R.global[name] = id
end

function Save:restoreMap(name, text)
    local R = self.runtime
    if text:sub(1, 2) ~= "m:" then
        R:unsupported("save map " .. name, "Not a map this port wrote: " .. text:sub(1, 40))
    end
    local id = R.builtins.ds_map_create(nil)
    R.builtins.ds_map_read(nil, id, text:sub(3))
    R.global[name] = id
end

function Save:restoreGrid(text)
    local R = self.runtime
    if text:sub(1, 2) ~= "g:" then
        R:unsupported("save grid", "Not a grid this port wrote: " .. text:sub(1, 40))
    end
    local width, height, body = text:sub(3):match("^(%d+)x(%d+)%{(.*)%}$")
    if not width then
        R:unsupported("save grid", "Not a grid this port wrote: " .. text:sub(1, 40))
    end
    local id = R.builtins.ds_grid_create(nil, tonumber(width), tonumber(height))
    if body ~= "" then
        for cell in body:gmatch("[^;]+") do
            local x, y, encoded = cell:match("^(%d+),(%d+),(.*)$")
            if not x then R:unsupported("save grid", "Malformed grid cell") end
            R.builtins.ds_grid_set(nil, id, tonumber(x), tonumber(y), self:decode(encoded))
        end
    end
    R.global.sworks_id_grid = id
end

function Save:applyPlayer(doc)
    local R = self.runtime
    local player = R.player
    if not player or not doc then return end
    local function take(key)
        return self:decode(doc[key])
    end
    local fields = {
        LV = "level", EXP = "exp", HP = "hp", ["Max HP"] = "maxHp",
        Gold = "gold", Name = "name",
    }
    for key, field in pairs(fields) do
        if doc[key] ~= nil then player[field] = take(key) end
    end
    player.stats = player.stats or {}
    if doc.Attack ~= nil then player.stats.attack = take("Attack") end
    if doc.Defense ~= nil then player.stats.defense = take("Defense") end
    player.inventory = player.inventory or {}
    for index = 1, 8 do
        local key = "Inventory." .. index
        if doc[key] ~= nil then player.inventory[index] = take(key) end
    end
    player.equipment = player.equipment or {}
    for _, field in ipairs({ "weapon", "armor", "ammo", "accessory" }) do
        local key = "Equipment." .. field
        if doc[key] ~= nil then player.equipment[field] = take(key) end
    end
    player.abilities = player.abilities or {}
    for _, field in ipairs({ "run", "menu", "interact" }) do
        local key = "Abilities." .. field
        if doc[key] ~= nil then player.abilities[field] = take(key) end
    end
    local phones = {}
    for key, raw in pairs(doc) do
        local index = key:match("^Other%.phone%.(%-?%d+)$")
        if index then phones[tonumber(index)] = self:decode(raw) end
        local name = key:match("^Other%.([%w_]+)$")
        if name and not key:match("^Other%.phone%.") then self:assignGlobal(name, self:decode(raw)) end
    end
    if next(phones) then
        local phone = R:array(R.global, "phone")
        for key in pairs(phone) do phone[key] = nil end
        for index, value in pairs(phones) do phone[index] = value end
    end
end

function Save:applyWorld(doc)
    if not doc then return end
    local R = self.runtime
    local arrays, arrays2 = {}, {}
    for key, raw in pairs(doc) do
        local name, row, col = key:match("^Event%.([%w_]+)%.(-?%d+)%.(%-?%d+)$")
        if name then
            arrays2[name] = arrays2[name] or {}
            arrays2[name][tonumber(row)] = arrays2[name][tonumber(row)] or {}
            arrays2[name][tonumber(row)][tonumber(col)] = self:decode(raw)
        else
            name, row = key:match("^Event%.([%w_]+)%.(-?%d+)$")
            if name then
                arrays[name] = arrays[name] or {}
                arrays[name][tonumber(row)] = self:decode(raw)
            end
        end
    end
    for name, entries in pairs(arrays) do self:restoreArray(name, entries) end
    for name, rows in pairs(arrays2) do
        local grid = {}
        for row, cols in pairs(rows) do
            grid[row] = {}
            for col, value in pairs(cols) do grid[row][col] = value end
        end
        R.global[name] = grid
    end
    for key, raw in pairs(doc) do
        local name = key:match("^Story%.([%w_]+)$")
        if name and name ~= "time" then self:assignGlobal(name, self:decode(raw)) end
        name = key:match("^Other%.([%w_]+)$")
        if name and name ~= "undertale_ini" and name ~= "sworks_id_grid" then
            self:assignGlobal(name, self:decode(raw))
        end
        name = key:match("^List%.([%w_]+)$")
        if name then self:restoreList(name, raw) end
    end
    if doc["NPC.party"] ~= nil then self:assignGlobal("party_member", self:decode(doc["NPC.party"])) end
    if doc["NPC.map"] then self:restoreMap("npc_map", doc["NPC.map"]) end
    if doc["NPC.talk"] then self:restoreMap("talk_map", doc["NPC.talk"]) end
    if doc["Other.sworks_id_grid"] then self:restoreGrid(doc["Other.sworks_id_grid"]) end
    if doc["Story.time"] ~= nil then
        local time = self:decode(doc["Story.time"])
        local id = (R.manifest.names or {}).obj_time
        local instance = id and R:select(id)[1]
        if instance then instance.v.time = time end
        self.savedTime = time
    end
    local ini = doc["Other.undertale_ini"]
    if ini and ini:sub(1, 2) == "s:" then
        R:writeSaveFile("undertale.ini", self:unescapeBlock(ini:sub(3)))
    end
end

function Save:scope()
    for _, instance in ipairs(self.runtime.instances) do
        if instance.alive then return instance end
    end
    return nil
end

function Save:place(doc)
    local R = self.runtime
    local travel = R.travel
    local world = doc["World"] and self:decode(doc["World"]) or (travel and travel.world)
    local id = travel and travel.ids[world] and travel.ids[world].player
    local player = id and R:select(id)[1]
    local x = doc.X and self:decode(doc.X) or 0
    local y = doc.Y and self:decode(doc.Y) or 0
    if not player and id then player = R:create(id, x, y) end
    if player then
        player.v.x, player.v.y = x, y
        player.v.xprevious, player.v.yprevious = x, y
        player.v.xstart, player.v.ystart = x, y
    end
    if doc.Facing ~= nil and R.player and R.player.movement then
        R.player.movement.facing = self:decode(doc.Facing)
    end
    if R.playerController then R.playerController:afterLoadRoom() end
    if self.savedTime ~= nil then
        local timeId = (R.manifest.names or {}).obj_time
        local time = timeId and R:select(timeId)[1]
        if time then time.v.time = self.savedTime end
    end
end

function Save:enter(doc)
    local R = self.runtime
    local travel = R.travel
    local area = doc["Current Area"] and self:decode(doc["Current Area"])
    if type(area) ~= "number" then
        R:unsupported("save room", "The unified save has no Current Area; nothing was guessed.")
    end
    if not R.manifest.rooms[area] then
        R:unsupported("room_goto",
            "Saved room " .. tostring(area) .. " is not in this build; nothing was substituted.")
    end
    self:applyPlayer(doc)
    local world = doc.World and self:decode(doc.World) or travel:worldOf(area)
    if world == "yellow" and travel and not travel.yellowReady then
        travel:initialize("yellow", self:scope())
    end
    self:applyWorld(doc)
    if doc.X then R.global.player_x = self:decode(doc.X) end
    if doc.Y then R.global.player_y = self:decode(doc.Y) end
    if doc.Facing ~= nil and R.player and R.player.movement then
        R.player.movement.facing = self:decode(doc.Facing)
        R.global.facing = R.player.movement.facing
    end
    self.restoring = true
    if travel then travel.world = world end
    R:gotoRoom(area)
    R:applyTransitions()
    self.restoring = false
    self:applyPlayer(doc)
    self:place(doc)
end

function Save:load(source, original, E)
    local R = self.runtime
    if self:playerRecorded() then
        self:enter(self:document().World and self:document().Player and self:document() or self:document())
        local doc = self:document()
        self:enter(doc.Player and doc.World and doc or doc)
        return 0
    end
    -- The double document() above is a mistake if enter consumes state. Fix
    -- below by reading once. This branch is the legacy path.
    return self:loadLegacy(source, original, E)
end

-- Replaced immediately below. The function above is not used; loadUnified is.
function Save:loadUnified(source, original, E)
    local R = self.runtime
    if self:playerRecorded() then
        local doc = self:document()
        local flat = {}
        for key, value in pairs(doc.Player or {}) do flat[key] = value end
        for key, value in pairs(doc.World or {}) do flat[key] = value end
        self:enter(flat)
        return 0
    end
    return self:loadLegacy(source, original, E)
end

function Save:loadLegacy(source, original, E)
    local R = self.runtime
    local B = R.builtins
    if source == "scr_load" and R.truth(B.file_exists(nil, "file0")) then
        local preserved = R:readSaveFile("file0")
        original(R, E)
        if R:readSaveFile("file0") ~= preserved then
            R:unsupported("file0", "Legacy migration changed file0; the old save must be preserved.")
        end
        self:write({ migrated_from = "file0", project = false })
        return 0
    end
    if source == "scr_loadgame" and R.truth(B.file_exists(nil, "Save.sav")) then
        self:migrateSaveSav()
        return 0
    end
    return original(R, E)
end

function Save:migrateSaveSav()
    local R = self.runtime
    local B = R.builtins
    local preserved = R:readSaveFile("Save.sav")
    B.ini_open(nil, "Save.sav")
    local encounters = B.ini_read_string(nil, "Encounters", "0", "")
    local npcs = B.ini_read_string(nil, "NPCs", "0", "")
    B.ini_close()
    local function foreign(label, text)
        if text ~= "" and text ~= "0" and text:sub(1, 1) ~= "{" then
            R:unsupported("Save.sav", "Not a save string this port wrote: " .. label .. " " .. text:sub(1, 40))
        end
    end
    foreign("Encounters", encounters)
    foreign("NPCs", npcs)
    -- Scalars this port's projection writes. A fuller GameMaker Save.sav stops
    -- above rather than being half-applied. The file itself is not deleted.
    B.ini_open(nil, "Save.sav")
    local roomName = B.ini_read_string(nil, "Save1", "room", "")
    local hp = B.ini_read_real(nil, "Save1", "HP", -1)
    local lv = B.ini_read_real(nil, "Save1", "LV", -1)
    local route = B.ini_read_real(nil, "Route", "00", -1)
    B.ini_close()
    if R:readSaveFile("Save.sav") ~= preserved then
        R:unsupported("Save.sav", "Legacy migration changed Save.sav; the old save must be preserved.")
    end
    if lv >= 0 and R.player then R.player.level = lv end
    if hp >= 0 and R.player then R.player.hp = hp end
    if route >= 0 then R.global.route = route end
    self:write({ migrated_from = "Save.sav", project = false })
    if roomName ~= "" and R.travel then
        local rooms = R.manifest.yellow_names and R.manifest.yellow_names.rooms or {}
        local area = rooms[roomName]
        if area then
            local doc = self:document()
            local flat = {}
            for key, value in pairs(doc.Player or {}) do flat[key] = value end
            for key, value in pairs(doc.World or {}) do flat[key] = value end
            flat["Current Area"] = self:encode(area)
            flat.World = self:encode("yellow")
            self:enter(flat)
        end
    end
end

function Save:keysFor(name)
    local R = self.runtime
    local scripts = R.manifest.scripts or {}
    local numeric = (R.manifest.names or {})[name]
    local entry = scripts[name] or (numeric and scripts[numeric])
    local keys = {}
    if entry ~= nil and scripts[name] ~= nil then keys[#keys + 1] = name end
    if numeric ~= nil and entry ~= nil and scripts[numeric] ~= nil then keys[#keys + 1] = numeric end
    return keys, entry
end

function Save:loadOriginal(entry, index)
    local path, export
    if type(entry) == "table" then path, export = entry.module, entry.export else path = entry end
    local loaded = require(path)
    if type(loaded) == "function" then return loaded end
    return loaded[export or "__main"] or loaded[index] or loaded.main
end

function Save:wrap(name, kind)
    local R = self.runtime
    local keys, entry = self:keysFor(name)
    if not entry then
        R:unsupported("save:" .. name, "The merged manifest has no such script to adapt.")
    end
    local original = self:loadOriginal(entry, keys[1])
    local bridge = self
    local fn
    if kind == "save" then
        fn = function(runtime, E)
            -- Snapshot even if the game's own writer stops. file0 is a list of
            -- reals, so a Yellow item name (a string in the shared inventory)
            -- makes scr_saveprocess's file_text_write_real stop. That projection
            -- is not the save.
            local ok, result = pcall(original, runtime, E)
            bridge:write({ project = name ~= "scr_saveprocess" })
            if not ok then
                runtime:warn("save-projection",
                    name .. " could not write its own file (" .. tostring(result)
                    .. "). The unified Player+World document was still written.")
                return 0
            end
            return result
        end
    elseif kind == "yellow-save" then
        fn = function(runtime, E)
            runtime:warn("save-yellow",
                "Yellow's scr_savegame is not the writer: it stops on ds_grid_write, which this runtime does not implement. The save point writes the unified Player+World document instead.")
            bridge:write({ project = true, migrated_from = nil })
            return 0
        end
    else
        fn = function(runtime, E)
            return bridge:loadUnified(name, original, E)
        end
    end
    for _, key in ipairs(keys) do R.scripts[key] = fn end
end

function Save:wrapScripts()
    for _, name in ipairs(SAVE_SCRIPTS) do self:wrap(name, "save") end
    for _, name in ipairs(LOAD_SCRIPTS) do self:wrap(name, "load") end
    self:wrap(YELLOW_SAVE, "yellow-save")
    self:wrap(YELLOW_LOAD, "load")
    self.runtime:warn("save-unified",
        "Save points in either world write one merge.sav Player+World document (version 2). file0 and Save.sav are projections so each continue menu still sees a save; load reads the unified document.")
end

return Save
