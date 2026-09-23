-- One authoritative owner of the merged player's core progression (piece 5a).
--
-- Converted code still spells HP as global.hp or global.current_hp_self, etc.
-- These are *views*, not copies synchronized each frame or on travel. Every
-- read/write, including Runtime:get/set/increment, addresses R.player directly.
-- No progression value is stored in a world-specific record or global.flag.
--
-- Only aliases with the same meaning are bound here. Inventory and primary
-- equipment need an item-ID compatibility table (UT numbers / Yellow strings),
-- Movement is the controller (piece 5c). The Player+World save is port/save.lua
-- (piece 5d). In
-- particular, kills (UT's total vs Yellow's remaining regional populations),
-- battle speed and temporary encounter state are NOT guessed to be synonyms.
local Player = {}
Player.__index = Player

-- Names from SCR_GAMESTART and the pinned Yellow scr_initialize. Defaults are
-- supplied by those scripts, not duplicated as a second set of numbers here.
local FIELDS = {
    {key = "hp",        aliases = {"hp", "current_hp_self"}},
    {key = "maxHp",     aliases = {"maxhp", "max_hp_self"}},
    {key = "level",     aliases = {"lv", "player_level"}},
    {key = "exp",       aliases = {"xp", "player_exp"}},
    {key = "gold",      aliases = {"gold", "player_gold"}},
    {key = "name",      aliases = {"charname", "player_name"}},
    {key = "attack",    group = "stats", aliases = {"at", "player_attack"}},
    {key = "defense",   group = "stats", aliases = {"df", "player_defense"}},
}

function Player.install(R)
    if R.manifest.game ~= "merged" then return nil end
    if R.playerBridge then return R.playerBridge end
    local state = {stats = {}}
    local bridge = setmetatable({state = state, defaultsDepth = 0}, Player)
    local aliases = {}
    for _, field in ipairs(FIELDS) do
        for _, name in ipairs(field.aliases) do
            -- Installing before any gameplay initialization is intentional:
            -- choosing between two pre-existing values would silently discard
            -- someone's progress. A misplaced late install must stop instead.
            if rawget(R.global, name) ~= nil then
                R:unsupported("Player alias " .. name, "Install the shared player before gameplay initialization.")
            end
            aliases[name] = field
        end
    end
    local fallback = getmetatable(R.global).__index
    setmetatable(R.global, {
        __index = function(global, name)
            local field = aliases[name]
            if not field then return fallback(global, name) end
            local owner = field.group and state[field.group] or state
            local value = owner[field.key]
            -- Preserve GML's unset-zero semantics, without treating zero HP,
            -- zero EXP or an empty name as an absent field during init.
            if value == nil then return 0 end
            return value
        end,
        __newindex = function(global, name, value)
            local field = aliases[name]
            if not field then rawset(global, name, value); return end
            local owner = field.group and state[field.group] or state
            if bridge.defaultsDepth == 0 or owner[field.key] == nil then
                owner[field.key] = value
            end
        end,
    })
    R.player, R.playerBridge = state, bridge
    return bridge
end

-- Content initialization needs to seed its world globals, collections and
-- controllers, not create a new protagonist. During that call only *absent*
-- Player fields may receive defaults; existing stats (including overheal and
-- zero/negative HP) stay live for Create/room code to read throughout the call.
-- This is not a capture/reset/restore cycle: no temporary fresh player is ever
-- exposed to nested scripts. Normal new-game/load/reward writes remain enabled.
function Player:withDefaults(initialize)
    self.defaultsDepth = self.defaultsDepth + 1
    local ok, result = pcall(initialize)
    self.defaultsDepth = self.defaultsDepth - 1
    if not ok then error(result, 0) end
    return result
end

return Player
