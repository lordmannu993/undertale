-- One inventory and one four-slot equipment set (fusion piece 5b).
--
-- Converted code still spells the inventory as global.item[0..7] (Undertale
-- numbers, 0 = empty) and global.item_slot[1..8] (Yellow names, "Nothing" =
-- empty), and the equipment as global.weapon/global.armor plus Yellow's
-- player_weapon/player_armor/player_weapon_modifier/player_armor_modifier.
-- Every one of those is a *view* of the shared state in R.player: one slot
-- list (R.player.inventory) and one equipment set (R.player.equipment =
-- weapon/armor/ammo/accessory).  No world keeps its own copy.
--
-- The numeric/string adapters are the projections: a slot stores the item in
-- the spelling it was obtained in (Undertale number or Yellow name), and each
-- view projects to the other game's spelling through the catalog's shared-name
-- pairing (extracted from source by tools/item_catalog.py - five names the two
-- games genuinely share, including identical stats like Toy Knife AT 3).
-- Foreign items - names with no counterpart - stay in their own spelling and
-- are handled by common item actions, so a Lemonade can be drunk in Snowdin
-- and a Monster Candy eaten in Steamworks through either menu.
--
-- Equipment stats are derived from the equipment tokens through the catalog
-- (which parses Undertale's scr_weaponeq/scr_armoreq if-chains and Yellow's
-- scr_item_stats_* tables): wstrength and player_weapon_attack are two views
-- of the weapon slot's attack (wstrength adds the Cowboy Hat/temy armour
-- bonuses exactly as scr_weaponeq does), adef and player_armor_defense the
-- armour slot's defense, and Yellow's ammo/accessory determine globals view
-- the modifier slots.  Writes to the derived globals are ignored: the
-- equipment tokens are the single source of truth, and the legacy if-chain
-- and determine writers compute exactly these values.
--
-- Like port/player.lua, content initialization cannot reset any of it:
-- during Player:withDefaults only never-written fields may receive defaults,
-- so Yellow's new-game seeding (which wipes item_slot and re-equips Toy Gun)
-- cannot destroy a merged inventory, while a fresh game still gets Yellow's
-- Rubber Ammo/Patch defaults on first entry (those slots start absent).
-- Yellow's Missing Poster is a new-game grant and is intentionally not
-- injected at crossings - it comes from Yellow content that grants it or not
-- at all (see docs/PORTING.md).
local Inventory = {}
Inventory.__index = Inventory

local UT_EMPTY = 0
local YELLOW_EMPTY = "Nothing"

local SLOT_COUNT = 8

-- global names -> shared field.  The spelling decides the projection.
local EQUIPMENT_VIEWS = {
    weapon = {field = "weapon", spelling = "ut"},
    armor = {field = "armor", spelling = "ut"},
    player_weapon = {field = "weapon", spelling = "yellow"},
    player_armor = {field = "armor", spelling = "yellow"},
    player_weapon_modifier = {field = "ammo", spelling = "yellow"},
    player_armor_modifier = {field = "accessory", spelling = "yellow"},
}

-- Derived gear stats: reads computed from the equipment tokens, writes
-- ignored.  wstrength composes the weapon attack with the armour's weapon
-- bonus because scr_weaponeq's if-chain does exactly that.
local DERIVED_VIEWS = {
    wstrength = "weaponStrength",
    player_weapon_attack = "weaponAttack",
    adef = "armorDefense",
    player_armor_defense = "armorDefense",
    player_weapon_modifier_attack = "ammoAttack",
    player_armor_modifier_defense = "accessoryDefense",
}

local ENTRY_FIELDS = {"item", "item_slot", "weapon", "armor", "wstrength", "adef",
    "player_weapon", "player_armor", "player_weapon_modifier", "player_armor_modifier",
    "player_weapon_attack", "player_armor_defense",
    "player_weapon_modifier_attack", "player_armor_modifier_defense"}

local function normalize(value)
    if value == nil or value == UT_EMPTY or value == YELLOW_EMPTY then return UT_EMPTY end
    return value
end

