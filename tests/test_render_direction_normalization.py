"""Direction encoding normalization for blueprint and camera render inputs."""

import pytest

from fle.commons.directions import normalize_render_direction
from fle.env.tools.admin.render.utils import flatten_entities

pytestmark = pytest.mark.no_factorio


def entity(name: str, direction) -> dict:
    return {"name": name, "position": {"x": 0, "y": 0}, "direction": direction}


def test_normalization_preserves_cardinals_and_snaps_diagonals():
    assert normalize_render_direction(0) == 0
    assert normalize_render_direction(4) == 4
    assert normalize_render_direction(12.0) == 12
    assert normalize_render_direction(6) == 8
    assert normalize_render_direction(14) == 0
    assert normalize_render_direction(None) == 0
    assert normalize_render_direction("junk") == 0


def test_normalization_supports_index_style_legacy_values():
    assert normalize_render_direction(1, index_direction=True) == 4
    assert normalize_render_direction(3, index_direction=True) == 8
    assert normalize_render_direction(6, index_direction=True) == 12


def test_flatten_keeps_cardinal_directions_when_later_entities_face_west():
    flattened = list(
        flatten_entities(
            [
                entity("burner-mining-drill", 4),
                entity("character", 12),
            ]
        )
    )
    assert [int(item.direction.value) for item in flattened] == [4, 12]


def test_flatten_detects_index_style_lists_and_never_mutates_input():
    source = [entity("burner-mining-drill", 1), entity("character", 3)]
    flattened = list(flatten_entities(source))
    assert [int(item.direction.value) for item in flattened] == [4, 8]
    assert [item["direction"] for item in source] == [1, 3]
