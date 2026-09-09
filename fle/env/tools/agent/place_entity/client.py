import json

from fle.env.entities import Position, Entity
from fle.env import DirectionInternal, Direction
from fle.env.game_types import Prototype
from fle.env.tools.agent.get_entity.client import GetEntity
from fle.env.tools.agent.pickup_entity.client import PickupEntity
from fle.env.tools import Tool
from fle.env.tools.spatial import normalize_spatial


class PlaceObject(Tool):
    def __init__(self, *args):
        super().__init__(*args)
        self.name = "place_entity"
        self.load()
        self.get_entity = GetEntity(*args)
        self.pickup_entity = PickupEntity(*args)

    def __call__(
        self,
        entity: Prototype,
        direction: Direction = Direction.UP,
        position: Position = Position(x=0, y=0),
        exact: bool = True,
        # relative=False
    ) -> Entity:
        """
        Places an entity e at local position (x, y) if you have it in inventory.
        :param entity: Entity to place
        :param direction: Cardinal direction to place
        :param position: Position to place entity
        :param exact: If True, place entity at exact position, else place entity at nearest possible position
        :return: Entity object
        """

        # if not isinstance(entity, Prototype):
        #    raise ValueError("The first argument must be a Prototype object")

        # If position is a tuple, cast it to a Position object:
        if isinstance(position, tuple):
            position = Position(x=position[0], y=position[1])

        if not isinstance(position, Position):
            raise ValueError("The position argument must be a Position object")

        if not isinstance(direction, (DirectionInternal, Direction)):
            raise ValueError("The second argument must be a Direction object")

        x, y = self.get_position(position)
        self.ensure_reachable(position)
        try:
            name, metaclass = entity.value
            while isinstance(metaclass, tuple):
                metaclass = metaclass[1]
        except Exception as e:
            raise Exception(f"Passed in {entity} argument is not a valid Prototype", e)

        factorio_direction = DirectionInternal.to_factorio_direction(direction)

        try:
            # If we are in `fast` mode, this is synchronous
            response, elapsed = self.execute(
                self.player_index, name, factorio_direction, x, y, exact
            )
        except Exception as error:
            raise RuntimeError(
                f"Could not place {name} at ({x}, {y}): {error}"
            ) from error

        if not isinstance(response, dict):
            raise RuntimeError(f"Could not place {name} at ({x}, {y}): {response}")
        if response.get("error"):
            raise RuntimeError(json.dumps(normalize_spatial(response), sort_keys=True))
        cleaned_response = self.clean_response(response)
        return metaclass(
            prototype=entity.name, game=self.connection, **cleaned_response
        )
