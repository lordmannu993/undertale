-- Builds the merged manifest out of the two converted games.
--
-- Both conversions keep their own ID bands: Undertale stays on its recovered
-- GameMaker 1.4 indices and Undertale Yellow sits at YELLOW_BASE (1,000,000)
-- and above, so the two games' objects, scripts, rooms, paths and assets can
-- share one manifest without a single ID being renumbered. Renumbering would
-- break the numeric room and object references inside Yellow's own code
-- (room_goto(56), instance_create(1074, ...)), which is why the bands are an
-- invariant this module checks instead of assuming.
local Merge = {}

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
        if (undertale.names or {})[name] ~= nil then collisions[#collisions + 1] = name end
    end
    table.sort(collisions)

    local yellowNames = {}
    for category, entries in pairs(yellow.yellow_names or {}) do
        yellowNames[category] = copied(entries)
    end
    -- Yellow's flat name map covers its scripts too, which yellow_names does
    -- not. Undertale's own names win on collision, exactly as the runtime's
    -- constant table already resolves them.
    yellowNames.all = copied(yellow.names)

    local manifest = {
        format = undertale.format or 1,
        game = "merged",
        source = {undertale = undertale.source, yellow = yellow.source},
        yellow_base = base,
        names = undertale.names,
        yellow_names = yellowNames,
        name_collisions_with_undertale = collisions,
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
