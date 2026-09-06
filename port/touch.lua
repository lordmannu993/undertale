-- Responsive touch controller, in window coordinates (never game coordinates).
-- Default layouts reserve space outside the 4:3 game image, including notches.
local Touch = {}
Touch.__index = Touch
local function clamp(x,a,b) return math.max(a,math.min(b,x)) end
local function inside(r,x,y) return x>=r.x and y>=r.y and x<r.x+r.w and y<r.y+r.h end
local defaults = {scale=1, opacity=0.75, southpaw=false, haptics=false}
local settingsPath = "touch-settings-v1.txt"
local pages = {
    {name="Actions", keys={{"Enter",13},{"Shift",16},{"Ctrl",17},{"Space",32},{"Esc",27},
        {"Back",8},{"Tab",9},{"Home",36},{"End",35},{"PgUp",33},{"PgDn",34},{"Ins",45},{"Del",46},{"Mouse L",1001},{"Mouse R",1002}}},
    {name="ABC / 123", keys={}},
    {name="F / Numpad", keys={}},
}
for i=48,57 do table.insert(pages[2].keys,{string.char(i),i}) end
for c in ("QWERTYUIOPASDFGHJKLZXCVBNM"):gmatch(".") do table.insert(pages[2].keys,{c,string.byte(c)}) end
for i=1,12 do table.insert(pages[3].keys,{"F"..i,111+i}) end
for i=0,9 do table.insert(pages[3].keys,{"Num "..i,96+i}) end
Touch.pages = pages

function Touch.new(input, mobile)
    local self=setmetatable({input=input, mobile=mobile, visible=mobile, settings={}, pointers={},
        extra=false, page=1, paused=false, controls={}, toolbar={}, extraButtons={}, lastHaptic=-1},Touch)
    for k,v in pairs(defaults) do self.settings[k]=v end
    if love and love.filesystem then
        local data=love.filesystem.read(settingsPath)
        if data then
            for key,val in data:gmatch("([a-z]+)=([^\n]+)") do
                if key=="scale" then self.settings.scale=clamp(tonumber(val) or 1,0.8,1.25)
                elseif key=="opacity" then self.settings.opacity=clamp(tonumber(val) or 0.75,0.3,1)
                elseif key=="southpaw" or key=="haptics" then self.settings[key]=val=="true" end
            end
        end
    end
    self:resize(960,540,{0,0,960,540})
    return self
end

