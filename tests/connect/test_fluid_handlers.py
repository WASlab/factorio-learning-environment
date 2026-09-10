import pytest

from fle.env.entities import Position, BuildingBox
from fle.env import DirectionInternal as Direction
from fle.env.game_types import Prototype, Resource


@pytest.fixture()
def game(instance):
    instance.initial_inventory = {
        **instance.initial_inventory,
        "stone-furnace": 10,
        "burner-inserter": 50,
        "offshore-pump": 4,
        "pipe": 300,
        "pipe-to-ground": 100,
        "small-electric-pole": 50,
        "transport-belt": 200,
        "coal": 100,
        "wooden-chest": 1,
        "assembling-machine-1": 10,
        "boiler": 3,
        "steam-engine": 3,
    }
    instance.reset()
    yield instance.namespace
    instance.reset()


def create_electricity_connection(game, steam_engine_pos, boiler_pos):
    water_pos = game.nearest(Resource.Water)
    game.move_to(water_pos)
    offshore_pump = game.place_entity(Prototype.OffshorePump, position=water_pos)
    print(offshore_pump)
    game.move_to(boiler_pos)
    boiler = game.place_entity(Prototype.Boiler, position=boiler_pos)
    game.insert_item(Prototype.Coal, boiler, 20)
    water_pipes = game.connect_entities(
        offshore_pump, boiler, {Prototype.Pipe, Prototype.UndergroundPipe}
    )

    game.move_to(steam_engine_pos)
    engine = game.place_entity(Prototype.SteamEngine, position=steam_engine_pos)
    steam_pipes = game.connect_entities(
        boiler, engine, {Prototype.Pipe, Prototype.UndergroundPipe}
    )
    engine = game.get_entity(Prototype.SteamEngine, engine.position)

    assert steam_pipes
    assert water_pipes
    assert engine.energy > 0


@pytest.mark.parametrize(
    "steam_engine_pos,boiler_pos",
    [
        pytest.param(
            Position(x=-15.5, y=-5.5).left(20).up(10),
            Position(x=-15.5, y=-5.5),
            id="far-west",
        ),
        pytest.param(
            Position(x=-5.5, y=0.5).up(4),
            Position(x=-5.5, y=0.5),
            id="vertical-close",
        ),
        pytest.param(
            Position(x=-5.5, y=4.5).up(15).left(15),
            Position(x=-5.5, y=4.5),
            id="northwest",
        ),
        pytest.param(
            Position(x=-5.5, y=4.5).left(20),
            Position(x=-5.5, y=4.5),
            id="far-west-horizontal",
        ),
        pytest.param(
            Position(x=-5.5, y=-2.5).right(5),
            Position(x=-5.5, y=-2.5),
            id="east",
        ),
        pytest.param(
            Position(x=-5.5, y=-2.5).down(5),
            Position(x=-5.5, y=-2.5),
            id="vertical-below",
        ),
        pytest.param(
            Position(x=-15.5, y=-7.5),
            Position(x=-5.5, y=-2.5),
            id="southwest",
        ),
        pytest.param(
            Position(x=-15.5, y=-7.5),
            Position(x=-5.5, y=5.5),
            id="southwest-far",
        ),
        pytest.param(
            Position(x=-15.5, y=-7.5),
            Position(x=-8.5, y=5.5),
            id="southwest-offset",
        ),
        pytest.param(
            Position(x=-5.5, y=-7.5),
            Position(x=-8.5, y=5.5),
            id="south",
        ),
        pytest.param(
            Position(x=8.5, y=15.5),
            Position(x=8.5, y=5.5),
            id="north",
        ),
        pytest.param(
            Position(x=8.5, y=4.5),
            Position(x=0.5, y=-5.5),
            id="southwest-horizontal",
        ),
    ],
)
def test_electricity_configuration(game, steam_engine_pos, boiler_pos):
    """Test electricity connection between a boiler and a steam engine"""
    create_electricity_connection(game, steam_engine_pos, boiler_pos)


