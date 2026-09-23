-- GameMaker Studio 2 facilities this port implements for real: data structures,
-- texture-group and GPU state, the extra drawing calls, cameras and viewports,
-- and the gamepad family (which reports "not connected": this port maps touch
-- and keyboard onto GameMaker's own key events instead).
--
-- Two documented deviations live here, both reported once per run rather than
-- silently:
--   * texture groups do not exist in this port. Assets are single files loaded
--     on demand, so texture_prefetch/texture_flush have nothing to do and
--     asset_get_tags has no tag records in the pinned decompilation to read.
--   * GPU state that has no LÖVE equivalent (alpha test, texel repeat, cull
--     mode, z-test, fog, colour write mask) is recorded and reported. Blend
--     modes DO have one and are applied.
-- Sprite sizes and origins answer in original-canvas pixels through the one
-- accessor both worlds share (port/assetcompat.lua, spec section 12).
local AssetCompat=require("port.assetcompat")
local BLEND={
    bm_normal={"alpha","alphamultiply"},
    bm_add={"add","premultiplied"},
    bm_subtract={"subtract","alphamultiply"},
    bm_max={"max","premultiplied"},
}
-- GMS2 data structure type constants.
local DS_MAP,DS_LIST,DS_STACK,DS_QUEUE,DS_GRID,DS_PRIORITY=1,2,3,4,5,6

return function(R)
    local B=R.builtins
    local N,T=R.num,R.truth
    local function scripts() return R.manifest.scripts or {} end
    local function hasScript(name)
        local names=R.manifest.names or {}
        return scripts()[name]~=nil or (names[name]~=nil and scripts()[names[name]]~=nil)
    end
    local function reg(name,fn)
        if B[name]==nil and not hasScript(name) then B[name]=function(E,...) return fn(E,...) end end
    end
    for name,value in pairs({ds_type_map=DS_MAP,ds_type_list=DS_LIST,ds_type_stack=DS_STACK,
        ds_type_queue=DS_QUEUE,ds_type_grid=DS_GRID,ds_type_priority=DS_PRIORITY,
        bm_normal=0,bm_add=3,bm_subtract=1,bm_max=2,
        gp_face1=32769,gp_face2=32770,gp_face3=32771,gp_face4=32772,
        gp_shoulderl=32773,gp_shoulderlb=32775,gp_shoulderr=32774,gp_shoulderrb=32776,
        gp_select=32777,gp_start=32778,gp_stickl=32779,gp_stickr=32780,
        gp_padu=32781,gp_padd=32782,gp_padl=32783,gp_padr=32784,
        gp_axislh=32785,gp_axislv=32786,gp_axisrh=32787,gp_axisrv=32788,
        mb_none=0,mb_any=-1,mb_left=1,mb_right=2,mb_middle=3}) do
        if R.constants[name]==nil then R.constants[name]=value end
    end

    -- Data structures -----------------------------------------------------
    local ds={entries={},next=1}
    R.ds=ds
    local function create(kind,data)
        local id=ds.next;ds.next=ds.next+1
        ds.entries[id]={kind=kind,data=data}
        return id
    end
    local function entry(id,kind)
        local found=type(id)=="number" and ds.entries[math.floor(id)] or nil
        if not found then
            R:unsupported(kind and (kind.." access") or "ds access",
                "Data structure "..tostring(id).." does not exist. Nothing was silently created.")
        end
        if kind and found.kind~=kind then
            R:unsupported(kind.." access","Data structure "..tostring(id).." is a "..found.kind..", not a "..kind)
        end
        return found
    end
    local function listOf(id) return entry(id,"list").data end
    local function insertAt(list,index,value)
        table.insert(list,math.max(1,math.min(#list+1,math.floor(index)+1)),value)
    end
    reg("ds_exists",function(_,id,kind)
        local found=type(id)=="number" and ds.entries[math.floor(id)] or nil
        if not found then return 0 end
        local kinds={[DS_MAP]="map",[DS_LIST]="list",[DS_GRID]="grid"}
        local wanted=kinds[kind]
        return N(wanted==nil or found.kind==wanted)
    end)
    reg("ds_list_create",function(_,...)
        local list={}
        for _,value in ipairs({...}) do list[#list+1]=value end
        return create("list",list)
    end)
    reg("ds_list_add",function(_,id,...) local list=listOf(id);for _,value in ipairs({...}) do list[#list+1]=value end end)
    reg("ds_list_insert",function(_,id,index,value) insertAt(listOf(id),index,value) end)
    reg("ds_list_replace",function(_,id,index,value)
        local list=listOf(id);local i=math.floor(index)+1
        if i>=1 and i<=#list then list[i]=value end
    end)
    reg("ds_list_delete",function(_,id,index) local list=listOf(id);table.remove(list,math.max(1,math.floor(index)+1)) end)
    reg("ds_list_clear",function(_,id) local list=listOf(id);for i=#list,1,-1 do list[i]=nil end end)
    reg("ds_list_size",function(_,id) return #listOf(id) end)
    reg("ds_list_empty",function(_,id) return N(#listOf(id)==0) end)
    reg("ds_list_find_value",function(_,id,index) local list=listOf(id);local value=list[math.floor(index)+1]
        return value==nil and R.UNDEFINED or value end)
    reg("ds_list_find_index",function(_,id,value)
        local list=listOf(id)
        for i,item in ipairs(list) do if item==value then return i-1 end end
        return -1
    end)
    reg("ds_list_sort",function(_,id,ascending)
        local list=listOf(id)
        table.sort(list,function(a,b)
            if type(a)==type(b) then return T(ascending) and a<b or a>b end
            return tostring(a)<tostring(b)
        end)
    end)
    reg("ds_list_shuffle",function(_,id)
        local list=listOf(id)
        for i=#list,2,-1 do local j=math.random(i);list[i],list[j]=list[j],list[i] end
    end)
    reg("ds_list_copy",function(_,destination,source)
        local target,origin=listOf(destination),listOf(source)
        for i=#target,1,-1 do target[i]=nil end
        for i,value in ipairs(origin) do target[i]=value end
    end)
    reg("ds_list_destroy",function(_,id) entry(id);ds.entries[math.floor(id)]=nil end)
    reg("ds_list_mark_as_list",function(_,id,index)
        R:warn("ds-nested","Nested ds_list/ds_map serialisation markers are ignored: this port writes the nested structure itself.")
    end)
    reg("ds_list_mark_as_map",function(_,id,index)
        R:warn("ds-nested","Nested ds_list/ds_map serialisation markers are ignored: this port writes the nested structure itself.")
    end)

    local function mapOf(id) return entry(id,"map").data end
    local function orderedKeys(map)
        local numbers,strings={},{}
        for key in pairs(map) do
            if type(key)=="number" then numbers[#numbers+1]=key else strings[#strings+1]=key end
        end
        table.sort(numbers);table.sort(strings)
        local out={}
        for _,key in ipairs(numbers) do out[#out+1]=key end
        for _,key in ipairs(strings) do out[#out+1]=key end
        return out
    end
    reg("ds_map_create",function(_,...)
        local map={};local args={...}
        for i=1,#args-1,2 do map[args[i]]=args[i+1] end
        return create("map",map)
    end)
    reg("ds_map_add",function(_,id,key,value) mapOf(id)[key]=value end)
    reg("ds_map_add_list",function(_,id,key,list) mapOf(id)[key]=listOf(list) end)
    reg("ds_map_add_map",function(_,id,key,map) mapOf(id)[key]=mapOf(map) end)
    reg("ds_map_replace",function(_,id,key,value) mapOf(id)[key]=value end)
    reg("ds_map_set",function(_,id,key,value) mapOf(id)[key]=value end)
    reg("ds_map_delete",function(_,id,key) mapOf(id)[key]=nil end)
    reg("ds_map_clear",function(_,id) local map=mapOf(id);for key in pairs(map) do map[key]=nil end end)
    reg("ds_map_destroy",function(_,id) entry(id);ds.entries[math.floor(id)]=nil end)
    reg("ds_map_empty",function(_,id) return N(next(mapOf(id))==nil) end)
    reg("ds_map_exists",function(_,id,key) return N(mapOf(id)[key]~=nil) end)
    reg("ds_map_size",function(_,id) local n=0;for _ in pairs(mapOf(id)) do n=n+1 end;return n end)
    reg("ds_map_find_value",function(_,id,key) local value=mapOf(id)[key];return value==nil and R.UNDEFINED or value end)
    reg("ds_map_find_first",function(_,id) local keys=orderedKeys(mapOf(id));return keys[1]==nil and R.UNDEFINED or keys[1] end)
    reg("ds_map_find_last",function(_,id) local keys=orderedKeys(mapOf(id));return keys[#keys]==nil and R.UNDEFINED or keys[#keys] end)
    reg("ds_map_find_next",function(_,id,key)
        local keys=orderedKeys(mapOf(id))
        for i,entry_key in ipairs(keys) do if entry_key==key then return keys[i+1]==nil and R.UNDEFINED or keys[i+1] end end
        return R.UNDEFINED
    end)
    reg("ds_map_find_previous",function(_,id,key)
        local keys=orderedKeys(mapOf(id))
        for i,entry_key in ipairs(keys) do if entry_key==key then return keys[i-1]==nil and R.UNDEFINED or keys[i-1] end end
        return R.UNDEFINED
    end)
    reg("ds_map_copy",function(_,destination,source)
        local target,origin=mapOf(destination),mapOf(source)
        for key in pairs(target) do target[key]=nil end
        for key,value in pairs(origin) do target[key]=value end
    end)

    local function gridOf(id) return entry(id,"grid").data end
    reg("ds_grid_create",function(_,width,height)
        return create("grid",{width=math.max(0,math.floor(width)),height=math.max(0,math.floor(height)),cells={}})
    end)
    reg("ds_grid_width",function(_,id) return gridOf(id).width end)
    reg("ds_grid_height",function(_,id) return gridOf(id).height end)
    reg("ds_grid_resize",function(_,id,width,height)
        local grid=gridOf(id);grid.width=math.max(0,math.floor(width));grid.height=math.max(0,math.floor(height))
    end)
    reg("ds_grid_clear",function(_,id,value)
        local grid=gridOf(id);grid.cells={}
        if value~=nil and value~=0 then
            for y=0,grid.height-1 do for x=0,grid.width-1 do grid.cells[y*grid.width+x]=value end end
        end
    end)
    reg("ds_grid_set",function(_,id,x,y,value) local grid=gridOf(id);grid.cells[math.floor(y)*grid.width+math.floor(x)]=value end)
    reg("ds_grid_get",function(_,id,x,y)
        local grid=gridOf(id)
        local value=grid.cells[math.floor(y)*grid.width+math.floor(x)]
        return value==nil and 0 or value
    end)
    reg("ds_grid_destroy",function(_,id) entry(id);ds.entries[math.floor(id)]=nil end)

    -- Serialisation. GameMaker's own ds_*_write string format is undocumented,
    -- so this port uses one it documents instead: tagged values, comma
    -- separated, nested. A string this port did not write is a named stop,
    -- never a silently empty structure.
    local encodeValue,encodeList,encodeMap
    local function escape(text) return (tostring(text):gsub("[\\]", "\\\\"):gsub("[,{}:]", "\\%1")) end
    local function encodeKey(value)
        if type(value)=="number" then return "N"..string.format("%.17g",value) end
        return "K"..escape(value)
    end
    local function isList(value)
        if #value>0 then return true end
        for key in pairs(value) do if type(key)~="number" then return false end end
        return true
    end
    function encodeValue(value)
        if type(value)=="number" then return "n"..string.format("%.17g",value) end
        if type(value)=="string" then return "s"..escape(value) end
        if type(value)=="table" then
            if value==R.UNDEFINED then return "u" end
            if isList(value) then return "l"..encodeList(value) end
            return "m"..encodeMap(value)
        end
        return "b"..(T(value) and "1" or "0")
    end
    function encodeList(list)
        local out={}
        for _,value in ipairs(list) do out[#out+1]=encodeValue(value) end
        return "{"..table.concat(out,",").."}"
    end
    function encodeMap(map)
        local out={}
        for _,key in ipairs(orderedKeys(map)) do out[#out+1]=encodeKey(key)..":"..encodeValue(map[key]) end
        return "{"..table.concat(out,",").."}"
    end
    reg("ds_list_write",function(_,id) return encodeList(listOf(id)) end)
    reg("ds_map_write",function(_,id) return encodeMap(mapOf(id)) end)
    -- A reader for the port's own encoding. Values are read back as plain
    -- Lua numbers/strings and nested lists/maps as fresh ds structures.
    local function decode(text,position)
        local tag=text:sub(position,position)
        if tag=="n" then
            local finish=text:find("[,}]",position+1) or (#text+1)
            return tonumber(text:sub(position+1,finish-1)) or 0,finish
        elseif tag=="s" or tag=="K" or tag=="N" then
            local finish=position+1
            while finish<=#text do
                local char=text:sub(finish,finish)
                if char=="\\" then finish=finish+2
                elseif char=="," or char=="}" or char==":" then break
                else finish=finish+1 end
            end
            local raw=text:sub(position+1,finish-1):gsub("\\\\","\1"):gsub("\\([,{}:])","%1"):gsub("\1","\\")
            if tag=="N" then return tonumber(raw) or 0,finish end
            return raw,finish
        elseif tag=="b" then return (text:sub(position+1,position+1)=="1") and 1 or 0,position+2
        elseif tag=="u" then return R.UNDEFINED,position+1
        elseif tag=="{" then
            local list={};local at=position+1
            while text:sub(at,at)~="}" and at<=#text do
                local value
                value,at=decode(text,at)
                list[#list+1]=value
                if text:sub(at,at)=="," then at=at+1 end
            end
            return list,at+1
        end
        R:unsupported("ds read","Not a save string this port wrote: "..tostring(text:sub(1,40)))
    end
    local function decodeMap(text,position)
        local map={};local at=position
        if text:sub(at,at)~="{" then R:unsupported("ds_map_read","Not a map string this port wrote") end
        at=at+1
        while text:sub(at,at)~="}" and at<=#text do
            local key,value
            key,at=decode(text,at)
            if text:sub(at,at)~=":" then R:unsupported("ds_map_read","Malformed map entry") end
            value,at=decode(text,at+1)
            map[key]=value
            if text:sub(at,at)=="," then at=at+1 end
        end
        return map,at+1
    end
    reg("ds_list_read",function(_,id,text)
        local list=listOf(id)
        for i=#list,1,-1 do list[i]=nil end
        local decoded=decode(tostring(text or ""),1)
        if type(decoded)~="table" then R:unsupported("ds_list_read","Not a list string this port wrote") end
        for i,value in ipairs(decoded) do list[i]=value end
    end)
    reg("ds_map_read",function(_,id,text)
        local map=mapOf(id)
        for key in pairs(map) do map[key]=nil end
        local decoded=decodeMap(tostring(text or ""),1)
        for key,value in pairs(decoded) do map[key]=value end
    end)

    -- Texture groups ------------------------------------------------------
    reg("texture_prefetch",function(_,group)
        R:warn("texture-groups","Texture groups ("..tostring(group)..") do not exist in this port: assets are single files loaded on demand.")
    end)
    reg("texture_flush",function(_,group)
        R:warn("texture-groups","Texture groups ("..tostring(group)..") do not exist in this port: assets are single files loaded on demand.")
    end)
    reg("texture_is_ready",function() return 1 end)
    reg("texture_get_texel_width",function() return 1 end)
    reg("texture_get_texel_height",function() return 1 end)
    reg("asset_get_tags",function(_,asset,kind)
        -- The pinned decompilation carries no tag records: Undertale_Yellow.yyp
        -- has no "tags" section and no resource .yy declares one. Returning an
        -- empty list is what GameMaker returns for an untagged asset, and it is
        -- reported so the missing source data is not hidden.
        R:warn("asset-tags","asset_get_tags: the pinned decompilation carries no tag records, so every asset reports no tags.")
        return R.defaults(-1)
    end)

    -- GPU state -----------------------------------------------------------
    local gpu={blendenable=true,alphatest=false,alphatestref=0,texrepeat=false,cullmode=0,
        ztest=false,zwrite=false,fog=false,colorwrite={true,true,true,true}}
    R.gpuState=gpu
    local function report(name,detail)
        R:warn("gpu:"..name,"gpu_"..name.." is recorded but has no LÖVE equivalent here: "..detail)
    end
    reg("gpu_set_blendmode",function(_,mode)
        gpu.blendmode=mode
        local love_blend=BLEND[math.floor(mode or 0)]
        if love_blend and love.graphics and not R.options.headless then
            love.graphics.setBlendMode(love_blend[1],love_blend[2])
        elseif not love_blend then
            report("set_blendmode","unknown blend mode "..tostring(mode))
        end
    end)
    -- GMS2 blend factors: bm_zero=1, bm_one=2, bm_src_colour=3, bm_inv_src_colour=4,
    -- bm_src_alpha=5, bm_inv_src_alpha=6, bm_dest_alpha=7, bm_inv_dest_alpha=8,
    -- bm_dest_colour=9, bm_inv_dest_colour=10.
    local FACTOR_PAIRS={
        ["2:1"]={"replace","alphamultiply"},          -- one / zero
        ["5:6"]={"alpha","alphamultiply"},            -- src_alpha / inv_src_alpha (normal)
        ["2:2"]={"add","alphamultiply"},              -- one / one (additive)
        ["5:2"]={"add","alphamultiply"},              -- src_alpha / one (additive)
        ["3:4"]={"add","premultiplied"},              -- src_colour / inv_src_colour
        ["9:10"]={"multiply","premultiplied"},        -- dest_colour / inv_dest_colour
    }
    reg("gpu_set_blendmode_ext",function(_,source,destination)
        gpu.blendmode_ext={source,destination}
        local pair=FACTOR_PAIRS[tostring(math.floor(source or 0))..":"..tostring(math.floor(destination or 0))]
        if pair and love.graphics and not R.options.headless then
            local ok,result=pcall(love.graphics.setBlendMode,pair[1],pair[2])
            if not ok then R:warn("gpu-blend-ext","Blend factors "..tostring(source).."/"..tostring(destination)..": "..tostring(result)) end
            return
        end
        report("set_blendmode_ext","factor pair "..tostring(source).."/"..tostring(destination).." is not one this port can reproduce; normal blending continues")
        B.gpu_set_blendmode(nil,0)
    end)
    reg("gpu_set_blendenable",function(_,enable)
        gpu.blendenable=T(enable)
        if love.graphics and not R.options.headless then love.graphics.setBlendMode(T(enable) and "alpha" or "replace") end
    end)
    reg("gpu_get_blendenable",function() return N(gpu.blendenable) end)
    reg("gpu_set_alphatestenable",function(_,enable) gpu.alphatest=T(enable);report("set_alphatestenable","alpha testing is always on at the LÖVE shader level") end)
    reg("gpu_get_alphatestenable",function() return N(gpu.alphatest) end)
    reg("gpu_set_alphatestref",function(_,value) gpu.alphatestref=value;report("set_alphatestref","the alpha-test reference value is not applied") end)
    reg("gpu_get_alphatestref",function() return gpu.alphatestref end)
    reg("gpu_set_texrepeat",function(_,enable) gpu.texrepeat=T(enable);report("set_texrepeat","texture repeating follows each background's own htiled/vtiled flags") end)
    reg("gpu_get_texrepeat",function() return N(gpu.texrepeat) end)
    reg("gpu_set_texrepeat_ext",function(_,enable) gpu.texrepeat=T(enable) end)
    reg("gpu_get_texrepeat_ext",function() return N(gpu.texrepeat) end)
    reg("gpu_set_texfilter",function(_,enable)
        gpu.texfilter=T(enable)
        R:warn("gpu:set_texfilter","This port always samples nearest-neighbour; pixel art must not be smoothed.")
    end)
    reg("gpu_set_texfilter_ext",function(_,enable) gpu.texfilter=T(enable) end)
    reg("gpu_set_cullmode",function(_,mode) gpu.cullmode=mode;report("set_cullmode","2D drawing has no culling here") end)
    reg("gpu_set_ztestenable",function(_,enable) gpu.ztest=T(enable);report("set_ztestenable","depth is the room's own depth sorting") end)
    reg("gpu_set_zwriteenable",function(_,enable) gpu.zwrite=T(enable);report("set_zwriteenable","depth is the room's own depth sorting") end)
    reg("gpu_set_colorwriteenable",function(_,r,gg,b,a)
        gpu.colorwrite={T(r),T(gg),T(b),a==nil or T(a)}
        report("set_colorwriteenable","colour channel masking is not applied")
    end)
    reg("gpu_set_fog",function(_,enable,colour,start,finish) gpu.fog=T(enable);report("set_fog","there is no fog pass") end)

    -- Drawing extras ------------------------------------------------------
    local function state() return R.graphicsState or {color=16777215,alpha=1} end
    reg("draw_clear",function(_,colour)
        B.draw_clear_alpha(nil,colour,1)
    end)
    reg("draw_clear_alpha",function(_,colour,alpha)
        if love.graphics and not R.options.headless then
            local c=math.floor(colour or 0)%16777216
            love.graphics.clear((c%256)/255,(math.floor(c/256)%256)/255,(math.floor(c/65536)%256)/255,alpha or 1)
        end
    end)
    reg("draw_get_alpha",function() return state().alpha end)
    reg("draw_get_color",function() return state().color end)
    reg("draw_get_colour",function() return state().color end)
    reg("draw_ellipse_colour",function(_,x1,y1,x2,y2,c1,c2,outline) B.draw_ellipse_color(nil,x1,y1,x2,y2,c1,c2,c1,outline) end)
    -- Scaling and tiling work in canvas pixels (piece 6d): one accessor with
    -- port/graphics.lua's draw_sprite_stretched, so the two worlds stretch and
    -- tile a sprite by the same size.
    reg("draw_sprite_stretched_ext",function(E,index,sub,x,y,w,h,tint,alpha)
        R.drawSpriteStretched(E,index,sub,x,y,w,h,tint,alpha)
    end)
    reg("draw_sprite_tiled",function(E,index,sub,x,y)
        local sprite=R.assets.sprites[index]
        local cw,ch=AssetCompat.width(sprite),AssetCompat.height(sprite)
        if not sprite or cw<=0 or ch<=0 then return end
        local view=R:views()[1] or {x=0,y=0,w=R.vars.room_width,h=R.vars.room_height}
        local startX=x+math.floor((view.x-x)/cw)*cw
        local startY=y+math.floor((view.y-y)/ch)*ch
        for yy=startY,view.y+view.h,ch do
            for xx=startX,view.x+view.w,cw do B.draw_sprite(E,index,sub,xx,yy) end
        end
    end)
    reg("draw_sprite_tiled_ext",function(E,index,sub,x,y,sx,sy,tint,alpha)
        local sprite=R.assets.sprites[index]
        local cw,ch=AssetCompat.width(sprite),AssetCompat.height(sprite)
        if not sprite or cw<=0 or ch<=0 then return end
        local w,h=cw*sx,ch*sy
        local view=R:views()[1] or {x=0,y=0,w=R.vars.room_width,h=R.vars.room_height}
        local startX=x+math.floor((view.x-x)/w)*w
        local startY=y+math.floor((view.y-y)/h)*h
        for yy=startY,view.y+view.h,h do
            for xx=startX,view.x+view.w,w do B.draw_sprite_ext(E,index,sub,xx,yy,sx,sy,0,tint,alpha) end
        end
    end)
    reg("draw_sprite_general",function(E,index,sub,l,t,w,h,x,y,sx,sy,c1,c2,c3,c4,alpha,angle)
        if c1~=c2 or c1~=c3 or c1~=c4 then R:warn("draw_sprite_general","Corner colours fall back to the first colour.") end
        B.draw_sprite_part_ext(E,index,sub,l,t,w,h,x,y,sx,sy,c1,alpha)
    end)
    local primitive=nil
    local PRIMITIVE_KINDS={[0]="trianglelist",[1]="trianglestrip",[2]="linelist",[3]="linestrip",[4]="pointlist"}
    reg("draw_primitive_begin",function(_,kind) primitive={kind=PRIMITIVE_KINDS[math.floor(kind or 0)],points={}} end)
    reg("draw_vertex",function(_,x,y)
        if primitive then primitive.points[#primitive.points+1]={x,y,state().color,state().alpha} end
    end)
    reg("draw_vertex_color",function(_,x,y,colour,alpha)
        if primitive then primitive.points[#primitive.points+1]={x,y,colour,alpha==nil and state().alpha or alpha} end
    end)
    reg("draw_vertex_colour",function(_,x,y,colour,alpha) B.draw_vertex_color(nil,x,y,colour,alpha) end)
    reg("draw_primitive_end",function()
        if not primitive then return end
        local points,kind=primitive.points,(primitive.kind or "trianglelist")
        primitive=nil
        if #points<2 or not love.graphics or R.options.headless then return end
        local vertices={}
        for _,point in ipairs(points) do
            local c=math.floor(point[3] or 16777215)%16777216
            vertices[#vertices+1]={point[1],point[2],0,0,(c%256)/255,(math.floor(c/256)%256)/255,
                (math.floor(c/65536)%256)/255,math.max(0,math.min(1,point[4] or 1))}
        end
        love.graphics.setColor(1,1,1,1)
        local mesh=love.graphics.newMesh(vertices,kind,"stream")
        love.graphics.draw(mesh);mesh:release()
    end)

    -- Shaders and the texture handles they consume.
    -- The pinned decompilation's shaders (sh_palette_swap and friends) are not
    -- converted by this port, and LÖVE cannot run GameMaker's GLSL as-is, so a
    -- shader that would be set here is reported and skipped: the scene keeps its
    -- original colours. sprite_get_texture/texture_get_uvs still return real
    -- values, because in this port every sprite frame really is its own texture
    -- covering the whole 0..1 UV range.
    local shaderHandles={};local nextHandle=1;local activeShader=nil
    R.shaderState={handles=shaderHandles,active=nil}
    local function shaderHandle(shader,name)
        local key=tostring(shader)..":"..tostring(name)
        local handle=shaderHandles[key]
        if not handle then
            handle=nextHandle;nextHandle=nextHandle+1
            shaderHandles[key]={shader=shader,name=name,handle=handle}
        end
        return handle
    end
    local function reportShader(name,verb)
        R:warn("shader:"..tostring(name),"Shaders are not converted by this port: shader "..tostring(name)..
            " is "..verb..", so the scene keeps its original colours.")
    end
    reg("shader_get_uniform",function(_,shader,name) reportShader(shader,"queried for uniform "..tostring(name));return shaderHandle(shader,name) end)
    reg("shader_get_sampler_index",function(_,shader,name) reportShader(shader,"queried for sampler "..tostring(name));return shaderHandle(shader,name) end)
    reg("shader_is_compiled",function(_,shader) reportShader(shader,"checked");return 1 end)
    reg("shader_set",function(_,shader) activeShader=shader;R.shaderState.active=shader;reportShader(shader,"requested") end)
    reg("shader_reset",function() activeShader=nil;R.shaderState.active=nil end)
    reg("shader_current",function() return activeShader or -1 end)
    for _,setter in ipairs({"i","f","i_array","f_array","matrix","matrix_array"}) do
        reg("shader_set_uniform_"..setter,function(_,handle,...)
            for _,entry in pairs(shaderHandles) do
                if entry.handle==handle then entry.value={...};break end
            end
        end)
    end
    reg("texture_set_stage",function(_,stage,texture)
        -- The palette-swap shader flow binds its palette texture here and
        -- draws one sprite through it. Shaders are reported and skipped by
        -- this port, so the binding is recorded and the draw that follows
        -- keeps the scene's original colours, exactly as shader_set does.
        R.shaderState.stages=R.shaderState.stages or {}
        R.shaderState.stages[stage]=texture
        R:warn("shader:stage","texture_set_stage: shaders are not converted by this port; "..
            "the palette binding is recorded and the scene keeps its original colours.")
    end)
    reg("sprite_get_texture",function(_,index,frame)
        local sprite=R.assets.sprites[index]
        if not sprite then return -1 end
        local file=sprite.frames[(math.floor(frame or 0)%#sprite.frames)+1]
        if not file then return -1 end
        local graphics=R.graphicsState
        local image=graphics and graphics.images and graphics.images[file]
        if image==nil and graphics and graphics.image then image=graphics.image(file) end
        if image==nil then
            R:warn("texture:"..tostring(file),"sprite_get_texture: "..tostring(file).." is not loaded in headless mode; the handle is unavailable.")
            return -1
        end
        return image
    end)
    reg("texture_get_uvs",function(_,texture)
        local out=R.defaults(0)
        out[0],out[1],out[2],out[3]=0,0,1,1
        if type(texture)=="userdata" or type(texture)=="table" then
            local ok,width=pcall(function() return texture:getWidth() end)
            local ok2,height=pcall(function() return texture:getHeight() end)
            out[4]=ok and width or 0
            out[5]=ok2 and height or 0
        end
        return out
    end)
    reg("background_get_texture",function(_,index) return B.sprite_get_texture(nil,index,0) end)
    -- Sprite-sheet coordinates (piece 6d, spec section 12). Studio 2 answers
    -- where a frame sits on its texture page: [0..3] the UV rectangle, [4]/[5]
    -- the pixels the asset compiler trimmed from the frame's left/top, [6]/[7]
    -- the fraction of the original width/height kept on the page (GameMaker
    -- manual, sprite_get_uvs). In this port every frame is its own texture, so
    -- the UVs are the whole 0..1 range, and the trim is exactly the crop the
    -- offset recovery pinned: (ox, oy) and exported/canvas size. An uncropped
    -- Yellow frame answers 0, 0, 1, 1. A frame outside the sprite, or a
    -- sprite that does not exist, answers -1 like the other queries here.
    reg("sprite_get_uvs",function(_,index,frame)
        local sprite=R.assets.sprites[index]
        if not sprite or #sprite.frames==0 then return -1 end
        local out=R.defaults(0)
        local cw,ch=AssetCompat.width(sprite),AssetCompat.height(sprite)
        out[0],out[1],out[2],out[3]=0,0,1,1
        out[4],out[5]=sprite.ox or 0,sprite.oy or 0
        out[6]=cw>0 and sprite.width/cw or 1
        out[7]=ch>0 and sprite.height/ch or 1
        return out
    end)

    -- Cameras and viewports ----------------------------------------------
    local cameras={};R.cameras=cameras;local nextCamera=1
    local function camera(id)
        local found=type(id)=="number" and cameras[math.floor(id)] or nil
        if not found then R:unsupported("camera","Camera "..tostring(id).." does not exist.") end
        return found
    end
    local function bind(found)
        -- A camera bound to a viewport drives that viewport's view_* variables,
        -- which is what this runtime's own view code and GameMaker 1.4 read.
        if found.port==nil then return end
        local v=R.vars;local i=found.port
        v.view_xview[i],v.view_yview[i]=found.x,found.y
        v.view_wview[i],v.view_hview[i]=found.width,found.height
        v.view_angle[i]=found.angle or 0
        v.view_hborder[i],v.view_vborder[i]=found.border_x or 32,found.border_y or 32
        v.view_hspeed[i],v.view_vspeed[i]=found.speed_x or -1,found.speed_y or -1
        v.view_object[i]=found.target or -1
    end
    reg("camera_create",function()
        local id=nextCamera;nextCamera=nextCamera+1
        cameras[id]={x=0,y=0,width=640,height=480,angle=0,port=nil,target=-1,speed_x=-1,speed_y=-1,border_x=32,border_y=32}
        return id
    end)
    reg("camera_create_view",function(_,x,y,width,height,angle,target,hspeed,vspeed)
        local id=nextCamera;nextCamera=nextCamera+1
        cameras[id]={x=x or 0,y=y or 0,width=width or 640,height=height or 480,angle=angle or 0,
            port=nil,target=target or -1,speed_x=hspeed or -1,speed_y=vspeed or -1,border_x=32,border_y=32}
        return id
    end)
    reg("camera_destroy",function(_,id) cameras[math.floor(id)]=nil end)
    reg("camera_get_active",function() return -1 end)
    reg("camera_get_default",function() return -1 end)
    -- GameMaker Studio 2 gives every viewport a camera of its own, which is why
    -- Yellow's GameMaker 1.4 compatibility shim (__view_get/__view_set_internal)
    -- reads and writes view_xview and friends through camera_get_view_x. This
    -- port creates that camera on demand, seeded from the viewport's own view_*
    -- variables, so the shim sees the same values it would on a real device.
    reg("view_get_camera",function(_,port)
        local index=math.floor(port or 0)
        R.vars.view_camera=R.vars.view_camera or R.defaults(-1)
        local existing=R.vars.view_camera[index]
        if type(existing)=="number" and existing>=0 and cameras[math.floor(existing)] then return existing end
        local v=R.vars
        local id=B.camera_create_view(nil,v.view_xview[index],v.view_yview[index],
            v.view_wview[index],v.view_hview[index],v.view_angle[index],
            v.view_object[index],v.view_hspeed[index],v.view_vspeed[index])
        cameras[id].border_x=v.view_hborder[index] or 32
        cameras[id].border_y=v.view_vborder[index] or 32
        B.view_set_camera(nil,index,id)
        return id
    end)
    reg("view_set_camera",function(_,port,id)
        R.vars.view_camera=R.vars.view_camera or R.defaults(-1)
        R.vars.view_camera[port]=id
        local found=type(id)=="number" and cameras[math.floor(id)] or nil
        if found then
            if found.port and found.port~=port then found.port=nil end
            found.port=port
            bind(found)
        end
    end)
    for _,field in ipairs({"visible","xport","yport","wport","hport"}) do
        reg("view_get_"..field,function(_,port) return R.vars["view_"..field][port or 0] or 0 end)
        reg("view_set_"..field,function(_,port,value) R.vars["view_"..field][port or 0]=value end)
    end
    local NAME_MAP={x="x",y="y",width="width",height="height",angle="angle",
        border_x="border_x",border_y="border_y",speed_x="speed_x",speed_y="speed_y",target="target"}
    local function cameraField(name,view)
        reg("camera_get_view_"..name,function(_,id)
            local found=camera(id)
            if found.port~=nil then return R.vars[view][found.port] or 0 end
            return found[NAME_MAP[name]] or 0
        end)
        reg("camera_set_view_"..name,function(_,id,value)
            local found=camera(id)
            found[NAME_MAP[name]]=value
            bind(found)
        end)
    end
    for name,view in pairs({x="view_xview",y="view_yview",width="view_wview",height="view_hview",
        angle="view_angle",border_x="view_hborder",border_y="view_vborder",
        speed_x="view_hspeed",speed_y="view_vspeed",target="view_object"}) do
        cameraField(name,view)
    end
    reg("camera_set_view_pos",function(_,id,x,y) local found=camera(id);found.x,found.y=x,y;bind(found) end)
    reg("camera_set_view_size",function(_,id,w,h) local found=camera(id);found.width,found.height=w,h;bind(found) end)
    reg("camera_set_view_speed",function(_,id,hspeed,vspeed) local found=camera(id);found.speed_x,found.speed_y=hspeed,vspeed;bind(found) end)
    reg("camera_set_view_border",function(_,id,hborder,vborder) local found=camera(id);found.border_x,found.border_y=hborder,vborder;bind(found) end)
    reg("camera_set_view_angle",function(_,id,angle) local found=camera(id);found.angle=angle;bind(found) end)
    reg("camera_set_view_target",function(_,id,target) local found=camera(id);found.target=target;bind(found) end)
    reg("camera_apply",function(_,id) local found=camera(id);bind(found) end)

    -- Gamepads: this port maps touch and keyboard onto GameMaker's key events,
    -- so no legacy gamepad is ever connected. Reported once, never silent.
    local function noGamepad(name)
        R:warn("gamepad","gamepad_"..name..": this port has no gamepad device; touch and keyboard feed the same key events instead.")
        return 0
    end
    reg("gamepad_is_connected",function(_,id) return noGamepad("is_connected") end)
    reg("gamepad_button_check",function(_,id,button) return noGamepad("button_check") end)
    reg("gamepad_button_check_pressed",function(_,id,button) return noGamepad("button_check_pressed") end)
    reg("gamepad_button_check_released",function(_,id,button) return noGamepad("button_check_released") end)
    reg("gamepad_button_value",function(_,id,button) return noGamepad("button_value") end)
    reg("gamepad_button_count",function(_,id) return noGamepad("button_count") end)
    reg("gamepad_axis_count",function(_,id) return noGamepad("axis_count") end)
    reg("gamepad_axis_value",function(_,id,axis) return noGamepad("axis_value") end)
    reg("gamepad_get_description",function(_,id) noGamepad("get_description");return "" end)
    reg("gamepad_set_axis_deadzone",function(_,id,value) noGamepad("set_axis_deadzone") end)

    -- Touch and mobile device helpers: this port maps touch and keyboard onto
    -- GameMaker's key events, so device mouse / touch buttons report inactive.
    reg("device_mouse_dbclick_enable",function(_,enable) return 0 end)
    reg("device_mouse_check_button",function(_,device,button) return 0 end)
    reg("device_mouse_check_button_pressed",function(_,device,button) return 0 end)
    reg("device_mouse_check_button_released",function(_,device,button) return 0 end)
    reg("device_mouse_x_to_gui",function(_,device) return -100 end)
    reg("device_mouse_y_to_gui",function(_,device) return -100 end)
    reg("device_mouse_x",function(_,device) return -100 end)
    reg("device_mouse_y",function(_,device) return -100 end)
    reg("device_mouse_raw_x",function(_,device) return -100 end)
    reg("device_mouse_raw_y",function(_,device) return -100 end)
    reg("device_is_keypad_open",function(_) return 0 end)
    reg("device_get_tilt_x",function(_) return 0 end)
    reg("device_get_tilt_y",function(_) return 0 end)
    reg("device_get_tilt_z",function(_) return 0 end)

    -- Miscellaneous Studio 2 helpers --------------------------------------
    reg("object_get_name",function(_,index) local object=R:object(index);return object and object.name or "" end)
    reg("object_get_parent",function(E,index)
        -- Both Yellow call sites (obj_shadow_master, obj_light_master_old)
        -- switch the result against Yellow's own raw numbers (1130 for
        -- obj_npc_base, ...), so a Yellow caller gets the parent back in
        -- Yellow's number space, exactly as its own project numbers it.
        local object=R:object(R:resolveObjectIndex(index,E))
        if not object then
            R:unsupported("object_get_parent","Unknown object ID "..tostring(index))
        end
        local parent=object.parent
        if parent==nil or parent<0 then return -1 end
        local base=R.manifest.yellow_base or 1000000
        if parent>=base and R:callerIsYellow(E) then return parent-base end
        return parent
    end)
    reg("object_is_ancestor",function(_,index,ancestor)
        local object=R:object(index)
        local visited={}
        while object and object.parent and object.parent>=0 and not visited[object.parent] do
            visited[object.parent]=true
            if object.parent==ancestor then return 1 end
            object=R:object(object.parent)
        end
        return 0
    end)
    reg("show_debug_message",function(_,text)
        R:warn("debug-message","show_debug_message: "..tostring(text))
    end)
    reg("alarm_set",function(E,alarm,value)
        local instance=E and E._self
        if instance then instance.v.alarm[math.floor(alarm or 0)]=math.floor(value or -1) end
    end)
    -- place_meeting/instance_place are port/collision.lua's caller-mask test
    -- (piece 6d); instance_place_list collects every instance the same test meets.
    reg("instance_place_list",function(E,x,y,object,list,ordered)
        local found=listOf(list)
        for i=#found,1,-1 do found[i]=nil end
        local self_=E and E._self
        if not self_ or not R:mask(self_) then return 0 end
        local ox,oy=self_.v.x,self_.v.y
        self_.v.x,self_.v.y=x,y
        local precise=R:mask(self_).colkind==0
        for _,inst in ipairs(R:select(object,E)) do
            local other=R:mask(inst)
            if inst~=self_ and other and R:overlap(self_,inst,precise and other.colkind==0) then
                found[#found+1]=inst.id
            end
        end
        self_.v.x,self_.v.y=ox,oy
        return #found
    end)
    reg("position_meeting",function(E,x,y,object) return N(B.collision_point(E,x,y,object,0,0)~=-4) end)
    reg("place_free",function(E,x,y)
        -- GameMaker 1.4's place_free: no SOLID instance blocks the caller's mask at (x,y).
        local self=E and E._self
        if not self then return 1 end
        local origin_x,origin_y=self.v.x,self.v.y
        self.v.x,self.v.y=x,y
        local free=1
        for _,inst in ipairs(R.instances) do
            if inst.alive and inst.active and inst~=self and T(inst.v.solid) and R:overlap(self,inst,false) then
                free=0
                break
            end
        end
        self.v.x,self.v.y=origin_x,origin_y
        return free
    end)
    reg("rectangle_in_rectangle",function(_,x1,y1,x2,y2,x3,y3,x4,y4)
        local l1,t1,r1,b1=math.min(x1,x2),math.min(y1,y2),math.max(x1,x2),math.max(y1,y2)
        local l2,t2,r2,b2=math.min(x3,x4),math.min(y3,y4),math.max(x3,x4),math.max(y3,y4)
        return N(r1>=l2 and l1<=r2 and b1>=t2 and t1<=b2)
    end)
    reg("point_in_rectangle",function(_,x,y,x1,y1,x2,y2)
        return N(x>=math.min(x1,x2) and x<=math.max(x1,x2) and y>=math.min(y1,y2) and y<=math.max(y1,y2))
    end)
    reg("point_in_circle",function(_,px,py,cx,cy,rad)
        local dx,dy=px-cx,py-cy
        return N(dx*dx+dy*dy<=rad*rad)
    end)
    reg("dsin",function(_,value) return math.sin(math.rad(value)) end)
    reg("dcos",function(_,value) return math.cos(math.rad(value)) end)
    reg("frac",function(value) local floor=math.floor(value);return value<0 and (value-floor+1)%1 or value-floor end)
    reg("date_second_span",function(_,first,second) return math.abs(second-first)*86400 end)
    reg("string_insert",function(_,needle,haystack,index)
        local at=math.max(1,math.floor(index or 1))
        local text=tostring(haystack)
        return text:sub(1,at-1)..tostring(needle)..text:sub(at)
    end)
    reg("sprite_get_number",function(_,index) local sprite=R.assets.sprites[index];return sprite and #sprite.frames or 0 end)
    reg("sprite_get_xoffset",function(_,index) return AssetCompat.xoffset(R.assets.sprites[index]) end)
    reg("sprite_get_yoffset",function(_,index) return AssetCompat.yoffset(R.assets.sprites[index]) end)
    reg("sprite_get_width",function(_,index) return AssetCompat.spriteWidth(R,index) end)
    reg("sprite_get_height",function(_,index) return AssetCompat.spriteHeight(R,index) end)
    reg("sprite_duplicate",function(_,index)
        local sprite=R.assets.sprites[index]
        if not sprite then return -1 end
        local graphics=state()
        local id=graphics.nextSprite or 40000
        graphics.nextSprite=id+1
        local copy={}
        for key,value in pairs(sprite) do copy[key]=value end
        copy.name=sprite.name.."_copy"..id
        R.assets.sprites[id]=copy
        return id
    end)
    reg("sprite_assign",function(_,destination,source)
        local sprite=R.assets.sprites[source]
        if not sprite then return end
        R.assets.sprites[destination]=sprite
    end)
end
