-- Reconstructed opening scenery, using the user's reference views, the room's
-- existing collision/door coordinates and the supplied bg_ruinsplaceholder
-- palette. Not a claim that missing original tile records have been recovered.
-- Drawn behind the ORIGINAL flower tiles/characters; collision is unchanged.
local M={}
M.palette={floor={58,57,72},outer={95,94,119},light={200,194,226},grass={34,177,76}}
M.rooms={room_area1=true,room_area1_2=true}
local function color(g,c) g.setColor(c[1]/255,c[2]/255,c[3]/255,1) end
local function round(g,x,y,w,h,r) g.rectangle("fill",x,y,w,h,r or 7,r or 7) end
local function doorway(g,cx,base)
    local dark={42,41,53};local stone=M.palette.floor;local trim={78,76,96}
    color(g,stone)
    -- Pillars and their feet/capitals, aligned to the existing 20px door trigger.
    for _,x in ipairs({cx-34,cx+24}) do
        g.rectangle("fill",x,base-49,10,47)
        g.rectangle("fill",x-3,base-51,16,3)
        g.rectangle("fill",x-2,base-46,14,3)
        g.rectangle("fill",x-3,base-4,16,4)
        color(g,dark);g.rectangle("fill",x+3,base-42,2,34)
        color(g,trim);g.rectangle("fill",x+1,base-42,1,34)
        color(g,stone)
    end
    g.rectangle("fill",cx-37,base-56,74,3)
    g.rectangle("fill",cx-39,base-58,78,1)
    -- Pixel-aligned double arch; no smoothed external art or watermarks.
    for _,r in ipairs({30,33}) do
        local points={}
        for i=0,48 do
            local a=math.pi+i*math.pi/48
            points[#points+1]=math.floor(cx+math.cos(a)*r+0.5)
            points[#points+1]=math.floor(base-57+math.sin(a)*20+0.5)
        end
        g.setLineWidth(1);g.line(points)
    end
    -- Small delta-rune motif and a broken post beside the doorway.
    for _,dx in ipairs({-8,0,8}) do
        local y=base-63-(dx==0 and 3 or 0)
        g.polygon("fill",cx+dx-3,y,cx+dx+3,y,cx+dx,y+4)
    end
    g.line(cx-20,base-66,cx-15,base-62,cx-9,base-63)
    g.line(cx+20,base-66,cx+15,base-62,cx+9,base-63)
    g.rectangle("fill",cx-48,base-15,7,15)
    g.rectangle("fill",cx-50,base-17,11,2)
    g.rectangle("fill",cx-50,base-2,12,2)
end
function M.draw(g,name)
    if not M.rooms[name] then return end
    g.push("all")
    g.setBlendMode("alpha");g.setLineStyle("rough");color(g,M.palette.floor)
    if name=="room_area1" then
        round(g,60,60,180,40)
        round(g,20,80,260,100)
        round(g,40,160,220,40)
        round(g,60,180,180,40)
        round(g,80,200,140,40)
        round(g,260,160,400,40)
        -- The three lit rings sit underneath the existing 60x40 flower tile.
        color(g,M.palette.outer);round(g,60,120,180,60,30)
        color(g,M.palette.light);round(g,80,120,140,60,30)
        color(g,M.palette.grass);round(g,100,120,100,60,30)
        doorway(g,620,160)
    else
        -- The second chamber follows the supplied stepped solid boundaries.
        round(g,140,150,40,60)
        round(g,80,170,160,50)
        round(g,40,190,240,50)
        round(g,20,210,280,110)
        round(g,40,300,240,40)
        round(g,60,320,200,40)
        round(g,100,340,120,40)
        round(g,120,360,80,70)
        doorway(g,160,170)
    end
    g.pop()
end
return M
