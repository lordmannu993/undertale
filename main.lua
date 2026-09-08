local Input=require("port.input")
local Touch=require("port.touch")
local Runtime=require("port.runtime")
local Presentation=require("port.presentation")
local Version=require("port.version")
local input,touch,game
local smoke,smokeMode=nil,false
local accumulator=0
local errorMessage=nil
local tester=false
local focused=true
local mobile=false
local recent={}
local pointerTouches={}
local viewport={x=0,y=0,w=640,h=480,scale=1}
local testExit,errorRestart

local function safeArea()
    if love.window.getSafeArea then return {love.window.getSafeArea()} end
    local w,h=love.graphics.getDimensions();return {0,0,w,h}
end
local function resize()
    local w,h=love.graphics.getDimensions()
    touch:resize(w,h,safeArea())
    pointerTouches={};input:releasePrefix("mouse:")
end
local function fail(err)
    errorMessage=tostring(err)
    print(errorMessage)
    input:cancelAll();touch:cancel()
    if game then game:suspendAudio();pcall(function() game:flushSaves() end) end
    -- Reset any interrupted graphics stack before drawing the error UI.
    love.graphics.reset()
    love.graphics.setDefaultFilter("nearest","nearest")
    love.filesystem.write("last-port-error.txt",errorMessage.."\n\nThis is an experimental conversion. See generated/conversion-report.json.\n")
    if smokeMode then
        local f=io.open("port-test-output/native-error.txt","w")
        if f then f:write(errorMessage);f:close() end
        love.event.quit(1)
    end
end
local function boot()
    if game then game:flushSaves();game:releaseAudio();game:releaseGraphics() end
    input:cancelAll();touch:cancel();pointerTouches={};input.mapping={};accumulator=0;errorMessage=nil
    if not love.filesystem.getInfo("generated/manifest.lua","file") then
        fail("The converted game is not built yet.\n\nRun from the repository:\npython3 tools/convert.py\nlove .\n\nOr build the Android-loadable archive with:\npython3 tools/package.py")
        return
    end
    local ok,err=pcall(function()
        game=Runtime.new(require("generated.manifest"),input,{trace=smokeMode,memorySaves=smokeMode,seed=smokeMode and 42 or nil})
        game:start()
    end)
    if not ok then fail(err) end
    -- The touch collision toggle is runtime-only, so a restart must re-apply it:
    -- the walk-through-walls debug state lives in the game's global.phasing.
    if game and touch.collision == false then game.global.phasing = 1 end
end
local function setTester(value)
    tester=value;input:cancelAll();recent={};accumulator=0
    touch.visible=true;touch.extra=false;resize()
    if game then if tester then game:suspendAudio() else game:resumeAudio() end end
end

function love.load(args)
    for _,a in ipairs(args or {}) do if a=="--smoke-test" then smokeMode=true end end
    if smokeMode then
        love.filesystem.setIdentity("undertale-love-port-selftest")
        love.window.setMode(1440,720,{resizable=true,vsync=0})
    end
    love.graphics.setDefaultFilter("nearest","nearest")
    love.graphics.setLineStyle("rough")
    mobile=love.system.getOS()=="Android" or love.system.getOS()=="iOS"
    input=Input.new();touch=Touch.new(input,mobile)
    touch.onPause=function(paused)
        accumulator=0
        if game then
            if paused then game:suspendAudio();game:flushSaves()
            elseif not tester and focused and not errorMessage then game:resumeAudio() end
        end
    end
    touch.onTest=function() setTester(not tester) end
    touch.onCollision=function(enabled)
        -- Maps the pause-menu toggle onto the game's own phasing debug global:
        -- collision ON keeps global.phasing = 0, OFF walks through walls (1).
        if game then game.global.phasing = enabled and 0 or 1 end
    end
    resize()
    for _,a in ipairs(args or {}) do if a=="--touch" then touch.visible=true;resize() elseif a=="--input-test" then tester=true end end
    if smokeMode then
        touch.visible=true;touch.settings.scale=1;touch.settings.pixels=false
        touch.settings.southpaw=false;touch.settings.haptics=false;resize()
    end
    boot()
    if smokeMode and not errorMessage then smoke=require("port.smoke").new(game,touch) end
    if tester then setTester(true) end
