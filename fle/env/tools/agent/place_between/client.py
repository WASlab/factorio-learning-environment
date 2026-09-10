from fle.env import Direction
from fle.env.entities import Position
from fle.env.tools import Tool


class PlaceBetween(Tool):
    """Place at an explicit tile and infer orientation from source to target."""

    def __call__(self, prototype, source, target, position):
        source_pos = source.position if hasattr(source, "position") else source
        target_pos = target.position if hasattr(target, "position") else target
        position = position if isinstance(position, Position) else Position(*position)
        dx, dy = target_pos.x - source_pos.x, target_pos.y - source_pos.y
        if abs(dx) >= abs(dy):
            direction = Direction.RIGHT if dx > 0 else Direction.LEFT
        else:
            direction = Direction.DOWN if dy > 0 else Direction.UP
        entity = self.game_state.place_entity(prototype, direction, position, True)
        return {
            "status": "completed",
            "entity": entity,
            "entity_id": entity.id,
            "direction": direction.name,
        }
