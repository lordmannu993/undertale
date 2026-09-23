-- One player controller for both worlds (fusion piece 5c).
--
-- obj_mainchara and obj_pl stay the worlds' own adapters: each room still
-- places the entity that room was built for, and Yellow's scr_normal_state
-- still owns Yellow's collision and its compiled 3+2 sprint. What is no longer
-- two isolated controllers is the decision those adapters share:
--
--   * one R.player.controller table, the same object after every crossing
--   * one facing, applied after the destination entity exists (obj_pl's Create
--     hardcodes direction = 270 and would otherwise forget it)
--   * one run ability (player_can_run) and one menu/interact gate
--   * Undertale runs on the same X/Shift cluster Yellow uses, as one extra
--     3px lattice step so the existing wall-slide still sees ±3
--   * one level-up rule: Undertale's scr_levelup. Yellow's award alarm still
--     grants EXP and gold; its *_next write is not a second formula
--
-- Piece 6 owns cropped sizes, origins, and Yellow's exact +2 speed. This
-- file does not change the ±3 step into 5, and it does not invent run sprites
-- for costumes that have no Clover pair.
local Controller = {}
Controller.__index = Controller

-- obj_mainchara's own step. Piece 6 replaces the extra lattice step with
-- Yellow's +2 once a 5px step can collide; until then running is strictly
-- faster than walking and still on the lattice the wall-slide assumes.
Controller.LATTICE = 3
-- scr_normal_state's sprint image_speed, not a new number.
Controller.RUN_IMAGE_SPEED = 1 / 3

local FACING_TO_DIRECTION = { [0] = 270, [1] = 0, [2] = 90, [3] = 180 }
local DIRECTION_TO_FACING = { [270] = 0, [0] = 1, [90] = 2, [180] = 3 }
local UT_SPRITE = { [0] = "dsprite", [1] = "rsprite", [2] = "usprite", [3] = "lsprite" }
local YELLOW_SPRITE = {
    [0] = "dsprite_walk", [1] = "rsprite_walk", [2] = "usprite_walk", [3] = "lsprite_walk",
}

-- Menu is cluster 2, interact is cluster 0. Both games' own handlers stay the
-- implementation; the controller only decides whether those keys are visible
-- to them. X/Shift (cluster 1) is not gated here: it is also cancel and the
-- boat latch, and player_can_run already gates the sprint itself.
local MENU_KEYS = { 17, 67, 99 }
local INTERACT_KEYS = { 13, 90, 122, 89 }

local YELLOW_ATTACK_SCRIPTS = {
    "scr_damage_determination_enemy",
    "scr_damage_determination_enemy_2",
    "scr_damage_determination_enemy_3",
    "scr_damage_determination_boss",
    "scr_determine_attacking_damage_stat_critical",
}
local UT_ATTACK_SCRIPTS = { "scr_attackcalc", "scr_mercystandard" }
local UT_DEFENSE_SCRIPTS = { "scr_damagestandard" }

local function asFlag(value)
    if value == true then return 1 end
    if value == false or value == nil then return 0 end
    if type(value) == "number" then return value end
    return 0
end

