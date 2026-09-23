-- Frisk-only rendering for the merged build.
--
-- The merged game's player is Frisk everywhere: Yellow's obj_pl keeps its own
-- mechanics (movement, states, masks, collisions all stay Clover's records, so
-- no room geometry or battle math changes), but the sprites its body is drawn
-- with are remapped at draw time to Undertale's. Clover's sprite set supplies
-- what Frisk's set does not have - most visibly the run animation the owner
-- wants on the X button, which stays Clover's spr_pl_run_*.
--
-- This is a rendering remap only, and only for sprites that name a body walk
-- cycle. Undertale has no equivalents for gun poses, goggles, the dance or the
-- lying poses, so those stay Clover and are reported. The table below is the
-- complete set of walk-cycle variants in the pinned conversion (28 sprites:
-- Clover's up-walk has no recolour variants; the other directions carry the
-- route, water, Snowdin and Steamworks-roof ones). A pair that stops
-- resolving is a broken merged manifest and fails the build.
--
-- The run cycle is the other half of the same contract and is asserted rather
-- than left implicit: every run pose the pinned source carries is listed in
-- Frisk.RUN_SPRITES, none of them may appear in the remap table, and one that
-- goes missing stops the build by name instead of silently drawing Frisk's
-- walk pose while the player is sprinting.
local Frisk = {}

Frisk.BODY_SPRITES = {
    "spr_pl_up", "spr_pl_up_water", "spr_pl_up_snowdin", "spr_pl_up_roof",
    "spr_pl_down", "spr_pl_down_geno", "spr_pl_down_water", "spr_pl_down_water_geno",
    "spr_pl_down_snowdin", "spr_pl_down_snowdin_geno", "spr_pl_down_roof", "spr_pl_down_roof_geno",
    "spr_pl_left", "spr_pl_left_geno", "spr_pl_left_water", "spr_pl_left_water_geno",
    "spr_pl_left_snowdin", "spr_pl_left_snowdin_geno", "spr_pl_left_roof", "spr_pl_left_roof_geno",
    "spr_pl_right", "spr_pl_right_geno", "spr_pl_right_water", "spr_pl_right_water_geno",
    "spr_pl_right_snowdin", "spr_pl_right_snowdin_geno", "spr_pl_right_roof", "spr_pl_right_roof_geno",
}

Frisk.DIRECTION_OF = {
    up = "spr_maincharau",
    down = "spr_maincharad",
    left = "spr_maincharal",
    right = "spr_maincharar",
}

-- Clover's run cycle: the poses that stay Clover on purpose, because Frisk's
-- set has no run animation at all. scr_determine_player_sprites picks one of
-- these four families whenever is_sprinting is set - the base cycle, Yellow's
-- genocide-route recolour, the water recolours, and the Snowdin/roof
-- recolours that the base cycle's own name resolution reaches through
-- global.player_sprites. All of them are listed so the swap the owner asked
-- for is checked in both directions: none may enter the walk remap.
Frisk.RUN_SPRITES = {
    "spr_pl_run_up", "spr_pl_run_down", "spr_pl_run_left", "spr_pl_run_right",
    "spr_pl_run_up_geno", "spr_pl_run_down_geno", "spr_pl_run_left_geno", "spr_pl_run_right_geno",
    "spr_pl_run_up_water", "spr_pl_run_down_water", "spr_pl_run_left_water", "spr_pl_run_right_water",
    "spr_pl_run_up_water_geno", "spr_pl_run_down_water_geno",
    "spr_pl_run_left_water_geno", "spr_pl_run_right_water_geno",
    "spr_pl_run_up_snowdin", "spr_pl_run_down_snowdin", "spr_pl_run_left_snowdin",
    "spr_pl_run_right_snowdin",
    "spr_pl_run_up_snowdin_geno", "spr_pl_run_down_snowdin_geno",
    "spr_pl_run_left_snowdin_geno", "spr_pl_run_right_snowdin_geno",
}

-- Poses that deliberately stay Clover because Frisk's set has no equivalent:
-- the revolver poses, the Steamworks goggles, the dance and the lying-down
-- poses. (The run cycle has its own list above.)
Frisk.KEPT_CLOVER = { "spr_pl_dance", "spr_pl_lying",
                      "spr_pl_goggles_up", "spr_pl_goggles_down",
                      "spr_pl_goggles_left", "spr_pl_goggles_right",
                      "spr_pl_goggles_hit", "spr_pl_goggles_shoot",
                      "spr_pl_goggleless_hit", "spr_pl_goggleless_shoot",
                      "spr_pl_down_geno_shoot", "spr_pl_up_geno_shoot",
                      "spr_pl_left_geno_shoot", "spr_pl_right_geno_shoot" }

