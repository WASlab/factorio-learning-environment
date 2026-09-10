from fle.env import Direction
from fle.env.entities import Position
from fle.env.tools import Tool


class RepeatPattern(Tool):
    def __call__(self, pattern, origin, count, stride):
        origin = origin if isinstance(origin, Position) else Position(*origin)
        placed = []
        for repetition in range(count):
            for entry in pattern:
                offset = entry.get("offset", (0, 0))
                position = Position(
                    x=origin.x + repetition * stride[0] + offset[0],
                    y=origin.y + repetition * stride[1] + offset[1],
                )
                try:
                    placed.append(
                        self.game_state.place_entity(
                            entry["prototype"],
                            entry.get("direction", Direction.UP),
                            position,
                            True,
                        )
                    )
                except Exception as exc:
                    return {
                        "status": "partial",
                        "placed": len(placed),
                        "entity_ids": [item.id for item in placed],
                        "stop_reason": str(exc),
                        "position": position.model_dump(),
                    }
        return {
            "status": "completed",
            "placed": len(placed),
            "entity_ids": [item.id for item in placed],
        }
