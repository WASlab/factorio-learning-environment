from PIL import Image
import pytest

from fle.agents.data.sprites.extractors.character import CharacterSpriteExtractor
from fle.agents.data.sprites.extractors.decoratives import DecorativeSpriteExtractor


pytestmark = pytest.mark.no_factorio


def test_hr_only_character_and_rocks_generate_renderer_scale_assets(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "sprites"
    sheet = source / "hr-level1_dead.png"
    Image.new("RGBA", (16, 8), "orange").save(sheet)
    CharacterSpriteExtractor(str(source), str(output)).extract_sprites_from_sheet(sheet, sheet.stem)
    with Image.open(output / "character/level1_dead_0_0.png") as sprite:
        assert sprite.size == (4, 4)
    rock = source / "rock-big"
    rock.mkdir()
    Image.new("RGBA", (12, 12), "gray").save(rock / "hr-rock-big-01.png")
    DecorativeSpriteExtractor(str(source), str(output)).extract_decorative_sprite("rock-big")
    with Image.open(output / "rock-big_1.png") as sprite:
        assert sprite.size == (6, 6)