function Frisk.install(R)
    if R.manifest.game ~= "merged" then return nil end
    local names = R.manifest.names or {}
    local yellowSprites = (R.manifest.yellow_names or {}).sprites or {}

    local remap, missing = {}, {}
    -- Counted, not taken with #remap: the table is keyed by Yellow's sprite
    -- IDs (1000000 + the pinned Asset_Order ID), so it has no array part and
    -- #remap is 0 however many poses are actually remapped.
    local mapped = 0
    for _, cloverName in ipairs(Frisk.BODY_SPRITES) do
        local direction = cloverName:match("^spr_pl_(%a+)")
        local friskName = Frisk.DIRECTION_OF[direction]
        local cloverId, friskId = yellowSprites[cloverName], friskName and names[friskName]
        if not cloverId or not friskId then
            missing[#missing + 1] = cloverId and friskName or cloverName
        else
            remap[cloverId] = friskId
            mapped = mapped + 1
        end
    end
    if #missing > 0 then
        table.sort(missing)
        error(("frisk: player sprite(s) missing from the merged manifest: %s")
            :format(table.concat(missing, ", ")))
    end

    -- Running must show Clover. Each run pose has to be present (a missing one
    -- would draw Frisk's walk pose instead) and outside the walk remap.
    for _, name in ipairs(Frisk.RUN_SPRITES) do
        local id = yellowSprites[name]
        if not id then
            error(("frisk: Yellow's run pose %s is missing from the merged manifest; "
                .. "running would draw Frisk's walk pose instead of Clover's"):format(name))
        end
        if remap[id] then
            error(("frisk: Yellow's run pose %s is remapped to Frisk; "
                .. "Clover's run cycle must stay Clover's"):format(name))
        end
    end

    local kept = {}
    for _, name in ipairs(Frisk.KEPT_CLOVER) do
        local id = yellowSprites[name]
        if not id then
            error(("frisk: Yellow sprite %s is missing from the merged manifest"):format(name))
        end
        if remap[id] then
            error(("frisk: %s is mapped both ways"):format(name))
        end
        kept[#kept + 1] = name
    end
    table.sort(kept)
    -- Undertale has no run cycle. While the shared controller says the live
    -- obj_mainchara is sprinting, the four base walk poses draw Clover's run
    -- cycle. The call is still pixels-only: sprite_index (the mask) is not
    -- changed. Alternate costumes have no Clover run pair and are not invented.
    -- A missing run id keeps the walk sprite; the run poses themselves are
    -- already required to exist above.
    local runOfWalk = {}
    local walkToRun = {
        [names.spr_maincharad] = "spr_pl_run_down",
        [names.spr_maincharau] = "spr_pl_run_up",
        [names.spr_maincharal] = "spr_pl_run_left",
        [names.spr_maincharar] = "spr_pl_run_right",
    }
    for walkId, runName in pairs(walkToRun) do
        local runId = yellowSprites[runName]
        if walkId and runId then runOfWalk[walkId] = runId end
    end
    local mainchara = names.obj_mainchara

    R:warn("frisk-remap",
        ("Frisk-only rendering: %d of Yellow's %d walk poses draw Undertale's Frisk; "
            .. "running swaps to Clover (%d run poses, none remapped). %d poses stay Clover "
            .. "for lack of a Frisk equivalent: %s. Undertale's base walk poses draw that "
            .. "same run cycle while the shared controller is sprinting; alternate costumes "
            .. "with no Clover run pair are not invented.")
            :format(mapped, #Frisk.BODY_SPRITES, #Frisk.RUN_SPRITES, #kept, table.concat(kept, ", ")))

    -- Draw-time hook consumed by port/graphics.lua. Sprite records, masks,
    -- image_number and every gameplay lookup keep resolving to Clover; only
    -- the pixels change. Undertale's own sprite IDs are never in the walk
    -- table. A direct call with no sprinting draw owner is identity for them,
    -- which is what the merged tests pin.
    function R.spriteForDraw(index)
        local movement = R.player and R.player.movement
        local owner = R.drawOwner
        if movement and movement.sprinting and owner and owner.v
            and owner.v.object_index == mainchara then
            local runId = runOfWalk[index]
            if runId then return runId end
        end
        return remap[index] or index
    end
    R.friskRemap = { remap = remap, walk = mapped, run = #Frisk.RUN_SPRITES }
    return remap
end

return Frisk
