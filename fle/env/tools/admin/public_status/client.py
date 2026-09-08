from typing import Any

from fle.env.tools import Tool


class PublicStatus(Tool):
    """Read the engine's bounded public machine-status samples."""

    def __call__(self, after_sequence: int = 0) -> dict[str, Any]:
        response, _ = self.execute(self.player_index, int(after_sequence))
        if isinstance(response, dict):
            for key in ("samples", "current"):
                value = response.get(key)
                if isinstance(value, dict):
                    response[key] = [value[index] for index in sorted(value, key=int)]
        return response
