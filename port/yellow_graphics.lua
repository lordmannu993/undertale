-- Studio room asset layers. Called only for converted Yellow drawables;
-- Undertale's existing background/tile pass is deliberately untouched.
local YellowGraphics={}
function YellowGraphics.install(R,sprite)
    return function(t,view)
        if t.visible==false then return end
        local tint=(t.colour or 4294967295)%16777216
        local alpha=math.floor((t.colour or 4294967295)/16777216)/255
        local asset=R.assets.sprites[t.sprite]
        if not asset then R:unsupported("room sprite",tostring(t.sprite));return end
        local frame=t.headPosition or 0
        if t.backgroundLayer then
            -- Background origins are top-left even when the referenced sprite
            -- has a custom origin. Movement/animation support is intentionally
            -- gated by the converter until its timing is verified.
            local sx=t.stretch and R.vars.room_width/asset.width or 1
            local sy=t.stretch and R.vars.room_height/asset.height or 1
            local w,h=asset.width*sx,asset.height*sy
            local x0,y0=t.x,t.y
            local x1,y1=x0,y0
            if t.htiled then x0=x0+math.floor((view.x-x0)/w)*w;x1=view.x+view.w end
            if t.vtiled then y0=y0+math.floor((view.y-y0)/h)*h;y1=view.y+view.h end
            for y=y0,y1,h do for x=x0,x1,w do
                sprite(nil,t.sprite,0,x,y,sx,sy,0,tint,alpha,{0,0,asset.width,asset.height})
            end end
        elseif t.resourceType=="GMRSpriteGraphic" then
            sprite(nil,t.sprite,frame,t.x,t.y,t.scaleX,t.scaleY,t.rotation,tint,alpha)
        else
            sprite(nil,t.sprite,0,t.x,t.y,t.scaleX or 1,t.scaleY or 1,0,tint,alpha,{t.xo,t.yo,t.w,t.h})
        end
    end
end
return YellowGraphics
