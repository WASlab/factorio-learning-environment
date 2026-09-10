import pytest

from fle.env.entities import Position
from fle.env.game_types import Prototype


@pytest.fixture()
def game(configure_game):
    return configure_game(
        inventory={
            "coal": 50,
            "iron-chest": 1,
            "iron-plate": 5,
            "stone-furnace": 1,
        }
    )


def test_move_to_invalid_positions(game):
    """Test move_to behavior with potentially problematic positions"""
    # Test some edge case positions that might trigger string responses
    edge_positions = [
        Position(x=0, y=0),  # Origin
        Position(x=-1, y=-1),  # Negative coordinates
        Position(x=1000, y=1000),  # Very far position
    ]

    for pos in edge_positions:
        try:
            game.move_to(pos)
            print(f"✓ Successfully moved to edge position {pos}")
        except Exception as e:
            # Should get properly formatted error messages, not raw Lua errors
            error_msg = str(e)
            assert "Could not move" in error_msg or "Could not get path" in error_msg, (
                f"Should get formatted error: {error_msg}"
            )
            print(f"✓ Got expected move failure for {pos}: {error_msg}")


def test_move_to_near_entities(game):
    """Test movement near entities doesn't cause string response errors"""
    # Place an entity
    game.move_to(Position(x=18, y=20))
    furnace = game.place_entity(Prototype.StoneFurnace, position=Position(x=20, y=20))
    assert furnace, "Failed to place furnace"

    # Try to move very close to the entity
    try:
        game.move_to(Position(x=20.1, y=20.1))  # Very close to entity
        print("✓ Can move very close to entities")
    except Exception as e:
        # Should get proper error message if movement fails
        error_msg = str(e)
        assert "Could not move" in error_msg, f"Should get formatted error: {error_msg}"
        print(f"✓ Got proper error for blocked movement: {error_msg}")
