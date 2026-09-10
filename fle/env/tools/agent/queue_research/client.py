from collections.abc import Sequence

from fle.env.game_types import Technology
from fle.env.tools import Tool


class QueueResearch(Tool):
    """Append enabled technologies to Factorio's native research queue."""

    def __call__(self, technologies: Technology | Sequence[Technology]) -> dict:
        values = (
            [technologies]
            if isinstance(technologies, (str, Technology))
            else list(technologies)
        )
        if not values:
            raise ValueError("technologies must not be empty")
        names = [
            value.value if hasattr(value, "value") else str(value) for value in values
        ]
        response, _ = self.execute(self.player_index, names)
        if not isinstance(response, dict):
            raise Exception(
                f"Could not queue research: {self.get_error_message(response)}"
            )
        cleaned = self.clean_response(response)
        for key in ("queued", "skipped"):
            if cleaned.get(key) == {}:
                cleaned[key] = []
        return cleaned
