from fle.env.entities import Position
from fle.env.tools import Tool


class TraceBelt(Tool):
    def __call__(self, position: Position, max_tiles: int = 64) -> dict:
        """Follow a belt downstream and report where flow stops.

        Each entry in ``tiles`` includes the belt position, flow direction,
        ``active`` flag, and per-lane item contents.  ``blocker`` is the first
        downstream tile that cannot accept items: ``end_of_line`` when no belt
        follows, ``blocked_by_entity`` (with the blocking entity) when a
        non-belt entity occupies the next tile, or ``max_tiles_reached``.
        Broken or wrong-facing belt segments show up as an ``end_of_line`` or
        a direction change that does not match the previous flow direction.

        :param position: Position of any belt tile in the line
        :param max_tiles: Maximum number of belt tiles to follow (1-256)
        :example trace_belt(Position(x=29, y=-80))
        :return: {start, tiles, total_tiles, blocker}
        """
        if not isinstance(position, Position):
            raise ValueError("position must be a Position")  # noqa: TRY004
        max_tiles = int(max_tiles)
        if not 1 <= max_tiles <= 256:
            raise ValueError("max_tiles must be between 1 and 256")
        response, _ = self.execute(
            self.player_index, position.x, position.y, max_tiles
        )
        if not isinstance(response, dict) or "tiles" not in response:
            message = str(response).split(":")[-1].strip()
            raise Exception(  # noqa: TRY002 - matches the tool error convention
                f"Could not trace belt at {position}: {message}"
            )
        return response
