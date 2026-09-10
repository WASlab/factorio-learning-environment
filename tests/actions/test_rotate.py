import pytest

from fle.env.game_types import Prototype, RecipeName
from fle.env.entities import Position, Direction


@pytest.fixture()
def game(configure_game):
    return configure_game(
        inventory={
            "iron-chest": 1,
            "pipe": 10,
            "assembling-machine-2": 2,
            "transport-belt": 10,
            "burner-inserter": 10,
            "iron-plate": 10,
            "assembling-machine-1": 1,
            "copper-cable": 3,
        }
    )


def test_rotate_assembling_machine_2(game):
    assembler = game.place_entity_next_to(
        Prototype.AssemblingMachine2,
        reference_position=Position(x=0, y=0),
        direction=Direction.RIGHT,
        spacing=2,
    )

    with pytest.raises(Exception):
        game.rotate_entity(assembler, Direction.DOWN)


def test_rotate_assembling_machine_2_with_recipe(game):
    assembler = game.place_entity_next_to(
        Prototype.AssemblingMachine2,
        reference_position=Position(x=0, y=0),
        direction=Direction.RIGHT,
        spacing=2,
    )
    # orthogonal direction to the boiler
    orthogonal_direction = Direction.DOWN

    assembler = game.set_entity_recipe(assembler, RecipeName.FillCrudeOilBarrel)
    # rotate the boiler to face the offshore pump
    assembler = game.rotate_entity(assembler, orthogonal_direction)

    # assert that the boiler is facing the offshore pump
    assert assembler.direction.value == orthogonal_direction.value


def test_rotate_boiler(game):
    # place the boiler next to the offshore pump
    boiler = game.place_entity_next_to(
        Prototype.Boiler,
        reference_position=Position(x=0, y=0),
        direction=Direction.RIGHT,
        spacing=2,
    )
    # orthogonal direction to the boiler
    orthogonal_direction = Direction.UP

    # rotate the boiler to face the offshore pump
    boiler = game.rotate_entity(boiler, orthogonal_direction)

    # assert that the boiler is facing the offshore pump
    assert boiler.direction.value == orthogonal_direction.value


@pytest.mark.parametrize(
    "entity_prototype",
    [Prototype.TransportBelt, Prototype.BurnerInserter],
)
def test_rotate_entity_directions(game, entity_prototype):
    entity = game.place_entity(
        entity_prototype, position=(0, 0), direction=Direction.UP
    )
    assert entity.direction.value == Direction.UP.value

    for direction in [Direction.RIGHT, Direction.LEFT, Direction.DOWN, Direction.UP]:
        entity = game.rotate_entity(entity, direction=direction)
        assert entity.direction.value == direction.value


def test_rotate_transport_belt_output_and_input_position(game):
    belt = game.place_entity(
        Prototype.TransportBelt, position=(0, 0), direction=Direction.UP
    )
    assert belt.direction.value == Direction.UP.value

    rotated_belt = game.rotate_entity(belt, direction=Direction.DOWN)

    assert belt.output_position == rotated_belt.input_position
    assert belt.input_position == rotated_belt.output_position


def test_rotate_inserters_drop_and_pickup_position(game):
    inserter = game.place_entity(
        Prototype.BurnerInserter, position=(0, 0), direction=Direction.UP
    )
    assert inserter.direction.value == Direction.UP.value

    rotated_inserter = game.rotate_entity(inserter, direction=Direction.DOWN)

    assert inserter.pickup_position == rotated_inserter.drop_position
    assert inserter.drop_position == rotated_inserter.pickup_position


def test_rotate_inserters(game):
    insert1 = game.place_entity_next_to(
        Prototype.BurnerInserter, Position(x=0, y=0), Direction.DOWN, spacing=0
    )
    insert1 = game.rotate_entity(insert1, Direction.UP)
    assert insert1 is not None, "Failed to place input inserter"
    assert insert1.direction.value == Direction.UP.value
