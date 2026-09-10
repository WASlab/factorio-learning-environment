import pytest
from time import sleep
from fle.env.entities import Position, ResourcePatch, Direction
from fle.env.game_types import Prototype, RecipeName, Resource


@pytest.fixture()
def game(instance):
    instance.initial_inventory = {
        "stone-furnace": 10,
        "burner-mining-drill": 10,
        "electric-mining-drill": 5,
        "transport-belt": 200,
        "underground-belt": 20,
        "splitter": 10,
        "burner-inserter": 50,
        "fast-inserter": 20,
        "pipe": 100,
        "pipe-to-ground": 20,
        "offshore-pump": 5,
        "boiler": 5,
        "steam-engine": 10,
        "small-electric-pole": 50,
        "medium-electric-pole": 20,
        "assembling-machine-1": 10,
        "iron-chest": 20,
        "coal": 500,
        "iron-plate": 200,
        "copper-plate": 200,
    }
    instance.reset()
    yield instance.namespace


def test_edge_case_entity_placement(game):
    """Test placement of entities in tight spaces."""
    # Place entities in a tight space
    game.place_entity(Prototype.StoneFurnace, position=Position(x=0, y=0))
    game.place_entity(Prototype.StoneFurnace, position=Position(x=3, y=0))
    with pytest.raises(Exception):
        game.place_entity(Prototype.StoneFurnace, position=Position(x=1.5, y=0))


def test_error_handling_and_invalid_inputs(game):
    """Test error handling for invalid inputs and operations."""
    # Try to place an entity of the wrong type
    with pytest.raises(ValueError):
        game.place_entity("invalid_entity", position=Position(x=0, y=0))

    # Try to set an invalid recipe
    assembler = game.place_entity(
        Prototype.AssemblingMachine1, position=Position(x=5, y=5)
    )
    with pytest.raises(ValueError):
        game.set_entity_recipe(assembler, "invalid_recipe")


def test_entity_interactions(game):
    """Test complex interactions between different types of entities."""
    # Create a small power network
    water_pos = game.nearest(Resource.Water)
    game.move_to(water_pos)
    offshore_pump = game.place_entity(Prototype.OffshorePump, position=water_pos)
    boiler = game.place_entity_next_to(
        Prototype.Boiler, offshore_pump.position, Direction.RIGHT, spacing=1
    )
    steam_engine = game.place_entity_next_to(
        Prototype.SteamEngine, boiler.position, Direction.RIGHT, spacing=1
    )
    game.connect_entities(offshore_pump, boiler, Prototype.Pipe)
    game.connect_entities(boiler, steam_engine, Prototype.Pipe)

    # Create an assembly line
    assembler = game.place_entity_next_to(
        Prototype.AssemblingMachine1, steam_engine.position, Direction.DOWN, spacing=5
    )
    game.set_entity_recipe(assembler, RecipeName.IronGearWheel)

    input_chest = game.place_entity_next_to(
        Prototype.IronChest,
        assembler.position,
        Direction.LEFT,
        spacing=assembler.tile_dimensions.tile_width - 1,
    )
    output_chest = game.place_entity_next_to(
        Prototype.IronChest,
        assembler.position,
        Direction.RIGHT,
        spacing=assembler.tile_dimensions.tile_width - 1,
    )

    game.place_entity_next_to(
        Prototype.BurnerInserter, input_chest.position, Direction.RIGHT, spacing=0.5
    )
    game.place_entity_next_to(
        Prototype.BurnerInserter, output_chest.position, Direction.LEFT, spacing=0.5
    )

    # Connect power
    game.connect_entities(steam_engine, assembler, Prototype.SmallElectricPole)

    # Insert materials and run the assembly line
    game.insert_item(Prototype.IronPlate, input_chest, 50)
    game.insert_item(Prototype.Coal, boiler, 50)

    # Wait for production
    sleep(30)

    # Check if iron gear wheels were produced
    output_inventory = game.inspect_inventory(output_chest)
    assert output_inventory[Prototype.IronGearWheel] > 0, (
        "No iron gear wheels were produced"
    )


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__])
