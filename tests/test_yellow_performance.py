"""D2 guards: Yellow rendering must not rebuild draw records every frame."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_render_reuses_the_yellow_draw_record_pool():
    source = (ROOT / "port/graphics.lua").read_text()
    assert "self._drawItemPool" in source
    assert "local function append(item)" in source
    assert "append({depth=(layer and layer.depth)" in source
    assert "append({depth=self:particleDepth(sys)" in source


def test_static_tile_draw_list_is_cached_per_room():
    source = (ROOT / "port/graphics.lua").read_text()
    assert "self.roomState.staticTileDrawList" in source
    assert "if not staticTiles then" in source
