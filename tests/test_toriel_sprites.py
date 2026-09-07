"""Toriel directional/talking sprite IDs must resolve to real sprite assets.

The decompiled GML sets dsprite/usprite/lsprite/rsprite and the *talking*
variants (dtsprite/utsprite/ltsprite/rtsprite) to numeric IDs that only a
small number of annotations recover. The obj_toriel_friendc / obj_toroverworld*
/ obj_torinteractable* / obj_torhandhold* objects reference the up-talking
sprite as 1111 and the hand-hold sprites as 1113/1117. Those IDs fell through to
synthetic IDs (or were absent entirely), so Toriel's up and hand-hold poses
rendered as a blank sprite. This test locks the documented overrides and
asserts every directional sprite ID a Toriel object assigns resolves to a real,
non-empty sprite.
"""
import re
from pathlib import Path

import pytest
from lupa.luajit21 import LuaError

ROOT = Path(__file__).resolve().parents[1]
SPRITE_ASSIGN = re.compile(r"\b([dlru]t?|u|r|l|d)sprite\s*=\s*(\d+)")


def _sprite_indexes():
    """Collect numeric sprite IDs referenced by any Toriel-family object."""
    indexes = set()
    for gmx in (ROOT / "objects").glob("*.gmx"):
        if not re.search(r"toriel|toroverworld|torinteract|torhandhold|tortrigger|tori(trigger|buster)|asriel", gmx.name):
            continue
        for _, index in SPRITE_ASSIGN.findall(gmx.read_text()):
            indexes.add(int(index))
    return indexes


def test_toriel_directional_sprite_constants(lua):
    expected = {
        "spr_toriel_d": 1103,
        "spr_toriel_dt": 1105,
        "spr_toriel_r": 1107,
        "spr_toriel_l": 1108,
        "spr_toriel_rt": 1109,
        "spr_toriel_lt": 1110,
        "spr_toriel_ut": 1111,
        "spr_toriel_u": 1112,
        "spr_toriel_handhold_d": 1113,
        "spr_toriel_handhold_u": 1117,
    }
    for name, index in expected.items():
        assert lua.eval(f"R.constants.{name}") == index, name
        sprite = lua.eval(f"R.assets.sprites[{index}]")
        assert sprite is not None, name
        assert lua.eval(f"#R.assets.sprites[{index}].frames") > 0, name


def test_every_toriel_directional_sprite_id_resolves(lua):
    # ids = {name -> index} for the whole sprite atlas as the runtime sees it.
    for index in sorted(_sprite_indexes()):
        sprite = lua.eval(f"R.assets.sprites[{index}]")
        assert sprite is not None, f"sprite ID {index} referenced by a Toriel object is unresolved"
        assert lua.eval(f"#R.assets.sprites[{index}].frames") > 0, f"sprite ID {index} has no frames"


def test_toriel_up_and_handhold_sprites_are_not_synthetic(lua):
    # These were previously absent/synthetic -> blank up/hand-hold Toriel sprite.
    for name in ("spr_toriel_ut", "spr_toriel_handhold_d", "spr_toriel_handhold_u"):
        assert lua.eval(f"R.constants.{name}") < 20000, name
        assert lua.eval(f"R.manifest.names.{name}") < 20000, name
