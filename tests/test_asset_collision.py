"""Collision boxes, hitboxes, scaling and sheet coordinates (unified-fusion piece 6d).

Spec section 12 lists collision boxes, hitboxes, scaling and sprite-sheet
coordinates among the things one compatibility layer normalises. Piece 6d finds
five places where the two worlds meant different things by the same collision
or size question and fixes each one in the shared system:

  * **Precise masks in canvas pixels.** ``R:maskPoint`` read the exported PNG at
    *canvas* coordinates. A cropped Undertale export starts at its recovered
    offset (the renderer draws it there), so every cropped sprite's pixel
    hitbox sat ``(ox, oy)`` away from its art -- 136 objects' collision masks.
  * **Composite vs per-frame masks.** GameMaker's *Precise* mask is the
    composite of every frame ("a composite of the edges of all the sub-images
    placed over each other"); only separate masks (1.4 ``sepmasks``, Studio 2
    *Precise (per frame)*) use the current frame. The runtime used frame 0 for a
    composite mask.
  * **Studio 2's collisionKind 4 is Precise (per frame).** The GMS2 sprite
    schema numbers the kinds 0 Precise, 1 Rectangle, 2 Ellipse, 3 Diamond,
    4 PrecisePerFrame, 5 RectangleWithRotation. The converter read 4 as a rotated
    rectangle and hard-coded ``sepmasks`` 0, compositing 74 per-frame masks.
  * **place_meeting / instance_place test the caller's collision box.** GameMaker
    moves the caller to (x, y) and checks *its mask*; the port checked the single
    point (x, y), so Yellow's 313 ``place_meeting`` calls missed anything the
    caller's origin had not reached.
  * **Scaling and sheet coordinates in canvas pixels.** ``draw_sprite_stretched``
    and Yellow's stretched/tiled draws scaled the *exported* size, so a cropped
    sprite stretched past its target; ``sprite_get_uvs`` (8 Yellow callers,
    including four placed reflection objects) was a compatibility stop.

These tests prove the collision and draw-log numbers headlessly, with mask
pixels supplied through a stand-in ``love.image``. They do not claim pixel-perfect
parity with either engine, Android, or a played-through scene.
"""
import json

import pytest

from conftest import ROOT
from test_yellow_merge import live, merged, vm, yellow_rooms  # noqa: F401

OFFSETS = json.loads((ROOT / "port/sprite_offsets.json").read_text())

# A single-frame cropped sprite with a recovered offset: exported 67x54, canvas
# 77x71, art at (10, 17) of the canvas, precise mask.
CROPPED = "spr_adate_body"

# Mask pixels for a headless run: a stand-in love.image whose ImageData answers
# from FAKE. The runtime reads precise masks through love.image either way, so
# the same stand-in drives the code before and after the change.
MASK_SOURCE = '''
    function fakeImage(width, height, solid)
        return {
            getWidth=function() return width end,
            getHeight=function() return height end,
            getPixel=function(_, x, y) return 1, 1, 1, solid(x, y) and 1 or 0 end,
        }
    end
    FAKE={}
    love={image={newImageData=function(file)
        local image=FAKE[file]
        assert(image, "no fake mask for "..tostring(file))
        return image
    end}}
'''


def test_a_cropped_precise_mask_is_read_at_its_recovered_offset(lua):
    """The pixel hitbox lines up with the drawn art, not with the crop's corner.

    ``spr_adate_body`` is exported 67x54 and drawn at canvas offset (10, 17).
    With only the export's two corner pixels solid, an instance at (0, 0) must
    be hit exactly at canvas (10, 17) and (76, 70) -- where the renderer puts
    those pixels -- and nowhere next to them. Without the change the export is
    read at canvas coordinates: both corners miss (canvas (10, 17) reads the
    export's transparent pixel (10, 17); (76, 70) falls outside the export).
    """
    record = OFFSETS["sprites"][CROPPED]
    assert (record["ox"], record["oy"]) == (10, 17) and record["png"] == [67, 54]
    lua.execute(MASK_SOURCE)
    result = lua.execute(f'''
        local s=R.assets.sprites[R.manifest.names["{CROPPED}"]]
        assert(s.colkind==0 and #s.frames==1, "{CROPPED} is not a single-frame precise mask")
        FAKE[s.frames[1]]=fakeImage(s.width, s.height, function(x, y)
            return (x==0 and y==0) or (x==s.width-1 and y==s.height-1)
        end)
        R.maskData={{}}
        a.v.sprite_index=R.manifest.names["{CROPPED}"]; a.v.mask_index=-1
        a.v.x, a.v.y=0, 0
        local function hit(x, y) return R:maskPoint(a, x+0.5, y+0.5, true) and "1" or "0" end
        return hit(10,17)..hit(76,70)..hit(11,17)..hit(10,18)..hit(75,70)
    ''')
    assert result == "11000", f"hits (10,17) (76,70) (11,17) (10,18) (75,70) = {result}, want 11000"


def test_a_composite_precise_mask_is_every_frame_and_a_per_frame_mask_is_one(lua):
    """Precise = the union of all frames; separate masks = the current frame only."""
    lua.execute(MASK_SOURCE)
    result = lua.execute('''
        R.assets.sprites[19500]={name="twoframe",width=4,height=1,xorig=0,yorigin=0,
            bbox_left=0,bbox_top=0,bbox_right=3,bbox_bottom=0,colkind=0,coltolerance=0,
            sepmasks=0,frames={"f0.png","f1.png"}}
        FAKE["f0.png"]=fakeImage(4,1,function(x) return x==0 end)
        FAKE["f1.png"]=fakeImage(4,1,function(x) return x==3 end)
        R.maskData={}
        a.v.sprite_index=19500; a.v.mask_index=-1; a.v.x,a.v.y=0,0; a.v.image_index=0
        local function row() local out="" for x=0,3 do out=out..(R:maskPoint(a,x+0.5,0.5,true) and "1" or "0") end return out end
        local composite=row()
        R.assets.sprites[19500].sepmasks=1
        local frame0=row()
        a.v.image_index=1
        local frame1=row()
        return composite.." "..frame0.." "..frame1
    ''')
    assert result == "1001 1000 0001", f"composite/frame0/frame1 = {result}"