function Controller.install(R)
    if R.manifest.game ~= "merged" then return nil end
    if R.playerController then return R.playerController end
    if not R.player or not R.playerBridge then
        R:unsupported("controller", "Install the shared player before the shared controller.")
    end
    local names = R.manifest.names or {}
    local yellowObjects = (R.manifest.yellow_names or {}).objects or {}
    local controller = setmetatable({
        runtime = R,
        sprinting = false,
        gated = {},
        mainchara = names.obj_mainchara,
        clover = yellowObjects.obj_pl,
    }, Controller)
    R.player.controller = controller
    R.player.movement = R.player.movement or { facing = nil, sprinting = false }
    R.player.abilities = R.player.abilities or {}
    -- 1/0, matching GML true/false. Run starts available so Undertale can
    -- sprint before Yellow's initializer has ever written player_can_run;
    -- withDefaults will not replace this existing value on the way in.
    if R.player.abilities.run == nil then R.player.abilities.run = 1 end
    if R.player.abilities.interact == nil then R.player.abilities.interact = 1 end
    if R.player.abilities.menu == nil then R.player.abilities.menu = 1 end
    R.playerController = controller

    controller:bindRunAbility()
    controller:wrapEvents()
    controller:wrapBattleConsumers()

    -- Capture before travel:resolve. Crossing runs scr_initialize, which
    -- creates obj_pl (direction hard-coded to 270) before the room loads.
    -- Capturing inside loadRoom would read that fresh instance and forget
    -- the facing the player just had.
    local gotoRoom = R.gotoRoom
    function R:gotoRoom(...)
        controller:captureFacing()
        return gotoRoom(self, ...)
    end
    local loadRoom = R.loadRoom
    function R:loadRoom(...)
        controller:beforeLoadRoom()
        local results = { loadRoom(self, ...) }
        controller:afterLoadRoom()
        return unpack(results)
    end
    local step = R.step
    function R:step(...)
        controller:beforeStep()
        local result = step(self, ...)
        controller:afterStep()
        return result
    end

    R:warn("controller",
        "Shared player controller: one R.player.controller drives both adapters. " ..
        "Undertale runs on X/Shift (one extra 3px lattice step, Clover's run cycle) while " ..
        "player_can_run is set; Yellow's scr_normal_state still owns Yellow's 3+2 step. " ..
        "AUTO RUN stays Yellow's option. Level-up is Undertale's scr_levelup " ..
        "(LV 20 is 99/99/99, EXP caps at 99999); current HP is not a level-up output. " ..
        "Exact speeds, origins and run-mask hitboxes are piece 6.")
    return controller
end

function Controller:world()
    local travel = self.runtime.travel
    return travel and travel.world or "undertale"
end

function Controller:entity()
    local id = self:world() == "yellow" and self.clover or self.mainchara
    if not id then return nil end
    for _, instance in ipairs(self.runtime.instances) do
        if instance.alive and instance.v.object_index == id then return instance end
    end
    return nil
end

-- player_can_run is the run ability, not a second flag beside it. Yellow's
-- compiled sprint line compares it to true (1); a Lua boolean would fail that.
function Controller:bindRunAbility()
    local R = self.runtime
    if rawget(R.global, "player_can_run") ~= nil then
        R:unsupported("Player ability player_can_run",
            "Install the shared controller before gameplay initialization.")
    end
    local current = getmetatable(R.global)
    local previousIndex, previousNewindex = current.__index, current.__newindex
    setmetatable(R.global, {
        __index = function(global, name)
            if name == "player_can_run" then
                local value = R.player.abilities.run
                if value == nil then return 0 end
                return value
            end
            return previousIndex(global, name)
        end,
        __newindex = function(global, name, value)
            if name == "player_can_run" then
                local bridge = R.playerBridge
                if not bridge or bridge.defaultsDepth == 0 or R.player.abilities.run == nil then
                    R.player.abilities.run = asFlag(value)
                end
                return
            end
            return previousNewindex(global, name, value)
        end,
    })
end

-- Compiled Yellow rule (scr_normal_state): autorun XOR (button AND can_run).
-- can_run gates the button only; autorun-on with the button up still sprints
-- in Yellow even when can_run is false. Undertale does not read AUTO RUN:
-- that option is Yellow's, and the shared ability there is the run button.
function Controller:runButton(entity)
    local R = self.runtime
    return R.truth(R:call("keyboard_multicheck", R:scope(entity), 1))
end

function Controller:canRun()
    return self.runtime.global.player_can_run == 1
end

function Controller:runEngaged(entity)
    local button = self:runButton(entity)
    local can = self:canRun()
    if self:world() == "yellow" then
        local autorun = self.runtime.truth(self.runtime.global.option_autorun)
        return autorun ~= (button and can)
    end
    return button and can
end

function Controller:applyAbilityGate()
    local R = self.runtime
    local abilities = R.player.abilities
    self.gated = {}
    local function gate(keys)
        for _, code in ipairs(keys) do
            self.gated[code] = true
            R.input.suppressed[code] = true
        end
    end
    if not R.truth(abilities.menu) then gate(MENU_KEYS) end
    if not R.truth(abilities.interact) then gate(INTERACT_KEYS) end
end

function Controller:clearAbilityGate()
    local suppressed = self.runtime.input.suppressed
    for code in pairs(self.gated or {}) do suppressed[code] = nil end
    self.gated = {}
end

function Controller:beforeStep()
    self.sprinting = false
    self:applyAbilityGate()
end

