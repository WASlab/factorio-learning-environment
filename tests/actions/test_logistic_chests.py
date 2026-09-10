"""
Logistic Chest Action Tests

Tests verifying logistic chest placement and basic interactions.
Covers all 5 logistic chest types: passive provider, active provider,
storage, requester, and buffer chests.
"""

import pytest

from fle.env.entities import Position
from fle.env.game_types import Prototype


@pytest.fixture()
def game(configure_game):
    return configure_game(
        inventory={
            "passive-provider-chest": 5,
            "active-provider-chest": 5,
            "storage-chest": 5,
            "requester-chest": 5,
            "buffer-chest": 5,
            "iron-plate": 100,
            "roboport": 2,
            "small-electric-pole": 20,
        }
    )


@pytest.mark.parametrize(
    "chest_prototype",
    [
        Prototype.PassiveProviderChest,
        Prototype.ActiveProviderChest,
        Prototype.StorageChest,
        Prototype.RequesterChest,
        Prototype.BufferChest,
    ],
)
def test_place_logistic_chest(game, chest_prototype):
    """Test basic logistic chest placement."""
    chest = game.place_entity(chest_prototype, position=Position(x=0, y=0))
    assert chest is not None
    # 1x1 entities placed at (0,0) have center at (0.5, 0.5)
    assert chest.position.is_close(Position(x=0.5, y=0.5))


def test_logistic_chest_inventory_decrement(game):
    """Test that chest inventory count decrements on placement."""
    before = game.inspect_inventory()[Prototype.PassiveProviderChest]
    game.place_entity(Prototype.PassiveProviderChest, position=Position(x=0, y=0))
    after = game.inspect_inventory()[Prototype.PassiveProviderChest]
    assert before - 1 == after


def test_insert_items_into_logistic_chest(game):
    """Test inserting items into a logistic chest."""
    chest = game.place_entity(
        Prototype.PassiveProviderChest, position=Position(x=0, y=0)
    )
    game.insert_item(Prototype.IronPlate, chest, 50)
    updated_chest = game.get_entity(Prototype.PassiveProviderChest, chest.position)
    assert updated_chest.inventory[Prototype.IronPlate] == 50


def test_logistic_chest_pickup(game):
    """Test picking up a logistic chest."""
    before = game.inspect_inventory()[Prototype.StorageChest]
    chest = game.place_entity(Prototype.StorageChest, position=Position(x=0, y=0))
    game.pickup_entity(chest)
    after = game.inspect_inventory()[Prototype.StorageChest]
    assert before == after


def test_logistic_chest_can_be_retrieved(game):
    """Test that placed logistic chest can be retrieved via get_entity."""
    chest = game.place_entity(Prototype.RequesterChest, position=Position(x=0, y=0))
    retrieved = game.get_entity(Prototype.RequesterChest, chest.position)
    assert retrieved is not None
    assert retrieved.position.x == chest.position.x
    assert retrieved.position.y == chest.position.y