end

function love.update(dt)
    if not focused or touch.paused then return end
    if tester then
        input:beginFrame()
        for k in pairs(input.pressed) do recent[#recent+1]="DOWN "..k end
        for k in pairs(input.released) do recent[#recent+1]="UP "..k end
        while #recent>10 do table.remove(recent,1) end
        input:endFrame()
        return
    end
    if errorMessage or not game then return end
    local frameTime=1/math.max(1,game.vars.room_speed)
    -- Bound catch-up after an OS stall; never fast-forward a battle on resume.
    accumulator=math.min(accumulator+dt,frameTime*5)
    local steps=0
    while accumulator>=frameTime and steps<5 do
        accumulator=accumulator-frameTime;steps=steps+1
        local ok,err=pcall(function()
            if smoke then smoke:beforeTick() end
            input:beginFrame()
            game:step()
            game:renderFrame()
            game:finishFrame()
            input:endFrame()
        end)
        if not ok then fail(err);return end
        if game.quitRequested then love.event.quit();return end
        if game.restartRequested then boot();return end
        frameTime=1/math.max(1,game.vars.room_speed)
    end
end

local function box(b,text)
    local g=love.graphics;g.setColor(0.12,0.19,0.22,1);g.rectangle("fill",b.x,b.y,b.w,b.h,8)
    g.setColor(0.75,0.95,0.89,1);g.printf(text,b.x,b.y+(b.h-g.getFont():getHeight())/2,b.w,"center")
end
function love.draw()
    local g=love.graphics
    g.clear(0.025,0.03,0.04,1)
    g.push("all")
    local p=touch.play
    if game and game.canvas and not tester and not errorMessage then
        viewport=Presentation.fit(p,game.displayWidth,game.displayHeight,touch.settings.pixels)
        g.setColor(1,1,1,1);g.setBlendMode("alpha","premultiplied")
        g.draw(game.canvas,viewport.x,viewport.y,0,viewport.scale,viewport.scale)
        g.setBlendMode("alpha")
    end
    if not g.getFont() then g.setFont(g.newFont(14)) end
    if tester then
        g.setColor(0.8,0.94,0.9,1);g.printf("TOUCH / KEYBOARD TEST",p.x,p.y+16,p.w,"center")
        local keys={};for k in pairs(input.logical) do keys[#keys+1]=k end;table.sort(keys)
        local text={};for _,k in ipairs(keys) do text[#text+1]=tostring(k) end
        g.setColor(1,1,1,1);g.printf("Held key codes: "..table.concat(text,", "),p.x+12,p.y+50,p.w-24,"center")
        g.setColor(0.58,0.66,0.7,1);g.printf("Use two fingers. Slide between directions.\nTry Z + movement, quick taps and the KEYS panel.\nReleasing one finger must not release another.",p.x+14,p.y+88,p.w-28,"center")
        g.setColor(0.65,0.75,0.8,1);g.printf(table.concat(recent,"   "),p.x+14,p.y+160,p.w-28,"center")
        testExit={x=p.x+p.w/2-70,y=p.y+p.h-50,w=140,h=36};box(testExit,"BACK TO GAME")
    elseif errorMessage then
        local w=math.min(p.w-24,740)
        local x=p.x+(p.w-w)/2
        g.setColor(1,0.68,0.45,1);g.printf("PORT COMPATIBILITY STOP",x,p.y+12,w,"left")
        g.setColor(0.85,0.86,0.9,1)
        g.printf(errorMessage:sub(1,1500),x,p.y+44,w,"left")
        errorRestart={x=x,y=p.y+p.h-46,w=150,h=36};box(errorRestart,"RESTART PORT")
    end
    -- Visible status is intentional: a generated archive is not proof of a
    -- complete, device-tested conversion. Details are included in the archive.
    g.setColor(0.38,0.43,0.49,1)
    if touch.w>650 then g.printf("EXPERIMENTAL LOVE "..Version.number,160,10,touch.w-320,"center") end
    g.pop()
    touch:draw()
    if smoke then
        local ok,err=pcall(function() smoke:draw(viewport) end)
        if not ok then fail(err) end
    end
end

local function hit(b,x,y) return b and x>=b.x and x<=b.x+b.w and y>=b.y and y<=b.y+b.h end
local function aim(x,y)
    if not game or not game.canvas or not hit(viewport,x,y) then return false end
    local cx=(x-viewport.x)/viewport.scale;local cy=(y-viewport.y)/viewport.scale
    for _,v in ipairs(game:views()) do
        if cx>=v.px and cx<v.px+v.pw and cy>=v.py and cy<v.py+v.ph then
            game.vars.mouse_x=v.x+(cx-v.px)*v.w/v.pw
            game.vars.mouse_y=v.y+(cy-v.py)*v.h/v.ph
            return true
        end
    end
    return false
end
function love.touchpressed(id,x,y)
    if tester and hit(testExit,x,y) then setTester(false);return end
    if errorMessage and hit(errorRestart,x,y) then boot();return end
    if not touch:pressed(id,x,y) and not tester and not errorMessage and aim(x,y) then
        pointerTouches[id]=true;input:mouseButton(id,1,true)
    end
end
function love.touchmoved(id,x,y)
    touch:moved(id,x,y)
    if pointerTouches[id] then aim(x,y) end
end
function love.touchreleased(id)
    touch:released(id)
    if pointerTouches[id] then input:mouseButton(id,1,false);pointerTouches[id]=nil end
end
function love.mousepressed(x,y,button,istouch)
    if istouch then return end -- Android also emits synthetic mouse events
    if button==1 then
        if tester and hit(testExit,x,y) then setTester(false);return end
        if errorMessage and hit(errorRestart,x,y) then boot();return end
        if touch:pressed("mouse",x,y) then return end
    end
    if not touch.paused and not tester and not errorMessage and aim(x,y) then input:mouseButton("hardware",button,true) end
end
function love.mousemoved(x,y,dx,dy,istouch)
    if istouch then return end
    touch:moved("mouse",x,y)
    if not touch.paused then aim(x,y) end
end
function love.mousereleased(x,y,button,istouch)
    if istouch then return end
    if button==1 then touch:released("mouse") end
    input:mouseButton("hardware",button,false)
end
function love.keypressed(key,scancode,isrepeat)
    -- The Android Back key opens a safe pause screen, not the game's hold-to-
    -- quit key. The virtual Esc key remains available, including sustained hold.
    if (mobile and key=="escape") or key=="f2" then
        if not isrepeat then touch:setPaused(not touch.paused) end
        return
    end
    if not touch.paused then input:keypressed(key,isrepeat) end
end
function love.keyreleased(key) input:keyreleased(key) end
function love.gamepadpressed(joystick,button) if not touch.paused then input:gamepadpressed(joystick,button) end end
function love.gamepadreleased(joystick,button) input:gamepadreleased(joystick,button) end
function love.gamepadaxis(joystick,axis,value) if not touch.paused then input:gamepadaxis(joystick,axis,value) end end
function love.joystickremoved(joystick) input:releasePrefix("gamepad:"..tostring(joystick)..":") end
function love.resize() if touch then resize();accumulator=0 end end
function love.focus(value)
    if smokeMode then return end -- Xvfb may have no window manager; not a lifecycle test
    focused=value
    if not value and touch then touch:setPaused(true) end
end
function love.visible(value) if smokeMode then return end; if not value then love.focus(false) else focused=true end end
function love.lowmemory()
    if game then
        game:trimGraphicsCache();game:trimAudioCache()
        game:warn("low-memory","Android reported low memory; unused texture, mask and audio caches were released.")
    end
    collectgarbage("collect")
end
function love.quit()
    if game then game:flushSaves();game:releaseAudio() end
    if touch then touch:save() end
end
