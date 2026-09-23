"""Unified-fusion piece 5c: one controller over both player adapters.

obj_mainchara and obj_pl stay the entities their rooms place. The shared
controller is what survives the crossing: facing, the run ability, the
menu/interact gate, Undertale's X-run, and one level-up rule (Undertale's
scr_levelup). Yellow's own 3+2 step is not rewritten. These tests do not
claim Android, audio, pixel-perfect origins, or piece 6's exact speeds.
"""
import pytest

from test_yellow_merge import live, merged, vm, yellow_rooms  # noqa: F401


@live
def test_undertale_runs_on_x_and_draws_clovers_cycle(vm):
    """Walking stays 3px. Holding X is Yellow's +2 on top of it and Clover's run.

    Piece 6c made the run one shared speed: 3+2 = 5px a step in both worlds
    (Yellow's scr_normal_state), so two steps run 10 -- piece 5c's extra 3px
    lattice step ran 12. Without the controller the same probe reports run
    distance 6, equal to the walk, and the draw log never contains
    spr_pl_run_right.
    """
    result = vm.execute('''
        R:start(); crossTo(4)
        assert(R.roomState.name=="room_area1", "room_area1 did not load")
        local frisk=R:select(playerOf("undertale"))[1]
        assert(frisk, "no Undertale player")
        assert(countInstances(playerOf("yellow"))==0, "Yellow's player is in an Undertale room")
        R.global.interact=0
        frisk.v.movement=1
        local function probe(keys)
            frisk.v.x, frisk.v.y=140, 120
            frisk.v.xprevious, frisk.v.yprevious=140, 120
            R.drawLog={}
            input:setSource("test", keys); tick(2)
            local moved=frisk.v.x-140
            local speed, sprinting=frisk.v.image_speed, frisk.v.is_sprinting
            local mask=frisk.v.sprite_index
            local drewRun=false
            for _, entry in ipairs(R.drawLog) do
                if entry[1]=="sprite" and entry[2]=="spr_pl_run_right" then drewRun=true end
            end
            input:setSource("test", {}); tick(1)
            return moved, speed, sprinting, mask, drewRun
        end
        local walk, walkSpeed, walkSprint, walkMask=probe({39})
        if walk~=6 then return "walk distance "..tostring(walk).." is not 2 steps of 3" end
        if R.truth(walkSprint) then return "arrows alone engaged the run" end
        if walkMask~=R.constants.spr_maincharar then
            return "walk mask is "..tostring(walkMask)
        end
        local run, runSpeed, runSprint, runMask, drewRun=probe({39, 88})
        if not R.truth(runSprint) then return "holding X did not sprint in Undertale" end
        if run~=10 then return "run distance "..tostring(run).." is not 2 steps of Yellow's 3+2" end
        if run<=walk then return "run distance "..run.." <= walk "..walk end
        if runMask~=R.constants.spr_maincharar then
            return "run changed the mask sprite to "..tostring(runMask)
        end
        if not drewRun then return "Undertale run did not draw spr_pl_run_right" end
        -- Yellow's sprint rate is 1/3 of a frame per step of the run pose.
        -- The record is the two-frame walk pose the six-frame run pose is
        -- drawn over at the same phase (piece 6b), so the record advances
        -- 1/3 * walk/run frames and the drawn pose advances exactly 1/3.
        local walkFrames=#R.assets.sprites[R.constants.spr_maincharar].frames
        local runFrames=#R.assets.sprites[R.manifest.yellow_names.sprites.spr_pl_run_right].frames
        if math.abs(runSpeed*runFrames/walkFrames-(1/3))>1e-9 then
            return "the drawn run pose advances "..tostring(runSpeed*runFrames/walkFrames)
                ..", not Yellow's 1/3 frame per step"
        end
        -- AUTO RUN is Yellow's option. It must not turn Undertale's walk into a run.
        R:setAutorun(true)
        local auto=probe({39})
        if auto~=6 then return "AUTO RUN changed Undertale's walk to "..tostring(auto) end
        R:setAutorun(false)
        -- The button is gated by the shared run ability, not by the key existing.
        R.global.player_can_run=0
        assert(R.player.abilities.run==0, "player_can_run is not the shared run ability")
        local blocked, _, blockedSprint=probe({39, 88})
        if blocked~=6 or R.truth(blockedSprint) then
            return "player_can_run false still ran: "..tostring(blocked)
        end
        R.global.player_can_run=1
        -- An alternate costume has no Clover run pair. Do not invent one.
        frisk.v.dsprite=R.constants.spr_maincharad_umbrella
        frisk.v.x, frisk.v.y=140, 120
        R.global.facing=0
        R.drawLog={}
        input:setSource("test", {40, 88}); tick(2)
        local drewInvented, drewUmbrella=false, false
        for _, entry in ipairs(R.drawLog) do
            if entry[1]=="sprite" and type(entry[2])=="string" and entry[2]:find("spr_pl_run_", 1, true) then
                drewInvented=true
            end
            if entry[1]=="sprite" and entry[2]=="spr_maincharad_umbrella" then drewUmbrella=true end
        end
        input:setSource("test", {})
        if drewInvented then return "an alternate costume was given an invented run sprite" end
        if not drewUmbrella then return "the umbrella costume was not drawn while running" end
        if frisk.v.sprite_index~=R.constants.spr_maincharad_umbrella then
            return "the umbrella mask was replaced"
        end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_undertale_run_stops_at_a_solid(vm):
    """The +2 run bonus collides. Without that, the bbox crosses the solid."""
    result = vm.execute('''
        R:start(); crossTo(4)
        local frisk=R:select(playerOf("undertale"))[1]
        -- Stay on the walk lattice. bbox()'s right edge is 0.0001 short, and
        -- feeding that back into x makes the step's own snap eat the bonus.
        frisk.v.x, frisk.v.y=140, 120
        frisk.v.xprevious, frisk.v.yprevious=140, 120
        R.global.interact=0
        frisk.v.movement=1
        local _, _, right=R:bbox(frisk)
        -- Four pixels of air past the real right edge: a 3px step stays clear,
        -- a 5px run step overlaps. obj_solidsmall's origin is its left edge.
        local solid=R:create(R.constants.obj_solidsmall, math.floor(right+0.0001)+4, 139)
        local sl=R:bbox(solid)
        local x0=frisk.v.x
        input:setSource("test", {39, 88}); tick(1)
        local _, _, r2=R:bbox(frisk)
        input:setSource("test", {})
        if not R.truth(frisk.v.is_sprinting) then return "the solid probe did not sprint" end
        -- The walk landed. The bonus was rejected back onto that spot.
        if frisk.v.x-x0~=3 then
            return "run step moved "..tostring(frisk.v.x-x0)..", not the walked 3 (bonus not rejected)"
        end
        if r2>sl then
            return "run step passed through the solid: right "..tostring(r2).." > "..tostring(sl)
        end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_one_controller_keeps_facing_and_abilities_across_both_adapters(vm):
    result = vm.execute('''
        R:start(); crossTo(4)
        local frisk=R:select(playerOf("undertale"))[1]
        input:setSource("test", {39}); tick(2); input:setSource("test", {}); tick(1)
        if R.global.facing~=1 then return "Undertale did not face right: "..tostring(R.global.facing) end
        local controller=R.player.controller
        if type(controller)~="table" then return "no shared controller" end
        R.global.player_can_run=0
        local yellow=R.manifest.yellow_names.rooms["rm_hotland_02"]
        crossTo(yellow)
        if R.player.controller~=controller then return "crossing replaced the controller" end
        if countInstances(playerOf("undertale"))~=0 then return "Undertale's player survived into Yellow" end
        if countInstances(playerOf("yellow"))~=1 then return "Yellow did not have exactly one player" end
        local pl=R:select(playerOf("yellow"))[1]
        if pl.v.direction~=0 then
            return "Yellow's Create left facing at "..tostring(pl.v.direction).." instead of right (0)"
        end
        if R.global.player_can_run~=0 then return "crossing reset the shared run ability" end
        -- Yellow's own step is unchanged: 2 ticks down+X is 10, walking is 6.
        pl.v.x, pl.v.y=170, 120
        R.global.player_can_run=1
        local y0=pl.v.y
        input:setSource("test", {40, 88}); tick(2)
        local runDistance=pl.v.y-y0
        input:setSource("test", {}); tick(1)
        pl.v.x, pl.v.y=170, 120
        y0=pl.v.y
        input:setSource("test", {40}); tick(2)
        local walkDistance=pl.v.y-y0
        input:setSource("test", {})
        if runDistance~=10 or walkDistance~=6 then
            return "Yellow's step changed: run "..tostring(runDistance)..", walk "..tostring(walkDistance)
        end
        input:setSource("test", {40}); tick(2); input:setSource("test", {}); tick(1)
        if pl.v.direction~=270 then return "Yellow did not face down: "..tostring(pl.v.direction) end
        -- Menu is one shared ability. Off in Yellow, off back in Undertale.
        R.player.abilities.menu=0
        if menuOpen() then return "Yellow's pause menu opened with the shared menu ability off" end
        R.player.abilities.menu=1
        if not menuOpen() then return "Yellow's pause menu did not open" end
        crossTo(4)
        if R.player.controller~=controller then return "the return trip replaced the controller" end
        if countInstances(playerOf("yellow"))~=0 then return "Yellow's player survived the return" end
        if countInstances(playerOf("undertale"))~=1 then return "Undertale did not have exactly one player" end
        if R.global.facing~=0 then return "facing did not survive back to Undertale: "..tostring(R.global.facing) end
        R.player.abilities.menu=0
        press(67)
        if R.global.interact~=0 then return "Undertale's menu opened with the shared menu ability off" end
        R.player.abilities.menu=1
        press(67)
        if R.global.interact~=5 then return "Undertale's menu did not open: interact "..tostring(R.global.interact) end
        press(88)
        if R.global.interact~=0 then return "X did not cancel Undertale's menu" end
        -- Interact is the same gate, on Z, not a second character flag.
        local object=R:object(playerOf("undertale"))
        local original=object.events["7:10"]
        local fired=false
        object.events["7:10"]=function(runtime, E)
            fired=true
            return original(runtime, E)
        end
        R.player.abilities.interact=0
        press(90)
        if fired then return "Z fired interact with the shared interact ability off" end
        R.player.abilities.interact=1
        press(90)
        if not fired then return "Z did not reach Undertale's interact handler" end
        object.events["7:10"]=original
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_yellow_award_uses_undertales_levelup_and_leaves_hp(vm):
    """The alarm still grants EXP and gold. Stats come from scr_levelup, not *_next.

    Yellow's table at this threshold writes max HP 20 (index 1) while setting
    LV 2. scr_levelup writes 24/12/10. LV 20 is 99, not Yellow's 100. Current
    HP is not a level-up output. A grant that does not change LV does not
    rewrite a custom AT.
    """
    result = vm.execute('''
        R:start(); crossTo(140)
        crossTo(R.manifest.yellow_names.rooms["rm_hotland_02"])
        local objects=R.manifest.yellow_names.objects
        local scope=R:scope(R:select(playerOf("yellow"))[1])
        R:call("scr_base_stats", scope)
        local function award(exp)
            local dialogue=R:create(objects.obj_dialogue_battle_flee, 0, 0)
            local fade=R:create(objects.obj_battle_fade_out_screen, 0, 0)
            R.global.enemy_count=1
            R.global.enemy_dead=1
            R.global.enemy_exp=exp
            R.global.enemy_gold=0
            R.global.current_room_overworld="rm_hotland_02"
            R:event(fade, 2, 0)
            if dialogue.alive then R:destroy(dialogue) end
            if fade.alive then R:destroy(fade) end
        end
        R.global.xp=9
        R.global.lv=1
        R.global.hp=13
        R.global.at=99
        award(1)
        if R.global.xp~=10 or R.global.player_exp~=10 then
            return "award did not share EXP: "..tostring(R.global.xp)
        end
        if R.global.lv~=2 or R.global.player_level~=2 then
            return "award LV is "..tostring(R.global.lv)
        end
        if R.global.maxhp~=24 or R.global.max_hp_self~=24 then
            return "LV 2 max HP is "..tostring(R.global.maxhp)..", not scr_levelup's 24"
        end
        if R.global.at~=12 or R.global.player_attack~=12 then
            return "LV 2 AT is "..tostring(R.global.at)..", not scr_levelup's 12"
        end
        if R.global.df~=10 or R.global.player_defense~=10 then
            return "LV 2 DF is "..tostring(R.global.df)
        end
        if R.global.hp~=13 or R.global.current_hp_self~=13 then
            return "level-up changed current HP to "..tostring(R.global.hp)
        end
        -- Same numbers the source script writes on its own.
        R.global.xp=9
        R.global.lv=1
        R:call("scr_levelup", scope)
        R.global.xp=10
        R.global.lv=1
        R:call("scr_levelup", scope)
        if R.global.maxhp~=24 or R.global.at~=12 or R.global.df~=10 or R.global.lv~=2 then
            return "scr_levelup itself disagrees with the award path"
        end
        -- A grant inside the same LV must not wipe a custom AT.
        R.global.at=40
        award(1)
        if R.global.xp~=11 then return "second award EXP is "..tostring(R.global.xp) end
        if R.global.lv~=2 then return "a same-LV award changed LV to "..tostring(R.global.lv) end
        if R.global.at~=40 then return "a same-LV award rewrote AT to "..tostring(R.global.at) end
        -- LV 20 is the shared cap, not Yellow's table.
        R.global.xp=99998
        R.global.lv=19
        R.global.hp=50
        award(1)
        if R.global.lv~=20 or R.global.xp~=99999 then
            return "LV20 cap is lv "..tostring(R.global.lv).." xp "..tostring(R.global.xp)
        end
        if R.global.maxhp~=99 or R.global.at~=99 or R.global.df~=99 then
            return "LV20 stats are "..tostring(R.global.maxhp).."/"..tostring(R.global.at).."/"..tostring(R.global.df)
        end
        if R.global.hp~=50 then return "LV20 award changed current HP to "..tostring(R.global.hp) end
        return "ok"
    ''')
    assert result == "ok", result


@live
def test_battle_scripts_compose_equipment_without_folding_the_views(vm):
    """Ammo stays out of wstrength except inside Undertale's fight scripts.

    Temy armour's +10 weapon bonus is already in wstrength (scr_weaponeq) and
    must also appear in Yellow's player_weapon_attack while a fight script
    runs. Accessory defense stays out of adef except inside scr_damagestandard.
    """
    result = vm.execute('''
        R:start(); crossTo(4)
        local frisk=R:select(playerOf("undertale"))[1]
        local scope=R:scope(frisk)
        R.global.weapon=52          -- Real Knife, AT 99
        R.global.armor=64           -- temy armor, DF 20, weapon bonus 10
        R.global.player_weapon_modifier="Silver Ammo"  -- weapon_mod_strength 3
        R.global.player_armor_modifier="Steel Buckle"  -- accessory DF 7
        R.global.at=10
        R.global.df=10
        R.global.hp=20
        R.global.maxhp=20
        R.global.invc=0
        if R.global.wstrength~=109 then
            return "wstrength folded ammo or dropped the bonus: "..tostring(R.global.wstrength)
        end
        if R.global.player_weapon_attack~=99 then
            return "player_weapon_attack is not the weapon alone: "..tostring(R.global.player_weapon_attack)
        end
        if R.global.adef~=20 then return "adef folded the accessory: "..tostring(R.global.adef) end
        if R.global.player_armor_modifier_defense~=7 then
            return "accessory defense is "..tostring(R.global.player_armor_modifier_defense)
        end
        R:call("scr_attackcalc", scope)
        if R.global.pwr~=122 then
            return "Undertale fight pwr is "..tostring(R.global.pwr)..", not 99+10+3+10"
        end
        if R.global.wstrength~=109 then return "the fight call left ammo inside wstrength" end
        R.global.enemy_defense_stat=0
        R.global.enemy_count=1
        R:call("scr_determine_attacking_damage_stat_critical", scope)
        -- ((99+10) + 3 + 10 - 0 + 2) * 2.5 = 310. Without the bonus it is 285.
        if R.global.attacking_damage_stat_critical~=310 then
            return "Yellow critical is "..tostring(R.global.attacking_damage_stat_critical)..", not 310"
        end
        if R.global.player_weapon_attack~=99 then
            return "Yellow's fight call left the armour bonus inside the view"
        end
        frisk.v.dmg=20
        R:call("scr_damagestandard", R:scope(frisk), 0, 1, 0, 0, 0)
        -- round(20 - (10+20+7)/5) = 13, so HP 20-13. Without the accessory it is 14.
        if R.global.hp~=7 then
            return "Undertale hurt left HP "..tostring(R.global.hp)..", not 7"
        end
        if R.global.adef~=20 then return "the hurt call left the accessory inside adef" end
        return "ok"
    ''')
    assert result == "ok", result
