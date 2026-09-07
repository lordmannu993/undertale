-- GameMaker 1.x execution model for generated Lua. This is deliberately an
-- explicit compatibility layer: missing assets/functions produce diagnostics.
local Runtime = {}
Runtime.__index = Runtime
Runtime.SWITCH_BREAK = {}
Runtime.bit = require("bit")
local atan2 = math.atan2
local unpack = unpack

function Runtime.num(b) return b and 1 or 0 end
function Runtime.truth(v)
    if type(v)=="number" then return v>0.5 end
    return v~=nil and v~=false
end
function Runtime.add(a,b)
    if type(a)=="string" and type(b)=="string" then return a..b end
    if type(a)~="number" or type(b)~="number" then error("GML + expects two numbers or two strings",2) end
    return a+b
end
function Runtime.div(a,b) local n=a/b;return n<0 and math.ceil(n) or math.floor(n) end
function Runtime.mod(a,b) return a-Runtime.div(a,b)*b end
function Runtime.count(n) return math.max(0,math.floor(n)) end
function Runtime.ternary(c,a,b) if Runtime.truth(c) then return a() else return b() end end
local function defaults(value) return setmetatable({}, {__index=function() return value end}) end
Runtime.defaults=defaults
local function copy(t) local r={};for k,v in pairs(t) do r[k]=v end;return r end
local function deepCopy(t)
    if type(t)~="table" then return t end
    local r={};for k,v in pairs(t) do r[k]=deepCopy(v) end
    return setmetatable(r,getmetatable(t))
end

function Runtime.new(manifest,input,options)
    local self=setmetatable({manifest=manifest,input=input,options=options or {},global=defaults(0),
        vars={},constants=copy(manifest.names),instances={},byId={},objects={},scripts={},rooms={},
        assets={sprites={},backgrounds={},sounds={},fonts={}},builtins={},warnings={},warningList={},
        storedRooms={},roomPersistence={},nextId=200000,frame=0,budget=0,globalNames={},currentEvent=nil,
        pathData={},roomState=nil},Runtime)
    for _,entry in ipairs(manifest.asset_modules or {}) do
        for id,asset in pairs(require(entry.module)) do self.assets[entry.kind][id]=deepCopy(asset) end
    end
    -- Recovered movement-path geometry, keyed by the original numeric path ID.
    for index,entry in pairs(manifest.path_points or {}) do self.pathData[index]=deepCopy(entry) end
    local constants={self=-1,other=-2,all=-3,noone=-4,pi=math.pi,os_windows=0,os_android=5,
        c_white=16777215,c_black=0,c_red=255,c_lime=65280,c_blue=16711680,c_yellow=65535,
        c_gray=8421504,c_silver=12632256,c_aqua=16776960,c_fuchsia=16711935,
        vk_nokey=0,vk_anykey=1,vk_enter=13,vk_shift=16,vk_control=17,vk_escape=27,vk_space=32,
        vk_left=37,vk_up=38,vk_right=39,vk_down=40,vk_backspace=8,
        fa_left=0,fa_center=1,fa_right=2,fa_top=0,fa_middle=1,fa_bottom=2,
        path_action_stop=0,path_action_restart=1,path_action_continue=2,path_action_reverse=3,
        ev_create=0,ev_destroy=1,ev_alarm=2,ev_step=3,ev_collision=4,ev_keyboard=5,
        ev_other=7,ev_draw=8,ev_keypress=9,ev_keyrelease=10,ev_step_normal=0,ev_step_begin=1,ev_step_end=2}
    constants["true"],constants["false"]=1,0
    for k,v in pairs(constants) do self.constants[k]=v end
    self.constants.working_directory="";self.constants.program_directory=""
    self.vars.mouse_x=0;self.vars.mouse_y=0
    self.vars.os_type=(love and love.system and love.system.getOS()=="Android") and 5 or 0
    self.vars.room_speed=30; self.vars.view_current=0; self.vars.current_time=0
    self.vars.room=-1;self.vars.room_width=640;self.vars.room_height=480
    self.vars.application_surface=-1;self.vars.transition_kind=0
    for _,name in ipairs({"view_xview","view_yview","view_wview","view_hview","view_xport","view_yport","view_wport","view_hport","view_visible","view_object","view_hborder","view_vborder","view_hspeed","view_vspeed","view_angle",
        "background_index","background_visible","background_foreground","background_x","background_y","background_hspeed","background_vspeed",
        "background_htiled","background_vtiled","background_xscale","background_yscale","background_alpha","background_blend"}) do
        self.vars[name]=defaults(0)
    end
    for i=0,7 do self.vars.view_object[i]=-1;self.vars.view_hspeed[i]=-1;self.vars.view_vspeed[i]=-1 end
    self.vars.background_width=setmetatable({}, {__index=function(_,i) local b=self.assets.backgrounds[self.vars.background_index[i]];return b and b.width or 0 end})
    self.vars.background_height=setmetatable({}, {__index=function(_,i) local b=self.assets.backgrounds[self.vars.background_index[i]];return b and b.height or 0 end})
    local now=os.date("*t")
    self.vars.current_year=now.year;self.vars.current_month=now.month;self.vars.current_day=now.day
    self.vars.current_weekday=now.wday;self.vars.current_hour=now.hour;self.vars.current_minute=now.min;self.vars.current_second=now.sec
    require("port.builtins")(self)
    require("port.storage")(self)
    require("port.audio")(self)
    require("port.graphics").install(self)
    require("port.collision").install(self)
    return self
