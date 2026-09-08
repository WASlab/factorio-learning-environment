from typing import Any

from fle.env.tools import Tool


class PublicView(Tool):
    """Bounded terrain and nearby tooltip state, without advancing the world."""

    def __call__(self, radius: int = 32, entity_limit: int = 32) -> dict[str, Any]:
        if not 8 <= radius <= 192:
            raise ValueError("radius must be between 8 and 192 tiles")
        if not 1 <= entity_limit <= 128:
            raise ValueError("entity_limit must be between 1 and 128")
        response, _ = self.execute(self.player_index, int(radius), int(entity_limit))
        if isinstance(response, dict):
            for key in ("cells", "entities"):
                value = response.get(key)
                if isinstance(value, dict):
                    response[key] = [value[index] for index in sorted(value, key=int)]
        return response
