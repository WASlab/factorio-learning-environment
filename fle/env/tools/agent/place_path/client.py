import json
import math

from fle.env import Direction
from fle.env.entities import Position
from fle.env.game_types import Prototype
from fle.env.tools import Tool


def _blocked_by_from_message(message: str) -> dict | None:
    """Extract the promoted ``blocked_by`` entity from a placement failure.

    Placement failures raise with a diagnostics payload embedded in the
    exception text.  Different call layers wrap it differently, so scan for
    the first JSON object and look for ``blocked_by`` (preferred) or fall back
    to the nearest ``overlapping_entities`` entry.
    """

    start = message.find("{")
    if start == -1:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(message[start:])
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    diagnostics = payload.get("diagnostics")
    if isinstance(diagnostics, dict):
        payload = diagnostics
    blocked_by = payload.get("blocked_by")
    if isinstance(blocked_by, dict):
        return blocked_by
    overlapping = payload.get("overlapping_entities")
    if isinstance(overlapping, list) and overlapping:
        nearest = overlapping[0]
        if isinstance(nearest, dict):
            return nearest
    return None


class PlacePath(Tool):
    """Place exactly the caller-specified polyline; never route around blockers."""

    def __call__(
        self,
        prototype: Prototype,
        points: list[Position | tuple[float, float]],
        routing: str = "polyline",
        on_collision: str = "stop",
        on_insufficient_materials: str = "stop",
    ) -> dict:
        if routing != "polyline":
            raise ValueError("routing must be 'polyline'")
        if on_collision not in {"stop", "raise"} or on_insufficient_materials not in {
            "stop",
            "raise",
        }:
            raise ValueError("stop policies must be 'stop' or 'raise'")
        route = self._rasterize(points)
        before_tick = self._tick()
        before = self.game_state.inspect_inventory()[prototype]
        placed = []
        blocker = None
        reason = "completed"
        for index, position in enumerate(route):
            direction = self._direction(route, index)
            try:
                placed.append(
                    self.game_state.place_entity(prototype, direction, position, True)
                )
            except Exception as exc:
                message = str(exc)
                reason = (
                    "materials_exhausted"
                    if "inventory" in message.lower()
                    else "collision"
                )
                blocker = {
                    "position": {"x": position.x, "y": position.y},
                    "message": message,
                }
                blocked_by = _blocked_by_from_message(message)
                if blocked_by is not None:
                    blocker["blocked_by"] = blocked_by
                policy = (
                    on_insufficient_materials
                    if reason == "materials_exhausted"
                    else on_collision
                )
                if policy == "raise":
                    raise
                break
        after = self.game_state.inspect_inventory()[prototype]
        return {
            "status": "completed" if len(placed) == len(route) else "partial",
            "placed": len(placed),
            "requested": len(route),
            "last_position": (
                {"x": placed[-1].position.x, "y": placed[-1].position.y}
                if placed
                else None
            ),
            "ticks_elapsed": max(self._tick() - before_tick, 0),
            "inventory_delta": {prototype.value[0]: int(after) - int(before)},
            "stop_reason": reason,
            "blocker": blocker,
            "entity_ids": [entity.id for entity in placed],
        }

    @staticmethod
    def _coerce(value):
        return (
            value if isinstance(value, Position) else Position(x=value[0], y=value[1])
        )

    @classmethod
    def _rasterize(cls, points):
        points = [cls._coerce(value) for value in points]
        if len(points) < 2:
            raise ValueError("place_path needs at least two points")
        route = []
        for start, end in zip(points, points[1:]):
            dx, dy = end.x - start.x, end.y - start.y
            if dx and dy:
                raise ValueError(
                    "polyline segments must be axis-aligned; provide the corner explicitly"
                )
            length = int(round(abs(dx or dy)))
            if not math.isclose(abs(dx or dy), length):
                raise ValueError("path endpoints must lie on the same unit grid")
            sx = 0 if dx == 0 else (1 if dx > 0 else -1)
            sy = 0 if dy == 0 else (1 if dy > 0 else -1)
            for step in range(length + 1):
                point = Position(x=start.x + sx * step, y=start.y + sy * step)
                if not route or point != route[-1]:
                    route.append(point)
        return route

    @staticmethod
    def _direction(route, index):
        current = route[index]
        if index + 1 < len(route):
            dx, dy = route[index + 1].x - current.x, route[index + 1].y - current.y
        else:
            dx, dy = current.x - route[index - 1].x, current.y - route[index - 1].y
        if dx > 0:
            return Direction.RIGHT
        if dx < 0:
            return Direction.LEFT
        if dy > 0:
            return Direction.DOWN
        return Direction.UP

    def _tick(self):
        return int(
            self.connection.rcon_client.send_command("/sc rcon.print(game.tick)") or 0
        )
