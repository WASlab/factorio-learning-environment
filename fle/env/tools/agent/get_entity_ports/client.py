from fle.env.entities import Entity
from fle.env.tools import Tool


class GetEntityPorts(Tool):
    def __call__(self, entity: Entity) -> dict:
        fresh = (
            self.game_state.resolve_entity(entity) if entity.id is not None else entity
        )
        return {
            "entity_id": fresh.id,
            "name": fresh.name,
            "inputs": getattr(fresh, "input_connection_points", []) or [],
            "outputs": getattr(fresh, "output_connection_points", []) or [],
        }
