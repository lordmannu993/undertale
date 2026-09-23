"""Per-frame handling and render anchors (unified-fusion piece 6b, spec section 12).

Spec section 12 names "sprite origins", "animation frame handling" and "render
anchors" as things one compatibility layer must normalise between the two
games. Piece 6b finds four places where the two worlds meant different things
by the same animation state and fixes each one in the shared system:

  * **Frame selection.** GameMaker draws the sub-image ``image_index`` rounds
    *down* to (manual, ``image_index``: "it is always rounded down to obtain the
    subimage that is drawn"). The renderer crossfaded the fraction instead, so
    every animating sprite in both worlds drew as two superimposed frames, and a
    counter that keeps climbing (the boat cover's ``cc += 0.1``) drew its next
    frame at an opacity above 1 once ``cc`` passed 2.
  * **Animation rate.** Studio 2 made ``image_speed`` a *multiplier* on the
    sprite's own playback speed; GameMaker 1.4's ``image_speed`` is frames per
    step. The converter already recorded Yellow's rate per sprite
    (``yellow.image_speed``); the runtime never applied it. ``AssetCompat.
    playbackRate`` answers 1 for every Undertale record, so one rule drives both.
  * **Render anchor.** Frisk's canvas origin is its top-left corner, Clover's is
    his body centre. A pixels-only remap drew the replacement at its *own*
    origin, so Yellow's player drew 9px right and 15px down of Clover's body
    (and of the collision mask it walks with) and Undertale's running Frisk 10px
    left and 15px up of its walk pose. The
    replacement now stands on the requested sprite's feet (canvas bottom centre,
    the point the depth rule already sorts by).
  * **Frame count.** A remap draws the replacement at the same *phase* of its
    own cycle: Clover's six-frame run over Frisk's two-frame side walk showed
    only frames 0 and 1; it now shows all six at Yellow's own 1/3 frame/step.

These tests prove the wiring and the numbers headlessly, from the draw log.
They do not claim pixel-perfect parity with either engine, Android behaviour, or
a played-through scene.
"""
import pytest

from test_yellow_merge import live, merged, vm, yellow_rooms  # noqa: F401


def test_a_fractional_sub_index_draws_the_floor_frame_only(lua):
    """One sub-image per draw: no crossfade fields, no second layer.

    Without the change the draw of sub-index 2.5 logs blend frame 3 at 0.5, and
    the boat cover's cc = 4.1 logs a blend "amount" of 4.1.
    """
    result = lua.execute('''
        local index=R.manifest.names["spr_riverman"]   -- two frames
        R.drawLog={}
        R.builtins.draw_sprite(E, index, 0.5, 100, 100)
        R.builtins.draw_sprite(E, index, 1.7, 100, 100)
        R.builtins.draw_sprite(E, index, 4.1, 100, 100)
        R.builtins.draw_sprite(E, index, -0.25, 100, 100)
        local out={}
        for _,e in ipairs(R.drawLog) do
            if e[1]=="sprite" then
                out[#out+1]=tostring(e[3]).."/"..tostring(e[13]).."/"..tostring(e[14])
            end
        end
        return table.concat(out," ")
    ''')
    # -0.25 is the "current frame" sentinel for draw_sprite(-1...) only when
    # negative: the dummy's image_index is 0, so it draws frame 0.
    assert result == "0/nil/nil 1/nil/nil 0/nil/nil 0/nil/nil", result


def test_undertale_sprites_keep_one_frame_per_step_at_image_speed_1(lua):
    """GameMaker 1.4's image_speed is frames per step: the rate is exactly 1."""
    result = lua.execute('''
        local AssetCompat=require("port.assetcompat")
        local bad={}
        for name,id in pairs(R.manifest.names) do
            local s=R.assets.sprites[id]
            if s and s.frames and AssetCompat.playbackRate(s)~=1 then bad[#bad+1]=name end
        end
        a.v.sprite_index=R.manifest.names["spr_riverman"]
        a.v.image_index=0; a.v.image_speed=0.25
        R:finishFrame(); R:finishFrame()
        return #bad..":"..tostring(a.v.image_index)
    ''')
    assert result == "0:0.5", result


