from fle.env.entities import Entity
from fle.env.game_types import Prototype
from fle.env.tools import Tool
from fle.env.tools.agent.get_entity.client import GetEntity


class ResolveEntity(Tool):
    """Resolve a stable Factorio unit-number handle to a fresh entity view."""

    def __init__(self, connection, game_state):
        super().__init__(connection, game_state)
        self.get_entity = GetEntity(connection, game_state)

    def __call__(self, handle: int | Entity):
        unit_number = handle.id if isinstance(handle, Entity) else handle
        if not isinstance(unit_number, int):
            raise ValueError("resolve_entity requires an entity id/unit number")
        response, _ = self.execute(self.player_index, unit_number)
        if not isinstance(response, dict):
            raise Exception(f"Entity handle {unit_number} is stale: {response}")
        name = str(response["name"]).strip('"')
        prototype = next((value for value in Prototype if value.value[0] == name), None)
        if prototype is None:
            raise Exception(f"No Prototype member for resolved entity {name}")
        from fle.env.entities import Position

        return self.get_entity(prototype, Position(**response["position"]))
