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
        self.done=true;love.event.quit(0)
    end)
    return self
end
function Smoke:beforeTick()
    if self.done then return end
    self.frames=self.frames+1
    assert(self.frames<3000,"Native smoke exceeded its tick budget")
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
