import math

from fle.env.entities import Position
from fle.env.tools import Tool


class PlacePowerLine(Tool):
    def __call__(self, points, pole, spacing: float = 7.0):
        if spacing <= 0:
            raise ValueError("spacing must be positive")
        points = [p if isinstance(p, Position) else Position(*p) for p in points]
        positions = [points[0]]
        for start, end in zip(points, points[1:]):
            dx, dy = end.x - start.x, end.y - start.y
            distance = math.hypot(dx, dy)
            segments = max(1, math.ceil(distance / spacing))
            for index in range(1, segments + 1):
                positions.append(
                    Position(
                        x=start.x + dx * index / segments,
                        y=start.y + dy * index / segments,
                    )
                )
        placed = []
        for position in positions:
            try:
                placed.append(
                    self.game_state.place_entity(pole, position=position, exact=True)
                )
            except Exception as exc:
                return {
                    "status": "partial",
                    "placed": len(placed),
                    "stop_reason": str(exc),
                    "position": position.model_dump(),
                }
        return {
            "status": "completed",
            "placed": len(placed),
            "entity_ids": [entity.id for entity in placed],
        }
