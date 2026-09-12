from fle.env.entities import Position
from fle.env.tools import Tool


class GetTileMap(Tool):
    def __call__(self, center: Position, radius: int = 16) -> dict:
        """Render a compact tile/entity map around a point.

        Returns ``rows`` of single-character cells (top row first, north up),
        a structured ``entities`` list with names, directions and statuses,
        and a legend. Use it to inspect a build site or the area around a
        placement failure before intervening.

        :param center: Center of the map as a Position
        :param radius: Half-size of the map in tiles (1-32)
        :example get_tile_map(Position(x=29, y=-82), radius=12)
        :return: {center, radius, rows, entities, entities_truncated, legend}
        """
        if not isinstance(center, Position):
            raise ValueError("center must be a Position")  # noqa: TRY004
        radius = int(radius)
        if not 1 <= radius <= 32:
            raise ValueError("radius must be between 1 and 32")
        response, _ = self.execute(self.player_index, center.x, center.y, radius)
        if not isinstance(response, dict) or "rows" not in response:
            message = str(response).split(":")[-1].strip()
            raise Exception(  # noqa: TRY002 - matches the tool error convention
                f"Could not build tile map at {center}: {message}"
            )
        return response
