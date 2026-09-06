-- Non-rendering GML builtins used by this checkout.
return function(R)
    local B=R.builtins
    local N,T=R.num,R.truth
    local function reg(name,fn) B[name]=function(_,...) return fn(...) end end
    for _,name in ipairs({"abs","floor","ceil","sin","cos","min","max","sqrt","tan","exp","log"}) do reg(name,math[name]) end
    reg("round",function(x)
        -- GameMaker rounds exact halves to even, including negative values.
        local f=math.floor(x);local n=x-f
        if n==0.5 then return f%2==0 and f or f+1 end
        return math.floor(x+0.5)
    end)
    reg("power",function(a,b) return a^b end)
    reg("degtorad",math.rad);reg("radtodeg",math.deg)
    reg("random",function(n) return math.random()*n end)
    reg("irandom",function(n) return math.random(0,n) end)
    reg("randomize",function() math.randomseed(R.options.seed or os.time()) end)
    reg("choose",function(...) local a={...};return a[math.random(#a)] end)
    reg("lengthdir_x",function(len,dir) return len*math.cos(math.rad(dir)) end)
    reg("lengthdir_y",function(len,dir) return -len*math.sin(math.rad(dir)) end)
    reg("point_distance",function(x1,y1,x2,y2) return math.sqrt((x2-x1)^2+(y2-y1)^2) end)
    reg("point_direction",function(x1,y1,x2,y2) return (-math.deg(math.atan2(y2-y1,x2-x1)))%360 end)
    reg("string",function(value) if type(value)=="number" and value==math.floor(value) then return string.format("%.0f",value) end;return tostring(value) end)
    reg("real",function(s) return tonumber(s) or 0 end)
    reg("chr",function(n) return string.char(math.floor(n)%256) end)
    reg("ord",function(s) return string.byte(s,1) or 0 end)
    reg("string_lower",string.lower)
    reg("string_length",string.len)
    reg("string_char_at",function(s,i) i=math.floor(i);return i>0 and s:sub(i,i) or "" end)
    reg("string_delete",function(s,i,count) i=math.max(1,math.floor(i));return s:sub(1,i-1)..s:sub(i+math.floor(count)) end)
    reg("string_pos",function(needle,haystack) return string.find(haystack,needle,1,true) or 0 end)
    reg("date_current_datetime",function() return os.time()/86400+25569 end)
    reg("keyboard_check",function(k) return N(R.input:check(k)) end)
    reg("keyboard_check_pressed",function(k) return N(R.input:check(k,"pressed")) end)
    reg("keyboard_check_released",function(k) return N(R.input:check(k,"released")) end)
    reg("keyboard_check_direct",function(k) return N(R.input:check(k,nil,true)) end)
    reg("keyboard_clear",function(k) R.input:clear(k) end)
    reg("keyboard_set_map",function(k,to) R.input:setMap(k,to) end)
    reg("keyboard_key_press",function(k) R.input:setSource("gml:"..k,{k}) end)
    reg("keyboard_key_release",function(k) R.input:setSource("gml:"..k,{}) end)
    -- Native LÖVE gamepads feed the SAME input layer. Reporting no legacy
    -- Windows joystick prevents the original DInput poller from double-firing.
    for _,name in ipairs({"joystick_exists","joystick_has_pov","joystick_buttons","joystick_check_button","joystick_xpos","joystick_ypos","joystick_direction"}) do reg(name,function() return 0 end) end
    reg("joystick_pov",function() return -1 end)
    for _,name in ipairs({"steam_initialised","steam_file_exists","steam_file_delete","steam_file_write_file"}) do
        reg(name,function() return 0 end) -- platform service deliberately unavailable, not game state
    end

    B.script_execute=function(E,index,...) return R:script(index,E,...) end
    B.instance_create=function(E,x,y,index) return R:create(index,x,y).id end
    B.instance_exists=function(E,index) return N(#R:select(index,E)>0) end
    B.instance_number=function(E,index) return #R:select(index,E) end
    B.instance_find=function(E,index,number) local a=R:select(index,E);return a[math.floor(number)+1] and a[math.floor(number)+1].id or -4 end
    B.instance_destroy=function(E,index)
        if index==nil then R:destroy(E._self) else for _,i in ipairs(R:select(index,E)) do R:destroy(i) end end
    end
    B.action_kill_object=B.instance_destroy
    B.instance_change=function(E,index,events)
        local inst=E._self;local def=R:object(index)
        if not def then R:unsupported("instance_change","Unknown object ID "..tostring(index)) end
        if T(events) then R:event(inst,1,0) end
        inst.v.object_index=index;inst.v.sprite_index=def.sprite;inst.v.mask_index=def.mask
        inst.v.visible=def.visible;inst.v.solid=def.solid;inst.v.persistent=def.persistent;inst.v.depth=def.depth
        if T(events) then R:event(inst,0,0) end
    end
    B.instance_deactivate_all=function(E,notme)
        for _,i in ipairs(R.instances) do if not T(notme) or i~=E._self then i.active=false end end
    end
    B.event_user=function(E,n) R:event(E._self,7,10+n,E._other) end
    B.event_perform=function(E,kind,number) R:event(E._self,kind,number,E._other) end
    B.event_inherited=function(E)
        local event=R.currentEvent
        if event then local def=R:object(event.owner);if def and def.parent>=0 then R:event(E._self,event.kind,event.number,E._other,def.parent) end end
    end
    B.move_towards_point=function(E,x,y,speed)
        R:instanceSet(E._self,"direction",(-math.deg(math.atan2(y-E.y,x-E.x)))%360)
        R:instanceSet(E._self,"speed",speed)
    end
    B.action_move_point=B.move_towards_point
    B.move_snap=function(E,xsnap,ysnap)
        if xsnap>0 then E.x=B.round(E,E.x/xsnap)*xsnap end
        if ysnap>0 then E.y=B.round(E,E.y/ysnap)*ysnap end
    end
    B.action_set_motion=function(E,dir,speed) E.direction=dir;E.speed=speed end
    B.action_set_hspeed=function(E,speed) E.hspeed=speed end
    B.action_set_gravity=function(E,dir,amount) E.gravity_direction=dir;E.gravity=amount end
    B.action_set_friction=function(E,amount) E.friction=amount end
    B.action_set_alarm=function(E,steps,alarm) E.alarm[alarm]=steps end
    B.action_move_to=function(E,x,y) E.x=x;E.y=y end
    B.action_create_object=function(E,object,x,y) return R:create(object,x,y).id end
    B.action_move=function(E,choices,speed)
        local angles={225,270,315,180,-1,0,135,90,45};local available={}
        for i=1,9 do if choices:sub(i,i)=="1" then available[#available+1]=angles[i] end end
        if #available==0 then return end
        local a=available[math.random(#available)]
        if a<0 then E.speed=0 else E.direction=a;E.speed=speed end
    end
    B.path_start=function(E,index,speed,action,absolute) R:startPath(E,index,speed,action,absolute) end
    B.path_end=function(E) E.path_index=-1;E.path_speed=0 end

    local positions={}
    for i,index in ipairs(R.manifest.room_order) do positions[index]=i end
    local function adjacent(index,delta)
        local position=positions[index]
        return position and R.manifest.room_order[position+delta] or -1
    end
    reg("room_next",function(index) return adjacent(index,1) end)
    reg("room_previous",function(index) return adjacent(index,-1) end)
    reg("room_goto",function(index) R:gotoRoom(index) end)
    reg("room_goto_next",function() R:gotoRoom(adjacent(R.vars.room,1)) end)
    reg("room_goto_previous",function() R:gotoRoom(adjacent(R.vars.room,-1)) end)
    B.action_previous_room=B.room_goto_previous
    reg("room_restart",function() R.storedRooms[R.vars.room]=nil;R.vars.room_persistent=0;R:gotoRoom(R.vars.room) end)
    reg("room_set_persistent",function(index,persistent)
        R.roomPersistence[index]=persistent
        if not T(persistent) then R.storedRooms[index]=nil end
        if index==R.vars.room then R.vars.room_persistent=persistent end
    end)
    reg("game_restart",function() R.restartRequested=true end)
    reg("game_end",function() R.quitRequested=true end)
    reg("window_get_fullscreen",function() return N(love and love.window and love.window.getFullscreen()) end)
    reg("window_set_fullscreen",function(full)
        if love and love.window and not R.options.headless and R.vars.os_type~=5 then love.window.setFullscreen(T(full),"desktop") end
    end)
    reg("window_set_caption",function(caption) if love and love.window then love.window.setTitle(caption) end end)
    -- Desktop-only window placement has no Android equivalent. Not game logic.
    reg("window_center",function() if love and love.window and R.vars.os_type~=5 then local w,h=love.window.getDesktopDimensions();local ww,wh=love.graphics.getDimensions();love.window.setPosition((w-ww)/2,(h-wh)/2) end end)
    reg("window_get_x",function() if love and love.window and love.window.getPosition then return (love.window.getPosition()) end;return 0 end)
    reg("window_get_y",function() if love and love.window and love.window.getPosition then local _,y=love.window.getPosition();return y end;return 0 end)
    reg("window_set_position",function(x,y) if love and love.window and R.vars.os_type~=5 then love.window.setPosition(x,y) end end)
end
