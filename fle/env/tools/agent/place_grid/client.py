from fle.env import Direction
from fle.env.entities import Position
from fle.env.tools import Tool


class PlaceGrid(Tool):
    def __call__(
        self, prototype, origin, rows, columns, spacing=(1, 1), direction=Direction.UP
    ):
        if rows <= 0 or columns <= 0:
            raise ValueError("rows and columns must be positive")
        origin = origin if isinstance(origin, Position) else Position(*origin)
        placed, failures = [], []
        for row in range(rows):
            for column in range(columns):
                position = Position(
                    x=origin.x + column * spacing[0], y=origin.y + row * spacing[1]
                )
                try:
                    placed.append(
                        self.game_state.place_entity(
                            prototype, direction, position, True
                        )
                    )
                except Exception as exc:
                    failures.append(
                        {"position": position.model_dump(), "message": str(exc)}
                    )
                    return {
                        "status": "partial",
                        "placed": len(placed),
                        "entity_ids": [item.id for item in placed],
                        "failures": failures,
                    }
        return {
            "status": "completed",
            "placed": len(placed),
            "entity_ids": [item.id for item in placed],
            "failures": failures,
        }
