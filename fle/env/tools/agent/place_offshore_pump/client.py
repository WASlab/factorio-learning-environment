from fle.env import Direction
from fle.env.entities import Position
from fle.env.game_types import Prototype
from fle.env.tools import Tool


class PlaceOffshorePump(Tool):
    def __call__(self, preferred_position: Position, direction=Direction.UP):
        return self.game_state.place_entity(
            Prototype.OffshorePump,
            direction=direction,
            position=preferred_position,
            exact=True,
        )
