import pytest

from fle.env.entities import Position, EntityStatus, Direction
from fle.env.game_types import Prototype, Resource


@pytest.fixture()
def game(instance):
    instance.initial_inventory = {
        **instance.initial_inventory,
        "stone-furnace": 10,
        "burner-inserter": 50,
        "offshore-pump": 4,
        "pipe": 100,
        "small-electric-pole": 50,
        "medium-electric-pole": 50,
        "big-electric-pole": 50,
        "transport-belt": 200,
        "coal": 100,
        "wooden-chest": 1,
        "assembling-machine-1": 10,
    }
    instance.reset()
    yield instance.namespace
    # instance.reset()


def test_connect_steam_engine_to_assembler_with_electricity_poles(game):
    """
    Place a steam engine and an assembling machine next to each other.
    Connect them with electricity poles.
    :param game:
    :return:
    """
    steam_engine = game.place_entity(Prototype.SteamEngine, position=Position(x=0, y=0))
    assembler = game.place_entity_next_to(
        Prototype.AssemblingMachine1,
        reference_position=steam_engine.position,
        direction=game.RIGHT,
        spacing=10,
    )
    game.move_to(Position(x=5, y=5))
    diagonal_assembler = game.place_entity(
        Prototype.AssemblingMachine1, position=Position(x=10, y=10)
    )

    # check to see if the assemblers are connected to the electricity network
    inspected_assemblers = game.get_entities(
        {Prototype.AssemblingMachine1}, position=diagonal_assembler.position
    )

    for a in inspected_assemblers:
        assert a.warnings == ["not connected to power network"]

    poles_in_inventory = game.inspect_inventory()[Prototype.SmallElectricPole]

    game.connect_entities(
        steam_engine, assembler, connection_type=Prototype.SmallElectricPole
    )
    poles2 = game.connect_entities(
        steam_engine, diagonal_assembler, connection_type=Prototype.SmallElectricPole
    )

    current_poles_in_inventory = game.inspect_inventory()[Prototype.SmallElectricPole]
    spent_poles = poles_in_inventory - current_poles_in_inventory

    assert spent_poles == len(poles2.poles)

    # check to see if the assemblers are connected to the electricity network
    assemblers = game.get_entities({Prototype.AssemblingMachine1})
    for assembler in assemblers:
        assert assembler.status == EntityStatus.NO_POWER


def test_connect_steam_engine_mining_drill(game):
    pos = game.nearest(Resource.Water)
    game.move_to(pos)
    pump = game.place_entity(Prototype.OffshorePump, position=pos)
    boiler = game.place_entity_next_to(
        Prototype.Boiler,
        reference_position=pump.position,
        spacing=2,
        direction=Direction.RIGHT,
    )
    game.connect_entities(pump, boiler, Prototype.Pipe)
    steam_engine = game.place_entity_next_to(
        Prototype.SteamEngine,
        reference_position=boiler.position,
        spacing=2,
        direction=Direction.UP,
    )
    game.connect_entities(boiler, steam_engine, Prototype.Pipe)
    game.insert_item(Prototype.Coal, boiler, 2)
    game.sleep(2)
    pos = game.nearest(Resource.IronOre)
    game.move_to(pos)
    drill = game.place_entity(Prototype.ElectricMiningDrill, position=pos)
    game.connect_entities(drill, steam_engine, Prototype.SmallElectricPole)
    game.sleep(2)
    drill = game.get_entity(Prototype.ElectricMiningDrill, position=pos)
    assert (
        drill.status == EntityStatus.WORKING
        or drill.status == EntityStatus.WAITING_FOR_SPACE_IN_DESTINATION
    )


def test_pole_groups(game):
    water_position = game.nearest(Resource.Water)
    game.move_to(water_position)
    offshore_pump = game.place_entity(Prototype.OffshorePump, position=water_position)
    print(offshore_pump)
    boiler = game.place_entity_next_to(
        Prototype.Boiler, reference_position=offshore_pump.position, spacing=3
    )
    boiler = game.insert_item(Prototype.Coal, boiler, 10)
    steam_engine = game.place_entity_next_to(
        Prototype.SteamEngine, reference_position=boiler.position, spacing=3
    )
    print(f"Placed steam_engine at {steam_engine.position}")  # Position(x=4, y = -21)
    game.connect_entities(offshore_pump, boiler, Prototype.Pipe)
    game.connect_entities(boiler, steam_engine, Prototype.Pipe)
    game.sleep(5)
    print(steam_engine)
    game.connect_entities(
        steam_engine.position, Position(x=4, y=-20), Prototype.SmallElectricPole
    )
    entities = game.get_entities()
    assert len(entities) == 6


