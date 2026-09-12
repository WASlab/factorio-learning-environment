from fle.env.entities import Position
from fle.env.tools import Tool


def _normalize_arrays(value):
    """Convert integer-keyed mappings into lists, recursively."""

    if isinstance(value, dict):
        keys = list(value.keys())
        if keys and all(
            isinstance(key, (int, str)) and str(key).lstrip("-").isdigit()
            for key in keys
        ):
            return [
                _normalize_arrays(value[key])
                for key in sorted(keys, key=lambda key: int(key))
            ]
        return {key: _normalize_arrays(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_arrays(item) for item in value]
    return value


class TraceBelt(Tool):
    def __call__(self, position: Position, max_tiles: int = 64) -> dict:
        """Follow a belt downstream and report where flow stops.

        Each entry in ``tiles`` includes the belt position, flow direction,
        ``active`` flag, and per-lane item contents.  ``blocker`` is the first
        downstream tile that cannot accept items: ``end_of_line`` when no belt
        follows, ``blocked_by_entity`` (with the blocking entity) when a
        non-belt entity occupies the next tile, or ``max_tiles_reached``.

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
        response, _ = self.execute(self.player_index, position.x, position.y, max_tiles)
        if not isinstance(response, dict) or "tiles" not in response:
            message = str(response).split(":")[-1].strip()
            raise Exception(  # noqa: TRY002 - matches the tool error convention
                f"Could not trace belt at {position}: {message}"
            )
        return _normalize_arrays(response)