end

function Runtime:warn(key,message)
    if self.warnings[key] then return end
    self.warnings[key]=true;self.warningList[#self.warningList+1]=message
    print("[port warning] "..message)
    if self.onWarning then self.onWarning(message) end
end
function Runtime:unsupported(name,detail)
    error("Compatibility stop: "..name.."\n"..(detail or "Not implemented by this runtime."),2)
end
function Runtime:guard()
    self.budget=self.budget+1
    if self.budget>1000000 then error("GML iteration budget exceeded; refusing to freeze the device.",2) end
end

function Runtime:object(id)
    if self.objects[id] then return self.objects[id] end
    local path=self.manifest.objects[id]
    if not path then return nil end
    local object=require(path);self.objects[id]=object;return object
end
function Runtime:isA(instance,selector)
    local index=instance.v.object_index
    local visited={}
    while index and index>=0 and not visited[index] do
        if index==selector then return true end
        visited[index]=true
        local def=self:object(index)
        index=def and def.parent
    end
    return false
end
function Runtime:select(selector,E)
    if type(selector)=="table" and rawget(selector,"_instance")==true then return selector.alive and selector.active and {selector} or {} end
    if selector==-1 then return E and E._self and E._self.alive and {E._self} or {} end
    if selector==-2 then return E and E._other and E._other.alive and {E._other} or {} end
    if selector==-4 or selector==nil then return {} end
    local found=self.byId[selector]
    if found then return found.alive and found.active and {found} or {} end
    if selector~=-3 and not self.manifest.objects[selector] then
        if type(selector)=="number" and selector>=0 and selector<100000 then
            self:warn("object:"..selector,"Unresolved original object ID "..selector.." (see conversion-report.json). Queries cannot match it.")
        end
        return {}
    end
    local result={}
    for _,inst in ipairs(self.instances) do
        if inst.alive and inst.active and (selector==-3 or self:isA(inst,selector)) then result[#result+1]=inst end
    end
    return result
end

function Runtime:instanceGet(inst,key)
    local v=inst.v
    if key=="id" then return inst.id end
    if key=="speed" then return v.speed end
    if key=="direction" then return v.direction end
    if key=="image_number" then local s=self.assets.sprites[v.sprite_index];return s and #s.frames or 0 end
    if key=="sprite_width" or key=="sprite_height" or key=="sprite_xoffset" or key=="sprite_yoffset" then
        local s=self.assets.sprites[v.sprite_index]
        if not s then return 0 end
        if key=="sprite_width" then return s.width*math.abs(v.image_xscale) end
        if key=="sprite_height" then return s.height*math.abs(v.image_yscale) end
        return key=="sprite_xoffset" and s.xorig or s.yorigin
    end
    if key:sub(1,5)=="bbox_" then
        local l,t,r,b=self:bbox(inst)
        return key=="bbox_left" and l or key=="bbox_top" and t or key=="bbox_right" and r or b
    end
    return v[key] or 0
end
function Runtime:instanceSet(inst,key,val)
    local v=inst.v
    if key=="speed" then
        local dir=math.rad(self:instanceGet(inst,"direction"))
        v.speed=val;v.hspeed=math.cos(dir)*val;v.vspeed=-math.sin(dir)*val
    elseif key=="hspeed" or key=="vspeed" then
        v[key]=val;v.speed=math.sqrt(v.hspeed*v.hspeed+v.vspeed*v.vspeed)
        if v.speed~=0 then v.direction=(-math.deg(atan2(v.vspeed,v.hspeed)))%360 end
    elseif key=="direction" then
        local speed=self:instanceGet(inst,"speed")
        v.direction=val%360;v.hspeed=math.cos(math.rad(val))*speed;v.vspeed=-math.sin(math.rad(val))*speed
    elseif key=="id" or key=="object_index" then
        self:warn("readonly:"..key,"Ignored assignment to read-only instance field "..key)
    else v[key]=val end
end

function Runtime:scope(instance,other,args,locals)
    local R=self
    local env={_scope=true,_self=instance,_other=other,_args=args or {},_locals=locals or {}}
    return setmetatable(env,{
        __index=function(E,key)
            if E._locals[key]~=nil then return E._locals[key] end
            if key=="global" then return R.global end
            if key=="self" then return E._self and E._self.id or -4 end
            if key=="other" then return E._other and E._other.id or -4 end
            if key=="argument_count" then return #E._args end
            if key=="argument" then local a=defaults(0);for i,v in ipairs(E._args) do a[i-1]=v end;return a end
            local arg=key:match("^argument(%d+)$")
            if arg then return E._args[tonumber(arg)+1] or 0 end
            if R.globalNames[key] then return R.global[key] end
            if R.constants[key]~=nil then return R.constants[key] end
            if key=="keyboard_lastkey" then return R.input.lastkey end
            if key=="instance_count" then return #R:select(-3,E) end
            if R.vars[key]~=nil then return R.vars[key] end
            if E._self then return R:instanceGet(E._self,key) end
            return 0
        end,
        __newindex=function(E,key,val)
            if E._locals[key]~=nil then E._locals[key]=val
            elseif R.globalNames[key] then R.global[key]=val
            elseif R.vars[key]~=nil then
                if key=="room" then R:gotoRoom(val) else R.vars[key]=val end
            elseif E._self then R:instanceSet(E._self,key,val)
            else R.vars[key]=val end
        end,
    })
end
function Runtime:withScope(inst,E) return self:scope(inst,E._self,E._args,E._locals) end
function Runtime:declare(E,name,value,global)
    if global then self.globalNames[name]=true;self.global[name]=value else E._locals[name]=value end
end
function Runtime:get(owner,key,E)
    if type(owner)=="table" then
        if rawget(owner,"_instance")==true then return self:instanceGet(owner,key) end
        return owner[key] or 0
    end
    local instances=self:select(owner,E)
    if instances[1] then return self:instanceGet(instances[1],key) end
    return 0 -- original project explicitly disables uninitialized-variable errors
end
function Runtime:set(owner,key,val,E)
    if type(owner)=="table" then
        if rawget(owner,"_instance")==true then self:instanceSet(owner,key,val) else owner[key]=val end
    else
        for _,inst in ipairs(self:select(owner,E)) do self:instanceSet(inst,key,val) end
    end
    return val
end
function Runtime:array(owner,key,E)
    local a=self:get(owner,key,E)
    if type(a)~="table" then a=defaults(0);self:set(owner,key,a,E) end
    return a
end
function Runtime:arrayRow(owner,key,row,E)
    local a=self:array(owner,key,E)
    if type(a[row])~="table" then a[row]=defaults(0) end
    return a[row]
end
function Runtime:increment(owner,key,amount,post,E)
    local old=self:get(owner,key,E);self:set(owner,key,old+amount,E)
    return post and old or old+amount
end

function Runtime:call(name,E,...)
    local builtin=self.builtins[name]
    if builtin then return builtin(E,...) or 0 end
    local index=self.manifest.names[name]
    if index and self.manifest.scripts[index] then return self:script(index,E,...) end
    self:unsupported(name,"Unknown GML function. Nothing was silently stubbed.")
end
function Runtime:script(index,E,...)
    local path=self.manifest.scripts[index]
    if not path then self:unsupported("script_execute", "Missing original script ID "..tostring(index)) end
    local fn=self.scripts[index] or require(path);self.scripts[index]=fn
    return fn(self,self:scope(E._self,E._other,{...})) or 0
end
function Runtime:dispatchSwitch(E,value,labels,handlers,default)
    local index=labels[value] or default
    if not index then return 0 end
    for i=index,#handlers do
        local result=handlers[i](self,E)
        if result==self.SWITCH_BREAK then return 0 end
        if result~=nil then return result end
    end
    return 0
end

function Runtime:findEvent(index,key)
    local visited={}
    while index and index>=0 and not visited[index] do
        visited[index]=true
        local object=self:object(index)
        if not object then return nil end
        if object.events[key] then return object.events[key],index end
        index=object.parent
    end
end
function Runtime:event(inst,kind,number,other,from)
    if not inst.alive then return end
    local key=tostring(kind)..":"..tostring(number)
    local fn,owner=self:findEvent(from or inst.v.object_index,key)
    if not fn then return false end
    local prior=self.currentEvent
    self.currentEvent={instance=inst,other=other,kind=kind,number=number,owner=owner}
    local ok,result=pcall(fn,self,self:scope(inst,other))
    self.currentEvent=prior
    if not ok then
        local object=self:object(inst.v.object_index)
        error((object and object.name or tostring(inst.v.object_index)).." ["..key.."] in "..(self.roomState and self.roomState.name or "startup").."\n"..tostring(result),0)
    end
    return true
end
function Runtime:create(objectIndex,x,y,spec,defer)
    local object=self:object(objectIndex)
    if not object then self:unsupported("instance_create","Missing original object ID "..tostring(objectIndex)) end
    spec=spec or {}
    local id=spec.id or self.nextId
    if not spec.id then self.nextId=self.nextId+1 end
    local instance={_instance=true,id=id,alive=true,active=true,
        v={object_index=objectIndex,x=x,y=y,xprevious=x,yprevious=y,xstart=x,ystart=y,
           sprite_index=object.sprite,mask_index=object.mask,visible=object.visible,solid=object.solid,
           persistent=object.persistent,depth=object.depth,image_index=0,image_speed=1,
           image_xscale=spec.scaleX or 1,image_yscale=spec.scaleY or 1,
           image_angle=spec.rotation or 0,image_blend=(spec.colour or 16777215)%16777216,image_alpha=1,
           hspeed=0,vspeed=0,speed=0,direction=0,friction=0,gravity=0,gravity_direction=270,
           alarm=defaults(-1),path_index=-1,path_position=0,path_positionprevious=0,
           path_speed=0,path_scale=1,path_orientation=0,path_endaction=0}}
    self.instances[#self.instances+1]=instance;self.byId[id]=instance
    if not defer then self:event(instance,0,0) end
    return instance
end
function Runtime:destroy(inst,runEvent)
    if not inst or not inst.alive or inst.destroying then return end
    inst.destroying=true
    if runEvent~=false then self:event(inst,1,0) end
    inst.alive=false;inst.destroying=false
end
function Runtime:compact()
    local alive={}
    for _,i in ipairs(self.instances) do
        if i.alive then alive[#alive+1]=i else if self.byId[i.id]==i then self.byId[i.id]=nil end end
    end
    self.instances=alive
end

function Runtime:gotoRoom(index)
    if not self.manifest.rooms[index] then
        local name=(self.manifest.missing_rooms or {})[index]
        self:unsupported("room_goto","Missing original room "..tostring(index)..(name and " ("..name..")" or "")..". Its source data is not supplied; room IDs must not be compacted around this gap.")
    end
    self.pendingRoom=index
end
function Runtime:roomData(index)
    if not self.rooms[index] then self.rooms[index]=require(self.manifest.rooms[index]) end
    return self.rooms[index]
end
function Runtime:loadRoom(index,first)
    self.pendingRoom=nil
    local persistent={}
    local old=copy(self.instances)
    for _,i in ipairs(old) do if i.alive then self:event(i,7,5) end end
    if self.roomState and Runtime.truth(self.vars.room_persistent) then
        local stored={}
        for _,i in ipairs(self.instances) do
            if i.alive and not Runtime.truth(i.v.persistent) then stored[#stored+1]=i end
        end
        local savedVars={}
        for name,v in pairs(self.vars) do
            if name:sub(1,5)=="view_" or (name:sub(1,11)=="background_" and name~="background_width" and name~="background_height") then savedVars[name]=deepCopy(v) end
        end
        savedVars.room_speed=self.vars.room_speed
        self.storedRooms[self.vars.room]={instances=stored,tiles=self.roomState.tiles,backgrounds=self.roomState.backgrounds,
            tileOffsets=self.roomState.tileOffsets,hiddenLayers=self.roomState.hiddenLayers,vars=savedVars}
    elseif self.roomState then
        self.storedRooms[self.vars.room]=nil
    end
    if self.roomState then self.roomPersistence[self.vars.room]=self.vars.room_persistent end
    for _,i in ipairs(self.instances) do if i.alive and Runtime.truth(i.v.persistent) then persistent[#persistent+1]=i end end
    self.instances=persistent;self.byId={}
    for _,i in ipairs(persistent) do self.byId[i.id]=i end
    local room=self:roomData(index)
    self.roomState={name=room.name,backdrop=room.port_backdrop,tiles={},backgrounds={},tileOffsets={},hiddenLayers={}}
    self.vars.room=index;self.vars.room_width=room.width;self.vars.room_height=room.height
    self.vars.room_speed=room.speed;self.vars.room_persistent=self.roomPersistence[index]~=nil and self.roomPersistence[index] or room.persistent
    self.vars.background_color=room.colour;self.vars.background_showcolor=room.showcolour
    self.vars.view_enabled=room.enableViews;self.vars.view_current=0
    for i,view in ipairs(room.views) do
        for _,field in ipairs({"xview","yview","wview","hview","xport","yport","wport","hport","visible"}) do
            self.vars["view_"..field][i-1]=view[field] or 0
        end
        self.vars.view_object[i-1]=self.manifest.names[view.objName] or -1
        self.vars.view_hborder[i-1]=view.hborder or 32;self.vars.view_vborder[i-1]=view.vborder or 32
        self.vars.view_hspeed[i-1]=view.hspeed or -1;self.vars.view_vspeed[i-1]=view.vspeed or -1
        self.vars.view_angle[i-1]=0
    end
    for i,b in ipairs(room.backgrounds) do
        local background=copy(b);self.roomState.backgrounds[i]=background
        for _,field in ipairs({"index","visible","foreground","x","y","hspeed","vspeed","htiled","vtiled"}) do
            self.vars["background_"..field][i-1]=b[field] or 0
        end
        self.vars.background_xscale[i-1]=1;self.vars.background_yscale[i-1]=1
        self.vars.background_alpha[i-1]=1;self.vars.background_blend[i-1]=16777215
    end
    for _,tile in ipairs(room.tiles) do self.roomState.tiles[#self.roomState.tiles+1]=copy(tile) end
    local stored=self.storedRooms[index]
    local new={}
    if stored then
        for _,i in ipairs(stored.instances) do if not self.byId[i.id] then self.instances[#self.instances+1]=i;self.byId[i.id]=i end end
        self.roomState.tiles=stored.tiles;self.roomState.backgrounds=stored.backgrounds
        self.roomState.tileOffsets=stored.tileOffsets;self.roomState.hiddenLayers=stored.hiddenLayers
        for name,v in pairs(stored.vars) do self.vars[name]=deepCopy(v) end
    else
        -- Make every editor instance addressable before any Create code runs.
        for _,spec in ipairs(room.instances) do
            if not self.byId[spec.id] then new[#new+1]={self:create(spec.object,spec.x,spec.y,spec,true),spec} end
        end
        for _,pair in ipairs(new) do
            local inst,spec=pair[1],pair[2]
            self:event(inst,0,0)
            if inst.alive and spec.create then spec.create(self,self:scope(inst)) end
        end
    end
    if first then for _,i in ipairs(copy(self.instances)) do if i.alive then self:event(i,7,2) end end end
    if not stored and room.create then room.create(self,self:scope(nil)) end
    for _,i in ipairs(copy(self.instances)) do if i.alive then self:event(i,7,4) end end
    self:compact()
    if self.trimGraphicsCache then self:trimGraphicsCache() end
    if self.trimAudioCache then self:trimAudioCache() end
    if self.onRoom then self.onRoom(room) end
end
function Runtime:start()
    self.budget=0
    self:loadRoom(self.manifest.room_order[1],true)
    self:applyTransitions()
end
function Runtime:applyTransitions()
    local count=0
    while self.pendingRoom do
        count=count+1
        if count>32 then error("Cyclic room transitions during startup",0) end
        self:loadRoom(self.pendingRoom,false)
    end
end

function Runtime:step()
    self.budget=0;self.frame=self.frame+1
    if self.frame%30==0 then
        local now=os.date("*t")
        self.vars.current_year=now.year;self.vars.current_month=now.month;self.vars.current_day=now.day
        self.vars.current_weekday=now.wday;self.vars.current_hour=now.hour;self.vars.current_minute=now.min;self.vars.current_second=now.sec
    end
    self.vars.current_time=self.vars.current_time+1000/self.vars.room_speed
    local snapshot=copy(self.instances)
    for _,i in ipairs(snapshot) do if i.alive and i.active then i.v.xprevious=i.v.x;i.v.yprevious=i.v.y end end
    local function each(kind,number)
        for _,i in ipairs(snapshot) do if i.alive and i.active then self:event(i,kind,number) end end
    end
    each(3,1) -- Begin Step
    for _,i in ipairs(snapshot) do
        if i.alive and i.active then
            for alarm=0,11 do
                local value=i.v.alarm[alarm]
                if value>=0 then
                    value=value-1;i.v.alarm[alarm]=value
                    if value==0 then self:event(i,2,alarm) end
                end
            end
        end
    end
    for _,key in ipairs(self.manifest.keys) do
        if self.input:check(key) then each(5,key) end
        if self.input:check(key,"pressed") then each(9,key) end
        if self.input:check(key,"released") then each(10,key) end
    end
    -- The two source mouse handlers are global Left Down (50) and Right
    -- Pressed (54). Touching the game image aims; extra keys supply both buttons.
    for button=1,3 do
        if self.input:checkMouse(button) then each(6,49+button) end
        if self.input:checkMouse(button,"pressed") then each(6,52+button) end
        if self.input:checkMouse(button,"released") then each(6,55+button) end
    end
    each(3,0)
    for _,i in ipairs(snapshot) do
        if i.alive and i.active then
            local v=i.v
            if v.friction~=0 then
                local speed=self:instanceGet(i,"speed")
                self:instanceSet(i,"speed",(speed<0 and -1 or 1)*math.max(0,math.abs(speed)-v.friction))
            end
            if v.gravity~=0 then
                local a=math.rad(v.gravity_direction)
                v.hspeed=v.hspeed+math.cos(a)*v.gravity;v.vspeed=v.vspeed-math.sin(a)*v.gravity
                self:instanceSet(i,"hspeed",v.hspeed)
            end
            if v.path_index>=0 then self:advancePath(i) else v.x=v.x+v.hspeed;v.y=v.y+v.vspeed end
        end
    end
    self:collisionEvents(snapshot)
    for _,i in ipairs(snapshot) do
        if i.alive and i.active then
            local l,t,r,b=self:bbox(i)
            if r<0 or b<0 or l>=self.vars.room_width or t>=self.vars.room_height then self:event(i,7,0) end
            if l<0 or t<0 or r>=self.vars.room_width or b>=self.vars.room_height then self:event(i,7,1) end
        end
    end
    each(3,2) -- End Step
    self:compact()
    self:applyTransitions()
    self:updateViews()
end

function Runtime:updateViews()
    local v=self.vars
    local function follow(position,size,border,target,speed)
        border=math.min(border,size/2)
        local desired=position
        if target<position+border then desired=target-border
        elseif target>position+size-border then desired=target-size+border end
        if speed<0 then return desired end
        return position+math.max(-speed,math.min(speed,desired-position))
    end
    for i=0,7 do
        local target=self:select(v.view_object[i])[1]
        if target and self.truth(v.view_visible[i]) then
            v.view_xview[i]=follow(v.view_xview[i],v.view_wview[i],v.view_hborder[i],target.v.x,v.view_hspeed[i])
            v.view_yview[i]=follow(v.view_yview[i],v.view_hview[i],v.view_vborder[i],target.v.y,v.view_vspeed[i])
        end
    end
end

function Runtime:finishFrame()
    -- Animation-end follows draw; events may replace the sprite mid-animation.
    for _,i in ipairs(copy(self.instances)) do
        if i.alive and i.active then
            local v=i.v;local sprite=self.assets.sprites[v.sprite_index]
            if sprite and #sprite.frames>0 and v.image_speed~=0 then
                v.image_index=v.image_index+v.image_speed
                if v.image_index>=#sprite.frames or v.image_index<0 then
                    v.image_index=v.image_index%#sprite.frames;self:event(i,7,7)
                end
            end
        end
    end
    for i=0,7 do
        self.vars.background_x[i]=self.vars.background_x[i]+self.vars.background_hspeed[i]
        self.vars.background_y[i]=self.vars.background_y[i]+self.vars.background_vspeed[i]
    end
    if self.updateAudio then self:updateAudio(1/self.vars.room_speed) end
    self:compact();self:applyTransitions()
end

-- GameMaker path playback. A path is the polyline through its authored points
-- (kind 0) or a Catmull-Rom spline sampled `precision` times per segment
-- (kind 1). An instance walks it at `path_speed` pixels per step; `path_position`
-- is the fraction of the total length covered, so the same number means the same
-- place on the path for every speed.
local function catmull(p0,p1,p2,p3,t)
    local t2,t3=t*t,t*t*t
    return 0.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t2+(-p0+3*p1-3*p2+p3)*t3)
end
local function sampledPoints(data)
    local points=data.points
    if data.kind~=1 or #points<3 then return points end
    local n,steps,span,out=#points,math.max(1,data.precision or 4),(data.closed and #points or #points-1),{}
    -- A closed path wraps its control points; an open one repeats its endpoints so the
    -- spline leaves the first and last authored point on a straight tangent.
    local function at(i)
        if data.closed then return points[((i-1)%n)+1] end
        return points[math.max(1,math.min(n,i))]
    end
    for i=1,span do
        local p0,p1,p2,p3=at(i-1),at(i),at(i+1),at(i+2)
        for s=0,steps-1 do
            local t=s/steps
            out[#out+1]={catmull(p0[1],p1[1],p2[1],p3[1],t),catmull(p0[2],p1[2],p2[2],p3[2],t)}
        end
    end
    out[#out+1]=points[data.closed and 1 or n]
    return out
end
function Runtime:pathGeometry(index)
    local data=index and index>=0 and self.pathData[index] or nil
    if not data then return nil end
    if data._length then return data end
    local points=sampledPoints(data)
    local count=#points
    local cumulative={0}
    local total=0
    for i=1,(data.closed and count or math.max(0,count-1)) do
        local a,b=points[i],points[i%count+1]
        total=total+math.sqrt((b[1]-a[1])^2+(b[2]-a[2])^2)
        cumulative[i+1]=total
    end
    data._points,data._cumulative,data._length=points,cumulative,total
    return data
end
local function pointAt(geo,position)
    local points,cumulative,total=geo._points,geo._cumulative,geo._length
    local count=#points
    if count==0 then return 0,0,0 end
    if total<=0 then local p=points[1];return p[1],p[2],0 end
    position=math.max(0,math.min(1,position))
    local target,i=position*total,1
    while i<count and cumulative[i+1]<target do i=i+1 end
    local a,b=points[i],points[i%count+1]
    local span=cumulative[i+1]-cumulative[i]
    local t=span>0 and (target-cumulative[i])/span or 0
    if t<0 then t=0 elseif t>1 then t=1 end
    local dx,dy=b[1]-a[1],b[2]-a[2]
    local angle=atan2(-dy,dx)*180/math.pi
    if angle<0 then angle=angle+360 end
    return a[1]+dx*t,a[2]+dy*t,angle
end

function Runtime:startPath(E,index,speed,action,absolute)
    local geo=self:pathGeometry(index)
    if not geo then self:unsupported("path_start("..tostring(index)..")",
        "The repository does not contain "..(self.manifest.paths[index] or "this path")..
        " and no point data was recovered for it; see docs/PATHS.md.") end
    local v=E._self.v
    v.path_index=index;v.path_speed=speed;v.path_endaction=action;v.path_position=0;v.path_positionprevious=0
    v._pathAbsolute=self.truth(absolute);v._pathStartX=v.x;v._pathStartY=v.y
    -- GameMaker puts the instance on the path start when the path begins, not a step later.
    local x,y=pointAt(geo,0)
    if v._pathAbsolute then v.x=x;v.y=y else v.x=v._pathStartX+x;v.y=v._pathStartY+y end
end
function Runtime:advancePath(inst)
    local v=inst.v
    local geo=self:pathGeometry(v.path_index)
    if not geo then v.path_index=-1;return end
    local step=geo._length>0 and (v.path_speed/geo._length) or 0
    local previous,action=v.path_position,v.path_endaction
    local position=previous+step
    if position>1 then
        if action==0 then position=1;v.path_index=-1 -- stop: the path ends on its last point
        elseif action==1 then position=position-1    -- restart: loop back to the beginning
        elseif action==3 then position=1;v.path_speed=-math.abs(v.path_speed) end
        -- action 2 (continue) holds the end position without ending the path.
    elseif position<0 then
        if action==3 then position=0;v.path_speed=math.abs(v.path_speed)
        else position=0;v.path_index=-1 end
    end
    v.path_positionprevious=previous;v.path_position=position
    local x,y,angle=pointAt(geo,position)
    if v._pathAbsolute then v.x=x;v.y=y else v.x=v._pathStartX+x;v.y=v._pathStartY+y end
    -- path_orientation < 0 follows the tangent; Undertale never sets path_scale, so
    -- that instance variable is intentionally not applied here (docs/PATHS.md).
    if v.path_orientation<0 then v.direction=angle end
end
return Runtime