@live
def test_yellow_animation_rate_is_the_sprites_own_playback_speed(vm):
    """Studio 2's image_speed multiplies the sprite's own playback speed.

    ``spr_mail_station_steamworks`` authors 10 frames per *second* at Yellow's
    30 FPS game speed: 1/3 frame per step at image_speed 1. Without the change it
    advances a whole frame per step (three times too fast), and a sprite that
    authors playbackSpeed 0 animates instead of holding its frame.
    """
    result = vm.execute('''
        R:start()
        local sprites=R.manifest.yellow_names.sprites
        local station=R.assets.sprites[sprites["spr_mail_station_steamworks"]]
        if station.yellow.playback_speed~=10 or station.yellow.playback_speed_type~=0 then
            return "the pinned record changed: "..tostring(station.yellow.playback_speed)
        end
        dummy(18500)
        local inst=R:create(18500, 0, 0)
        inst.v.sprite_index=sprites["spr_mail_station_steamworks"]
        inst.v.image_index=0; inst.v.image_speed=1
        for _=1,3 do R:finishFrame() end
        if math.abs(inst.v.image_index-1)>1e-9 then
            return "10 fps at 30 steps/s advanced "..tostring(inst.v.image_index).." frames in 3 steps, not 1"
        end
        -- A per-step sprite keeps GameMaker 1.4's unit (Clover's run: 1 frame/step).
        inst.v.sprite_index=sprites["spr_pl_run_down"]
        inst.v.image_index=0; inst.v.image_speed=1/3
        for _=1,3 do R:finishFrame() end
        if math.abs(inst.v.image_index-1)>1e-9 then
            return "the run pose advanced "..tostring(inst.v.image_index).." in 3 steps at 1/3, not 1"
        end
        -- playbackSpeed 0 is authored, not missing: the frame holds.
        local lemonade=R.assets.sprites[sprites["spr_lemonade"]]
        if lemonade.yellow.playback_speed~=0 then
            return "spr_lemonade's authored playbackSpeed 0 was coerced to "..tostring(lemonade.yellow.playback_speed)
        end
        inst.v.sprite_index=sprites["spr_lemonade"]
        inst.v.image_index=0; inst.v.image_speed=1
        for _=1,3 do R:finishFrame() end
        if inst.v.image_index~=0 then return "a playbackSpeed-0 sprite animated to "..tostring(inst.v.image_index) end
        R:destroy(inst,false)
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_yellows_player_draws_frisk_standing_on_clovers_feet(vm):
    """The remapped pose keeps the gameplay record's canvas bottom centre.

    Clover's ``spr_pl_down`` is 20x31 with its origin at (9,16); Frisk's
    ``spr_maincharad`` canvas is 20x30 with its origin at (0,0). Drawn at
    Clover's (x, y), Frisk's canvas must start at (x-9, y-15) so both feet meet
    at (x+1, y+15). Without the anchor it starts at (x, y): 9px right and 15px
    down of where Clover's body is, drawn with the collision mask elsewhere.
    """
    result = vm.execute('''
        R:start(); R:gotoRoom(140); R:applyTransitions(); tick(1)
        R:gotoRoom(R.manifest.yellow_names.rooms["rm_hotland_02"]); R:applyTransitions(); tick(1)
        local pl=R:select(playerOf("yellow"))[1]
        local sprites=R.manifest.yellow_names.sprites
        pl.v.sprite_index=sprites["spr_pl_down"]; pl.v.image_index=0; pl.v.image_speed=0
        R.drawLog={}; R:renderFrame()
        for _,e in ipairs(R.drawLog) do
            if e[1]=="sprite" and e[16]==pl.id then
                if e[2]~="spr_maincharad" then return "drew "..tostring(e[2]).." for Clover's down pose" end
                -- Without the anchor the drawn sprite's own origin applies.
                local drawn=R.assets.sprites[e[15]]
                local left,top=e[4]-(e[17] or drawn.xorig),e[5]-(e[18] or drawn.yorigin)
                if left~=pl.v.x-9 or top~=pl.v.y-15 then
                    return string.format("Frisk's canvas starts at (%s,%s), want (%s,%s)",left,top,pl.v.x-9,pl.v.y-15)
                end
                return "ok"
            end
        end
        return "Yellow's player was not drawn"
    ''')
    assert result == "ok", result


@live
def test_undertale_run_shows_every_clover_run_frame_on_frisks_feet(vm):
    """Clover's six-frame run over Frisk's two-frame side walk shows all six.

    The run pose stands on the walk pose's feet: ``spr_maincharar``'s canvas is
    20x30 at origin (0,0), ``spr_pl_run_right`` is 20x32 at (10,17), so the run
    pose's origin lands at (10-10, 17-15) = (0,2) of the walk canvas. The drawn
    pose advances Yellow's own 1/3 frame per step. Without the change the run
    shows frames 0 and 1 only, drawn at its own origin (10px left, 15px up).
    """
    result = vm.execute('''
        R:start(); crossTo(4)
        local frisk=R:select(playerOf("undertale"))[1]
        R.global.interact=0; frisk.v.movement=1
        frisk.v.x, frisk.v.y=140, 120
        frisk.v.xprevious, frisk.v.yprevious=140, 120
        local sequence, anchored={}, true
        input:setSource("test", {39, 88})
        -- 18 steps from x=140 stay on open floor in room_area1 (a wall
        -- stops the run at x=260, twenty steps in).
        for _=1,18 do
            tick(1)
            for _,e in ipairs(R.drawLog) do
                if e[1]=="sprite" and e[16]==frisk.id and e[2]=="spr_pl_run_right" then
                    sequence[#sequence+1]=e[3]
                    local drawn=R.assets.sprites[e[15]]
                    if (e[17] or drawn.xorig)~=0 or (e[18] or drawn.yorigin)~=2 then anchored=false end
                end
            end
        end
        input:setSource("test", {}); tick(1)
        if #sequence<16 then return "the run pose was drawn only "..#sequence.." times in 18 running steps" end
        if not anchored then return "the run pose was not drawn on the walk pose's feet" end
        local seen={}
        for _,f in ipairs(sequence) do seen[f]=true end
        local shown={}
        for f=0,5 do if seen[f] then shown[#shown+1]=f end end
        if #shown~=6 then return "run frames shown: "..table.concat(shown,",") end
        -- Yellow's 1/3 frame per step: each run frame stays up for about
        -- three consecutive steps (the first and last runs may be cut short).
        local runs, length={}, 1
        for i=2,#sequence do
            if sequence[i]==sequence[i-1] then length=length+1
            else runs[#runs+1]=length; length=1 end
        end
        if #runs<4 then return "only "..#runs.." frame changes in "..#sequence.." steps" end
        for i=2,#runs do
            if runs[i]<2 or runs[i]>4 then
                return "a run frame stayed up "..runs[i].." steps, not Yellow's 3 (runs: "..table.concat(runs,",")..")"
            end
        end
        return "ok"
    ''')
    assert result == "ok", result


def test_anchor_and_phase_are_identity_without_a_remap(lua):
    """No remap, no shift: every Undertale draw keeps its own origin and frame."""
    result = lua.execute('''
        local AssetCompat=require("port.assetcompat")
        local s=R.assets.sprites[R.manifest.names["spr_riverman"]]
        local dx,dy=AssetCompat.anchor(s,s)
        local sub=AssetCompat.remapFrame(s,s,1.5)
        R.drawLog={}
        R.builtins.draw_sprite(E, R.manifest.names["spr_riverman"], 1, 100, 100)
        local e
        for _,entry in ipairs(R.drawLog) do if entry[1]=="sprite" then e=entry end end
        return dx..","..dy..","..sub..","..tostring(e[17])..","..tostring(e[18])..","..s.xorig..","..s.yorigin
    ''')
    parts = result.split(",")
    assert parts[:3] == ["0", "0", "1.5"], result
    assert parts[3:5] == parts[5:7], f"an unremapped draw changed origin: {result}"