def test_place_meeting_tests_the_callers_whole_collision_box(lua):
    """place_meeting(x, y, obj) moves the caller's mask, not a single point.

    A 20x20 box three pixels left of a 10x10 target: moving the box 5px right
    overlaps the target (its right edge crosses it) although the caller's
    origin never reaches it. Without the change place_meeting tests the point
    (x, y) only and answers 0; instance_place answers noone.
    """
    result = lua.execute('''
        R.assets.sprites[19510]={name="box20",width=20,height=20,xorig=0,yorigin=0,
            bbox_left=0,bbox_top=0,bbox_right=19,bbox_bottom=19,colkind=1,coltolerance=0,sepmasks=0,frames={"b.png"}}
        R.assets.sprites[19511]={name="box10",width=10,height=10,xorig=0,yorigin=0,
            bbox_left=0,bbox_top=0,bbox_right=9,bbox_bottom=9,colkind=1,coltolerance=0,sepmasks=0,frames={"c.png"}}
        a.v.sprite_index=19510; a.v.mask_index=-1; a.v.x,a.v.y=0,0
        b.v.sprite_index=19511; b.v.mask_index=-1; b.v.x,b.v.y=23,5
        local B=R.builtins
        local far=B.place_meeting(E, 0, 0, 18001)
        local near=B.place_meeting(E, 5, 0, 18001)
        local id=B.instance_place(E, 5, 0, 18001)
        local unmoved=a.v.x==0 and a.v.y==0
        return far..","..near..","..(id==b.id and "b" or tostring(id))..","..tostring(unmoved)
    ''')
    assert result == "0,1,b,true", f"far,near,instance,unmoved = {result}"


def test_draw_sprite_stretched_scales_the_canvas(lua):
    """Stretching a cropped sprite over w x h scales its canvas, not the crop.

    ``spr_adate_body`` (canvas 77x71, export 67x54) stretched over 154x142 is a
    2x draw of the canvas. Without the change it scales by the export
    (154/67, 142/54), so the art overflows the requested rectangle.
    """
    result = lua.execute(f'''
        local index=R.manifest.names["{CROPPED}"]
        R.drawLog={{}}
        R.builtins.draw_sprite_stretched(E, index, 0, 10, 20, 154, 142)
        for _,e in ipairs(R.drawLog) do
            if e[1]=="sprite" then return e[6]..","..e[7]..","..e[11]..","..e[12] end
        end
    ''')
    assert result == "2,2,10,17", f"sx,sy,ox,oy = {result}"


@live
def test_yellow_precise_per_frame_masks_convert_to_separate_masks(vm):
    """collisionKind 4 (74 sprites) is precise with separate masks; kind 0 stays composite."""
    result = vm.execute('''
        local perFrame, composite, wrong=0, 0, {}
        for name,id in pairs(R.manifest.yellow_names.sprites) do
            local s=R.assets.sprites[id]
            if s and s.yellow then
                local kind=s.yellow.collision_kind
                if kind==4 then
                    perFrame=perFrame+1
                    if s.colkind~=0 or s.sepmasks~=1 then wrong[#wrong+1]=name end
                elseif kind==0 then
                    composite=composite+1
                    if s.colkind~=0 or s.sepmasks~=0 then wrong[#wrong+1]=name end
                end
            end
        end
        return perFrame..","..composite..","..#wrong..","..tostring(wrong[1])
    ''')
    per_frame, composite, wrong, first = result.split(",")
    assert per_frame == "74", result
    assert int(composite) > 0, result
    assert wrong == "0", f"collision kinds converted wrongly, first: {first}"


@live
def test_sprite_get_uvs_answers_the_frames_sheet_coordinates(vm):
    """sprite_get_uvs answers from the frame instead of stopping by name.

    Four placed Yellow reflection objects call it every draw (rm_snowdin_04/10,
    two Hotland Complex rooms). An uncropped Yellow frame is its whole texture:
    UVs 0..1, no trim, all of it kept. A cropped Undertale frame reports its
    recovered crop as the trim. Without the change the call is a compatibility
    stop.
    """
    result = vm.execute(f'''
        R:start()
        local ok, err=pcall(function()
            local B=R.builtins
            local y=B.sprite_get_uvs(nil, R.manifest.yellow_names.sprites["spr_pl_down"], 0)
            local ut=B.sprite_get_uvs(nil, R.manifest.names["{CROPPED}"], 0)
            local function row(t) local o={{}} for i=0,7 do o[#o+1]=string.format("%.4g", t[i]) end return table.concat(o," ") end
            UVS=row(y).."|"..row(ut).."|"..tostring(B.sprite_get_uvs(nil, -1, 0))
        end)
        return ok and UVS or tostring(err)
    ''')
    assert "Compatibility stop" not in result, result
    yellow, undertale, missing = result.split("|")
    assert yellow == "0 0 1 1 0 0 1 1", yellow
    # spr_adate_body: trim (10, 17), 67/77 and 54/71 of the canvas kept.
    assert undertale == "0 0 1 1 10 17 0.8701 0.7606", undertale
    assert missing == "-1", missing