def test_connect_steam_engines(game):
    steam_engine_pos1 = Position(x=0, y=4.5)
    game.move_to(steam_engine_pos1)
    engine1 = game.place_entity(Prototype.SteamEngine, position=steam_engine_pos1)

    steam_engine_pos2 = Position(x=5, y=4.5)
    game.move_to(steam_engine_pos2)
    engine2 = game.place_entity(Prototype.SteamEngine, position=steam_engine_pos2)

    pipes = game.connect_entities(engine1, engine2, Prototype.Pipe)
    game.connect_entities(engine1, engine2, Prototype.Pipe)

    assert pipes


def test_connect_boilers(game):
    pos1 = Position(x=0, y=4.5)
    game.move_to(pos1)
    boiler1 = game.place_entity(Prototype.Boiler, position=pos1)

    pos2 = Position(x=5, y=4.5)
    game.move_to(pos2)
    boiler2 = game.place_entity(Prototype.Boiler, position=pos2)

    pipes = game.connect_entities(boiler1, boiler2, Prototype.Pipe)

    assert pipes


def test_multiple(game):
    # Find water source for power system
    water_pos = game.nearest(Resource.Water)
    print(f"Found water source at {water_pos}")

    # Place offshore pump
    game.move_to(water_pos)
    offshore_pump = game.place_entity(Prototype.OffshorePump, position=water_pos)
    print(f"Placed offshore pump at {offshore_pump.position}")

    # Place boiler next to pump
    building_box = BuildingBox(width=3, height=3)
    buildable_coords = game.nearest_buildable(
        Prototype.Boiler, building_box, offshore_pump.position
    )
    boiler_pos = Position(
        x=buildable_coords.left_top.x + 1.5, y=buildable_coords.left_top.y + 1.5
    )
    game.move_to(boiler_pos)
    boiler = game.place_entity(Prototype.Boiler, position=boiler_pos)
    print(f"Placed boiler at {boiler.position}")

    # Place steam engine next to boiler
    building_box = BuildingBox(width=3, height=5)
    buildable_coords = game.nearest_buildable(
        Prototype.SteamEngine, building_box, boiler.position
    )
    engine_pos = (
        buildable_coords.center
    )  # Position(x=buildable_coords.left_top.x, y=buildable_coords.left_top.y)
    game.move_to(engine_pos)
    steam_engine = game.place_entity(Prototype.SteamEngine, position=engine_pos)
    print(f"Placed steam engine at {steam_engine.position}")

    # Connect offshore pump to boiler with pipes
    pump_to_boiler = game.connect_entities(
        offshore_pump.position, boiler.position, Prototype.Pipe
    )
    print(f"Connected offshore pump to boiler with pipes: {pump_to_boiler}")

    # Connect boiler to steam engine with pipes
    boiler_to_engine = game.connect_entities(
        boiler.position, steam_engine.position, Prototype.Pipe
    )
    print(f"Connected boiler to steam engine with pipes: {boiler_to_engine}")


def test_for_attribute_error(game):
    # Find water dynamically and place offshore pump
    water_pos = game.nearest(Resource.Water)
    game.move_to(water_pos)
    pump = game.place_entity(
        Prototype.OffshorePump, position=water_pos, direction=Direction.UP
    )
    # Place boiler near the pump
    boiler = game.place_entity_next_to(
        Prototype.Boiler,
        reference_position=pump.position,
        direction=pump.direction,
        spacing=3,
    )
    game.connect_entities(pump, boiler, Prototype.Pipe)
    try:
        engine = game.place_entity_next_to(
            Prototype.SteamEngine,
            reference_position=boiler.position,
            direction=boiler.direction,
            spacing=3,
        )
        game.connect_entities(engine, boiler, Prototype.Pipe)
    except Exception as e:
        # fail the test if the exception is an AttributeError
        assert not isinstance(e, AttributeError)
