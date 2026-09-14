-- GameMaker Studio 2 room layers: the layer records a converted Yellow room
-- carries, the elements on them, and the layer_* builtins that read and mutate
-- both. Undertale rooms have no layers, so every function here is inert for
-- them: layer_get_all() returns an empty array and lookups fail by name.
--
-- Element type constants follow the order the GameMaker manual lists them for
-- layer_get_element_type (background, instance, sprite, tilemap, oldtilemap,
-- particlesystem, legacy tile, sequence). Yellow's own imported GameMaker 1.4
-- tile_layer_* compatibility scripts test elements against the legacy tile
-- value 7; Yellow's rooms are native Studio 2 tilemaps, so those scripts find
-- nothing to change here exactly as they find nothing in GameMaker.
local ELEMENT_UNDEFINED=-1
local ELEMENT_BACKGROUND=1
local ELEMENT_INSTANCE=2
local ELEMENT_SPRITE=3
local ELEMENT_TILEMAP=4
local ELEMENT_OLDTILEMAP=5
local ELEMENT_PARTICLE=6
local ELEMENT_TILE=7
local ELEMENT_SEQUENCE=8

return function(R)
    local B=R.builtins
    local N=R.num
    R.layerElementType={background=ELEMENT_BACKGROUND,instance=ELEMENT_INSTANCE,sprite=ELEMENT_SPRITE,
        tilemap=ELEMENT_TILEMAP,oldtilemap=ELEMENT_OLDTILEMAP,particle=ELEMENT_PARTICLE,
        tile=ELEMENT_TILE,sequence=ELEMENT_SEQUENCE,undefined=ELEMENT_UNDEFINED}
    for name,value in pairs(R.layerElementType) do R.constants["layerelementtype_"..name]=value end

    local function scripts() return R.manifest.scripts or {} end
    local function hasScript(name)
        local names=R.manifest.names or {}
        return scripts()[name]~=nil or (names[name]~=nil and scripts()[names[name]]~=nil)
    end
    local function reg(name,fn)
        if B[name]==nil and not hasScript(name) then B[name]=function(E,...) return fn(E,...) end end
    end
    local function state() return R.roomState end

    --- Resolve a layer id or name to (record, index).
    local function layer(value)
        local st=state()
        if not st or not st.layers then return nil end
        if type(value)=="string" then
            for i,entry in ipairs(st.layers) do
                if not entry.destroyed and entry.name==value then return entry,i end
            end
            return nil
        end
        if type(value)~="number" then return nil end
        local index=math.floor(value)
        local entry=st.layers[index]
        if entry and not entry.destroyed then return entry,index end
        return nil
    end
    local function layerIndex(value) return (layer(value)) end
    local function element(value)
        local st=state()
        if not st or type(value)~="number" then return nil end
        local entry=st.elements and st.elements[math.floor(value)]
        if entry and not entry.destroyed then return entry end
        return nil
    end
    --- The drawable an element owns: a background/sprite element has one, a
    --- tilemap element owns the layer's tile cells.
    local function drawable(value)
        local entry=element(value)
        return entry and entry.drawable
    end
    local function array(values)
        local out=R.defaults(-1)
        for i,value in ipairs(values) do out[i-1]=value end
        return out
    end

    function R:buildLayerElements()
        local st=self.roomState
        if not st or not st.layers then return end
        local elements={}
        st.elements=elements
        local tilemaps={}
        local function add(entry)
            entry.id=#elements+1
            elements[entry.id]=entry
            return entry
        end
        for _,tile in ipairs(st.tiles) do
            local index=tile.layer
            if index and st.layers[index] then
                if tile.background then
                    local map=tilemaps[index]
                    if not map then
                        map=add({type=ELEMENT_TILEMAP,layer=index,tiles={}})
                        tilemaps[index]=map
                    end
                    map.tiles[#map.tiles+1]=tile
                    tile.element=map
                elseif tile.backgroundLayer or tile.colourLayer then
                    tile.element=add({type=ELEMENT_BACKGROUND,layer=index,drawable=tile})
                else
                    tile.element=add({type=ELEMENT_SPRITE,layer=index,drawable=tile})
                end
            end
        end
        for _,inst in ipairs(self.instances) do
            if inst.alive and inst.layer and st.layers[inst.layer] then
                inst.element=add({type=ELEMENT_INSTANCE,layer=inst.layer,instance=inst})
            end
        end
    end

    -- Layer identity and state -------------------------------------------
    reg("layer_get_id",function(_,name) return layerIndex(name) or -1 end)
    reg("layer_exists",function(_,id) return N(layer(id)~=nil) end)
    reg("layer_get_name",function(_,id) local entry=layer(id);return entry and entry.name or "" end)
    reg("layer_get_depth",function(_,id) local entry=layer(id);return entry and entry.depth or 0 end)
    reg("layer_depth",function(_,id,depth) local entry=layer(id);if entry then entry.depth=depth end end)
    reg("layer_set_visible",function(_,id,visible) local entry=layer(id);if entry then entry.visible=R.truth(visible) end end)
    reg("layer_get_visible",function(_,id) local entry=layer(id);return N(entry and entry.visible~=false) end)
    reg("layer_get_all",function()
        local st=state();local out={}
        if st and st.layers then
            for i,entry in ipairs(st.layers) do if not entry.destroyed then out[#out+1]=i end end
        end
        return array(out)
    end)
    for _,name in ipairs({"x","y","hspeed","vspeed"}) do
        -- A layer's position and speed move everything on it: tile cells and
        -- asset sprites are stored relative to their layer, and the renderer
        -- adds the layer offset each frame, so layer_hspeed() scrolls a
        -- background exactly as Studio 2 does.
        reg("layer_"..name,function(_,id,value) local entry=layer(id);if entry then entry[name]=value or 0 end end)
        reg("layer_get_"..name,function(_,id) local entry=layer(id);return entry and (entry[name] or 0) or 0 end)
    end
    reg("layer_get_all_elements",function(_,id)
        local entry,index=layer(id);local out={}
        if entry and state().elements then
            for _,element_entry in ipairs(state().elements) do
                if not element_entry.destroyed and element_entry.layer==index then out[#out+1]=element_entry.id end
            end
        end
        return array(out)
    end)
    reg("layer_get_element_type",function(_,id) local entry=element(id);return entry and entry.type or ELEMENT_UNDEFINED end)
    reg("layer_get_element_layer",function(_,id) local entry=element(id);return entry and entry.layer or -1 end)
    reg("layer_element_move",function(_,id,target)
        local entry=element(id)
        local moved,index=layer(target)
        if not entry or not moved then return end
        entry.layer=index
        if entry.drawable then entry.drawable.layer=index end
        for _,tile in ipairs(entry.tiles or {}) do tile.layer=index end
    end)
    reg("layer_instance_get_instance",function(_,id)
        local entry=element(id)
        return (entry and entry.instance and entry.instance.id) or -4
    end)
    reg("layer_create",function(_,depth,name)
        local st=state()
        if not st then R:unsupported("layer_create","No room is loaded, so there is no layer stack to add to.") end
        st.layers=st.layers or {}
        local index=#st.layers+1
        st.layers[index]={name=name or ("port_layer_"..index),kind="GMRCreatedLayer",depth=depth or 0,
            visible=true,x=0,y=0,hspeed=0,vspeed=0}
        return index
    end)
    reg("layer_destroy",function(_,id)
        local entry,index=layer(id)
        if not entry then return end
        entry.destroyed=true
        -- Studio 2 destroys a layer's particle systems with the layer.
        if R.destroyLayerParticleSystems then R:destroyLayerParticleSystems(index) end
        local st=state()
        local kept={}
        for _,tile in ipairs(st.tiles) do if tile.layer~=index then kept[#kept+1]=tile end end
        st.tiles=kept
        for _,element_entry in ipairs(st.elements or {}) do
            if element_entry.layer==index then element_entry.destroyed=true end
        end
        -- Destroying a layer destroys the instances on it, as Studio 2 does.
        for _,inst in ipairs(R.instances) do
            if inst.alive and inst.layer==index then inst.layer=nil;inst.element=nil;R:destroy(inst) end
        end
        if R.indexAnimated then R:indexAnimated() end
    end)
    reg("layer_destroy_instances",function(_,id)
        local entry,index=layer(id)
        if not entry then return end
        for _,inst in ipairs(R.instances) do
            if inst.layer==index then R:destroy(inst) end
        end
    end)

    -- Background elements -------------------------------------------------
    reg("layer_background_get_id",function(_,id)
        local entry,index=layer(id)
        if not entry or not state().elements then return -1 end
        for _,element_entry in ipairs(state().elements) do
            if not element_entry.destroyed and element_entry.layer==index and element_entry.type==ELEMENT_BACKGROUND then
                return element_entry.id
            end
        end
        return -1
    end)
    reg("layer_background_exists",function(_,id) local entry=element(id);return N(entry~=nil and entry.type==ELEMENT_BACKGROUND) end)
    reg("layer_background_create",function(_,id,sprite,visible)
        local entry,index=layer(id)
        if not entry then return -1 end
        local st=state()
        local tile={sprite=sprite,backgroundLayer=true,depth=entry.depth,visible=visible==nil or R.truth(visible),
            yellow=true,layer=index,x=0,y=0,colour=4294967295,stretch=false,htiled=false,vtiled=false,
            frame=0,speed=0,frames=(R.assets.sprites[sprite] and #R.assets.sprites[sprite].frames) or 0}
        st.tiles[#st.tiles+1]=tile
        st.elements=st.elements or {}
        local element_entry={type=ELEMENT_BACKGROUND,layer=index,drawable=tile}
        element_entry.id=#st.elements+1
        st.elements[element_entry.id]=element_entry
        tile.element=element_entry
        return element_entry.id
    end)
    reg("layer_background_destroy",function(_,id)
        local entry=element(id)
        if not entry or entry.type~=ELEMENT_BACKGROUND then return end
        entry.destroyed=true
        local st=state()
        local kept={}
        for _,tile in ipairs(st.tiles) do if tile~=entry.drawable then kept[#kept+1]=tile end end
        st.tiles=kept
        if R.indexAnimated then R:indexAnimated() end
    end)
    reg("layer_background_change",function(_,id,sprite)
        local tile=drawable(id)
        if not tile then return end
        tile.sprite=sprite
        local asset=R.assets.sprites[sprite]
        tile.frames=asset and #asset.frames or 0
        tile.frame=0
        if R.indexAnimated then R:indexAnimated() end
    end)
    reg("layer_background_get_sprite",function(_,id) local tile=drawable(id);return tile and tile.sprite or -1 end)
    reg("layer_background_get_index",function(_,id) local tile=drawable(id);return tile and tile.sprite or -1 end)
    reg("layer_background_visible",function(_,id,visible) local tile=drawable(id);if tile then tile.visible=R.truth(visible) end end)
    reg("layer_background_get_visible",function(_,id) local tile=drawable(id);return N(tile and tile.visible~=false) end)
    reg("layer_background_alpha",function(_,id,alpha)
        local tile=drawable(id)
        if not tile then return end
        local colour=tile.colour or 4294967295
        tile.colour=math.floor(math.max(0,math.min(1,alpha or 1))*255)*16777216+(colour%16777216)
    end)
    reg("layer_background_get_alpha",function(_,id)
        local tile=drawable(id);return tile and math.floor((tile.colour or 4294967295)/16777216)/255 or 1
    end)
    reg("layer_background_blend",function(_,id,colour)
        local tile=drawable(id)
        if not tile then return end
        local current=tile.colour or 4294967295
        tile.colour=(math.floor(current/16777216)*16777216)+((colour or 16777215)%16777216)
    end)
    reg("layer_background_get_blend",function(_,id) local tile=drawable(id);return tile and (tile.colour or 4294967295)%16777216 or 16777215 end)
    for _,field in ipairs({"htiled","vtiled","stretch"}) do
        reg("layer_background_"..field,function(_,id,value) local tile=drawable(id);if tile then tile[field]=R.truth(value) end end)
        reg("layer_background_get_"..field,function(_,id) local tile=drawable(id);return N(tile and tile[field]) end)
    end
    for _,field in ipairs({"xscale","yscale"}) do
        reg("layer_background_"..field,function(_,id,value)
            local tile=drawable(id);if tile then tile[field]=value end
        end)
        reg("layer_background_get_"..field,function(_,id) local tile=drawable(id);return tile and (tile[field] or 1) or 1 end)
    end
    reg("layer_tilemap_get_id",function(_,id)
        local entry,index=layer(id)
        if not entry or not state().elements then return -1 end
        for _,element_entry in ipairs(state().elements) do
            if not element_entry.destroyed and element_entry.layer==index and element_entry.type==ELEMENT_TILEMAP then
                return element_entry.id
            end
        end
        return -1
    end)
    reg("layer_tilemap_exists",function(_,id) local entry=element(id);return N(entry~=nil and entry.type==ELEMENT_TILEMAP) end)
end