function Controller:afterStep()
    self:clearAbilityGate()
    local entity = self:entity()
    local movement = self.runtime.player.movement
    if self:world() == "yellow" and entity then
        movement.sprinting = self.runtime.truth(entity.v.is_sprinting)
    else
        movement.sprinting = self.sprinting and true or false
        if entity then entity.v.is_sprinting = self.sprinting and 1 or 0 end
    end
    self.sprinting = false
    self:captureFacing(entity)
end

-- Undertale's End Step already follows x for the camera and decides moving
-- from xprevious. The extra lattice step has to land before that, with
-- xprevious restored afterwards so a blocked bonus does not look like the
-- walk never happened.
function Controller:undertaleEndStep(E)
    local entity = E and E._self
    if not entity or not entity.alive or entity.v.object_index ~= self.mainchara then return end
    if not self:runEngaged(entity) then return end
    local frameX, frameY = entity.v.xprevious, entity.v.yprevious
    local dx, dy = entity.v.x - frameX, entity.v.y - frameY
    local function lattice(delta)
        if delta == Controller.LATTICE or delta == -Controller.LATTICE then return delta end
        return 0
    end
    local bx, by = lattice(dx), lattice(dy)
    if bx ~= 0 or by ~= 0 then
        local walkedX, walkedY = entity.v.x, entity.v.y
        entity.v.xprevious, entity.v.yprevious = walkedX, walkedY
        entity.v.x, entity.v.y = walkedX + bx, walkedY + by
        if entity.alive then self.runtime:collisionEvents({ entity }) end
        if entity.alive then
            entity.v.xprevious, entity.v.yprevious = frameX, frameY
        end
    end
    if entity.alive then
        self.sprinting = entity.v.x ~= frameX or entity.v.y ~= frameY
    end
end

function Controller:finishUndertaleEndStep(entity)
    if not entity or not entity.alive then return end
    if self.sprinting and entity.v.image_speed ~= 0 then
        entity.v.image_speed = Controller.RUN_IMAGE_SPEED
    end
    entity.v.is_sprinting = self.sprinting and 1 or 0
end

function Controller:captureFacing(entity)
    entity = entity or self:entity()
    if not entity or not entity.alive then return end
    local facing
    if self:world() == "yellow" then
        facing = DIRECTION_TO_FACING[entity.v.direction]
    else
        local value = self.runtime.global.facing
        if type(value) == "number" and FACING_TO_DIRECTION[value] then facing = value end
    end
    if facing ~= nil then self.runtime.player.movement.facing = facing end
end

function Controller:beforeLoadRoom()
    -- Do not recapture here. By the time the room loads, scr_initialize has
    -- already created obj_pl at direction 270. gotoRoom captured the departing
    -- entity; only publish that value so Undertale's Create, which reads
    -- global.facing during this load, agrees with afterLoadRoom.
    local facing = self.runtime.player.movement.facing
    if facing ~= nil then self.runtime.global.facing = facing end
end

function Controller:afterLoadRoom()
    local facing = self.runtime.player.movement.facing
    if facing == nil then return end
    local entity = self:entity()
    if not entity then return end
    if self:world() == "yellow" then
        entity.v.direction = FACING_TO_DIRECTION[facing]
        local sprite = entity.v[YELLOW_SPRITE[facing]]
        if type(sprite) == "number" and sprite > 0 then entity.v.sprite_index = sprite end
    else
        self.runtime.global.facing = facing
        entity.v.facing = facing
        local sprite = entity.v[UT_SPRITE[facing]]
        if type(sprite) == "number" and sprite > 0 then entity.v.sprite_index = sprite end
    end
end

function Controller:wrapEvents()
    local R = self.runtime
    if not self.mainchara then
        R:unsupported("controller:obj_mainchara", "Undertale's player object is missing from the merged manifest.")
    end
    local player = R:object(self.mainchara)
    local endStep = player and player.events and player.events["3:2"]
    if type(endStep) ~= "function" then
        R:unsupported("controller:obj_mainchara End Step",
            "Undertale's player has no End Step to attach the run step to.")
    end
    local controller = self
    player.events["3:2"] = function(runtime, E)
        controller:undertaleEndStep(E)
        if not E._self.alive then return 0 end
        local result = endStep(runtime, E)
        controller:finishUndertaleEndStep(E._self)
        return result
    end

    local fadeId = ((R.manifest.yellow_names or {}).objects or {}).obj_battle_fade_out_screen
    if not fadeId then
        R:unsupported("controller:obj_battle_fade_out_screen",
            "Yellow's battle-award object is missing from the merged manifest.")
    end
    local fade = R:object(fadeId)
    local alarm = fade and fade.events and fade.events["2:0"]
    if type(alarm) ~= "function" then
        R:unsupported("controller:obj_battle_fade_out_screen Alarm 0",
            "Yellow's battle-award alarm is missing; level-up would keep a second formula.")
    end
    fade.events["2:0"] = function(runtime, E)
        return controller:afterYellowAward(alarm, runtime, E)
    end
