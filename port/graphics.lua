-- Pixel-art renderer and the drawing builtins used by the converted events.
-- Draw events run once per GAME tick, because this game also updates logic in
-- Draw. love.draw only presents the cached canvas; 120 Hz phones must not run
-- dialogue/battle logic four times faster than 30 Hz GameMaker rooms.
local Graphics={}
-- Sprite sizes are reported in original-game (canvas) pixels through one
-- accessor, so a cropped Undertale export and an uncropped Yellow sprite answer
-- in the same units (see port/assetcompat.lua and spec section 12).
local AssetCompat=require("port.assetcompat")
local function clamp(n,a,b) return math.max(a,math.min(b,n)) end
local function rgba(color,alpha)
    color=math.floor(color or 16777215)%16777216
    return (color%256)/255,(math.floor(color/256)%256)/255,(math.floor(color/65536)%256)/255,clamp(alpha or 1,0,1)
end
local function rgb(r,g,b) return math.floor(clamp(r,0,255))+math.floor(clamp(g,0,255))*256+math.floor(clamp(b,0,255))*65536 end
Graphics.rgba=rgba

function Graphics.install(R)
    local B=R.builtins
    local g=love and love.graphics
    if R.options.headless then g=nil end
    local state={color=16777215,alpha=1,font=-1,halign=0,valign=0,precision=32,images={},quads={},surfaces={},nextSurface=1,nextSprite=40000}
    R.graphicsState=state
    -- GameMaker Studio 2 draws its GUI layer in its own coordinate space, sized
    -- by display_set_gui_size and stretched over the presented image. 0 means
    -- "follow the display", which is Studio 2's own default.
    R.gui={width=0,height=0}
    R.applicationSurfaceDraw=true
    R.drawLog={}
    local function log(kind,...)
        if R.options.trace and #R.drawLog<20000 then R.drawLog[#R.drawLog+1]={kind,...} end
    end
    local function color(c,a) if g then g.setColor(rgba(c or state.color,a or state.alpha)) end end
    local function image(file)
        if not g then return nil end
        if state.images[file] then return state.images[file] end
        local ok,result=pcall(g.newImage,file)
        if not ok then R:warn("image:"..file,"Image unavailable: "..file..": "..tostring(result));return nil end
        result:setFilter("nearest","nearest")
        state.images[file]=result
        return result
    end
    local function quad(file,x,y,w,h,iw,ih)
        local key=file..":"..x..":"..y..":"..w..":"..h
        if not state.quads[key] then state.quads[key]=g.newQuad(x,y,w,h,iw,ih) end
        return state.quads[key]
    end
    local function partImage(img,key,left,top,width,height,x,y,sx,sy,tint,alpha,transform)
        if not img or width<=0 or height<=0 or sx==0 or sy==0 then return end
        local iw,ih=img:getDimensions()
        local l,t=math.max(0,left),math.max(0,top)
        local r,b=math.min(iw,left+width),math.min(ih,top+height)
        if r<=l or b<=t then return end
        local q=key and quad(key,l,t,r-l,b-t,iw,ih) or (g and g.newQuad(l,t,r-l,b-t,iw,ih))
        if not q then return end
        color(tint,alpha)
        if transform and (transform.mirror or transform.flip or transform.rotate) then
            -- GameMaker's tile transform: mirror (horizontal) and flip
            -- (vertical) about the cell centre, then a 90 degree clockwise
            -- rotation, which swaps the drawn box of a non-square tile.
            local w,h=(r-l)*math.abs(sx),(b-t)*math.abs(sy)
            if transform.rotate then w,h=h,w end
            g.draw(img,q,x+w/2,y+h/2,transform.rotate and math.rad(90) or 0,
                transform.mirror and -math.abs(sx) or math.abs(sx),
                transform.flip and -math.abs(sy) or math.abs(sy),(r-l)/2,(b-t)/2)
        else
            g.draw(img,q,x+(l-left)*sx,y+(t-top)*sy,0,sx,sy)
        end
        if not key and q.release then q:release() end
    end
    local function part(file,left,top,width,height,x,y,sx,sy,tint,alpha,transform)
        if width<=0 or height<=0 or sx==0 or sy==0 then return end
        partImage(image(file),file,left,top,width,height,x,y,sx,sy,tint,alpha,transform)
    end
    local function sprite(E,index,sub,x,y,sx,sy,angle,tint,alpha,crop)
        -- Merged builds draw Yellow's player body as Frisk (port/frisk.lua);
        -- the remap is pixels-only, so gameplay reads stay on the same record.
        local requested=index
        if R.spriteForDraw then index=R.spriteForDraw(index) end
        local s=R.assets.sprites[index]
        if not s then
            if index>=0 then R:warn("sprite:"..tostring(index),"Unresolved sprite ID "..tostring(index).."; see conversion-report.json.") end
            return
        end
        if #s.frames==0 then return end
        if sub<0 then sub=E and E.image_index or 0 end
        -- Render anchor (piece 6b, spec section 12). A pixels-only remap draws
        -- another game's sprite in place of the requested one, and the two
        -- games put origins in different places (Frisk's canvas corner,
        -- Clover's body centre). The replacement stands on the requested
        -- sprite's feet -- the canvas bottom centre the depth rule already
        -- sorts by -- and at the same phase of its own animation cycle.
        local from=requested~=index and R.assets.sprites[requested] or nil
        local ax,ay=0,0
        local originX,originY=s.xorig,s.yorigin
        if from then
            ax,ay=AssetCompat.anchor(from,s)
            originX,originY=from.xorig-ax,from.yorigin-ay
            sub=AssetCompat.remapFrame(from,s,sub)
        end
        -- Frame selection (piece 6b, spec section 12): GameMaker draws the
        -- sub-image the index rounds *down* to -- "The value can have a
        -- fractional part. In this case it is always rounded down to obtain
        -- the subimage that is drawn" (GameMaker manual, image_index), and
        -- YoYo's own runner truncates it the same way in Sprite.Draw. It never
        -- blends two frames. Piece 3 crossfaded the fraction instead, which
        -- drew every animating sprite in both worlds as two superimposed
        -- frames (walk cycles run at image_speed 0.2 or 1/3, so almost every
        -- step was fractional) and let the boat cover's ever-growing cc paint
        -- its next frame opaque once cc passed 2. One frame per draw.
        local n=#s.frames
        local base=math.floor(sub)%n
        local file=s.frames[base+1]
        -- The checkout exported some sprite images cropped to their collision
        -- bbox while events keep drawing in original canvas coordinates, so
        -- the crop offset is added back here (see port/sprite_offsets.json and
        -- tools/recover_sprite_offsets.py). xorig/yorigin stay canvas values.
        local ox,oy=s.ox or 0,s.oy or 0
        -- Provenance, for the duplicate-draw gate (spec §8): the sprite ID this
        -- draw actually resolved to -- after the Frisk remap, so an Undertale
        -- and a Yellow asset that share a name are still told apart -- and the
        -- instance that asked for it. R.drawOwner is set by the instance draw
        -- loops below; a draw a particle system or a background makes has none.
        local owner=R.drawOwner
        -- Shader-guarded redraw (spec §8). Yellow draws an actor and then asks
        -- scr_draw_palette_shader to paint the very same pixels again under
        -- sh_palette_swap, whose entire job is to recolour them; with no shader
        -- applied (port/yellow_studio.lua reports them and keeps the original
        -- colours) that second draw is the base sprite drawn twice. A draw that
        -- repeats the previous sprite of the same instance with the same frame,
        -- position, scale, angle, tint and alpha while an unconverted shader is
        -- set is a duplicate and is not issued: the pixels are already correct.
        -- Everything else still draws, so a shader-guarded draw that is the
        -- only draw of that sprite is kept and nothing disappears. The blend
        -- state counts too: the same pixels added on top of themselves are a
        -- glow the original asked for (port/yellow_studio.lua records every
        -- gpu_set_blendmode in R.gpuState), not a duplicate, so a repeat is
        -- dropped only when the blend state did not change either.
        local previous=state.lastSprite
        local blendState=false
        if R.gpuState then
            blendState=R.gpuState.blendmode or -1
            local ext=R.gpuState.blendmode_ext
            if ext then blendState=tostring(blendState)..":"..tostring(ext[1])..":"..tostring(ext[2]) end
        end
        if R.shaderState and R.shaderState.active and previous
           and previous.index==index and previous.base==base
           and previous.x==x and previous.y==y and previous.sx==sx and previous.sy==sy
           and previous.angle==angle and previous.tint==tint and previous.alpha==alpha
           and previous.owner==owner and previous.blendState==blendState then
            R.shaderRedraws=(R.shaderRedraws or 0)+1
            log("sprite-suppressed",s.name,index,owner and owner.id or -1)
            R:warn("shader-redraw",
                "Shaders are not converted by this port, so an unconverted shader's redraw of a "
                .. "sprite it cannot recolour is not repeated: the sprite keeps its original colours "
                .. "and is drawn once (spec §8).")
            return
        end
        state.lastSprite={index=index,base=base,x=x,y=y,sx=sx,sy=sy,angle=angle,
            tint=tint,alpha=alpha,owner=owner,blendState=blendState}
        -- Fields 13/14 stay nil: they carried piece 3's crossfade frame and
        -- amount, and GameMaker draws one sub-image (see frame selection
        -- above). Fields 17/18: the canvas point of the drawn sprite placed at
        -- (x, y) -- its own origin, or the anchored origin of a remapped draw.
        log("sprite",s.name,base,x,y,sx,sy,angle,tint,alpha,ox,oy,nil,nil,
            index,owner and owner.id or -1,originX,originY)
        if not g then return end
        local function layer(file_,alpha_)
            -- A part draw names a region of the requested sprite's canvas;
            -- the anchor moves it onto the replacement's canvas.
            if crop then part(file_,crop[1]-ax-ox,crop[2]-ay-oy,crop[3],crop[4],x,y,sx,sy,tint,alpha_)
            else
                local img=image(file_);if not img then return end
                color(tint,alpha_);g.draw(img,x,y,-math.rad(angle),sx,sy,originX-ox,originY-oy)
            end
        end
        layer(file,alpha)
    end
    local function backgroundPart(asset,left,top,width,height,x,y,sx,sy,tint,alpha,transform)
        if not asset then return end
        log("background",asset.name,x,y,left,top,width,height,sx,sy)
        part(asset.file,left,top,width,height,x,y,sx,sy,tint,alpha,transform)
    end
    function R:fillRectangle(x1,y1,x2,y2,tint,alpha)
        log("rectangle",x1,y1,x2,y2,0,tint,alpha)
        if not g then return end
        color(tint,alpha)
        g.rectangle("fill",math.min(x1,x2),math.min(y1,y2),math.abs(x2-x1)+1,math.abs(y2-y1)+1)
    end
    local yellowDrawable=require("port.yellow_graphics").install(R,sprite,backgroundPart)

    -- Particle shapes. Sprite particles use the sprite's own pixels exactly;
    -- the fourteen built-in shapes below are this port's documented
    -- approximation of GameMaker's particle glyphs, sized in pixels at size 1
    -- (the particle's own size and scale multiply them). Yellow's Snowdin
    -- snow, smoke, embers, glass shards and battle backgrounds are all sprite
    -- particles, so they are exact; the shapes only carry battle and ambient
    -- effects whose systems this port does not otherwise certify.
    local function particleShape(kind,x,y,size,sx,sy,angle,tint,alpha)
        if not g or size<=0 then return end
        color(tint,alpha)
        local radians=math.rad(angle or 0)
        local cosA,sinA=math.cos(radians),math.sin(radians)
        local function point(dx,dy)
            -- GameMaker angles run counterclockwise from east; the screen's y
            -- axis points down, so the rotated y is negated on the way out.
            return x+dx*cosA-dy*sinA,y-(dx*sinA+dy*cosA)
        end
        local function poly(points)
            local flat={}
            for _,p in ipairs(points) do flat[#flat+1],flat[#flat+2]=point(p[1],p[2]) end
            g.polygon("fill",flat)
        end
        local function seg(x1,y1,x2,y2)
            local ax,ay=point(x1,y1)
            local bx,by=point(x2,y2)
            g.line(ax,ay,bx,by)
        end
        if kind==0 then
            local w,h=math.max(1,math.floor(size*sx+0.5)),math.max(1,math.floor(size*sy+0.5))
            g.rectangle("fill",x-w/2,y-h/2,w,h)
        elseif kind==1 or kind==7 or kind==10 or kind==11 or kind==12 then
            local base=kind==1 and 3 or kind==7 and 4 or kind==10 and 8 or 6
            local radius=base*size*(sx+sy)/2
            if radius>=0.5 then g.circle("fill",x,y,radius,16) end
        elseif kind==2 then
            local h=3*size
            poly({{-h*sx,-h*sy},{h*sx,-h*sy},{h*sx,h*sy},{-h*sx,h*sy}})
        elseif kind==3 then
            g.setLineWidth(math.max(1,math.floor(size*sy+0.5)))
            local h=8*size*sx
            seg(-h,0,h,0)
            g.setLineWidth(1)
        elseif kind==4 then
            local outer,inner=5*size,2*size
            local points={}
            for i=0,9 do
                local r=i%2==0 and outer or inner
                local a=math.pi/2+i*math.pi/5
                points[#points+1]={math.cos(a)*r*sx,math.sin(a)*r*sy}
            end
            poly(points)
        elseif kind==5 then
            local radius=4*size*(sx+sy)/2
            if radius>=0.5 then g.circle("line",x,y,radius,24) end
        elseif kind==6 then
            local radius=4*size*(sx+sy)/2
            if radius>=0.5 then
                g.setLineWidth(math.max(2,math.floor(radius/3+0.5)))
                g.circle("line",x,y,radius,24)
                g.setLineWidth(1)
            end
        elseif kind==8 then
            local arm=6*size
            seg(-arm*sx,0,arm*sx,0)
            seg(0,-arm*sy,0,arm*sy)
            g.circle("fill",x,y,math.max(1,2*size*(sx+sy)/2),12)
        elseif kind==9 then
            local arm=3*size
            seg(-arm*sx,0,arm*sx,0)
            seg(0,-arm*sy,0,arm*sy)
        elseif kind==13 then
            local arm=3*size
            for i=0,2 do
                local a=i*math.pi/3
                local dx,dy=math.cos(a)*arm,math.sin(a)*arm
                seg(-dx*sx,-dy*sy,dx*sx,dy*sy)
            end
        end
    end
    local function particleSprite(index,sub,x,y,sx,sy,angle,tint,alpha)
        -- The shared sprite() helper would remap Clover poses to Frisk and log
        -- every flake; particles need neither, so this draws quietly instead.
        local s=R.assets.sprites[index]
        if not s then
            if index>=0 then R:warn("sprite:"..tostring(index),"Unresolved sprite ID "..tostring(index).."; see conversion-report.json.") end
            return
        end
        if #s.frames==0 then return end
        local file=s.frames[math.floor(sub)%#s.frames+1]
        if not g then return end
        local img=image(file)
        if not img then return end
        color(tint,alpha)
        g.draw(img,x,y,-math.rad(angle or 0),sx,sy,s.xorig,s.yorigin)
    end
    local function drawParticles(sys,view,depth)
        local list=sys.particles
        local total=#list
        if total==0 then return end
        local drawn=0
        local prevMode,prevAlpha=nil,nil
        if g and g.getBlendMode then prevMode,prevAlpha=g.getBlendMode() end
        local blendAdditive=nil
        local first,last,step=1,total,1
        if sys.oldtonew==false then first,last,step=total,1,-1 end
        for i=first,last,step do
            local p=list[i]
            local x,y,tint,alpha,size,angle,sprite,frame,shape,sx,sy,additive=R:particleAppearance(sys,p)
            if size>0 and alpha>0
                and x>view.x-64 and x<view.x+view.w+64
                and y>view.y-64 and y<view.y+view.h+64 then
                drawn=drawn+1
                if g then
                    if additive~=blendAdditive then
                        blendAdditive=additive
                        if additive then g.setBlendMode("add","premultiplied")
                        else g.setBlendMode("alpha","alphamultiply") end
                    end
                    if sprite~=nil and sprite>=0 then
                        particleSprite(sprite,frame,x,y,size*sx,size*sy,angle,tint,alpha)
                    elseif shape~=nil and shape>=0 then
                        particleShape(shape,x,y,size,sx,sy,angle,tint,alpha)
                    end
                end
            end
        end
        if g and blendAdditive~=nil and prevMode then g.setBlendMode(prevMode,prevAlpha) end
        if drawn>0 then log("particles",sys.id,drawn,depth) end
    end
    -- Manual draw for part_system_drawit: the system draws at the point the
    -- Draw event calls it, outside depth order, exactly as GameMaker does.
    function R:drawParticlesNow(id)
        local sys=self.particles and self.particles.systems[math.floor(id or -1)]
        if not sys or #sys.particles==0 then return end
        if not self:particleLayerVisible(sys) then return end
        local views=self:views()
        local view=views[1]
        for _,v in ipairs(views) do
            if v.index==self.vars.view_current then view=v break end
        end
        drawParticles(sys,view,self:particleDepth(sys))
    end
    B.draw_self=function(E)
        -- Studio 2's draw_self is exactly what this renderer does for an
        -- instance whose object has no Draw event of its own.
        local inst=E and E._self
        if not inst then return end
        local v=inst.v
        -- draw_self is the one draw that can name its owner exactly, even when
        -- an event draws another instance's sprite: the provenance recorded for
        -- this draw is the instance whose pixels were drawn, not the event that
        -- asked for them.
        local previous=R.drawOwner
        R.drawOwner=inst
        sprite(E,v.sprite_index,v.image_index,v.x,v.y,v.image_xscale,v.image_yscale,
            v.image_angle,v.image_blend,v.image_alpha)
        R.drawOwner=previous
    end
    -- Display, window and GUI size. Studio 2 keeps a GUI layer of its own size
    -- and stretches it over the presented image, so display_set_gui_size(320,240)
    -- on a 1920x1440 surface draws GUI coordinates at 320x240 and scales them.
    local function displaySize()
        if g then return g.getDimensions() end
        return R.displayWidth or 0,R.displayHeight or 0
    end
    function R:guiSize(displayWidth,displayHeight)
        if self.gui.width>0 and self.gui.height>0 then return self.gui.width,self.gui.height end
        return displayWidth or self.displayWidth or 0,displayHeight or self.displayHeight or 0
    end
    B.display_get_width=function() return (displaySize()) end
    B.display_get_height=function() return select(2,displaySize()) end
    B.window_get_width=B.display_get_width
    B.window_get_height=B.display_get_height
    B.display_get_gui_width=function() return (R:guiSize(displaySize())) end
    B.display_get_gui_height=function() return select(2,R:guiSize(displaySize())) end
    B.display_set_gui_size=function(_,w,h)
        w,h=math.floor(w or 0),math.floor(h or 0)
        -- A non-positive size is Studio 2's "back to the display size".
        if w<=0 or h<=0 then R.gui.width,R.gui.height=0,0 else R.gui.width,R.gui.height=w,h end
    end
    B.display_set_gui_maximize=function(_,scale)
        local width,height=displaySize()
        scale=(type(scale)=="number" and scale>0) and scale or 1
        R.gui.width,R.gui.height=width/scale,height/scale
    end
    local function surfaceCanvas(id)
        if id==0 or id==R.vars.application_surface then return state.surfaces[0] end
        return state.surfaces[id]
    end
    B.surface_exists=function(_,id)
        if id==0 or id==R.vars.application_surface then return R.num(R.applicationSurfaceDraw or surfaceCanvas(0)~=nil) end
        return R.num(surfaceCanvas(id)~=nil)
    end
    B.surface_get_width=function(_,id)
        local canvas=surfaceCanvas(id)
        if canvas and canvas.getWidth then return canvas:getWidth() end
        if id==0 or id==R.vars.application_surface then return R.displayWidth or 0 end
        return 0
    end
    B.surface_get_height=function(_,id)
        local canvas=surfaceCanvas(id)
        if canvas and canvas.getHeight then return canvas:getHeight() end
        if id==0 or id==R.vars.application_surface then return R.displayHeight or 0 end
        return 0
    end
    B.surface_resize=function(_,id,w,h)
        w,h=math.max(1,math.floor(w or 1)),math.max(1,math.floor(h or 1))
        if id==0 or id==R.vars.application_surface then
            -- This port presents the room's viewport union fitted to the window,
            -- so a larger application surface would only supersample the same
            -- image. The request is recorded and reported, never silently dropped.
            R.applicationSurfaceSize={width=w,height=h}
            R:warn("application-surface-resize","surface_resize(application_surface, "..w..", "..h..
                ") is recorded; this port scales the room's viewport union to the window instead.")
            return
        end
        local canvas=surfaceCanvas(id)
        if canvas and canvas.resize then canvas:resize(w,h) end
    end
    B.surface_free=function(_,id)
        if id==0 or id==R.vars.application_surface then
            R:warn("application-surface-free","The application surface belongs to the port's renderer and is not freed.")
            return
        end
        local canvas=state.surfaces[id]
        if canvas and canvas.release then canvas:release() end
        state.surfaces[id]=nil
    end
    B.surface_set_target=function(_,id) local canvas=surfaceCanvas(id);if g and canvas then g.setCanvas(canvas) end end
    B.surface_reset_target=function() if g then g.setCanvas(state.surfaces[0] or nil) end end
    B.application_surface_draw_enable=function(_,enable) R.applicationSurfaceDraw=R.truth(enable) end
    B.application_surface_is_enabled=function() return R.num(R.applicationSurfaceDraw) end
    B.draw_surface=function(_,id,x,y) partImage(surfaceCanvas(id),"__surface_"..tostring(id),0,0,
        B.surface_get_width(nil,id),B.surface_get_height(nil,id),x,y,1,1,16777215,state.alpha) end
    B.draw_surface_ext=function(_,id,x,y,sx,sy,angle,tint,alpha)
        local canvas=surfaceCanvas(id)
        if not canvas then return end
        log("surface",tostring(id),x,y,sx,sy)
        if not g then return end
        color(tint,alpha);g.draw(canvas,x,y,-math.rad(angle or 0),sx,sy)
    end
    B.draw_surface_part=function(_,id,l,t,w,h,x,y) partImage(surfaceCanvas(id),"__surface_"..tostring(id),l,t,w,h,x,y,1,1,16777215,state.alpha) end
    B.draw_surface_part_ext=function(_,id,l,t,w,h,x,y,sx,sy,tint,alpha)
        log("surface",tostring(id),x,y,sx,sy)
        partImage(surfaceCanvas(id),"__surface_"..tostring(id),l,t,w,h,x,y,sx,sy,tint,alpha)
    end
    B.draw_sprite=function(E,index,sub,x,y) sprite(E,index,sub,x,y,1,1,0,16777215,state.alpha) end
    B.draw_sprite_ext=function(E,index,sub,x,y,sx,sy,angle,tint,alpha) sprite(E,index,sub,x,y,sx,sy,angle,tint,alpha) end
    B.draw_sprite_part=function(E,index,sub,l,t,w,h,x,y) sprite(E,index,sub,x,y,1,1,0,16777215,state.alpha,{l,t,w,h}) end
    B.draw_sprite_part_ext=function(E,index,sub,l,t,w,h,x,y,sx,sy,tint,alpha) sprite(E,index,sub,x,y,sx,sy,0,tint,alpha,{l,t,w,h}) end
    -- Stretching scales the *canvas* over w x h (piece 6d, spec section 12
    -- "scaling"): GameMaker stretches the whole sub-image, whose size is the
    -- original canvas, with the origin ignored. The canvas region is a part
    -- draw, so a cropped export's recovered offset still places its pixels.
    local function stretched(E,index,sub,x,y,w,h,tint,alpha)
        local s=R.assets.sprites[index]
        local cw,ch=AssetCompat.width(s),AssetCompat.height(s)
        if s and cw>0 and ch>0 then sprite(E,index,sub,x,y,w/cw,h/ch,0,tint,alpha,{0,0,cw,ch}) end
    end
    R.drawSpriteStretched=stretched
    B.draw_sprite_stretched=function(E,index,sub,x,y,w,h) stretched(E,index,sub,x,y,w,h,16777215,state.alpha) end
    -- The original canvas size, not the exported (possibly cropped) pixels:
    -- Undertale's own events size enemy attacks and reels from these numbers, and
    -- the canvas is what they were written against (see port/assetcompat.lua).
    B.sprite_get_width=function(_,index) return AssetCompat.spriteWidth(R,index) end
    B.sprite_get_height=function(_,index) return AssetCompat.spriteHeight(R,index) end
    B.sprite_get_name=function(_,index) local s=R.assets.sprites[index];return s and s.name or "<undefined>" end
    B.sprite_exists=function(_,index) return R.num(R.assets.sprites[index]~=nil) end
    B.sprite_delete=function(_,index)
        local s=R.assets.sprites[index]
        if s then
            for _,file in ipairs(s.frames) do
                if state.images[file] then state.images[file]:release();state.images[file]=nil end
                if R.maskData then R.maskData[file]=nil end
            end
            R.assets.sprites[index]=nil
        end
    end
    B.sprite_replace=function(_,index,file,number,removeback,smooth,ox,oy)
        if not (love and love.filesystem and love.filesystem.getInfo(file,"file")) then
            R:unsupported("sprite_replace", "Missing external image "..file..". The checkout does not supply the external/ resource directory.")
        end
        if file:lower():match("%.gif$") then R:unsupported("sprite_replace", "Animated GIF import requires extracting its real frames before conversion: "..file) end
        local img=image(file);if not img then return -1 end
        if number~=1 and number~=0 then R:unsupported("sprite_replace","Horizontal sprite strips need pre-extracted frames: "..file) end
        local w,h=img:getDimensions()
        R.assets.sprites[index]={name=file,frames={file},width=w,height=h,xorig=ox,yorigin=oy,
            bbox_left=0,bbox_top=0,bbox_right=w-1,bbox_bottom=h-1,colkind=0,coltolerance=0,sepmasks=0}
        if R.truth(removeback) then R:warn("sprite-removeback","Dynamic sprite background-color removal is not implemented; supplied alpha is retained.") end
        return index
    end
    B.sprite_collision_mask=function(_,index,separate,mode,left,top,right,bottom,kind,tolerance)
        local s=R.assets.sprites[index]
        if s then s.sepmasks=separate;s.bboxmode=mode;s.bbox_left=left;s.bbox_top=top;s.bbox_right=right;s.bbox_bottom=bottom;s.colkind=kind;s.coltolerance=tolerance end
    end
    B.surface_create=function(_,w,h)
        local id=state.nextSurface;state.nextSurface=id+1
        state.surfaces[id]=g and g.newCanvas(math.max(1,math.floor(w)),math.max(1,math.floor(h))) or {w=w,h=h}
        return id
    end
    B.sprite_create_from_surface=function(_,surface,x,y,w,h,removeback,smooth,ox,oy)
        if not g then return -1 end
        local canvas=state.surfaces[surface]
        if not canvas then return -1 end
        local current=g.getCanvas();g.setCanvas()
        local data=canvas:newImageData(1,1,math.floor(x),math.floor(y),math.floor(w),math.floor(h))
        g.setCanvas(current)
        local id=state.nextSprite;state.nextSprite=id+1
        local file="__surface_"..id
        state.images[file]=g.newImage(data);state.images[file]:setFilter("nearest","nearest")
        R.maskData[file]=data
        R.assets.sprites[id]={name=file,frames={file},width=w,height=h,xorig=ox,yorigin=oy,bbox_left=0,bbox_top=0,bbox_right=w-1,bbox_bottom=h-1,colkind=0,coltolerance=0,sepmasks=0}
        return id
    end
    B.background_add=function(_,file,removeback,smooth)
        if not (love and love.filesystem and love.filesystem.getInfo(file,"file")) then
            R:warn("background-file:"..file,"Optional background is absent: "..file);return -1
        end
        local img=image(file);if not img then return -1 end
        local id=state.nextSprite;state.nextSprite=id+1
        local w,h=img:getDimensions();R.assets.backgrounds[id]={name=file,file=file,width=w,height=h};return id
    end
    B.draw_background=function(_,index,x,y)
        local b=R.assets.backgrounds[index]
        if not b then R:warn("background:"..tostring(index),"Unresolved background ID "..tostring(index));return end
        log("background",b.name,x,y,0,0,b.width,b.height,1,1)
        part(b.file,0,0,b.width,b.height,x,y,1,1,16777215,state.alpha)
    end
    B.draw_background_part_ext=function(_,index,l,t,w,h,x,y,sx,sy,tint,alpha)
        local b=R.assets.backgrounds[index]
        if b then log("background",b.name,x,y,l,t,w,h,sx,sy);part(b.file,l,t,w,h,x,y,sx,sy,tint,alpha)
        elseif index>=0 then R:warn("background:"..index,"Unresolved background ID "..index) end
    end
    B.draw_set_color=function(_,v) state.color=v end
    B.draw_set_alpha=function(_,v) state.alpha=clamp(v,0,1) end
    B.draw_set_font=function(_,v) state.font=v end
    B.draw_set_halign=function(_,v) state.halign=v end
    B.draw_set_valign=function(_,v) state.valign=v end
    B.draw_set_circle_precision=function(_,v) state.precision=clamp(math.floor(v),4,128) end
    B.make_color_rgb=function(_,r,gg,b) return rgb(r,gg,b) end
    B.merge_color=function(_,a,b,amount)
        local ar,ag,ab=rgba(a);local br,bg,bb=rgba(b);amount=clamp(amount,0,1)
        return rgb((ar+(br-ar)*amount)*255,(ag+(bg-ag)*amount)*255,(ab+(bb-ab)*amount)*255)
    end
    B.make_color_hsv=function(_,h,s,v)
        h=(h%256)/255*6;s=clamp(s,0,255)/255;v=clamp(v,0,255)/255
        local c=v*s;local x=c*(1-math.abs(h%2-1));local m=v-c;local r,gg,b=0,0,0
        if h<1 then r,gg=c,x elseif h<2 then r,gg=x,c elseif h<3 then gg,b=c,x elseif h<4 then gg,b=x,c elseif h<5 then r,b=x,c else r,b=c,x end
        return rgb((r+m)*255,(gg+m)*255,(b+m)*255)
    end
    local function lines(text)
        text=tostring(text):gsub("\\#","\1"):gsub("#","\n"):gsub("\1","#")
        local out={};for line in (text.."\n"):gmatch("([^\n]*)\n") do out[#out+1]=line end;return out
    end
    local function font() return R.assets.fonts[state.font] end
    local function measureLine(line,f)
        if not f then return #line*8 end
        local w=0;for i=1,#line do local glyph=f.glyphs[line:byte(i)] or f.glyphs[63];w=w+(glyph and glyph.shift or 0) end;return w
    end
    B.string_width=function(_,text) local max=0;for _,line in ipairs(lines(text)) do max=math.max(max,measureLine(line,font())) end;return max end
    B.string_height=function(_,text) local f=font();return #lines(text)*(f and f.height or 16) end
    local function text(x,y,str,sx,sy,angle,alpha,wrapped,sep)
        sx,sy,angle=sx or 1,sy or 1,angle or 0
        local f=font();local ls=wrapped or lines(str);local height=f and f.height or 16
        local spacing=sep and sep>=0 and sep or height
        log("text",tostring(str),x,y,state.font)
        if not g then return end
        g.push();g.translate(x,y);g.rotate(-math.rad(angle));g.scale(sx,sy)
        color(state.color,alpha or state.alpha)
        local yy=state.valign==1 and -#ls*spacing/2 or state.valign==2 and -#ls*spacing or 0
        for _,line in ipairs(ls) do
            local width=measureLine(line,f)
            local xx=state.halign==1 and -width/2 or state.halign==2 and -width or 0
            if f then
                for i=1,#line do
                    local ch=line:byte(i);local glyph=f.glyphs[ch] or f.glyphs[63]
                    if glyph then
                        if ch~=32 and glyph.w>0 and glyph.h>0 then part(f.file,glyph.x,glyph.y,glyph.w,glyph.h,xx+glyph.offset,yy,1,1,state.color,alpha or state.alpha) end
                        xx=xx+glyph.shift
                    end
                end
            else
                if not state.fallback then state.fallback=g.newFont(14) end
                g.setFont(state.fallback);g.print(line,xx,yy)
            end
            yy=yy+spacing
        end
        g.pop()
    end
    B.draw_text=function(_,x,y,str) text(x,y,str) end
    B.draw_text_transformed=function(_,x,y,str,sx,sy,angle) text(x,y,str,sx,sy,angle) end
    B.draw_text_transformed_color=function(_,x,y,str,sx,sy,angle,c1,c2,c3,c4,alpha)
        local prior=state.color;state.color=c1
        if c1~=c2 or c1~=c3 or c1~=c4 then R:warn("text-gradient","Gradient text currently uses its first corner color.") end
        text(x,y,str,sx,sy,angle,alpha);state.color=prior
    end
    B.draw_text_ext=function(_,x,y,str,sep,width)
        local wrapped={}
        for _,line in ipairs(lines(str)) do
            local current=""
            for word in line:gmatch("%S+") do
                local next=current=="" and word or current.." "..word
                if current~="" and measureLine(next,font())>width then wrapped[#wrapped+1]=current;current=word else current=next end
            end
            wrapped[#wrapped+1]=current
        end
        text(x,y,str,1,1,0,state.alpha,wrapped,sep)
    end
    local function rectangle(x1,y1,x2,y2,outline,radius)
        log("rectangle",x1,y1,x2,y2,outline)
        if g then
            color();g.setLineWidth(1)
            local x,y=math.min(x1,x2),math.min(y1,y2)
            local w,h=math.abs(x2-x1)+1,math.abs(y2-y1)+1
            if R.truth(outline) then g.rectangle("line",x+0.5,y+0.5,w-1,h-1,radius or 0,radius or 0)
            else g.rectangle("fill",x,y,w,h,radius or 0,radius or 0) end
        end
    end
    B.draw_rectangle=function(_,...) rectangle(...) end
    B.draw_roundrect=function(_,x1,y1,x2,y2,outline) rectangle(x1,y1,x2,y2,outline,4) end
    B.draw_circle=function(_,x,y,r,outline)
        log("circle",x,y,r,outline);if g and r>=0 then color();g.setLineWidth(1);g.circle(R.truth(outline) and "line" or "fill",x,y,r,state.precision) end
    end
    local function vertex(x,y,c,a) local r,gg,b,alpha=rgba(c,a);return {x,y,0,0,r,gg,b,alpha} end
    local function mesh(vertices)
        if not g then return end
        g.setColor(1,1,1,1);local m=g.newMesh(vertices,"fan","stream");g.draw(m);m:release()
    end
    B.draw_rectangle_color=function(_,x1,y1,x2,y2,c1,c2,c3,c4,outline)
        if R.truth(outline) then B.draw_line_color(nil,x1,y1,x2,y1,c1,c2);B.draw_line_color(nil,x2,y1,x2,y2,c2,c4);B.draw_line_color(nil,x2,y2,x1,y2,c4,c3);B.draw_line_color(nil,x1,y2,x1,y1,c3,c1)
        else mesh({vertex(x1,y1,c1,state.alpha),vertex(x2,y1,c2,state.alpha),vertex(x2,y2,c4,state.alpha),vertex(x1,y2,c3,state.alpha)}) end
    end
    B.draw_triangle_color=function(_,x1,y1,x2,y2,x3,y3,c1,c2,c3,outline)
        if R.truth(outline) then B.draw_line_color(nil,x1,y1,x2,y2,c1,c2);B.draw_line_color(nil,x2,y2,x3,y3,c2,c3);B.draw_line_color(nil,x3,y3,x1,y1,c3,c1)
        else mesh({vertex(x1,y1,c1,state.alpha),vertex(x2,y2,c2,state.alpha),vertex(x3,y3,c3,state.alpha)}) end
    end
    B.draw_triangle=function(E,x1,y1,x2,y2,x3,y3,outline) B.draw_triangle_color(E,x1,y1,x2,y2,x3,y3,state.color,state.color,state.color,outline) end
    B.draw_line_width_color=function(_,x1,y1,x2,y2,width,c1,c2)
        local dx,dy=x2-x1,y2-y1;local len=math.sqrt(dx*dx+dy*dy)
        if len==0 then return end
        local nx,ny=-dy/len*width/2,dx/len*width/2
        mesh({vertex(x1+nx,y1+ny,c1,state.alpha),vertex(x2+nx,y2+ny,c2,state.alpha),vertex(x2-nx,y2-ny,c2,state.alpha),vertex(x1-nx,y1-ny,c1,state.alpha)})
    end
    B.draw_line_color=function(E,x1,y1,x2,y2,c1,c2) B.draw_line_width_color(E,x1,y1,x2,y2,1,c1,c2) end
    B.draw_line_width=function(E,x1,y1,x2,y2,width) B.draw_line_width_color(E,x1,y1,x2,y2,width,state.color,state.color) end
    B.draw_line=function(E,x1,y1,x2,y2) B.draw_line_width(E,x1,y1,x2,y2,1) end
    B.draw_point_color=function(_,x,y,c) if g then color(c);g.points(x,y) end end
    B.draw_ellipse_color=function(_,x1,y1,x2,y2,inner,outer,outline)
        local cx,cy=(x1+x2)/2,(y1+y2)/2;local rx,ry=math.abs(x2-x1)/2,math.abs(y2-y1)/2
        if R.truth(outline) then if g then color(outer);g.ellipse("line",cx,cy,rx,ry,state.precision) end;return end
        local vertices={vertex(cx,cy,inner,state.alpha)}
        for i=0,state.precision do local angle=i/state.precision*math.pi*2;vertices[#vertices+1]=vertex(cx+math.cos(angle)*rx,cy+math.sin(angle)*ry,outer,state.alpha) end
        mesh(vertices)
    end
    B.draw_getpixel=function(_,x,y)
        if not g then return 0 end
        local canvas=g.getCanvas();if not canvas or x<0 or y<0 or x>=canvas:getWidth() or y>=canvas:getHeight() then return 0 end
        g.setCanvas();local data=canvas:newImageData(1,1,math.floor(x),math.floor(y),1,1);g.setCanvas(canvas)
        local r,gg,b=data:getPixel(0,0);data:release();return rgb(r*255,gg*255,b*255)
    end
    B.tile_layer_shift=function(_,depth,x,y)
        local offsets=R.roomState.tileOffsets;offsets[depth]=offsets[depth] or {0,0}
        offsets[depth][1]=offsets[depth][1]+x;offsets[depth][2]=offsets[depth][2]+y
    end
    B.tile_layer_hide=function(_,depth) R.roomState.hiddenLayers[depth]=true end
    B.tile_layer_show=function(_,depth) R.roomState.hiddenLayers[depth]=nil end

    function R:views()
        local result={};local v=self.vars
        if self.truth(v.view_enabled) then
            for i=0,7 do if self.truth(v.view_visible[i]) and v.view_wview[i]>0 and v.view_hview[i]>0 then
                result[#result+1]={index=i,x=v.view_xview[i],y=v.view_yview[i],w=v.view_wview[i],h=v.view_hview[i],
                    px=v.view_xport[i],py=v.view_yport[i],pw=v.view_wport[i],ph=v.view_hport[i],angle=v.view_angle[i]}
            end end
        end
        if #result==0 then result[1]={index=0,x=0,y=0,w=v.room_width,h=v.room_height,px=0,py=0,pw=v.room_width,ph=v.room_height} end
        return result
    end
    local function backgrounds(foreground,view)
        for i,b in ipairs(R.roomState.backgrounds) do
            local n=i-1;local v=R.vars
            if R.truth(v.background_visible[n]) and R.truth(v.background_foreground[n])==foreground then
                local asset=R.assets.backgrounds[v.background_index[n]]
                if asset then
                    local x,y=v.background_x[n],v.background_y[n]
                    local sx,sy=v.background_xscale[n],v.background_yscale[n]
                    if R.truth(b.stretch) then sx=R.vars.room_width/asset.width;sy=R.vars.room_height/asset.height end
                    local iw,ih=asset.width*sx,asset.height*sy
                    local ht,vt=R.truth(v.background_htiled[n]),R.truth(v.background_vtiled[n])
                    if iw>0 and ih>0 then
                        local startX=ht and x+math.floor((view.x-x)/iw)*iw or x
                        local startY=vt and y+math.floor((view.y-y)/ih)*ih or y
                        for yy=startY,vt and view.y+view.h or startY,ih do
                            for xx=startX,ht and view.x+view.w or startX,iw do
                                part(asset.file,0,0,asset.width,asset.height,xx,yy,sx,sy,v.background_blend[n],v.background_alpha[n])
                            end
                        end
                    end
                end
            end
        end
    end
    function R:renderFrame()
        self.drawLog={}
        -- The duplicate-draw comparison is per frame: every frame paints a fresh
        -- canvas, so the first draw of a frame always happens.
        state.lastSprite=nil
        local views=self:views();local width,height=1,1
        for _,v in ipairs(views) do width=math.max(width,v.px+v.pw);height=math.max(height,v.py+v.ph) end
        self.displayWidth,self.displayHeight=width,height
        if g then
            if not self.canvas or self.canvas:getWidth()~=width or self.canvas:getHeight()~=height then
                if self.canvas then self.canvas:release() end
                self.canvas=g.newCanvas(width,height,{dpiscale=1});self.canvas:setFilter("nearest","nearest")
                state.surfaces[0]=self.canvas;self.vars.application_surface=0
            end
            g.push("all");g.setCanvas(self.canvas);g.origin();g.setBlendMode("alpha");g.clear(rgba(self.vars.background_color,1))
        end
        local list={}
        local layers=self.roomState.layers
        local staticTiles=self.roomState.staticTileDrawList
        if not staticTiles then
            staticTiles={}
            for i,tile in ipairs(self.roomState.tiles) do
                local layer=tile.layer and layers[tile.layer]
                staticTiles[#staticTiles+1]={depth=(layer and layer.depth) or tile.depth,order=i,tile=tile,layer=layer}
            end
            self.roomState.staticTileDrawList=staticTiles
        end
        for i=1,#staticTiles do
            local item=staticTiles[i]
            local layer=item.layer
            if layer then item.depth=layer.depth or item.tile.depth end
            item.slot=item.tile.layer
            list[i]=item
        end
        local base=#list
        for i,inst in ipairs(self.instances) do
            if inst.alive and inst.active then
                local layer=inst.layer and layers[inst.layer]
                base=base+1
                list[base]={depth=(layer and layer.depth) or inst.v.depth or 0,order=1000000+i,instance=inst,layer=layer,
                    slot=inst._homeLayer or inst.layer}
            end
        end
        -- Particle systems draw at their own depth among the instances and
        -- tiles. Undertale owns no systems, so its draw list is unchanged.
        if self.particles then
            for id,sys in pairs(self.particles.systems) do
                if sys.autoDraw and #sys.particles>0 and self:particleLayerVisible(sys) then
                    list[#list+1]={depth=self:particleDepth(sys),order=2000000+id,particles=sys}
                end
            end
        end
        table.sort(list,function(a,b)
            if a.depth==b.depth then
                -- Across layers the room's own list order breaks the tie: the
                -- layer nearer the front of the list (lower slot) draws later,
                -- so a foreground tile layer covers a tied actor. A managed
                -- actor compares by its home slot, not its appended layer.
                -- Unlayered GameMaker 1.4 entries have no slot and keep the
                -- creation order GameMaker uses for depth ties.
                local sa,sb=a.slot,b.slot
                if sa~=nil and sb~=nil and sa~=sb then return sa>sb end
                return a.order<b.order
            end
            return a.depth>b.depth
        end)
        -- GameMaker runs a whole Draw Begin pass over the instances, then Draw,
        -- then Draw End, and skips all of them for an invisible instance. A
        -- Studio 2 layer hidden with layer_set_visible hides its instances too:
        -- the draw pass never reaches them, while their Step events still run.
        local function drawable(item)
            local layer=item.layer
            return not (layer and layer.visible==false)
        end
        local function drawPass(kind,number,ignoreLayers)
            local key=tostring(kind)..":"..tostring(number)
            local any=false
            for _,inst in ipairs(self.instances) do
                if inst.alive and inst.active and self:findEvent(inst.v.object_index,key) then
                    any=true
                    break
                end
            end
            if not any then return end
            for _,item in ipairs(list) do
                local inst=item.instance
                if inst and inst.alive and inst.active and self.truth(inst.v.visible)
                   and (ignoreLayers or drawable(item)) then
                    -- Draw Begin/End, Pre/Post Draw and the GUI passes name the
                    -- instance they are drawing for, so every sprite entry in the
                    -- log has a provenance even outside the main Draw pass.
                    R.drawOwner=inst
                    self:event(inst,kind,number)
                    R.drawOwner=nil
                end
            end
        end
        drawPass(8,76) -- Pre Draw: before this frame's own drawing starts
        for _,view in ipairs(views) do
            self.vars.view_current=view.index
            -- Clamp the displayed viewport to room bounds; camera parity still
            -- needs reference testing in the cutscenes that override these values.
            view.x=clamp(view.x,0,math.max(0,self.vars.room_width-view.w));view.y=clamp(view.y,0,math.max(0,self.vars.room_height-view.h))
            if #views==1 and self.truth(self.vars.view_visible[view.index]) then self.vars.view_xview[view.index]=view.x;self.vars.view_yview[view.index]=view.y end
            if g then
                g.push();g.setScissor(view.px,view.py,view.pw,view.ph);g.translate(view.px,view.py);g.scale(view.pw/view.w,view.ph/view.h);g.translate(view.w/2,view.h/2);g.rotate(math.rad(view.angle or 0));g.translate(-view.x-view.w/2,-view.y-view.h/2)
            end
            if self.roomState.backdrop then
                log("reconstructed-background",self.roomState.backdrop)
                if g then require("port.opening_backdrops").draw(g,self.roomState.backdrop) end
            end
            backgrounds(false,view)
            drawPass(8,72) -- Draw Begin
            for _,item in ipairs(list) do
                if item.tile then
                    local t=item.tile
                    if t.yellow then
                        -- Studio 2 drawable: tile map cell, asset-layer sprite or
                        -- texture region, scrolling/animated background layer, or
                        -- a colour-only background layer. Its layer owns depth,
                        -- visibility and position offsets.
                        if drawable(item) and not self.roomState.hiddenLayers[item.depth] then
                            yellowDrawable(t,view,item.layer)
                        end
                    elseif t.visible~=false and not self.roomState.hiddenLayers[t.depth] then
                        local shift=self.roomState.tileOffsets[t.depth] or {0,0}
                        local x,y=t.x+shift[1],t.y+shift[2]
                        if x+t.w*(t.scaleX or 1)>=view.x and x<=view.x+view.w and y+t.h*(t.scaleY or 1)>=view.y and y<=view.y+view.h then
                            B.draw_background_part_ext(nil,t.background,t.xo,t.yo,t.w,t.h,x,y,t.scaleX or 1,t.scaleY or 1,(t.colour or 16777215)%16777216,1)
                        end
                    end
                else
                    local inst=item.instance
                    if inst then
                        if inst.alive and inst.active and self.truth(inst.v.visible) and drawable(item) then
                            R.drawOwner=inst
                            local drawn=self:event(inst,8,0)
                            if not drawn and inst.v.sprite_index>=0 then
                                local v=inst.v;sprite(self:scope(inst),v.sprite_index,v.image_index,v.x,v.y,v.image_xscale,v.image_yscale,v.image_angle,v.image_blend,v.image_alpha)
                            end
                            R.drawOwner=nil
                        end
                    elseif item.particles then
                        drawParticles(item.particles,view,item.depth)
                    end
                end
            end
            drawPass(8,73) -- Draw End
            backgrounds(true,view)
            if g then g.pop() end
        end
        drawPass(8,77) -- Post Draw
        -- Draw GUI is display space: no view transform, no viewport scissor.
        -- The canvas this draws into is what love.draw presents, so GUI events
        -- land on screen exactly where they say, unscaled by any view.
        -- Studio 2 additionally gives the GUI layer its own size, which the
        -- display stretches: display_set_gui_size(320,240) on a 640x480 image
        -- draws GUI coordinates at half scale.
        local guiWidth,guiHeight=self:guiSize(width,height)
        self.guiScaleX=(guiWidth>0 and width/guiWidth) or 1
        self.guiScaleY=(guiHeight>0 and height/guiHeight) or 1
        if g then
            g.setScissor();g.origin()
            if self.guiScaleX~=1 or self.guiScaleY~=1 then g.scale(self.guiScaleX,self.guiScaleY) end
        end
        -- GUI drawing is not bound to a room layer's visibility.
        drawPass(8,74,true) -- Draw GUI Begin
        drawPass(8,64,true) -- Draw GUI
        drawPass(8,75,true) -- Draw GUI End
        if g then g.setScissor();g.setCanvas();g.pop() end
        self.vars.view_current=0
    end
    function R:trimGraphicsCache()
        -- Static textures/masks are lazy and can be reloaded. Retain only
        -- runtime-generated sprites; their pixels do not exist in the archive.
        for file,img in pairs(state.images) do
            if file:sub(1,10)~="__surface_" then img:release();state.images[file]=nil end
        end
        for key,q in pairs(state.quads) do q:release();state.quads[key]=nil end
        for file,data in pairs(self.maskData or {}) do
            if file:sub(1,10)~="__surface_" then if data.release then data:release() end;self.maskData[file]=nil end
        end
        collectgarbage("step",256)
    end
    function R:releaseGraphics()
        if self.canvas then self.canvas:release();self.canvas=nil end
        for _,img in pairs(state.images) do img:release() end
        for _,q in pairs(state.quads) do q:release() end
        for id,canvas in pairs(state.surfaces) do if id~=0 and canvas.release then canvas:release() end end
        for _,data in pairs(self.maskData or {}) do if data.release then data:release() end end
        state.images={};state.quads={};state.surfaces={};self.maskData={}
    end
end
return Graphics