function Touch:save()
    if not (love and love.filesystem) then return end
    local lines={}
    for _,key in ipairs({"scale","opacity","southpaw","haptics"}) do lines[#lines+1]=key.."="..tostring(self.settings[key]) end
    love.filesystem.write(settingsPath,table.concat(lines,"\n"))
end

function Touch:cancel()
    self.pointers={}
    self.input:releasePrefix("touch:")
end

function Touch:resize(w,h,safe)
    self:cancel()
    self.w,self.h=w,h
    self.safe=safe or {0,0,w,h}
    local sx,sy,sw,sh=unpack(self.safe)
    local bar=clamp(sh*0.085,32,48)
    self.bar=bar
    self.controls={}
    if not self.visible then
        self.play={x=sx,y=sy,w=sw,h=sh}
    elseif sw/sh>=1.55 then
        local rail=clamp(sw*0.205,126,sh*0.60)
        self.play={x=sx+rail+8,y=sy+bar,w=sw-2*rail-16,h=sh-bar-8}
        local r=clamp(math.min(rail*0.37,sh*0.24)*self.settings.scale,46,rail*0.46)
        self.pad={x=sx+rail/2,y=sy+sh*0.62,r=r}
        local size=clamp(math.min(rail*0.38,sh*0.18)*self.settings.scale,44,rail*0.48)
        local cx=sx+sw-rail/2
        self.controls={
            {label="Z",caption="CONFIRM",key=90,x=cx-size*0.1,y=sy+sh*0.61,w=size,h=size},
            {label="X",caption="CANCEL",key=88,x=cx-size*0.95,y=sy+sh*0.38,w=size,h=size},
            {label="C",caption="MENU",key=67,x=cx-size*0.1,y=sy+sh*0.14,w=size,h=size},
        }
    else
        -- Portrait and 4:3: game above a separate control deck, never stretched.
        local deck=clamp(sh*0.34,140,sw*0.53)
        self.play={x=sx+8,y=sy+bar,w=sw-16,h=sh-deck-bar-10}
        local r=math.min(sw*0.17,deck*0.36)*self.settings.scale
        self.pad={x=sx+sw*0.23,y=sy+sh-deck/2,r=r}
        local size=clamp(math.min(sw*0.14,deck*0.31)*self.settings.scale,44,sw*0.175)
        self.controls={
            {label="Z",caption="CONFIRM",key=90,x=sx+sw*0.83-size/2,y=sy+sh-deck*0.50,w=size,h=size},
            {label="X",caption="CANCEL",key=88,x=sx+sw*0.65-size/2,y=sy+sh-deck*0.50,w=size,h=size},
            {label="C",caption="MENU",key=67,x=sx+sw*0.74-size/2,y=sy+sh-deck*0.94,w=size,h=size},
        }
    end
    if self.visible and self.settings.southpaw then
        self.pad.x=sx+sw-(self.pad.x-sx)
        for _,b in ipairs(self.controls) do b.x=sx+sw-(b.x-sx)-b.w end
    end
    self.toolbar={
        {label="KEYS",action="keys",x=sx+10,y=sy+4,w=64,h=bar-8},
        {label=self.visible and "HIDE" or "TOUCH",action="visible",x=sx+82,y=sy+4,w=64,h=bar-8},
        {label="PAUSE",action="pause",x=sx+sw-84,y=sy+4,w=74,h=bar-8},
    }
    self:layoutExtras()
    self:layoutMenu()
end

function Touch:layoutExtras()
    self.extraButtons={}
    if not self.extra then return end
    local sx,sy,sw,sh=unpack(self.safe)
    local keys=pages[self.page].keys
    local gap=5
    local maxcols=math.max(3,math.floor((sw-15)/49))
    local maxrows=math.max(1,math.floor((sh-self.bar-52)/49))
    local columns=math.min(maxcols,math.max(sw<540 and 6 or 10,math.ceil(#keys/maxrows)))
    local rows=math.ceil(#keys/columns)
    local cell=clamp((sh-self.bar-52)/rows-gap,24,52)
    local width=math.min(sw-20,columns*70)
    local x=sx+(sw-width)/2
    local y=sy+self.bar+8
    self.panel={x=x-6,y=y-4,w=width+12,h=36+rows*(cell+gap)+8}
    local tabw=(width-2*gap)/3
    for i,p in ipairs(pages) do
        self.extraButtons[#self.extraButtons+1]={label=p.name,action="page",page=i,x=x+(i-1)*(tabw+gap),y=y,w=tabw,h=30,selected=i==self.page}
    end
    local cw=(width-(columns-1)*gap)/columns
    for i,key in ipairs(keys) do
        self.extraButtons[#self.extraButtons+1]={label=key[1],key=key[2],extra=true,
            x=x+((i-1)%columns)*(cw+gap),y=y+36+math.floor((i-1)/columns)*(cell+gap),w=cw,h=cell}
    end
end

function Touch:layoutMenu()
    local sx,sy,sw,sh=unpack(self.safe)
    local width=math.min(sw-32,420)
    local height=math.min(sh-20,390)
    self.menu={x=sx+(sw-width)/2,y=sy+(sh-height)/2,w=width,h=height}
    local m=self.menu
    local row=math.min(44,(height-76)/6)
    self.menuButtons={}
    local function b(label,action,column,line)
        local bw=(width-36)/2
        self.menuButtons[#self.menuButtons+1]={label=label,action=action,x=m.x+12+column*(bw+12),y=m.y+58+line*row,w=bw,h=row-6}
    end
    b("SIZE -","smaller",0,0); b("SIZE +","larger",1,0)
    b("FADE -","fainter",0,1); b("FADE +","stronger",1,1)
    b("LEFT / RIGHT HAND","southpaw",0,2); b("VIBRATION","haptics",1,2)
    b("RESET CONTROLS","reset",0,3); b("EXTRA KEYS","keys",1,3)
    b("RESUME","pause",0,4); b("TOUCH ON / OFF","visible",1,4)
    b("CONTROL TEST","test",0,5)
end

function Touch:setPaused(value)
    self.paused=value
    self:cancel()
    self.input:cancelAll()
    if self.onPause then self.onPause(value) end
end

function Touch:action(button)
    local a=button.action
    if a=="pause" then self:setPaused(not self.paused)
    elseif a=="test" then
        self:setPaused(false)
        if self.onTest then self.onTest() end
    elseif a=="keys" then
        self.extra=not self.extra
        if self.paused then self:setPaused(false) end
        if not self.visible then
            self.visible=true;self:resize(self.w,self.h,self.safe)
        else
            if not self.extra then
                for id,p in pairs(self.pointers) do if p.extra then self:released(id) end end
            end
            self:layoutExtras()
        end
        return
    elseif a=="visible" then self.visible=not self.visible; self.extra=false
    elseif a=="page" then
        -- Keep already-held extra keys captured until release; this permits
        -- modifiers/chords across pages without losing the other thumb's D-pad.
        self.page=button.page
        for _,p in pairs(self.pointers) do if p.extra then p.zone="fixed" end end
        self:layoutExtras()
        return
    elseif a=="smaller" then self.settings.scale=clamp(self.settings.scale-0.1,0.8,1.25)
    elseif a=="larger" then self.settings.scale=clamp(self.settings.scale+0.1,0.8,1.25)
    elseif a=="fainter" then self.settings.opacity=clamp(self.settings.opacity-0.1,0.3,1)
    elseif a=="stronger" then self.settings.opacity=clamp(self.settings.opacity+0.1,0.3,1)
    elseif a=="southpaw" then self.settings.southpaw=not self.settings.southpaw
    elseif a=="haptics" then self.settings.haptics=not self.settings.haptics
    elseif a=="reset" then for k,v in pairs(defaults) do self.settings[k]=v end end
    self:save()
    self:resize(self.w,self.h,self.safe)
end

function Touch:dpadKeys(x,y,previous)
    local p=self.pad
    if not p then return {} end
    local dx,dy=(x-p.x)/p.r,(y-p.y)/p.r
    if math.max(math.abs(dx),math.abs(dy))>1.2 then return {} end
    if dx*dx+dy*dy<0.17^2 then return {} end
    local ratio=0.48
    local horizontal=math.abs(dx)>math.abs(dy)*ratio
    local vertical=math.abs(dy)>math.abs(dx)*ratio
    -- Widen a held diagonal's boundary slightly, reducing thumb-edge chatter.
    if previous and #previous==2 then
        horizontal=math.abs(dx)>math.abs(dy)*0.39
        vertical=math.abs(dy)>math.abs(dx)*0.39
    end
    local keys={}
    if horizontal then keys[#keys+1]=dx<0 and 37 or 39 end
    if vertical then keys[#keys+1]=dy<0 and 38 or 40 end
    return keys
end

function Touch:buttonAt(x,y)
    for _,b in ipairs(self.extraButtons) do if inside(b,x,y) then return b end end
    -- Panel absorbs gaps: tapping between extra keys cannot press underneath.
    if self.extra and self.panel and inside(self.panel,x,y) then return nil end
    if self.visible then
        for _,b in ipairs(self.controls) do if inside(b,x,y) then return b end end
    end
end

function Touch:haptic()
    if not (self.settings.haptics and love and love.system and love.system.vibrate) then return end
    local t=love.timer.getTime()
    if t-self.lastHaptic>0.04 then love.system.vibrate(0.012); self.lastHaptic=t end
end

function Touch:pressed(id,x,y)
    if self.paused then
        for _,b in ipairs(self.menuButtons) do if inside(b,x,y) then self:action(b); return true end end
        return true
    end
    for _,b in ipairs(self.toolbar) do if inside(b,x,y) then self:action(b); return true end end
    local button=self:buttonAt(x,y)
    if button and button.action then self:action(button); return true end
    local pointer
    if button and button.key then pointer={zone="buttons",keys={button.key},extra=button.extra,bounds=button}
    elseif self.extra and self.panel and inside(self.panel,x,y) then return true
    elseif self.visible and self.pad and math.abs(x-self.pad.x)<=self.pad.r*1.12 and math.abs(y-self.pad.y)<=self.pad.r*1.12 then
        pointer={zone="pad",keys=self:dpadKeys(x,y)}
    end
    if pointer then
        self.pointers[id]=pointer
        self.input:setSource("touch:"..tostring(id),pointer.keys)
        self:haptic()
        return true
    end
    return self.extra and self.panel and inside(self.panel,x,y) or false
end

function Touch:moved(id,x,y)
    local pointer=self.pointers[id]
    if not pointer then return end
    if pointer.zone=="pad" then pointer.keys=self:dpadKeys(x,y,pointer.keys)
    elseif pointer.zone=="fixed" then
        if not inside(pointer.bounds,x,y) then pointer.keys={} end
    else
        local b
        -- A panel opening above an already-held action must not hijack that
        -- finger into a different key. Keep each capture in its original deck.
        for _,candidate in ipairs(pointer.extra and self.extraButtons or self.controls) do
            if inside(candidate,x,y) then b=candidate;break end
        end
        pointer.keys=b and b.key and {b.key} or {}
    end
    self.input:setSource("touch:"..tostring(id),pointer.keys)
end

function Touch:released(id)
    self.pointers[id]=nil
    self.input:setSource("touch:"..tostring(id),{})
end

function Touch:held(key)
    for _,p in pairs(self.pointers) do for _,k in ipairs(p.keys) do if key==k then return true end end end
    return self.input.raw[key]==true or self.input.logical[self.input.mapping[key] or key]==true
end

function Touch:draw()
    local g=love.graphics
    g.push("all")
    if not self.font then self.font=g.newFont(13) end
    if not self.largeFont then self.largeFont=g.newFont(25) end
    if not self.captionFont then self.captionFont=g.newFont(9) end
    g.setFont(self.font)
    local opacity=self.settings.opacity
    local function button(b)
        local held=b.key and self:held(b.key) or b.selected
        g.setColor(held and 0.35 or 0.08,held and 0.65 or 0.10,held and 0.63 or 0.13,opacity)
        g.rectangle("fill",b.x,b.y,b.w,b.h,8,8)
        g.setLineWidth(held and 2 or 1)
        g.setColor(held and 0.76 or 0.38,held and 1 or 0.43,held and 0.94 or 0.48,opacity)
        g.rectangle("line",b.x+0.5,b.y+0.5,b.w-1,b.h-1,8,8)
        g.setColor(0.96,0.96,0.95,opacity)
        g.setFont(b.caption and self.largeFont or self.font)
        g.printf(b.label,b.x,b.y+(b.h-g.getFont():getHeight())/2-(b.caption and 6 or 0),b.w,"center")
        if b.caption then
            g.setFont(self.captionFont); g.setColor(0.67,0.7,0.74,opacity)
            g.printf(b.caption,b.x,b.y+b.h-13,b.w,"center")
        end
    end
    if self.visible then
        local p=self.pad
        g.setColor(0.07,0.09,0.12,opacity)
        g.rectangle("fill",p.x-p.r,p.y-p.r,p.r*2,p.r*2,p.r*0.25)
        local d=p.r*0.59
        local axes={{37,-d,0,-1,0},{39,d,0,1,0},{38,0,-d,0,-1},{40,0,d,0,1}}
        for _,a in ipairs(axes) do
            local active=self:held(a[1]); local x,y=p.x+a[2],p.y+a[3]; local s=p.r*0.20
            g.setColor(active and 0.7 or 0.4,active and 1 or 0.45,active and 0.92 or 0.51,opacity)
            if a[4]~=0 then g.polygon("fill",x+a[4]*s,y,x-a[4]*s,y-s,x-a[4]*s,y+s)
            else g.polygon("fill",x,y+a[5]*s,x-s,y-a[5]*s,x+s,y-a[5]*s) end
        end
        g.setColor(0.2,0.24,0.29,opacity);g.circle("fill",p.x,p.y,p.r*0.11)
        for _,b in ipairs(self.controls) do button(b) end
    end
    if self.extra then
        local p=self.panel
        g.setColor(0.025,0.03,0.04,0.97);g.rectangle("fill",p.x,p.y,p.w,p.h,8)
        for _,b in ipairs(self.extraButtons) do button(b) end
    end
    for _,b in ipairs(self.toolbar) do button(b) end
    if self.paused then
        g.setColor(0,0,0,0.83);g.rectangle("fill",0,0,self.w,self.h)
        local m=self.menu
        g.setColor(0.055,0.065,0.085,1);g.rectangle("fill",m.x,m.y,m.w,m.h,12)
        g.setColor(1,1,1,1);g.setFont(self.largeFont);g.printf("PAUSED",m.x,m.y+15,m.w,"center")
        for _,b in ipairs(self.menuButtons) do button(b) end
    end
    g.pop()
end
return Touch
