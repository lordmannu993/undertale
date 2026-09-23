-- Bounding-box broad phase and transformed sprite-mask narrow phase.
local C={}
local function intersects(l,t,r,b,L,T,R,B) return l<=R and r>=L and t<=B and b>=T end
local function clamp(n,a,b) return math.max(a,math.min(b,n)) end

function C.install(R)
    local B=R.builtins
    R.maskData={}
    function R:mask(inst)
        local id=inst.v.mask_index>=0 and inst.v.mask_index or inst.v.sprite_index
        return self.assets.sprites[id]
    end
    function R:bbox(inst)
        local v=inst.v;local s=self:mask(inst)
        if not s then return v.x,v.y,v.x-1,v.y-1 end
        local x1,x2=(s.bbox_left-s.xorig)*v.image_xscale,(s.bbox_right+1-s.xorig)*v.image_xscale
        local y1,y2=(s.bbox_top-s.yorigin)*v.image_yscale,(s.bbox_bottom+1-s.yorigin)*v.image_yscale
        if v.image_angle==0 then
            local l=v.x+(x1<x2 and x1 or x2)
            local r=v.x+(x1<x2 and x2 or x1)
            local t=v.y+(y1<y2 and y1 or y2)
            local b=v.y+(y1<y2 and y2 or y1)
            return l,t,r-0.0001,b-0.0001
        end
        local rad=math.rad(v.image_angle)
        local c,si=math.cos(rad),math.sin(rad)
        local px1,py1=x1*c+y1*si,y1*c-x1*si
        local px2,py2=x2*c+y1*si,y1*c-x2*si
        local px3,py3=x1*c+y2*si,y2*c-x1*si
        local px4,py4=x2*c+y2*si,y2*c-x2*si
        local l=v.x+math.min(px1,px2,px3,px4)
        local r=v.x+math.max(px1,px2,px3,px4)
        local t=v.y+math.min(py1,py2,py3,py4)
        local b=v.y+math.max(py1,py2,py3,py4)
        return l,t,r-0.0001,b-0.0001
    end
    function R:maskPoint(inst,x,y,precise)
        local s=self:mask(inst);if not s then return false end
        local l,t,r,b=self:bbox(inst)
        if x<l or x>r or y<t or y>b then return false end
        if not precise or s.colkind==1 then return true end
        local v=inst.v
        if v.image_xscale==0 or v.image_yscale==0 then return false end
        local c,si=math.cos(math.rad(v.image_angle)),math.sin(math.rad(v.image_angle))
        local dx,dy=x-v.x,y-v.y
        local px=(dx*c-dy*si)/v.image_xscale+s.xorig
        local py=(dx*si+dy*c)/v.image_yscale+s.yorigin
        if px<s.bbox_left or px>=s.bbox_right+1 or py<s.bbox_top or py>=s.bbox_bottom+1 then return false end
        if s.colkind==2 or s.colkind==3 then
            local cx,cy=(s.bbox_left+s.bbox_right+1)/2,(s.bbox_top+s.bbox_bottom+1)/2
            local nx=(px-cx)/math.max(0.5,(s.bbox_right-s.bbox_left+1)/2)
            local ny=(py-cy)/math.max(0.5,(s.bbox_bottom-s.bbox_top+1)/2)
            return s.colkind==2 and nx*nx+ny*ny<=1 or s.colkind==3 and math.abs(nx)+math.abs(ny)<=1
        end
        -- Precise mask (piece 6d, spec section 12). px/py are canvas pixels;
        -- a cropped export's pixels start at its recovered offset (ox, oy),
        -- the same offset the renderer draws with, so the mask is read there.
        -- Reading the exported image at canvas coordinates shifted every
        -- cropped sprite's hitbox by its crop.
        --
        -- Which frames make the mask: one frame when the sprite has separate
        -- masks (GameMaker 1.4 sepmasks, Studio 2 "Precise (per frame)",
        -- collisionKind 4); otherwise the composite of every frame -- "If the
        -- sprite has multiple sub-images, then this will be a composite of
        -- the edges of all the sub-images placed over each other" (GameMaker
        -- manual, Sprite Editor: Precise).
        local cx,cy=math.floor(px)-(s.ox or 0),math.floor(py)-(s.oy or 0)
        if s.sepmasks~=0 then
            local file=s.frames[math.floor(v.image_index)%#s.frames+1]
            return file~=nil and self:maskPixel(file,cx,cy,s.coltolerance)
        end
        for _,file in ipairs(s.frames) do
            if self:maskPixel(file,cx,cy,s.coltolerance) then return true end
        end
        return false
    end
    -- One pixel of one exported frame: is it solid at the mask's tolerance?
    -- A headless run without love.image keeps the bbox answer, as before.
    function R:maskPixel(file,x,y,tolerance)
        local data=self.maskData[file]
        if not data then
            if self.options.headless and not (love and love.image) then return true end
            data=love.image.newImageData(file);self.maskData[file]=data
        end
        if x<0 or y<0 or x>=data:getWidth() or y>=data:getHeight() then return false end
        local _,_,_,a=data:getPixel(x,y)
        return a>(tolerance or 0)/255
    end
    function R:overlap(a,b,precise)
        if not self:mask(a) or not self:mask(b) then return false end
        local l,t,r,bot=self:bbox(a);local L,T,RR,BB=self:bbox(b)
        if not intersects(l,t,r,bot,L,T,RR,BB) then return false end
        if not precise then return true end
        local left,top,right,bottom=math.max(l,L),math.max(t,T),math.min(r,RR),math.min(bot,BB)
        -- Sample at world pixel centers, plus the center for subpixel slivers.
        local cx,cy=(left+right)/2,(top+bottom)/2
        if self:maskPoint(a,cx,cy,true) and self:maskPoint(b,cx,cy,true) then return true end
        for y=math.floor(top)+0.5,bottom,1 do
            for x=math.floor(left)+0.5,right,1 do
                if self:maskPoint(a,x,y,true) and self:maskPoint(b,x,y,true) then return true end
            end
        end
        return false
    end
    local function candidates(E,object,notme)
        local list=R:select(object,E)
        if not R.truth(notme) then return list end
        local out={};for _,inst in ipairs(list) do if inst~=E._self then out[#out+1]=inst end end;return out
    end
    -- The caller's collision box at (x, y) against `object` (piece 6d, spec
    -- section 12 "collision boxes"). GameMaker's place_meeting/instance_place
    -- "move the instance to the new position, check for a collision, move
    -- back" with the caller's own mask, precise only when both masks are
    -- (GameMaker manual, place_meeting). Checking the single point (x, y)
    -- instead let a 20px-wide player walk its whole body into anything its
    -- origin had not reached. Returns the first instance met, or nil.
    function R:placeMeeting(E,x,y,object)
        local self_=E and E._self
        if not self_ or not self:mask(self_) then return nil end
        local ox,oy=self_.v.x,self_.v.y
        self_.v.x,self_.v.y=x,y
        local found
        local precise=self:mask(self_).colkind==0
        for _,inst in ipairs(candidates(E,object,1)) do
            local other=self:mask(inst)
            if other and self:overlap(self_,inst,precise and other.colkind==0) then found=inst;break end
        end
        self_.v.x,self_.v.y=ox,oy
        return found
    end
    B.place_meeting=function(E,x,y,object) return R.num(R:placeMeeting(E,x,y,object)~=nil) end
    B.instance_place=function(E,x,y,object)
        local found=R:placeMeeting(E,x,y,object)
        return found and found.id or -4
    end
    B.collision_point=function(E,x,y,object,precise,notme)
        for _,inst in ipairs(candidates(E,object,notme)) do
            if R:maskPoint(inst,x,y,R.truth(precise)) then return inst.id end
        end
        return -4
    end
    B.instance_position=function(E,x,y,object) return B.collision_point(E,x,y,object,1,0) end
    B.collision_rectangle=function(E,x1,y1,x2,y2,object,precise,notme)
        local l,t,r,b=math.min(x1,x2),math.min(y1,y2),math.max(x1,x2),math.max(y1,y2)
        for _,inst in ipairs(candidates(E,object,notme)) do
            local L,T,RR,BB=R:bbox(inst)
            if R:mask(inst) and intersects(l,t,r,b,L,T,RR,BB) then
                if not R.truth(precise) then return inst.id end
                local left,top,right,bottom=math.max(l,L),math.max(t,T),math.min(r,RR),math.min(b,BB)
                if R:maskPoint(inst,(left+right)/2,(top+bottom)/2,true) then return inst.id end
                for y=math.floor(top)+0.5,bottom,1 do for x=math.floor(left)+0.5,right,1 do
                    if R:maskPoint(inst,x,y,true) then return inst.id end
                end end
            end
        end
        return -4
    end
    local function clipLine(x1,y1,x2,y2,l,t,r,b)
        local dx,dy=x2-x1,y2-y1;local u1,u2=0,1
        local p,q={-dx,dx,-dy,dy},{x1-l,r-x1,y1-t,b-y1}
        for i=1,4 do
            if p[i]==0 then if q[i]<0 then return nil end
            else
                local u=q[i]/p[i]
                if p[i]<0 then u1=math.max(u1,u) else u2=math.min(u2,u) end
                if u1>u2 then return nil end
            end
        end
        return u1,u2
    end
    B.collision_line=function(E,x1,y1,x2,y2,object,precise,notme)
        for _,inst in ipairs(candidates(E,object,notme)) do
            local l,t,r,b=R:bbox(inst)
            local u1,u2=clipLine(x1,y1,x2,y2,l,t,r,b)
            if R:mask(inst) and u1 then
                if not R.truth(precise) then return inst.id end
                local dx,dy=x2-x1,y2-y1;local count=math.max(1,math.ceil(math.sqrt(dx*dx+dy*dy)*(u2-u1)*2))
                for i=0,count do local u=u1+(u2-u1)*i/count
                    if R:maskPoint(inst,x1+u*dx,y1+u*dy,true) then return inst.id end
                end
            end
        end
        return -4
    end
    B.collision_circle=function(E,x,y,radius,object,precise,notme)
        for _,inst in ipairs(candidates(E,object,notme)) do
            local l,t,r,b=R:bbox(inst);local nx,ny=clamp(x,l,r),clamp(y,t,b)
            if R:mask(inst) and (nx-x)^2+(ny-y)^2<=radius^2 then
                if not R.truth(precise) or R:maskPoint(inst,nx,ny,true) then return inst.id end
                for py=math.floor(math.max(t,y-radius))+0.5,math.min(b,y+radius),1 do
                    for px=math.floor(math.max(l,x-radius))+0.5,math.min(r,x+radius),1 do
                        if (px-x)^2+(py-y)^2<=radius^2 and R:maskPoint(inst,px,py,true) then return inst.id end
                    end
                end
            end
        end
        return -4
    end
    B.distance_to_point=function(E,x,y)
        local l,t,r,b=R:bbox(E._self);return math.sqrt((x-clamp(x,l,r))^2+(y-clamp(y,t,b))^2)
    end
    B.distance_to_object=function(E,object)
        local best=10000000000;local l,t,r,b=R:bbox(E._self)
        for _,inst in ipairs(candidates(E,object,1)) do
            local L,T,RR,BB=R:bbox(inst)
            local dx,dy=math.max(0,l-RR,L-r),math.max(0,t-BB,T-b)
            best=math.min(best,math.sqrt(dx*dx+dy*dy))
        end
        return best
    end
    function R:collisionEvents(snapshot)
        local cache=self.collisionSelectors
        for _,inst in ipairs(snapshot) do
            if inst.alive and inst.active then
                local objIndex=inst.v.object_index
                local selectors=cache[objIndex]
                if not selectors then
                    local sel,seen={},{}
                    local index=objIndex
                    while index and index>=0 do
                        local obj=self:object(index);if not obj then break end
                        for key in pairs(obj.events) do
                            if key:sub(1,2)=="4:" then
                                local selector=tonumber(key:sub(3))
                                if not seen[selector] then sel[#sel+1]=selector;seen[selector]=true end
                            end
                        end
                        index=obj.parent
                    end
                    table.sort(sel)
                    selectors=sel
                    cache[objIndex]=selectors
                end
                if #selectors>0 then
                    local inst_l,inst_t,inst_r,inst_bot=self:bbox(inst)
                    for _,selector in ipairs(selectors) do
                        for _,other in ipairs(self:select(selector,self:scope(inst))) do
                            if inst~=other and other.alive then
                                local other_l,other_t,other_r,other_bot=self:bbox(other)
                                if inst_l<=other_r and inst_r>=other_l and inst_t<=other_bot and inst_bot>=other_t then
                                    -- A more-specific collision event shadows an ancestor
                                    -- event for the same target, as in GameMaker.
                                    local shadowed=false
                                    for _,specific in ipairs(selectors) do
                                        if specific~=selector and self:isA(other,specific) then
                                            local def=self:object(specific)
                                            while def and def.parent>=0 do
                                                if def.parent==selector then shadowed=true;break end
                                                def=self:object(def.parent)
                                            end
                                        end
                                        if shadowed then break end
                                    end
                                    if not shadowed and self:overlap(inst,other,true) then
                                        if self.truth(other.v.solid) then inst.v.x=inst.v.xprevious;inst.v.y=inst.v.yprevious end
                                        self:event(inst,4,selector,other)
                                        inst_l,inst_t,inst_r,inst_bot=self:bbox(inst)
                                    end
                                end
                            end
                        end
                    end
                end
            end
        end
    end
end
return C
