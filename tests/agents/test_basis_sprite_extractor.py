from pathlib import Path

from PIL import Image
import pytest

from fle.agents.data.sprites.extractors.entities import EntitySpritesheetExtractor
from fle.env.tools.admin.render.renderer import Renderer

pytestmark = pytest.mark.no_factorio


def test_basis_cache_key_is_flat_on_windows(tmp_path, monkeypatch):
    data_path = tmp_path / "spritemaps"
    data_path.mkdir()
    (data_path / "data.json").write_text("{}", encoding="utf-8")
    source = data_path / "__base__" / "graphics" / "entity" / "furnace.basis"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"basis")
    extractor = EntitySpritesheetExtractor(str(data_path), str(tmp_path / "sprites"))
    outputs: list[Path] = []

    def fake_transcode(_source: Path, output: Path) -> bool:
        outputs.append(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (1, 1)).save(output)
        return True

    monkeypatch.setattr(extractor, "_transcode_basis_to_png", fake_transcode)

    extractor._load_basis_file(source)

    assert outputs[0].parent == extractor.cache_dir
    assert "\\" not in outputs[0].name


def test_renderer_uses_explicit_world_center(tmp_path):
    renderer = Renderer(
        entities=[{"name": "stone-furnace", "position": {"x": 11, "y": -3}}],
        sprites_dir=tmp_path,
        max_render_radius=8,
        center_position={"x": 10, "y": -4},
    )

    assert renderer.offset_x == 10
    assert renderer.offset_y == -4
    assert renderer.entities[0].position.x == 1
    assert renderer.entities[0].position.y == 1