def test_connect_electricity_2(game):
    # Find water for power generation
    print("Starting to build power infrastructure")
    water_pos = game.nearest(Resource.Water)
    game.move_to(water_pos)

    # Place offshore pump
    pump = game.place_entity(Prototype.OffshorePump, position=water_pos)
    print(f"Placed offshore pump at {pump.position}")

    # Place boiler with spacing for pipes
    boiler = game.place_entity_next_to(
        Prototype.Boiler,
        reference_position=pump.position,
        direction=Direction.RIGHT,
        spacing=2,
    )
    print(f"Placed boiler at {boiler.position}")

    # Add coal to boiler
    boiler = game.insert_item(Prototype.Coal, boiler, 50)
    print("Added coal to boiler")

    # Place steam engine with spacing for pipes
    steam_engine = game.place_entity_next_to(
        Prototype.SteamEngine,
        reference_position=boiler.position,
        direction=Direction.RIGHT,
        spacing=2,
    )
    print(f"Placed steam engine at {steam_engine.position}")

    # Connect pump to boiler with pipes
    game.connect_entities(pump, boiler, Prototype.Pipe)
    print("Connected water from pump to boiler")

    # Connect boiler to steam engine with pipes
    game.connect_entities(boiler, steam_engine, Prototype.Pipe)
    print("Connected steam from boiler to engine")

    # Sleep to let system start up
    game.sleep(5)

    # Verify power generation
    steam_engine = game.get_entity(Prototype.SteamEngine, steam_engine.position)
    assert steam_engine.energy > 0, "Steam engine is not generating power"
    print("Power infrastructure successfully built and generating electricity")
    pole_group = game.connect_entities(
        steam_engine, Position(x=0, y=0), Prototype.SmallElectricPole
    )
    pole_group = game.connect_entities(
        pole_group, Position(x=10, y=-10), Prototype.SmallElectricPole
    )


def test_prevent_power_pole_cobwebbing(game):
    """
    Test that the connect_entities function prevents unnecessary power pole placement
    when points are already connected to the same power network.
    """
    # Place initial power setup
    steam_engine = game.place_entity(Prototype.SteamEngine, position=Position(x=0, y=0))

    # Place a series of poles forming a basic grid
    pole1 = game.place_entity_next_to(
        Prototype.SmallElectricPole, steam_engine.position, Direction.RIGHT, spacing=3
    )
    pole2 = game.place_entity_next_to(
        Prototype.SmallElectricPole, steam_engine.position, Direction.DOWN, spacing=3
    )
    pole3 = game.place_entity_next_to(
        Prototype.SmallElectricPole, pole1.position, Direction.DOWN, spacing=3
    )

    # First connection should work - creates initial power network
    game.connect_entities(
        steam_engine, pole3, connection_type=Prototype.SmallElectricPole
    )
    nr_of_poles = len(game.get_entities({Prototype.ElectricityGroup})[0].poles)
    # Now attempt to connect points that are already in the same network
    game.connect_entities(pole1, pole2, connection_type=Prototype.SmallElectricPole)

    # Verify no additional poles were placed
    groups = game.get_entities({Prototype.ElectricityGroup})
    assert len(groups[0].poles) == nr_of_poles, (
        f"Expected only {nr_of_poles} poles, found {len(groups[0].poles)}"
    )

    # Check that all poles share the same electrical network ID
    ids = {pole.electrical_id for pole in groups[0].poles}
    assert len(ids) == 1, "All poles should be in the same network"


@pytest.mark.parametrize(
    "source,target,poles_type",
    [
        pytest.param(
            Position(x=30, y=30),
            Position(x=35, y=30),
            Prototype.SmallElectricPole,
            id="positions-small-poles",
        ),
        pytest.param(
            Position(x=40, y=40),
            Position(x=50, y=50),
            Prototype.SmallElectricPole,
            id="positions-far-small-poles",
        ),
        pytest.param(
            Position(x=100, y=100),
            Position(x=110, y=100),
            Prototype.SmallElectricPole,
            id="far-positions-small-poles",
        ),
        pytest.param(
            Position(x=100, y=100),
            Position(x=110, y=100),
            Prototype.MediumElectricPole,
            id="far-positions-medium-poles",
        ),
        pytest.param(
            Position(x=100, y=100),
            Position(x=110, y=100),
            Prototype.BigElectricPole,
            id="far-positions-big-poles",
        ),
    ],
)
def test_get_existing_electricity_connection_group(game, source, target, poles_type):
    """Test existing electricity group return functionality"""
    # First electricity connection
    first_poles = game.connect_entities(source, target, poles_type)
    assert first_poles, "Initial pole connection should succeed"

    # Second attempt should return existing group
    second_poles = game.connect_entities(source, target, poles_type)
    assert second_poles, "Second pole connection should return existing group"
