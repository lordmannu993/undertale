-- Opt-in native rendering regression driver: love game.love --smoke-test
-- Uses the real touch callbacks and game ticks, with a separate identity and
-- in-memory saves selected by main.lua. Never runs during normal gameplay.
local Smoke={}
Smoke.__index=Smoke
local function write(name,bytes)
    local f=assert(io.open("port-test-output/"..name,"wb"),"Create port-test-output before --smoke-test")
    f:write(bytes);f:close()
end
function Smoke.new(game,touch)
    local self=setmetatable({game=game,touch=touch,frames=0,capture=nil,pending=false,done=false},Smoke)
    local function wait(n) for _=1,n do coroutine.yield() end end
    local function down(k)
        local p=touch.pad
        if k>=37 and k<=40 then
            local dx=k==37 and -0.7 or k==39 and 0.7 or 0
            local dy=k==38 and -0.7 or k==40 and 0.7 or 0
            love.touchpressed("smoke",p.x+p.r*dx,p.y+p.r*dy)
        else
            for _,b in ipairs(touch.controls) do
                if b.key==k then love.touchpressed("smoke",b.x+b.w/2,b.y+b.h/2);return end
            end
            error("No smoke-test touch target for "..k)
        end
    end
    local function hold(k,n) down(k);wait(n);love.touchreleased("smoke");wait(1) end
    local function tap(k) hold(k,1) end
    local function capture(name)
        self.capture=name
        repeat wait(1) until not self.capture
    end
    self.thread=coroutine.create(function()
        wait(10);tap(90);wait(40);tap(90)
        assert(game.roomState.name=="room_intromenu","Title -> menu failed")
        tap(90);tap(90)
        for _=1,5 do tap(39) end
        tap(38);tap(90);tap(39);tap(90);wait(200)
        assert(game.roomState.name=="room_area1" and game.global.charname=="A","Naming -> first room failed")
        capture("native-flowers")
        hold(40,10);hold(39,160)
        capture("native-corridor")
        hold(38,20);hold(38,100)
        assert(game.roomState.name=="room_area1_2","First doorway failed")
        local greeting=game:select(game.constants.OBJ_WRITER)[1]
        assert(greeting and greeting.v.originalstring:find("Howdy",1,true),"Flowey's first greeting has the wrong text")
        capture("native-greeting")
        for _=1,40 do
            tap(90);wait(30)
            if game.roomState.name~="room_area1_2" then break end
        end
        assert(game.roomState.name=="room_floweybattle","Flowey went to the wrong room: "..game.roomState.name)
        wait(90)
        assert(#game:select(game.constants.obj_floweybattle1)==1,"Flowey controller is missing")
        assert(game.global.idealborder[0]==237 and game.global.idealborder[3]==385,"Battle borders are uninitialized")
        local writer=game:select(game.constants.OBJ_WRITER)[1]
        assert(writer and writer.v.originalstring:find("See that heart",1,true),"Wrong dialogue selected for Flowey")
        assert(not writer.v.originalstring:find("Sit down",1,true),"Undyne's choice text leaked into Flowey")
        capture("native-flowey")
        touch.settings.pixels=true;touch:resize(touch.w,touch.h,touch.safe)
        capture("native-integer-scale")
        print("NATIVE SMOKE PASS: restored chamber/rings/corridor, touch navigation, correct SOUL dialogue, four rendered borders, fit/integer presentation")
        -- Play Flowey's tutorial fight out the way the headless regression does, then
        -- follow Toriel into the ruins. Before the recovered path data this is exactly
        -- where a phone stopped with "Compatibility stop: path_start(...)".
        local deadline=self.frames+2400
        while game.roomState.name=="room_floweybattle" and self.frames<deadline do
            hold(38,2);tap(90)
        end
        assert(game.roomState.name=="room_area1_2","Tutorial battle did not return to the corridor: "..game.roomState.name)
        deadline=self.frames+1200
        local trigger
        while self.frames<deadline do
            wait(10);tap(90)
            trigger=game:select(game.constants.obj_floweytrigger)[1]
            if trigger and trigger.v.conversation>=4 and game.global.interact==0 then break end
        end
        assert(trigger and trigger.v.conversation>=4,"obj_floweytrigger never advanced past the battle")
        local function walking()
            for _,id in ipairs({game.constants.obj_toroverworld2,game.constants.obj_toroverworld1}) do
                local instance=game:select(id)[1]
                if instance and instance.v.path_index>=0 then return instance end
            end
        end
        local walker
        for round=1,700 do
            if game.roomState.name~="room_area1_2" then break end
            hold(38,6)
            if round%20==0 then tap(90) end
        end
        assert(game.roomState.name=="room_ruins1","Following Toriel never reached the ruins entry: "..game.roomState.name)
        for round=1,60 do
            hold(38,4)
            walker=walking()
            if walker and walker.v.path_index>=0 then break end
        end
        assert(walker and walker.v.path_index==game.manifest.names.path_torielwalk1,
            "Toriel is not walking path_torielwalk1 in room_ruins1 (path_index="..tostring(walker and walker.v.path_index)..")")
        local startY,startX=walker.v.y,walker.v.x
        self.walkStartY=startY
        local furthest=0
        for round=1,400 do
            hold(38,4)
            if round%20==0 then tap(90) end
            if walker.v.path_position>furthest then furthest=walker.v.path_position end
            if walker.v.path_position>=1 or walker.v.path_index<0 then break end
        end
        assert(furthest>0.02,"Toriel never advanced along the recovered path (position stayed at 0)")
        assert(walker.v.y<startY-20,"Toriel did not walk up the corridor: y="..tostring(walker.v.y).." of "..tostring(startY))
        assert(math.abs(walker.v.x-startX)>2 or math.abs(walker.v.y-startY)>2,"Toriel's position never changed")
        self.walkTarget=walker
        capture("native-toriel-walk")
        print(string.format("NATIVE SMOKE PASS: path_torielwalk1 walked to %.0f%% at (%.0f,%.0f), position recorded by the renderer",
            walker.v.path_position*100,walker.v.x,walker.v.y))
        self.done=true;love.event.quit(0)
    end)
    return self
end
function Smoke:beforeTick()
    if self.done then return end
    self.frames=self.frames+1
    -- Budget covers the whole scripted opening including Flowey's tutorial fight
    -- and Toriel's walked corridor; a hang must still fail fast, not run forever.
    assert(self.frames<9000,"Native smoke exceeded its tick budget")
    local ok,err=coroutine.resume(self.thread)
    if not ok then error("Native smoke: "..tostring(err)) end
end
function Smoke:draw(viewport)
    if not self.capture or self.pending then return end
    local name=self.capture
    local g=love.graphics
    local data=self.game.canvas:newImageData()
    local function worldPixel(x,y)
        local v=self.game:views()[1]
        return data:getPixel(math.floor(v.px+(x-v.x)*v.pw/v.w),math.floor(v.py+(y-v.y)*v.ph/v.h))
    end
    local function worldColor(x,y,expected)
        local r,gg,b=worldPixel(x,y)
        assert(math.abs(r-expected[1]/255)<0.03 and math.abs(gg-expected[2]/255)<0.03 and math.abs(b-expected[3]/255)<0.03,"Backdrop color mismatch at "..x..","..y)
    end
    if name=="native-flowers" then
        local palette=require("port.opening_backdrops").palette
        worldColor(150,190,palette.floor)
        worldColor(65,150,palette.outer)
        worldColor(85,150,palette.light)
        worldColor(105,150,palette.grass)
    elseif name=="native-corridor" then
        worldColor(400,180,require("port.opening_backdrops").palette.floor)
        local r,gg,b=worldPixel(586,122)
        assert(r+gg+b>0.3,"The corridor doorway is missing")
    elseif name=="native-greeting" then
        worldColor(230,300,require("port.opening_backdrops").palette.floor)
    elseif name=="native-flowey" then
        local function white(x,y)
            local r,gg,b=data:getPixel(x,y)
            assert(r>0.9 and gg>0.9 and b>0.9,"Missing native border pixel at "..x..","..y)
        end
        white(240,251);white(240,386);white(238,320);white(398,320)
        local colored=0
        for y=134,221 do for x=281,363 do
            local r,gg,b=data:getPixel(x,y)
            if r+gg+b>0.5 then colored=colored+1 end
        end end
        assert(colored>80,"Flowey's native image is blank")
        local r,gg,b=data:getPixel(315,319)
        -- The supplied base SOUL texture uses red=128/255; its flashing frame
        -- uses 255/255. Validate the actual palette, not assumed retail colors.
        assert(r>0.47 and gg<0.05 and b<0.05,"The native SOUL pixel is missing: "..r..","..gg..","..b)
        local writer=self.game:select(self.game.constants.OBJ_WRITER)[1]
        local bubble=self.game:select(self.game.constants.obj_blconwdflowey)[1]
        local right=bubble.v.x+self.game:instanceGet(bubble,"sprite_width")
        local bottom=bubble.v.y+self.game:instanceGet(bubble,"sprite_height")
        local displayed={}
        for _,entry in ipairs(self.game.drawLog) do
            if entry[1]=="text" and entry[5]==writer.v.myfont and entry[4]<250 then
                displayed[#displayed+1]=entry[2]
                local glyph=self.game.assets.fonts[writer.v.myfont].glyphs[entry[2]:byte(1)]
                assert(entry[3]+glyph.offset+glyph.w<=right and entry[4]+glyph.h<=bottom,"Dialogue overflows its bubble")
            end
        end
        assert(table.concat(displayed):find("See that heart",1,true) and table.concat(displayed):find("SOUL",1,true),"Native dialogue content is wrong")
        assert(viewport.w>880,"Phone fit mode is still unnecessarily small")
        write("native-render.txt", "PASS\nroom="..self.game.roomState.name.."\nflowey_pixels="..colored.."\nviewport_width="..viewport.w.."\n")
    elseif name=="native-toriel-walk" then
        -- Renderer-side proof: her sprite must be drawn where the recovered path put
        -- her, and no longer where the room placed her. Pixel thresholds over unknown
        -- ruins tiles would only flake, so the traced draw calls are the assertion and
        -- the PNG below is the human-readable record.
        local walker=self.walkTarget
        local drawn
        for _,entry in ipairs(self.game.drawLog) do
            if entry[1]=="sprite" and entry[2] and entry[2]:find("spr_toriel",1,true) then drawn=entry end
        end
        assert(drawn,"Toriel's sprite was never drawn in room_ruins1")
        assert(math.abs(drawn[5]-walker.v.x)<=2 and math.abs(drawn[6]-walker.v.y)<=64,
            "Toriel was drawn at "..drawn[5]..","..drawn[6].." but walked to "..walker.v.x..","..walker.v.y)
        assert(math.abs(drawn[6]-self.walkStartY)>20,
            "Toriel is still drawn at her room placement, so the recovered path did not move the render")
        write("native-toriel-walk.txt","sprite="..tostring(drawn[2]).." drawn="..drawn[5]..","..drawn[6]..
            " instance="..string.format("%.1f,%.1f",walker.v.x,walker.v.y)..
            " path_position="..string.format("%.4f",walker.v.path_position)..
            " path_speed="..tostring(walker.v.path_speed).."\n")
    end
    data:release()
    self.pending=true
    g.captureScreenshot(function(image)
        local ok,err=pcall(function()
            local png=image:encode("png")
            write(name..".png",png:getString());png:release();image:release()
            print("Captured "..name..".png")
        end)
        if not ok then print(err);self.done=true;love.event.quit(1) end
        self.pending=false;self.capture=nil
    end)
end
return Smoke
