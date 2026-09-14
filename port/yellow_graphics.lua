-- Studio 2 room drawables: tile map cells, asset-layer sprites and texture
-- regions, background layers (scrolling and animating) and colour-only layers.
-- Called only for converted Yellow drawables; Undertale's own background/tile
-- pass in port/graphics.lua is deliberately untouched.
local YellowGraphics={}
function YellowGraphics.install(R,sprite,background)
    -- A tileset's cell rectangle, from the same authored geometry the converter
    -- used for a static tile: column/row inside the texture page, plus the
    -- tileset's own offsets and inter-tile separation.
    local function cell(yellow,index)
        local columns=yellow.out_columns
        if columns<=0 then return 0,0 end
        return yellow.tile_x_offset+(index%columns)*(yellow.tile_width+yellow.tile_h_separation),
               yellow.tile_y_offset+math.floor(index/columns)*(yellow.tile_height+yellow.tile_v_separation)
    end
    return function(t,view,layer)
        if t.visible==false then return end
        if layer and layer.visible==false then return end
        local lx,ly=(layer and layer.x) or 0,(layer and layer.y) or 0
        local colour=t.colour or 4294967295
        local tint=colour%16777216
        local alpha=math.floor(colour/16777216)/255
        if t.colourLayer then
            -- A Studio 2 background layer with no sprite fills the room with its
            -- own colour at its own depth; that is where a GameMaker 1.4 room's
            -- background colour lives after an import (Compatibility_Colour).
            R:fillRectangle(lx,ly,lx+R.vars.room_width-1,ly+R.vars.room_height-1,tint,alpha)
            return
        end
        local asset=R.assets.sprites[t.sprite]
        if t.background then
            local tileset=R.assets.backgrounds[t.background]
            if not tileset then R:unsupported("room tile",tostring(t.background));return end
            local xo,yo=t.xo,t.yo
            if t.index then
                local yellow=tileset.yellow
                local frames=yellow and yellow.animation_frame_count or 1
                if frames>1 then
                    -- One shared tick drives every animated tile of a tileset,
                    -- at the speed the tileset authors in FPS.
                    local speed=(yellow.animation_speed or 0)/math.max(1,R.vars.room_speed or 30)
                    local step=math.floor((R.roomState and R.roomState.tileTime or 0)*speed)%frames
                    local index=yellow.animation_frames[t.index*frames+step+1]
                    if not index then R:unsupported("animated tile",tostring(t.index).." frame "..step) end
                    xo,yo=cell(yellow,index)
                end
            end
            local x,y=t.x+lx,t.y+ly
            if x+t.w>=view.x and x<=view.x+view.w and y+t.h>=view.y and y<=view.y+view.h then
                background(tileset,xo,yo,t.w,t.h,x,y,1,1,tint,alpha,t)
            end
            return
        end
        if not asset then R:unsupported("room sprite",tostring(t.sprite));return end
        local frame=math.floor(t.frame or t.headPosition or 0)
        if t.backgroundLayer then
            -- Background origins are top-left even when the referenced sprite
            -- has a custom origin, and the layer's own x/y/hspeed/vspeed move it.
            local sx=(t.stretch and R.vars.room_width/asset.width or 1)*(t.xscale or 1)
            local sy=(t.stretch and R.vars.room_height/asset.height or 1)*(t.yscale or 1)
            local w,h=asset.width*sx,asset.height*sy
            local x0,y0=t.x+lx,t.y+ly
            local x1,y1=x0,y0
            if w<=0 or h<=0 then return end
            if t.htiled then x0=x0+math.floor((view.x-x0)/w)*w;x1=view.x+view.w end
            if t.vtiled then y0=y0+math.floor((view.y-y0)/h)*h;y1=view.y+view.h end
            for y=y0,y1,h do for x=x0,x1,w do
                sprite(nil,t.sprite,frame,x,y,sx,sy,0,tint,alpha,{0,0,asset.width,asset.height})
            end end
        elseif t.resourceType=="GMRSpriteGraphic" then
            sprite(nil,t.sprite,frame,t.x+lx,t.y+ly,t.scaleX,t.scaleY,t.rotation,tint,alpha)
        else
            sprite(nil,t.sprite,0,t.x+lx,t.y+ly,t.scaleX or 1,t.scaleY or 1,0,tint,alpha,{t.xo,t.yo,t.w,t.h})
        end
    end
end
return YellowGraphics
