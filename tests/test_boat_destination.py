"""D4 guards for the River Person's two-phase destination contract."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TRAVEL = (ROOT / "port/travel.lua").read_text()
BOAT = (ROOT / "objects/obj_dogboat_thing.object.gmx").read_text()


def test_boarding_room_is_not_consumed_as_a_destination():
    """The committed destination survives the room-316 boarding request."""
    assert "local boardingRoom = 316" in TRAVEL
    guard = "if index == boardingRoom then\n        return index\n    end"
    assert guard in TRAVEL
    assert "self.riverDestination = nil" in TRAVEL


def test_x_override_is_only_sampled_during_the_ride():
    """Holding X at a dock must not retarget a later native choice."""
    assert "local boardingRoom = 316" in TRAVEL
    assert "if index == boardingRoom then" in TRAVEL
    assert "self:exists(self.ids.undertale.boat)" in TRAVEL
    assert "RIVER_DESTINATIONS[index]" in TRAVEL


def test_native_boat_has_explicit_final_dock_switches():
    """The source boat, rather than stale current-room state, owns the route."""
    for room in (70, 125, 140):
        assert f"room_goto({room})" in BOAT
    assert "global.flag[459]" in BOAT
    assert re.search(r"if\(global\.flag\[459\] == 1\).*room_goto\(70\)", BOAT, re.S)


def test_yellow_points_keep_source_rooms_and_coordinates():
    for label, room, x, y in (
        ("Dunes - West Mines", "rm_dunes_05", 510, 170),
        ("Hotland - Crossroads", "rm_hotland_02", 170, 120),
    ):
        assert f'label = "{label}", room = "{room}"' in TRAVEL
        assert f'["{label}"] = {{{x}, {y}}}' in TRAVEL
