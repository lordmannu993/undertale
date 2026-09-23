-- One place that answers "how big is this sprite in the original game".
--
-- Both source games keep a sprite's *canvas* size in their own records, but the
-- decompiled Undertale checkout exported many PNGs cropped to their collision
-- bbox, so `width`/`height` are the exported pixels there, not the canvas the
-- game's own arithmetic assumes. tools/recover_sprite_offsets.py pins the
-- original canvas for those sprites (with the evidence for each one) and
-- tools/convert.py carries it beside the exported size as `cw`/`ch`, where it
-- was verified. Yellow's GMS2 sprite records are not cropped, so their
-- `width`/`height` already are the canvas and the same accessor returns them
-- unchanged.
--
-- Everything that reports or uses a sprite's size goes through here, so the two
-- worlds answer in the same units:
--
--   * `sprite_width` / `sprite_height` (instance reads; scripts/scr_depth.gml
--     turns the height into Undertale's Y-sort key),
--   * `sprite_get_width` / `sprite_get_height` (both worlds' builtins),
--   * the sprite origin builtins,
--   * the per-step animation rate (piece 6b: Studio 2's image_speed is a
--     multiplier on the sprite's own playback speed),
--   * the render anchor a pixels-only remap draws with (piece 6b).
--
-- The renderer keeps drawing the *exported* pixels with the recovered crop
-- offset (port/graphics.lua), which is what puts the art back where the
-- original canvas had it. A recovered canvas is never a guess: the sprites the
-- recovery could not pin keep their exported size here and are listed by name
-- in port/sprite_offsets.json.
local AssetCompat = {}

--: Canvas width of a sprite record, in original-game pixels.
function AssetCompat.width(sprite)
    if not sprite then return 0 end
    return sprite.cw or sprite.width or 0
end

--: Canvas height of a sprite record, in original-game pixels.
function AssetCompat.height(sprite)
    if not sprite then return 0 end
    return sprite.ch or sprite.height or 0
end

--: Canvas x origin. Cropping never moved it: it was always a canvas coordinate.
function AssetCompat.xoffset(sprite)
    if not sprite then return 0 end
    return sprite.xorig or 0
end

--: Canvas y origin.
function AssetCompat.yoffset(sprite)
    if not sprite then return 0 end
    return sprite.yorigin or 0
end

--: Frames advanced per game step at image_speed 1 (piece 6b).
--
-- GameMaker 1.4 has no per-sprite speed: image_speed *is* frames per step,
-- so every Undertale record answers 1. Studio 2 made image_speed a
-- multiplier on the sprite's own playback speed; tools/yellow/assets.py
-- already converts that speed into frames per step (`yellow.image_speed`,
-- FPS types divided by Yellow's own 30 FPS game speed). One rule then drives
-- both worlds: advance = image_speed * playbackRate(sprite).
function AssetCompat.playbackRate(sprite)
    local yellow = sprite and sprite.yellow
    local rate = yellow and yellow.image_speed
    if type(rate) == "number" then return rate end
    return 1
end

--: The canvas point a sprite stands on: its bottom centre (piece 6b).
--
-- The fusion's depth rule already sorts by the visual bottom point, so the
-- same point is the render anchor when one game's pixels stand in for the
-- other's (port/frisk.lua's remaps): the feet, in canvas pixels.
function AssetCompat.feet(sprite)
    return AssetCompat.width(sprite) / 2, AssetCompat.height(sprite)
end

--: Canvas shift that keeps `from`'s feet where `to` is drawn instead.
--
-- Returns (dx, dy) = feet(from) - feet(to). `to` then draws with its canvas
-- top-left at `from`'s top-left + (dx, dy): an origin draw uses
-- `from`'s origin minus (dx, dy) as `to`'s origin, and a part draw reads
-- `to`'s region shifted by -(dx, dy). Zero when no remap happened.
function AssetCompat.anchor(from, to)
    if not from or not to or from == to then return 0, 0 end
    local fx, fy = AssetCompat.feet(from)
    local tx, ty = AssetCompat.feet(to)
    return fx - tx, fy - ty
end

--: The drawn sub-image when `to` stands in for `from` (piece 6b).
--
-- One animation state drives a remapped draw: the gameplay record's
-- image_index. A replacement with a different frame count is drawn at the
-- same *phase* of its own cycle, so every one of its frames shows (Clover's
-- six-frame run over Frisk's two-frame side walk) instead of the first few.
function AssetCompat.remapFrame(from, to, sub)
    if not from or not to or from == to then return sub end
    local nFrom, nTo = #(from.frames or {}), #(to.frames or {})
    if nFrom <= 0 or nTo <= 0 or nFrom == nTo then return sub end
    return (sub % nFrom) * nTo / nFrom
end

function AssetCompat.sprite(R, index)
    return R.assets.sprites[index]
end

function AssetCompat.spriteWidth(R, index)
    return AssetCompat.width(R.assets.sprites[index])
end

function AssetCompat.spriteHeight(R, index)
    return AssetCompat.height(R.assets.sprites[index])
end

return AssetCompat
