-- Fit the entire virtual canvas without cropping or stretching its aspect.
-- Fractional nearest-neighbour scaling uses the available phone area; optional
-- integer scaling preserves uniform pixel sizes when there is enough space.
local Presentation={}
function Presentation.fit(rect,width,height,integer)
    assert(width>0 and height>0 and rect.w>0 and rect.h>0,"Invalid viewport dimensions")
    local scale=math.min(rect.w/width,rect.h/height)
    if integer and scale>=1 then scale=math.max(1,math.floor(scale)) end
    return {x=rect.x+(rect.w-width*scale)/2,y=rect.y+(rect.h-height*scale)/2,
        w=width*scale,h=height*scale,scale=scale}
end
return Presentation