end

function Controller:progressionSnapshot()
    local player = self.runtime.player
    local stats = player.stats or {}
    return {
        level = player.level,
        hp = player.hp,
        maxHp = player.maxHp,
        attack = stats.attack,
        defense = stats.defense,
    }
end

-- Yellow's alarm grants EXP and gold, then copies *_next[i] while setting
-- level = i + 1 (one behind the table label). That write is not the shared
-- rule. scr_levelup is: it assigns LV from EXP and, only when LV changes,
-- writes max HP / AT / DF, including the LV 20 cap of 99/99/99 and the EXP
-- cap of 99999. Current HP is restored because the source script does not
-- touch it. A grant that does not change LV or those stats is left alone,
-- except the EXP cap, which the script applies without rewriting stats when
-- LV is already 20.
function Controller:reconcileProgression(before, E)
    local R = self.runtime
    local stats = R.player.stats or {}
    local changed = R.player.level ~= before.level
        or R.player.maxHp ~= before.maxHp
        or stats.attack ~= before.attack
        or stats.defense ~= before.defense
    if changed then
        local hp = before.hp
        R.player.level = -1
        R:call("scr_levelup", E)
        if R.player.level == -1 then R.player.level = before.level end
        R.player.hp = hp
        return
    end
    if type(R.player.exp) == "number" and R.player.exp >= 99999 then
        R:call("scr_levelup", E)
    end
end

function Controller:afterYellowAward(original, runtime, E)
    local before = self:progressionSnapshot()
    local ok, result = pcall(original, runtime, E)
    if not ok then error(result, 0) end
    if E and E._self then self:reconcileProgression(before, E) end
    return result
end

function Controller:loadScript(key)
    local R = self.runtime
    local entry = (R.manifest.scripts or {})[key]
    if not entry then
        R:unsupported("controller:" .. tostring(key),
            "Battle consumer script is missing from the merged manifest.")
    end
    local path, export
    if type(entry) == "table" then
        path, export = entry.module, entry.export
    else
        path = entry
    end
    local loaded = require(path)
    local fn = loaded
    if type(loaded) == "table" then
        fn = loaded[export or "__main"] or loaded.main
    end
    if type(fn) ~= "function" then
        R:unsupported("controller:" .. tostring(key),
            "Battle consumer did not export a function.")
    end
    return fn
end

function Controller:compose(mode, fn)
    local player = self.runtime.player
    local prior = player.battleCompose
    player.battleCompose = mode
    local ok, result = pcall(fn)
    player.battleCompose = prior
    if not ok then error(result, 0) end
    return result
end

-- The gear views stay what piece 5b pinned (ammo is not wstrength, accessory
-- is not adef). Battle scripts are the consumers that compose them: Undertale's
-- fight reads wstrength and so must see ammo there, its hurt reads adef and so
-- must see the accessory, and Yellow's fight reads player_weapon_attack and so
-- must see the armour's weapon bonus. Yellow's hurt already adds the accessory
-- itself and is not wrapped.
function Controller:wrapBattleConsumers()
    local R = self.runtime
    local function wrap(key, mode)
        local original = self:loadScript(key)
        R.scripts[key] = function(runtime, E)
            return self:compose(mode, function() return original(runtime, E) end)
        end
    end
    for _, name in ipairs(UT_ATTACK_SCRIPTS) do
        local index = (R.manifest.names or {})[name]
        if not index then
            R:unsupported("controller:" .. name, "Undertale battle script is missing from the merged manifest.")
        end
        wrap(index, "ut-attack")
    end
    for _, name in ipairs(UT_DEFENSE_SCRIPTS) do
        local index = (R.manifest.names or {})[name]
        if not index then
            R:unsupported("controller:" .. name, "Undertale battle script is missing from the merged manifest.")
        end
        wrap(index, "ut-defense")
    end
    for _, name in ipairs(YELLOW_ATTACK_SCRIPTS) do
        wrap(name, "yellow-attack")
    end
end

return Controller
