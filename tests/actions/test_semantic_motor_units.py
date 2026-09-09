from pathlib import Path

import pytest

from fle.env import Direction
from fle.env.entities import Position
from fle.env.game_types import Resource
from fle.env.tools.agent.harvest_resource.client import HarvestResource
from fle.env.tools.agent.place_path.client import PlacePath
from fle.envd.knowledge import ApiReference


pytestmark = pytest.mark.no_factorio


def test_place_path_requires_explicit_axis_aligned_corners():
    with pytest.raises(ValueError, match="axis-aligned"):
        PlacePath._rasterize([Position(0, 0), Position(2, 2)])


def test_place_path_rasterizes_and_orients_without_routing():
    route = PlacePath._rasterize(
        [Position(0, 0), Position(2, 0), Position(2, 2)]
    )

    assert [(point.x, point.y) for point in route] == [
        (0, 0), (1, 0), (2, 0), (2, 1), (2, 2)
    ]
    assert PlacePath._direction(route, 0) == Direction.RIGHT
    assert PlacePath._direction(route, 2) == Direction.DOWN
    assert PlacePath._direction(route, 4) == Direction.DOWN


def test_move_to_manual_documents_occupied_target_approach_semantics():
    manual = ApiReference().read("api/agent/move_to")["content"]

    assert "move_to(coal_pos)" in manual
    assert "interaction actions auto-approach" in manual.lower()
    assert "occupied destinations are not silently replaced" in manual.lower()


def test_live_walking_controller_has_a_bounded_no_progress_stop():
    server = (Path(__file__).parents[2] / "fle/env/tools/agent/move_to/server.lua").read_text(
        encoding="utf-8"
    )

    assert 'queue.stop_reason = "blocked_no_progress"' in server
    assert "game.tick - (queue.last_progress_tick or game.tick) >= 180" in server


def test_harvest_resource_recognizes_copper_and_uranium():
    assert HarvestResource._resource_type_from_name("copper-ore") == Resource.CopperOre
    assert HarvestResource._resource_type_from_name("uranium-ore") == Resource.UraniumOre
    assert HarvestResource._resource_type_from_name("tree-01") == Resource.Wood
