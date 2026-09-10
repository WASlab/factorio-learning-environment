from fle.env.game_types import Prototype
from fle.env.tools import Tool


class GetProductionStatistics(Tool):
    """Read the player's native production/consumption statistics."""

    def __call__(self, items=None, window_seconds=60, category="item", limit=32):
        if category not in {"item", "fluid"}:
            raise ValueError("category must be item or fluid")
        if isinstance(window_seconds, bool) or window_seconds not in {5, 60, 600, 3600}:
            raise ValueError("window_seconds must be 5, 60, 600, or 3600")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 64
        ):
            raise ValueError("limit must be an integer between 1 and 64")
        if items is not None and not isinstance(items, (list, tuple)):
            raise ValueError("items must be a list of up to 64 names or Prototypes")
        names = [
            item.value[0] if isinstance(item, Prototype) else item
            for item in (items or [])
        ]
        if len(names) > 64 or any(
            not isinstance(name, str) or not name for name in names
        ):
            raise ValueError("items must contain up to 64 nonempty names")
        response, _ = self.execute(
            self.player_index, names, window_seconds, category, limit
        )
        if not isinstance(response, dict) or response.get("error"):
            raise RuntimeError(f"Production statistics unavailable: {response}")
        for field in ("entries", "unknown_products"):
            entries = response.get(field, [])
            if isinstance(entries, dict):
                entries = [entries[key] for key in sorted(entries, key=int)]
            response[field] = entries
        return response