function Inventory.install(R)
    if R.manifest.game ~= "merged" then return nil end
    if R.inventoryBridge then return R.inventoryBridge end
    local catalog = require("generated.merged.items")

    local utByName = {}
    for item_id, entry in pairs(catalog.ut) do
        if entry.name then utByName[entry.name] = item_id end
    end
    -- Yellow's use switch is the set of items Yellow's own menus can act on.
    -- Paired names (Monster Candy, Spider Donut, Toy Knife, Sea Tea, Popato
    -- Chisps) resolve to each world's own native handling where one exists;
    -- Toy Knife has stats but no use case, so it equips through the catalog.
    local yellowUse = {}
    for name, entry in pairs(catalog.yellow) do
        if entry.use then yellowUse[name] = true end
    end

    for _, name in ipairs(ENTRY_FIELDS) do
        if rawget(R.global, name) ~= nil then
            R:unsupported("Inventory alias " .. name,
                "Install the shared inventory before gameplay initialization.")
        end
    end

    local state = R.player
    state.inventory = state.inventory or {}
    state.equipment = state.equipment or {}
    local scratch = {}

    local bridge = setmetatable({state = state, catalog = catalog}, Inventory)
    R.inventoryBridge, R.itemCatalog = bridge, catalog

    local function guarding()
        local player = R.playerBridge
        return player and player.defaultsDepth and player.defaultsDepth > 0
    end

    local function setSlot(index, value)
        if index < 1 or index > SLOT_COUNT then return end
        -- Content initialization may fill an empty slot (Yellow's own starter
        -- grant, item_slot[1] = "Missing Poster") but never replaces what the
        -- shared inventory already carries: scr_initialize's per-crossing wipe
        -- lands only on empty slots and so cannot clobber the player's items.
        if guarding() and normalize(state.inventory[index]) ~= UT_EMPTY then return end
        state.inventory[index] = normalize(value)
    end

    local function setEquipment(field, value)
        if guarding() and state.equipment[field] ~= nil then return end
        state.equipment[field] = normalize(value)
    end

    local function toUT(token)
        if type(token) == "number" then return token end
        if type(token) == "string" then return utByName[token] or token end
        return UT_EMPTY
    end

    local function toYellow(token, empty)
        if type(token) == "string" then return token end
        if type(token) == "number" and token ~= UT_EMPTY then
            local entry = catalog.ut[token]
            return (entry and (catalog.pairs[token] or entry.name)) or YELLOW_EMPTY
        end
        return empty
    end

    local function entryOf(token)
        if type(token) == "number" then return catalog.ut[token] end
        if type(token) == "string" then
            return catalog.yellow[token] or catalog.ut[utByName[token]]
        end
        return nil
    end

    local function statOf(token, kind)
        local entry = entryOf(token)
        if not entry then return 0 end
        if kind == "weapon" then return entry.weapon_strength or entry.atk or 0 end
        if kind == "armor" then return entry.armor_defense or entry.def or 0 end
        if kind == "ammo" then return entry.weapon_mod_strength or entry.atk or 0 end
        if kind == "accessory" then return entry.armor_mod_defense or entry.def or 0 end
        if kind == "bonus" then return entry.armor_weapon_bonus or 0 end
        return 0
    end

    local function derived(name)
        local equipment = state.equipment
        if name == "weaponAttack" then return statOf(equipment.weapon, "weapon") end
        if name == "weaponStrength" then
            return statOf(equipment.weapon, "weapon") + statOf(equipment.armor, "bonus")
        end
        if name == "armorDefense" then return statOf(equipment.armor, "armor") end
        if name == "ammoAttack" then return statOf(equipment.ammo, "ammo") end
        if name == "accessoryDefense" then return statOf(equipment.accessory, "accessory") end
        return 0
    end

    -- Both inventory spellings are live views over the same eight slots.
    local item = setmetatable({}, {
        __index = function(_, index)
            index = tonumber(index)
            if index == nil then return UT_EMPTY end
            if index == 8 then return scratch[8] or UT_EMPTY end
            local token = state.inventory[(index or 0) + 1]
            return toUT(normalize(token))
        end,
        __newindex = function(_, index, value)
            index = tonumber(index)
            if index == nil then return end
            if index == 8 then scratch[8] = value return end
            setSlot((index or 0) + 1, value)
        end,
    })
    local itemSlot = setmetatable({}, {
        __index = function(_, index)
            index = tonumber(index)
            if index == nil or index < 1 or index > SLOT_COUNT then return YELLOW_EMPTY end
            return toYellow(normalize(state.inventory[index]), YELLOW_EMPTY)
        end,
        __newindex = function(_, index, value)
            index = tonumber(index)
            if index == nil then return end
            setSlot(index, value)
        end,
    })

    -- Common item actions: what using an item *does*, for items the calling
    -- menu's own switch has no case for.  Effects and messages come from the
    -- catalog's extracted fields; nothing is invented here.
    local function applyEffects(entry)
        if entry.heal == "max" then
            R.global.hp = R.global.maxhp
        elseif type(entry.heal) == "number" and entry.heal > 0 then
            local hp = R.global.hp + entry.heal
            if hp > R.global.maxhp then hp = R.global.maxhp end
            R.global.hp = hp
        end
        for _, stat in ipairs({{"pp", "current_pp_self", "max_pp_self"},
                               {"sp", "current_sp_self", "max_sp_self"},
                               {"rp", "current_rp_self", "max_rp_self"}}) do
            local amount = entry[stat[1]]
            if type(amount) == "number" and amount > 0 then
                local value = R.global[stat[2]] + amount
                if value > R.global[stat[3]] then value = R.global[stat[3]] end
                R.global[stat[2]] = value
            end
        end
    end

    local function showMessage(E, entry, flavor)
        local messages = entry.messages
        if not messages or #messages == 0 then return end
        if flavor == "undertale" then
            local msg = R:array(R.global, "msg", E)
            for i, line in ipairs(messages) do msg[i - 1] = line end
            R:call("scr_writetext", E, 0, "x", 0, 0)
        else
            R:call("scr_text", E)
            for _, instance in ipairs(R:select(E["msg"], E)) do
                local message = R:array(instance, "message", E)
                for i, line in ipairs(messages) do message[i - 1] = line end
            end
        end
    end

    local function removeSlot(index)
        for slot = index, SLOT_COUNT - 1 do state.inventory[slot] = state.inventory[slot + 1] end
        state.inventory[SLOT_COUNT] = UT_EMPTY
    end

    function bridge.commonUse(E, token, slot, flavor)
        local entry = entryOf(token)
        if not entry then return false end
        local kind = entry.kind
        if entry.heal == "max" or (type(entry.heal) == "number" and entry.heal > 0) then
            -- The item's own use case is a consumable: Bandage heals through
            -- Undertale's useb even though it is equippable armour.
            applyEffects(entry)
            removeSlot(slot)
        elseif kind == "weapon" or kind == "armor" or kind == "ammo" or kind == "accessory" then
            -- Equip swaps: the used slot receives whatever was equipped there.
            local old = normalize(state.equipment[kind])
            state.equipment[kind] = normalize(token)
            state.inventory[slot] = old
        end
        showMessage(E, entry, flavor)
        return true
    end

    -- Array views live under their global names, never rawset on the global.
    local views = {item = item, item_slot = itemSlot}

    -- The equipment views project per spelling: Undertale's names read
    -- numbers where a number exists, Yellow's names read names.
    local function equipmentRead(name)
        local view = EQUIPMENT_VIEWS[name]
        local token = state.equipment[view.field]
        if token == nil or normalize(token) == UT_EMPTY then return UT_EMPTY end
        return view.spelling == "ut" and toUT(token) or toYellow(token, UT_EMPTY)
    end

    local function equipmentWrite(name, value)
        local view = EQUIPMENT_VIEWS[name]
        if guarding() and state.equipment[view.field] ~= nil then return end
        state.equipment[view.field] = normalize(value)
    end

    local mt = getmetatable(R.global)
    local fallbackIndex, fallbackNewindex = mt.__index, mt.__newindex
    mt.__index = function(global, name)
        if views[name] ~= nil then return views[name] end
        if EQUIPMENT_VIEWS[name] then return equipmentRead(name) end
        if DERIVED_VIEWS[name] then return derived(DERIVED_VIEWS[name]) end
        return fallbackIndex and fallbackIndex(global, name) or nil
    end
    mt.__newindex = function(global, name, value)
        if views[name] ~= nil then
            R:unsupported("Inventory view " .. name,
                "The shared inventory arrays are views; write their elements, not the array.")
            return
        end
        if EQUIPMENT_VIEWS[name] then return equipmentWrite(name, value) end
        -- Derived gear stats are computed from the equipment tokens.  The
        -- legacy writers (scr_weaponeq/scr_armoreq if-chains, scr_initialize's
        -- determine calls) assign exactly the computed values; a write here
        -- cannot become a second source of truth.
        if DERIVED_VIEWS[name] then return end
        if fallbackNewindex then return fallbackNewindex(global, name, value) end
        rawset(global, name, value)
    end

    -- ------------------------------------------------------------------
    -- Script adapters.  Each wrapper runs the original script untouched for
    -- every token that script's own tables cover, and only handles foreign
    -- tokens (names from the other game) through the catalog.
    -- ------------------------------------------------------------------

    local function keysFor(name)
        local scripts = R.manifest.scripts or {}
        local numeric = (R.manifest.names or {})[name]
        local entry = scripts[name] or scripts[numeric]
        local keys = {}
        -- The merged scripts map is a read-only proxy that is only ever
        -- indexed (see port/merge.lua), so the call flavors are addressed
        -- explicitly: script_execute(numeric) for Undertale and
        -- R:call("name", ...) for Yellow.
        if entry ~= nil and scripts[name] ~= nil then keys[#keys + 1] = name end
        if numeric ~= nil and entry ~= nil and scripts[numeric] ~= nil then keys[#keys + 1] = numeric end
        return keys, entry
    end

    local function loadOriginal(entry)
        local path, export
        if type(entry) == "table" then path, export = entry.module, entry.export else path = entry end
        local loaded = require(path)
        if type(loaded) == "function" then return loaded end
        return loaded[export or "__main"] or loaded.main
    end

    local function override(name, wrapper)
        local keys, entry = keysFor(name)
        if not entry then
            R:unsupported("inventory:" .. name, "The merged manifest has no such script to adapt.")
            return
        end
        local original = loadOriginal(entry)
        local fn = function(runtime, E) return wrapper(original, runtime, E) end
        for _, key in ipairs(keys) do R.scripts[key] = fn end
    end

    -- Name/value consumers: fill the foreign entries the original switch
    -- cannot match, leaving every native entry exactly as the game produced
    -- it.  scr_itemvalue fills the caller-scope array `value` (GML scripts
    -- share the caller's variables), the rest fill globals.
    local function fillInventorySlots(arrayName, fill, inScope)
        return function(original, R, E)
            original(R, E)
            local names = R:array(inScope and E or R.global, arrayName, E)
            for index = 0, SLOT_COUNT - 1 do
                local token = item[index]
                if type(token) == "string" then names[index] = fill(token) end
            end
        end
    end

    override("scr_itemname", fillInventorySlots("itemname", function(token) return token end))
    override("scr_itemnameb", fillInventorySlots("itemnameb", function(token) return token end))
    override("scr_itemvalue", fillInventorySlots("value", function() return 0 end, true))

    override("scr_storagename", function(original, R, E)
        original(R, E)
        local base = E.argument0
        local flags = R:array(R.global, "flag", E)
        local names = R:array(R.global, "itemname", E)
        for index = 0, 10 do
            local token = flags[base + index]
            if type(token) == "string" then names[index] = token end
        end
    end)

    override("scr_itemdesc", function(original, R, E)
        local token = E.argument0
        if type(token) ~= "string" then return original(R, E) end
        local entry = entryOf(token)
        local msg = R:array(R.global, "msg", E)
        local messages = entry and entry.messages or {}
        for i = 0, 10 do msg[i] = nil end
        if #messages == 0 then
            msg[0] = "* (You cannot use this item.)"
        else
            for i, line in ipairs(messages) do msg[i - 1] = line end
        end
        return 0
    end)

    -- Use dispatch: the common item actions carry foreign items in both
    -- directions, so every item is usable from either content set's menu.
    override("scr_itemuseb", function(original, R, E)
        local token = E.argument1
        if type(token) ~= "string" then return original(R, E) end
        bridge.commonUse(E, token, E.argument0 + 1, "undertale")
        return 0
    end)

    override("scr_item_use", function(original, R, E)
        local token = E.argument0
        if yellowUse[token] or utByName[token] == nil then return original(R, E) end
        -- A foreign Undertale name: Yellow's switch would drop the item with
        -- no effect (its fall-through consumes at heal 0), so route it to the
        -- catalog's action instead.
        bridge.commonUse(E, utByName[token], E.argument1, "yellow")
        return 0
    end)

    -- Yellow's determine chain (scr_determine_* -> scr_item_stats_*) is the
    -- equipment-stat entry point.  Foreign tokens resolve through the
    -- catalog; Yellow's own names keep the original tables verbatim.
    local statKinds = {
        scr_item_stats_weapon = "weapon",
        scr_item_stats_armor = "armor",
        scr_item_stats_weapon_mod = "ammo",
        scr_item_stats_armor_mod = "accessory",
    }
    for name, kind in pairs(statKinds) do
        local kindOf = kind
        override(name, function(original, R, E)
            local token = E.argument0
            local entry = entryOf(token)
            if not entry or catalog.yellow[token] then return original(R, E) end
            return statOf(token, kindOf)
        end)
    end

    -- Heal table used by Yellow's info text; foreign items report their own
    -- extracted heal (or 0 when the source has no fixed number).
    override("scr_item_stats_heal", function(original, R, E)
        local token = R:get(E, "argument0", E)
        local entry = entryOf(token)
        if not entry or catalog.yellow[token] then return original(R, E) end
        return type(entry.heal) == "number" and entry.heal or 0
    end)

    R:warn("inventory",
        "One shared inventory and one four-slot equipment set: global.item and " ..
        "global.item_slot are views of the same eight slots, and the gear stat " ..
        "globals are derived from the equipped tokens. Items from either game " ..
        "are usable in both.")
    return bridge
end

return Inventory
