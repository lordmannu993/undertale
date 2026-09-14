-- GameMaker particle systems: part_system_*, part_type_*, part_emitter_* and
-- part_particles_create/clear, as used by Undertale Yellow's 33 particle
-- objects (37 objects reference the family; the other four only emit into or
-- destroy systems owned elsewhere).
--
-- Undertale's own checkout calls none of these, so everything here is inert
-- for Undertale: no systems exist, the per-step update loops over nothing,
-- and the renderer builds the same draw list as before.
--
-- Semantics follow the GameMaker manual:
--   * systems own emitters and live particles, draw all of them at one depth,
--     and persist across rooms until destroyed (Room End handlers such as
--     part_snow's Other_5 destroy them explicitly);
--   * types own the attribute record; each spawned particle randomises its own
--     speed, direction, size, orientation, life and colour-mix factor;
--   * emitters own a region (rectangle/ellipse/diamond/line) plus a
--     distribution (linear/gaussian/inverse-gaussian) and an optional stream;
--   * direction 0 is east and 90 is up, matching Runtime:instanceSet, and
--     gravity is a vector added to the velocity each step;
--   * colour/alpha gradients interpolate over life (1: constant, 2: across the
--     whole life, 3: first half then second half); colour_mix instead fixes one
--     random blend per particle.
--
-- Documented deviations, each reported rather than hidden:
--   * Yellow's part_type_sprite sites pass the decompiler's raw numeric sprite
--     IDs (636 for spr_snowflake, 665, 238, ...), which are Yellow's own asset
--     numbers. When the caller is Yellow code they resolve through the merged
--     ID band (636 -> 1000000+636), exactly as Travel reads Yellow's room
--     numbers through that band; Undertale callers keep exact IDs. A Yellow
--     number with no banded sprite draws nothing and warns instead of drawing
--     an unrelated Undertale sprite. (Yellow's few other raw-number asset
--     arguments, e.g. audio_play_sound(229), keep their existing behaviour;
--     they are outside this piece.)
--   * part_system_create takes no arguments in GameMaker, but two Yellow sites
--     pass one (obj_waterfall_foreground passes 2, obj_martlet_final_syringe
--     passes 1). The extra argument is ignored with a warning.
--   * Destroy/clear/exists on an already-destroyed handle are lenient no-ops
--     returning false, as in GameMaker: several Yellow objects destroy a
--     shared global.ps from both Destroy and Room End. Burst/stream/create
--     calls on a missing handle are likewise ignored, warning once per builtin
--     per run so a real bug is still visible.
--   * Inverse-gaussian sampling is min/max-of-two-uniforms edge bias, and
--     gaussian is mean-of-three; the manual only specifies linear exactly.
--   * Shape pixel sizes are approximate (documented per shape in
--     port/graphics.lua); sprite particles use the sprite's own pixels exactly.
--   * Fractional burst/stream counts are floored; a fractional stream chance
--     (e.g. -(room_width/18.82)) keeps its fractional probability.
--   * Particle ids start at 1, so a stored handle is always truthy in GML.
return function(R)
    local B = R.builtins
    local N, T = R.num, R.truth

    for name, value in pairs({
        pt_shape_pixel = 0, pt_shape_disk = 1, pt_shape_square = 2, pt_shape_line = 3,
        pt_shape_star = 4, pt_shape_circle = 5, pt_shape_ring = 6, pt_shape_sphere = 7,
        pt_shape_flare = 8, pt_shape_spark = 9, pt_shape_explosion = 10, pt_shape_cloud = 11,
        pt_shape_smoke = 12, pt_shape_snow = 13,
        ps_shape_rectangle = 0, ps_shape_ellipse = 1, ps_shape_diamond = 2, ps_shape_line = 3,
        ps_distr_linear = 0, ps_distr_gaussian = 1, ps_distr_invgaussian = 2,
    }) do
        if R.constants[name] == nil then R.constants[name] = value end
    end

    local P = {systems = {}, types = {}, nextSystem = 1, nextType = 1}
    R.particles = P

    local function scripts() return R.manifest.scripts or {} end
    local function hasScript(name)
        local names = R.manifest.names or {}
        return scripts()[name] ~= nil or (names[name] ~= nil and scripts()[names[name]] ~= nil)
    end
    local function reg(name, fn)
        if B[name] == nil and not hasScript(name) then
            B[name] = function(E, ...) return fn(E, ...) end
        end
    end

    local function systemOf(id)
        return type(id) == "number" and P.systems[math.floor(id)] or nil
    end
    local function typeOf(id)
        return type(id) == "number" and P.types[math.floor(id)] or nil
    end
    local function emitterOf(sys, id)
        return sys and type(id) == "number" and sys.emitters[math.floor(id)] or nil
    end
    local function missingHandle(name, detail)
        R:warn("particles-missing:" .. name,
            detail .. " GameMaker ignores the call too, so nothing was spawned or changed.")
    end

    local function rnd(a, b)
        a, b = a or 0, b or 0
        if a == b then return a end
        if a > b then a, b = b, a end
        return a + math.random() * (b - a)
    end
    local function wobble(amount)
        return amount ~= 0 and rnd(-amount, amount) or 0
    end

    local function resolveSprite(E, index)
        local base = R.manifest.yellow_base or 1000000
        if type(index) ~= "number" or index < 0 or index >= base then return index end
        index = math.floor(index)
        -- One rule for all of Yellow's decompiler numbers (see
        -- Runtime:resolveObjectIndex): a Yellow caller means its own asset.
        if not R:callerIsYellow(E) then return index end
        local banded = base + index
        local sprite = R.assets.sprites[banded]
        if sprite then
            R:warn("particle-sprite:" .. index,
                "part_type_sprite(" .. index .. ") is Yellow's own asset number; resolved to " ..
                banded .. " (" .. tostring(sprite.name) .. ") through the merged ID band.")
            return banded
        end
        R:warn("particle-sprite-missing:" .. index,
            "part_type_sprite(" .. index .. ") names no Yellow sprite in the merged build; " ..
            "the particle type draws nothing rather than an unrelated sprite.")
        return -1
    end

    local function spawn(sys, typeId, x, y, colour)
        local t = typeOf(typeId)
        if not t then return nil end
        local dir = rnd(t.dirMin, t.dirMax)
        local speed = rnd(t.speedMin, t.speedMax)
        local radians = math.rad(dir)
        local life = t.lifeMin
        if t.lifeMax ~= t.lifeMin then
            life = math.floor(rnd(math.min(t.lifeMin, t.lifeMax), math.max(t.lifeMin, t.lifeMax) + 1))
        end
        local particle = {
            type = math.floor(typeId), x = x, y = y,
            vx = math.cos(radians) * speed, vy = -math.sin(radians) * speed,
            speed = speed, dir = dir,
            size = rnd(t.sizeMin, t.sizeMax),
            ang = rnd(t.oriMin, t.oriMax),
            age = 0, life = math.max(1, math.floor(life)),
            mix = math.random(),
            colour = colour,
            frame = 0,
        }
        if t.sprite ~= nil and t.sprite >= 0 then
            local sprite = R.assets.sprites[t.sprite]
            local frames = sprite and #sprite.frames or 0
            if frames > 1 and T(t.randomStart) then
                particle.frame = math.floor(math.random() * frames)
            end
        end
        sys.particles[#sys.particles + 1] = particle
        return particle
    end

    local function sampleUnit(distr)
        if distr == 1 then
            return (math.random() + math.random() + math.random()) / 3
        end
        if distr == 2 then
            local a, b = math.random(), math.random()
            if math.random() < 0.5 then return math.min(a, b) end
            return math.max(a, b)
        end
        return math.random()
    end
    local function emitPoint(em)
        local shape = em.shape or 0
        if shape == 3 then
            local t = sampleUnit(em.distr)
            return em.xmin + (em.xmax - em.xmin) * t, em.ymin + (em.ymax - em.ymin) * t
        end
        for _ = 1, 8 do
            local u, v = sampleUnit(em.distr), sampleUnit(em.distr)
            if shape == 0 then
                return em.xmin + (em.xmax - em.xmin) * u, em.ymin + (em.ymax - em.ymin) * v
            end
            local dx, dy = u * 2 - 1, v * 2 - 1
            local inside = shape == 1 and dx * dx + dy * dy <= 1
                or shape == 2 and math.abs(dx) + math.abs(dy) <= 1
            if inside then
                return em.xmin + (em.xmax - em.xmin) * u, em.ymin + (em.ymax - em.ymin) * v
            end
        end
        return (em.xmin + em.xmax) / 2, (em.ymin + em.ymax) / 2
    end
    local function emit(sys, em, typeId, colour)
        local x, y = emitPoint(em)
        return spawn(sys, typeId, x, y, colour)
    end

    local function updateParticle(sys, p)
        local t = typeOf(p.type)
        p.age = p.age + 1
        if p.age >= p.life then
            if t and t.deathNumber > 0 and typeOf(t.deathType) then
                for _ = 1, math.floor(t.deathNumber) do spawn(sys, t.deathType, p.x, p.y) end
            end
            return false
        end
        if t then
            if t.stepNumber > 0 and typeOf(t.stepType) then
                for _ = 1, math.floor(t.stepNumber) do spawn(sys, t.stepType, p.x, p.y) end
            end
            p.speed = p.speed + t.speedIncr + wobble(t.speedWiggle)
            p.dir = (p.dir + t.dirIncr + wobble(t.dirWiggle)) % 360
            local radians = math.rad(p.dir)
            p.vx = math.cos(radians) * p.speed
            p.vy = -math.sin(radians) * p.speed
            if t.gravAmount ~= 0 then
                local gravity = math.rad(t.gravDir)
                p.vx = p.vx + math.cos(gravity) * t.gravAmount
                p.vy = p.vy - math.sin(gravity) * t.gravAmount
                p.speed = math.sqrt(p.vx * p.vx + p.vy * p.vy)
                if p.speed > 0 then
                    p.dir = (-math.deg(math.atan2(p.vy, p.vx))) % 360
                end
            end
            p.x = p.x + p.vx
            p.y = p.y + p.vy
            p.size = p.size + t.sizeIncr + wobble(t.sizeWiggle)
            p.ang = p.ang + t.oriIncr + wobble(t.oriWiggle)
        end
        return true
    end

    local function updateSystem(sys)
        for _, em in pairs(sys.emitters) do
            if em.streamType ~= nil and em.streamType >= 0 and em.streamNumber ~= 0
                and typeOf(em.streamType) then
                local number = em.streamNumber
                if number > 0 then
                    for _ = 1, math.floor(number) do emit(sys, em, em.streamType) end
                elseif math.random() < 1 / math.abs(number) then
                    emit(sys, em, em.streamType)
                end
            end
        end
        -- Newborns (streams, step and death spawns) join the back of the array
        -- and update next step, so a death chain can never loop inside one step
        -- and the array stays in creation order for draw_order.
        local list, count = sys.particles, #sys.particles
        local kept = {}
        for i = 1, count do
            if updateParticle(sys, list[i]) then kept[#kept + 1] = list[i] end
        end
        for i = count + 1, #list do kept[#kept + 1] = list[i] end
        sys.particles = kept
    end

    function R:updateParticles()
        for _, sys in pairs(P.systems) do
            if sys.autoUpdate then updateSystem(sys) end
        end
    end

    -- Systems created on a room layer die with the room unless they were made
    -- persistent; a persistent one keeps its last depth but unbinds, because
    -- the next room has its own layers. Classic part_system_create systems are
    -- global and survive, which is why Yellow destroys them in Room End.
    function R:clearRoomParticleSystems()
        for id, sys in pairs(P.systems) do
            if sys.layer ~= nil then
                if sys.persistent then
                    sys.depth = self:particleDepth(sys)
                    sys.layer = nil
                else
                    P.systems[id] = nil
                end
            end
        end
    end
    function R:destroyLayerParticleSystems(index)
        for id, sys in pairs(P.systems) do
            if sys.layer == index then P.systems[id] = nil end
        end
    end
    function R:particleDepth(sys)
        if sys.layer ~= nil and self.roomState and self.roomState.layers then
            local layer = self.roomState.layers[sys.layer]
            if layer and not layer.destroyed then return layer.depth or sys.depth end
        end
        return sys.depth
    end
    function R:particleLayerVisible(sys)
        if sys.layer ~= nil and self.roomState and self.roomState.layers then
            local layer = self.roomState.layers[sys.layer]
            if not layer or layer.destroyed then return false end
            return layer.visible ~= false
        end
        return true
    end

    -- The draw-ready values for one particle: position (with the system's own
    -- offset), interpolated colour and alpha, current size and angle, and the
    -- sprite frame. The renderer in port/graphics.lua owns the actual drawing.
    function R:particleAppearance(sys, p)
        local t = typeOf(p.type) or {}
        local frac = p.life > 0 and math.min(1, p.age / p.life) or 1
        local colour = p.colour
        if colour == nil then
            local mode = t.colourMode or "none"
            if mode == "mix" then
                colour = B.merge_color(nil, t.mixA, t.mixB, p.mix)
            elseif mode == "c1" then
                colour = t.c1
            elseif mode == "c2" then
                colour = B.merge_color(nil, t.c1, t.c2, frac)
            elseif mode == "c3" then
                colour = frac < 0.5 and B.merge_color(nil, t.c1, t.c2, frac * 2)
                    or B.merge_color(nil, t.c2, t.c3, (frac - 0.5) * 2)
            else
                colour = 16777215
            end
        end
        local alphaMode = t.alphaMode or "none"
        local alpha = 1
        if alphaMode == "a1" then
            alpha = t.a1
        elseif alphaMode == "a2" then
            alpha = t.a1 + (t.a2 - t.a1) * frac
        elseif alphaMode == "a3" then
            alpha = frac < 0.5 and t.a1 + (t.a2 - t.a1) * frac * 2
                or t.a2 + (t.a3 - t.a2) * (frac - 0.5) * 2
        end
        local angle = p.ang
        if t.oriRelative then angle = angle + p.dir end
        local sprite, frame = -1, 0
        if t.sprite ~= nil and t.sprite >= 0 then
            sprite = t.sprite
            local asset = R.assets.sprites[sprite]
            local frames = asset and #asset.frames or 0
            if frames > 0 then
                if T(t.animat) then
                    if T(t.stretch) then
                        frame = p.frame + math.floor(frac * frames)
                    else
                        frame = p.frame + p.age
                    end
                else
                    frame = p.frame
                end
                frame = frame % frames
            end
        end
        return (sys.x or 0) + p.x, (sys.y or 0) + p.y,
            colour, math.max(0, math.min(1, alpha)),
            p.size, angle, sprite, frame,
            (t.shape == nil or t.shape < 0) and -1 or t.shape,
            t.xscale or 1, t.yscale or 1, T(t.blend)
    end

    -- Systems ------------------------------------------------------------
    local function newSystem()
        local id = P.nextSystem
        P.nextSystem = P.nextSystem + 1
        local sys = {
            id = id, depth = 0, x = 0, y = 0,
            particles = {}, emitters = {}, nextEmitter = 1,
            autoUpdate = true, autoDraw = true, oldtonew = true,
            layer = nil, persistent = false,
        }
        P.systems[id] = sys
        return id
    end
    reg("part_system_create", function(_, extra)
        if extra ~= nil then
            R:warn("particles-create-args",
                "part_system_create takes no arguments in GameMaker; the extra argument (" ..
                tostring(extra) .. ") is ignored.")
        end
        return newSystem()
    end)
    reg("part_system_create_layer", function(_, layer, persistent)
        local id = newSystem()
        local sys = P.systems[id]
        sys.persistent = T(persistent)
        local index = nil
        if R.roomState and R.roomState.layers then
            if type(layer) == "string" then
                for i, entry in ipairs(R.roomState.layers) do
                    if not entry.destroyed and entry.name == layer then index = i break end
                end
            elseif type(layer) == "number" then
                local entry = R.roomState.layers[math.floor(layer)]
                if entry and not entry.destroyed then index = math.floor(layer) end
            end
        end
        if index then
            sys.layer = index
            sys.depth = R.roomState.layers[index].depth or 0
        else
            R:warn("particles-layer:" .. tostring(layer),
                "part_system_create_layer(" .. tostring(layer) .. "): no such room layer; " ..
                "the system draws unbound at depth 0 instead.")
        end
        return id
    end)
    reg("part_system_destroy", function(_, id) P.systems[math.floor(id or -1)] = nil end)
    reg("part_system_exists", function(_, id) return N(systemOf(id) ~= nil) end)
    reg("part_system_clear", function(_, id)
        local sys = systemOf(id)
        if sys then sys.particles = {} end
    end)
    reg("part_system_draw_order", function(_, id, oldtonew)
        local sys = systemOf(id)
        if sys then sys.oldtonew = T(oldtonew) end
    end)
    reg("part_system_depth", function(_, id, depth)
        local sys = systemOf(id)
        if sys then sys.depth = depth or 0 end
    end)
    reg("part_system_position", function(_, id, x, y)
        local sys = systemOf(id)
        if sys then sys.x, sys.y = x or 0, y or 0 end
    end)
    reg("part_system_automatic_update", function(_, id, automatic)
        local sys = systemOf(id)
        if sys then sys.autoUpdate = T(automatic) end
    end)
    reg("part_system_automatic_draw", function(_, id, draw)
        local sys = systemOf(id)
        if sys then sys.autoDraw = T(draw) end
    end)
    reg("part_system_update", function(_, id)
        local sys = systemOf(id)
        if sys then updateSystem(sys) end
    end)
    reg("part_system_drawit", function(_, id)
        if R.drawParticlesNow then R:drawParticlesNow(id) end
    end)

    -- Types --------------------------------------------------------------
    local function typeDefaults()
        return {
            shape = -1, sprite = -1, animat = false, stretch = false, randomStart = true,
            sizeMin = 1, sizeMax = 1, sizeIncr = 0, sizeWiggle = 0,
            xscale = 1, yscale = 1,
            speedMin = 0, speedMax = 0, speedIncr = 0, speedWiggle = 0,
            dirMin = 0, dirMax = 0, dirIncr = 0, dirWiggle = 0,
            oriMin = 0, oriMax = 0, oriIncr = 0, oriWiggle = 0, oriRelative = false,
            gravAmount = 0, gravDir = 270,
            colourMode = "none", c1 = 16777215, c2 = 16777215, c3 = 16777215,
            mixA = 16777215, mixB = 16777215,
            alphaMode = "none", a1 = 1, a2 = 1, a3 = 1,
            blend = false,
            lifeMin = 100, lifeMax = 100,
            stepNumber = 0, stepType = -1,
            deathNumber = 0, deathType = -1,
        }
    end
    local function newType()
        local id = P.nextType
        P.nextType = P.nextType + 1
        P.types[id] = typeDefaults()
        return id
    end
    reg("part_type_create", function() return newType() end)
    reg("part_type_destroy", function(_, id) P.types[math.floor(id or -1)] = nil end)
    reg("part_type_exists", function(_, id) return N(typeOf(id) ~= nil) end)
    reg("part_type_clear", function(_, id)
        local t = typeOf(id)
        if t then
            local fresh = typeDefaults()
            for key in pairs(t) do t[key] = nil end
            for key, value in pairs(fresh) do t[key] = value end
        end
    end)
    local function withType(id, fn)
        local t = typeOf(id)
        if t then fn(t) end
    end
    reg("part_type_shape", function(_, id, shape)
        withType(id, function(t) t.shape = math.floor(shape or 0) end)
    end)
    reg("part_type_sprite", function(E, id, sprite, animat, stretch, random)
        withType(id, function(t)
            t.sprite = resolveSprite(E, sprite)
            t.animat = T(animat)
            t.stretch = T(stretch)
            t.randomStart = random == nil or T(random)
        end)
    end)
    reg("part_type_size", function(_, id, sizeMin, sizeMax, sizeIncr, sizeWiggle)
        withType(id, function(t)
            t.sizeMin, t.sizeMax = sizeMin or 1, sizeMax == nil and sizeMin or sizeMax
            t.sizeIncr, t.sizeWiggle = sizeIncr or 0, sizeWiggle or 0
        end)
    end)
    reg("part_type_scale", function(_, id, xscale, yscale)
        withType(id, function(t) t.xscale, t.yscale = xscale or 1, yscale == nil and xscale or yscale end)
    end)
    reg("part_type_speed", function(_, id, speedMin, speedMax, speedIncr, speedWiggle)
        withType(id, function(t)
            t.speedMin, t.speedMax = speedMin or 0, speedMax == nil and speedMin or speedMax
            t.speedIncr, t.speedWiggle = speedIncr or 0, speedWiggle or 0
        end)
    end)
    reg("part_type_direction", function(_, id, dirMin, dirMax, dirIncr, dirWiggle)
        withType(id, function(t)
            t.dirMin, t.dirMax = dirMin or 0, dirMax == nil and dirMin or dirMax
            t.dirIncr, t.dirWiggle = dirIncr or 0, dirWiggle or 0
        end)
    end)
    reg("part_type_orientation", function(_, id, angMin, angMax, angIncr, angWiggle, relative)
        withType(id, function(t)
            t.oriMin, t.oriMax = angMin or 0, angMax == nil and angMin or angMax
            t.oriIncr, t.oriWiggle = angIncr or 0, angWiggle or 0
            t.oriRelative = T(relative)
        end)
    end)
    reg("part_type_gravity", function(_, id, amount, direction)
        withType(id, function(t) t.gravAmount, t.gravDir = amount or 0, direction or 270 end)
    end)
    local function colour1(_, id, c1)
        withType(id, function(t) t.colourMode, t.c1 = "c1", math.floor(c1 or 16777215) % 16777216 end)
    end
    local function colour2(_, id, c1, c2)
        withType(id, function(t)
            t.colourMode, t.c1, t.c2 = "c2",
                math.floor(c1 or 16777215) % 16777216, math.floor(c2 or 16777215) % 16777216
        end)
    end
    local function colour3(_, id, c1, c2, c3)
        withType(id, function(t)
            t.colourMode, t.c1, t.c2, t.c3 = "c3",
                math.floor(c1 or 16777215) % 16777216,
                math.floor(c2 or 16777215) % 16777216,
                math.floor(c3 or 16777215) % 16777216
        end)
    end
    reg("part_type_colour1", colour1)
    reg("part_type_color1", colour1)
    reg("part_type_colour2", colour2)
    reg("part_type_color2", colour2)
    reg("part_type_colour3", colour3)
    reg("part_type_color3", colour3)
    local function colourMix(_, id, c1, c2)
        withType(id, function(t)
            t.colourMode, t.mixA, t.mixB = "mix",
                math.floor(c1 or 16777215) % 16777216, math.floor(c2 or 16777215) % 16777216
        end)
    end
    reg("part_type_colour_mix", colourMix)
    reg("part_type_color_mix", colourMix)
    reg("part_type_alpha1", function(_, id, a1)
        withType(id, function(t) t.alphaMode, t.a1 = "a1", a1 == nil and 1 or a1 end)
    end)
    reg("part_type_alpha2", function(_, id, a1, a2)
        withType(id, function(t)
            t.alphaMode, t.a1, t.a2 = "a2", a1 == nil and 1 or a1, a2 == nil and 1 or a2
        end)
    end)
    reg("part_type_alpha3", function(_, id, a1, a2, a3)
        withType(id, function(t)
            t.alphaMode, t.a1, t.a2, t.a3 = "a3",
                a1 == nil and 1 or a1, a2 == nil and 1 or a2, a3 == nil and 1 or a3
        end)
    end)
    reg("part_type_blend", function(_, id, additive)
        withType(id, function(t) t.blend = T(additive) end)
    end)
    reg("part_type_life", function(_, id, lifeMin, lifeMax)
        withType(id, function(t)
            t.lifeMin, t.lifeMax = lifeMin or 100, lifeMax == nil and lifeMin or lifeMax
        end)
    end)
    reg("part_type_step", function(_, id, number, stepType)
        withType(id, function(t) t.stepNumber, t.stepType = number or 0, stepType or -1 end)
    end)
    reg("part_type_death", function(_, id, number, deathType)
        withType(id, function(t) t.deathNumber, t.deathType = number or 0, deathType or -1 end)
    end)

    -- Emitters -----------------------------------------------------------
    reg("part_emitter_create", function(_, id)
        local sys = systemOf(id)
        if not sys then
            missingHandle("part_emitter_create", "No particle system " .. tostring(id) .. ".")
            return -1
        end
        local emitter = sys.nextEmitter
        sys.nextEmitter = sys.nextEmitter + 1
        sys.emitters[emitter] = {
            xmin = 0, xmax = 0, ymin = 0, ymax = 0, shape = 0, distr = 0,
            streamType = -1, streamNumber = 0,
        }
        return emitter
    end)
    reg("part_emitter_destroy", function(_, id, emitter)
        local sys = systemOf(id)
        if sys then sys.emitters[math.floor(emitter or -1)] = nil end
    end)
    reg("part_emitter_destroy_all", function(_, id)
        local sys = systemOf(id)
        if sys then sys.emitters = {} end
    end)
    reg("part_emitter_exists", function(_, id, emitter)
        return N(emitterOf(systemOf(id), emitter) ~= nil)
    end)
    reg("part_emitter_clear", function(_, id, emitter)
        local em = emitterOf(systemOf(id), emitter)
        if em then em.streamType, em.streamNumber = -1, 0 end
    end)
    reg("part_emitter_region", function(_, id, emitter, xmin, xmax, ymin, ymax, shape, distr)
        local em = emitterOf(systemOf(id), emitter)
        if not em then
            missingHandle("part_emitter_region", "No emitter " .. tostring(emitter) ..
                " on particle system " .. tostring(id) .. ".")
            return
        end
        xmin, xmax = xmin or 0, xmax or 0
        ymin, ymax = ymin or 0, ymax or 0
        if xmin > xmax then xmin, xmax = xmax, xmin end
        if ymin > ymax then ymin, ymax = ymax, ymin end
        em.xmin, em.xmax, em.ymin, em.ymax = xmin, xmax, ymin, ymax
        em.shape, em.distr = math.floor(shape or 0), math.floor(distr or 0)
    end)
    local function burst(sys, em, typeId, number, colour)
        if not typeOf(typeId) then
            missingHandle("part_emitter_burst", "No particle type " .. tostring(typeId) .. ".")
            return
        end
        for _ = 1, math.max(0, math.floor(number or 0)) do emit(sys, em, typeId, colour) end
    end
    reg("part_emitter_burst", function(_, id, emitter, typeId, number)
        local sys = systemOf(id)
        local em = emitterOf(sys, emitter)
        if not em then
            missingHandle("part_emitter_burst", "No emitter " .. tostring(emitter) ..
                " on particle system " .. tostring(id) .. ".")
            return
        end
        burst(sys, em, typeId, number)
    end)
    reg("part_emitter_stream", function(_, id, emitter, typeId, number)
        local em = emitterOf(systemOf(id), emitter)
        if not em then
            missingHandle("part_emitter_stream", "No emitter " .. tostring(emitter) ..
                " on particle system " .. tostring(id) .. ".")
            return
        end
        em.streamType, em.streamNumber = typeId or -1, number or 0
    end)

    -- Direct creation ----------------------------------------------------
    local function createAt(id, x, y, typeId, number, colour, name)
        local sys = systemOf(id)
        if not sys then
            missingHandle(name, "No particle system " .. tostring(id) .. ".")
            return
        end
        if not typeOf(typeId) then
            missingHandle(name, "No particle type " .. tostring(typeId) .. ".")
            return
        end
        for _ = 1, math.max(0, math.floor(number or 0)) do spawn(sys, typeId, x, y, colour) end
    end
    reg("part_particles_create", function(_, id, x, y, typeId, number)
        createAt(id, x or 0, y or 0, typeId, number, nil, "part_particles_create")
    end)
    local function createColour(_, id, x, y, typeId, colour, number)
        createAt(id, x or 0, y or 0, typeId, number,
            colour == nil and nil or math.floor(colour) % 16777216, "part_particles_create_colour")
    end
    reg("part_particles_create_colour", createColour)
    reg("part_particles_create_color", createColour)
    reg("part_particles_clear", function(_, id)
        local sys = systemOf(id)
        if sys then sys.particles = {} end
    end)
end
