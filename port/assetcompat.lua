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
--   * the sprite origin builtins.
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
