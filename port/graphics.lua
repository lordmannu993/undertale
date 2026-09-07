-- Pixel-art renderer and the drawing builtins used by the converted events.
-- Draw events run once per GAME tick, because this game also updates logic in
-- Draw. love.draw only presents the cached canvas; 120 Hz phones must not run
-- dialogue/battle logic four times faster than 30 Hz GameMaker rooms.
local Graphics={}
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
        local key=file..":"..table.concat({x,y,w,h},",")
        if not state.quads[key] then state.quads[key]=g.newQuad(x,y,w,h,iw,ih) end
        return state.quads[key]
    end
    local function part(file,left,top,width,height,x,y,sx,sy,tint,alpha)
        if width<=0 or height<=0 or sx==0 or sy==0 then return end
        local img=image(file);if not img then return end
        local iw,ih=img:getDimensions()
        local l,t=math.max(0,left),math.max(0,top)
        local r,b=math.min(iw,left+width),math.min(ih,top+height)
        if r<=l or b<=t then return end
        color(tint,alpha)
        g.draw(img,quad(file,l,t,r-l,b-t,iw,ih),x+(l-left)*sx,y+(t-top)*sy,0,sx,sy)
    end
    local function sprite(E,index,sub,x,y,sx,sy,angle,tint,alpha,crop)
        local s=R.assets.sprites[index]
        if not s then
            if index>=0 then R:warn("sprite:"..tostring(index),"Unresolved sprite ID "..tostring(index).."; see conversion-report.json.") end
            return
        end
        if #s.frames==0 then return end
        if sub<0 then sub=E and E.image_index or 0 end
        local file=s.frames[math.floor(sub)%#s.frames+1]
        log("sprite",s.name,math.floor(sub)%#s.frames,x,y,sx,sy,angle,tint,alpha)
        if not g then return end
        if crop then part(file,crop[1],crop[2],crop[3],crop[4],x,y,sx,sy,tint,alpha)
        else
            local img=image(file);if not img then return end
            color(tint,alpha);g.draw(img,x,y,-math.rad(angle),sx,sy,s.xorig,s.yorigin)
        end
    end
    B.draw_sprite=function(E,index,sub,x,y) sprite(E,index,sub,x,y,1,1,0,16777215,state.alpha) end
    B.draw_sprite_ext=function(E,index,sub,x,y,sx,sy,angle,tint,alpha) sprite(E,index,sub,x,y,sx,sy,angle,tint,alpha) end
    B.draw_sprite_part=function(E,index,sub,l,t,w,h,x,y) sprite(E,index,sub,x,y,1,1,0,16777215,state.alpha,{l,t,w,h}) end
    B.draw_sprite_part_ext=function(E,index,sub,l,t,w,h,x,y,sx,sy,tint,alpha) sprite(E,index,sub,x,y,sx,sy,0,tint,alpha,{l,t,w,h}) end
    B.draw_sprite_stretched=function(E,index,sub,x,y,w,h)
        local s=R.assets.sprites[index];if s then sprite(E,index,sub,x,y,w/s.width,h/s.height,0,16777215,state.alpha,{0,0,s.width,s.height}) end
    end
    B.sprite_get_width=function(_,index) local s=R.assets.sprites[index];return s and s.width or 0 end
    B.sprite_get_height=function(_,index) local s=R.assets.sprites[index];return s and s.height or 0 end
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
        log("background",b.name,x,y)
        part(b.file,0,0,b.width,b.height,x,y,1,1,16777215,state.alpha)
    end
    B.draw_background_part_ext=function(_,index,l,t,w,h,x,y,sx,sy,tint,alpha)
        local b=R.assets.backgrounds[index]
        if b then log("background",b.name,x,y);part(b.file,l,t,w,h,x,y,sx,sy,tint,alpha)
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
        for i,tile in ipairs(self.roomState.tiles) do list[#list+1]={depth=tile.depth,order=i,tile=tile} end
        for i,inst in ipairs(self.instances) do if inst.alive and inst.active then list[#list+1]={depth=inst.v.depth,order=1000000+i,instance=inst} end end
        table.sort(list,function(a,b) if a.depth==b.depth then return a.order<b.order end;return a.depth>b.depth end)
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
            for _,item in ipairs(list) do
                if item.tile then
                    local t=item.tile
                    if not self.roomState.hiddenLayers[t.depth] then
                        local shift=self.roomState.tileOffsets[t.depth] or {0,0}
                        local x,y=t.x+shift[1],t.y+shift[2]
                        if x+t.w*(t.scaleX or 1)>=view.x and x<=view.x+view.w and y+t.h*(t.scaleY or 1)>=view.y and y<=view.y+view.h then
                            B.draw_background_part_ext(nil,t.background,t.xo,t.yo,t.w,t.h,x,y,t.scaleX or 1,t.scaleY or 1,(t.colour or 16777215)%16777216,1)
                        end
                    end
                else
                    local inst=item.instance
                    if inst.alive and inst.active and self.truth(inst.v.visible) then
                        local drawn=self:event(inst,8,0)
                        if not drawn and inst.v.sprite_index>=0 then
                            local v=inst.v;sprite(self:scope(inst),v.sprite_index,v.image_index,v.x,v.y,v.image_xscale,v.image_yscale,v.image_angle,v.image_blend,v.image_alpha)
                        end
                    end
                end
            end
            backgrounds(true,view)
            if g then g.pop() end
        end
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
