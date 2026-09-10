import pytest

from fle.env import DirectionInternal
from fle.env.entities import Position
from fle.env.game_types import Prototype, RecipeName, Resource


@pytest.fixture()
def game(configure_game):
    return configure_game(
        inventory={
            "coal": 5,
            "iron-chest": 1,
            "iron-plate": 50,
            "iron-ore": 10,
            "stone-furnace": 1,
            "assembling-machine-1": 1,
            "burner-mining-drill": 1,
            "lab": 1,
            "automation-science-pack": 1,
            "gun-turret": 1,
            "firearm-magazine": 5,
            "boiler": 1,
            "offshore-pump": 1,
        },
        merge=True,
    )


def test_get_offshore_pump(game):
    """
    Test to ensure that the inventory of an offshore pump is correctly updated after mining water
    :param game:
    :return:
    """
    # Check initial inventory
    position = game.nearest(Resource.Water)
    game.move_to(position)
    offshore_pump = game.place_entity(
        Prototype.OffshorePump, DirectionInternal.RIGHT, position
    )
    assert offshore_pump is not None, "Failed to place offshore pump"

    boiler = game.place_entity_next_to(
        Prototype.Boiler, offshore_pump.position, DirectionInternal.RIGHT, spacing=2
    )
    assert boiler

    pipes = game.connect_entities(boiler, offshore_pump, Prototype.Pipe)
    assert pipes
    game.sleep(1)
    # Load entities from the game
    offshore_pump = game.get_entities({Prototype.OffshorePump})[0]
    assert offshore_pump is not None, "Failed to retrieve offshore pump"
    # Check to see if the offshore pump has water
    assert offshore_pump.fluid_box, "Failed to get water"
    boiler = game.get_entities({Prototype.Boiler})[0]
    assert boiler is not None, "Failed to retrieve boiler"
    # Check to see if the boiler has water
    assert boiler.fluid_box, "Failed to get water"


def test_get_mining_drill(game):
    """
    Test to ensure that the inventory of a mining drill is correctly updated after mining iron ore
    :param game:
    :return:
    """
    # Check initial inventory
    position = game.nearest(Resource.IronOre)
    game.move_to(position)
    mining_drill = game.place_entity(
        Prototype.BurnerMiningDrill, DirectionInternal.UP, position
    )
    game.insert_item(Prototype.Coal, mining_drill, 5)
    assert mining_drill is not None, "Failed to place mining drill"

    game.sleep(5)
    retrieved_drill = game.get_entity(
        Prototype.BurnerMiningDrill, mining_drill.position
    )

    assert retrieved_drill is not None, "Failed to retrieve mining drill"
    assert retrieved_drill.fuel.get(Prototype.Coal, 0) < 5, "Failed to burn fuel"


@pytest.mark.parametrize(
    "prototype,position,recipe,crafts,insertions,expected_inventory",
    [
        pytest.param(
            Prototype.IronChest,
            Position(x=3, y=0),
            None,
            [],
            [(Prototype.Coal, 5), (Prototype.IronPlate, 5)],
            [("inventory", Prototype.Coal, 5), ("inventory", Prototype.IronPlate, 5)],
            id="iron-chest",
        ),
        pytest.param(
            Prototype.AssemblingMachine1,
            Position(x=5, y=0),
            RecipeName.IronGearWheel,
            [(Prototype.IronGearWheel, 5)],
            [(Prototype.IronPlate, 5), (Prototype.IronGearWheel, 5)],
            [
                ("assembling_machine_input", Prototype.IronPlate, 5),
                ("assembling_machine_output", Prototype.IronGearWheel, 5),
            ],
            id="assembling-machine",
        ),
        pytest.param(
            Prototype.Lab,
            Position(x=5, y=0),
            None,
            [],
            [(Prototype.AutomationSciencePack, 1)],
            [("lab_input", Prototype.AutomationSciencePack, 1)],
            id="lab",
        ),
        pytest.param(
            Prototype.GunTurret,
            Position(x=3, y=0),
            None,
            [],
            [(Prototype.FirearmMagazine, 5)],
            [("turret_ammo", Prototype.FirearmMagazine, 5)],
            id="turret",
        ),
        pytest.param(
            Prototype.Boiler,
            Position(x=5, y=0),
            None,
            [],
            [(Prototype.Coal, 5)],
            [("fuel", Prototype.Coal, 5)],
            id="boiler",
        ),
    ],
)
def test_get_entity_inventory(
    game, prototype, position, recipe, crafts, insertions, expected_inventory
):
    """
    Test that an entity's inventory is correctly reported via get_entity after inserting items
    :param game:
    :return:
    """
    # Check initial inventory
    inventory = game.inspect_inventory()
    assert inventory.get(prototype, 0) != 0, f"Failed to get {prototype} count"

    # Place entity away from player origin (0,0) to avoid collision
    entity = game.place_entity(prototype, position=position)
    if recipe is not None:
        game.set_entity_recipe(entity, recipe)
    for item, quantity in crafts:
        game.craft_item(item, quantity)
    for item, quantity in insertions:
        game.insert_item(item, entity, quantity=quantity)

    retrieved = game.get_entity(prototype, entity.position)

    assert retrieved is not None, f"Failed to retrieve {prototype}"
    for attr, item, quantity in expected_inventory:
        assert getattr(retrieved, attr).get(item, 0) == quantity, (
            f"Failed to insert {item} into {prototype} {attr}"
        )
