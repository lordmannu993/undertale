-- Builds the merged manifest out of the two converted games.
--
-- Both conversions keep their own ID bands: Undertale stays on its recovered
-- GameMaker 1.4 indices and Undertale Yellow sits at YELLOW_BASE (1,000,000)
-- and above, so the two games' objects, scripts, rooms, paths and assets can
-- share one manifest without a single ID being renumbered. Renumbering would
-- break the numeric room and object references inside Yellow's own code
-- (room_goto(56), instance_create(1074, ...)), which is why the bands are an
-- invariant this module checks instead of assuming.
--
-- Some assets carry the same *name* in both games while being different files
-- (10 sprites, 10 objects, 21 sounds and 1 font at the pinned revisions). A
-- flat name table cannot hold both, so this module records every pair as
-- `double_named` -- one authoritative asset per name per world -- and leaves
-- Undertale's value in the flat table for every Lua-side reference that reads
-- it directly. The runtime resolves those names by the caller's world instead
-- (spec §8: select the appropriate asset, never draw both); the list is read
-- off the two manifests, so a new shared name appears here by itself.
local Merge = {}

-- Undertale's flat name map and Yellow's per-category maps, as the collision
-- audit sees them. Yellow's flat map has no objects (its code references
-- objects numerically), which is exactly why the object names have to come
-- from yellow_names.objects.
local DOUBLE_NAMED_CATEGORIES = { "sprites", "objects", "sounds", "fonts", "backgrounds" }

local function proxy(undertale, yellow)
    -- Read-only view: look the key up in Undertale first, then in Yellow. The
    -- runtime only ever indexes these tables, it never iterates them.
    return setmetatable({}, {__index = function(_, key)
        local value = undertale[key]
        if value ~= nil then return value end
        return yellow[key]
    end})
end

local function union(first, second)
    local out, seen = {}, {}
    for _, list in ipairs({first or {}, second or {}}) do
        for _, value in ipairs(list) do
            if not seen[value] then seen[value] = true; out[#out + 1] = value end
        end
    end
    return out
end

local function copied(source)
    local out = {}
    for key, value in pairs(source or {}) do out[key] = value end
    return out
end

function Merge.manifests(undertale, yellow)
    local base = yellow.yellow_base or 1000000
    local collisions = {}
    for name, id in pairs(undertale.names or {}) do
        if id >= base then
            error(("merged manifest: Undertale name %s has ID %d inside Yellow's band (%d+)"):format(name, id, base))
        end
    end
    for name, id in pairs(yellow.names or {}) do
        if id < base then
            error(("merged manifest: Yellow name %s has ID %d below YELLOW_BASE (%d)"):format(name, id, base))
        end
    end

    local yellowNames = {}
    for category, entries in pairs(yellow.yellow_names or {}) do
        yellowNames[category] = copied(entries)
    end
    -- Yellow's flat name map covers its scripts too, which yellow_names does
    -- not. Undertale's own names win on collision, exactly as the runtime's
    -- constant table already resolves them.
    yellowNames.all = copied(yellow.names)

    -- Every asset both games name, with each game's own ID. Undertale's side
    -- is read through its flat map, Yellow's from its own categories.
    local doubleNamed = {}
    for _, category in ipairs(DOUBLE_NAMED_CATEGORIES) do
        for name, yellowId in pairs(yellowNames[category] or {}) do
            local undertaleId = (undertale.names or {})[name]
            if undertaleId ~= nil then
                if type(yellowId) ~= "number" or yellowId < base then
                    error(("merged manifest: Yellow name %s in %s has ID %s below YELLOW_BASE")
                        :format(name, category, tostring(yellowId)))
                end
                doubleNamed[#doubleNamed + 1] = {name = name, category = category,
                    undertale = undertaleId, yellow = yellowId}
            end
        end
    end
    table.sort(doubleNamed, function(a, b)
        if a.category ~= b.category then return a.category < b.category end
        return a.name < b.name
    end)
    for _, entry in ipairs(doubleNamed) do collisions[#collisions + 1] = entry.name end
    table.sort(collisions)

    local manifest = {
        format = undertale.format or 1,
        game = "merged",
        source = {undertale = undertale.source, yellow = yellow.source},
        yellow_base = base,
        names = undertale.names,
        yellow_names = yellowNames,
        name_collisions_with_undertale = collisions,
        double_named = doubleNamed,
        objects = proxy(undertale.objects or {}, yellow.objects or {}),
        scripts = proxy(undertale.scripts or {}, yellow.scripts or {}),
        rooms = proxy(undertale.rooms or {}, yellow.rooms or {}),
        paths = proxy(undertale.paths or {}, yellow.paths or {}),
        path_points = copied(undertale.path_points),
        asset_modules = {},
        room_order = undertale.room_order,
        keys = union(undertale.keys, yellow.keys),
        mouse_events = union(undertale.mouse_events, yellow.mouse_events),
        missing_rooms = union(undertale.missing_rooms, yellow.missing_rooms),
    }
    for index, entry in pairs(yellow.path_points or {}) do
        if manifest.path_points[index] ~= nil then
            error(("merged manifest: path %s exists in both games"):format(tostring(index)))
        end
        manifest.path_points[index] = entry
    end
    for _, list in ipairs({undertale.asset_modules or {}, yellow.asset_modules or {}}) do
        for _, entry in ipairs(list) do manifest.asset_modules[#manifest.asset_modules + 1] = entry end
    end
    return manifest
end

return Merge
