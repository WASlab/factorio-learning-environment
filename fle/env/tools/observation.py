"""Small shared boundary for public, read-only player information tools."""

import math

from fle.env.tools import Tool


def name_of(value):
    value = getattr(value, "value", value)
    if isinstance(value, tuple):
        value = value[0]
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected a nonempty prototype or technology name")
    return value


def bounded_integer(value, name, minimum=1, maximum=128):
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
    return value


class ObservationTool(Tool):
    def position_args(self, position):
        x, y = self.get_position(position)
        if any(
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            for v in (x, y)
        ):
            raise ValueError("position coordinates must be finite numbers")
        return x, y

    def read(self, *args, arrays=(), nested_arrays=()):
        result, _ = self.execute(self.player_index, *args)
        if not isinstance(result, dict) or result.get("error"):
            raise RuntimeError(f"Player information unavailable: {result}")

        def normalize(value, field=None):
            if isinstance(value, dict):
                if field in (*arrays, *nested_arrays):
                    return [normalize(value[key]) for key in sorted(value, key=int)]
                return {key: normalize(item, key) for key, item in value.items()}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            return value

        return normalize(result)
