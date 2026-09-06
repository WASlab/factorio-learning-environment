from unittest.mock import Mock

import pytest

from fle.env.game_types import Prototype
from fle.env.tools.agent.nearest.client import Nearest
from fle.env.tools.agent.place_entity_next_to.client import PlaceEntityNextTo

pytestmark = pytest.mark.no_factorio


def test_missing_entity_is_a_lookup_error():
    tool = object.__new__(Nearest)
    tool.player_index = 1
    tool.execute = Mock(return_value=("Could not find an entity called iron-chest", 0))
    with pytest.raises(LookupError, match="No iron-chest"):
        tool(Prototype.IronChest)


def test_invalid_direction_has_actionable_error_before_execution():
    tool = object.__new__(PlaceEntityNextTo)
    with pytest.raises(ValueError, match="Direction.RIGHT"):
        tool(Prototype.WoodenChest, direction=4)
