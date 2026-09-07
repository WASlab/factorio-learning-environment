from time import sleep as wall_sleep
from typing import Any

from fle.env.tools import Tool


class Wait(Tool):
    """Wait over authoritative Factorio ticks, optionally stopping on a condition."""

    def __call__(
        self, ticks: int, until: dict[str, Any] | None = None, poll_ticks: int = 30
    ) -> dict[str, Any]:
        ticks = self._positive("ticks", ticks)
        poll_ticks = self._positive("poll_ticks", poll_ticks)
        condition = self._validate(until)
        start = self._tick()
        target = start + ticks
        now = start
        speed = self.game_state.instance.get_speed()
        met, observed = self._check(condition)
        while now < target and not met:
            if getattr(self.game_state, "_cancel_requested", False):
                raise TimeoutError("Wait cancelled by program execution timeout")
            remaining = target - now
            chunk = min(poll_ticks, remaining)
            # Bound cancellation latency even for very large polling intervals.
            wall_sleep(max(min(chunk / 60.0 / speed, 0.25), 0.001))
            now = self._tick()
            met, observed = self._check(condition)
        end = now
        return {
            "status": "condition_met" if met else "timeout",
            "requested_ticks": ticks,
            "simulation_ticks_advanced": max(end - start, 0),
            "condition_met": met if condition else None,
            "observed": observed,
            "stop_reason": "condition_met" if met else "timeout",
        }

    @staticmethod
    def _positive(name, value):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return value

    @staticmethod
    def _validate(until):
        if until is None:
            return None
        if not isinstance(until, dict) or len(until) != 1:
            raise ValueError("until must contain exactly one condition")
        kind, payload = next(iter(until.items()))
        if kind not in {"inventory", "research", "craft_queue", "production_rate"}:
            raise ValueError(
                "condition must be inventory, research, craft_queue, or production_rate"
            )
        if not isinstance(payload, dict):
            raise ValueError("condition payload must be a dictionary")
        return {"kind": kind, **payload}

    def _check(self, condition):
        if condition is None:
            return False, None
        kind = condition["kind"]
        if kind == "inventory":
            inventory = self.game_state.inspect_inventory(condition.get("entity"))
            count = int(inventory[condition["item"]])
            observed = {
                "kind": kind,
                "count": count,
                "at_least": int(condition["at_least"]),
            }
            return count >= observed["at_least"], observed
        if kind == "research":
            technology = condition["technology"]
            name = technology.value if hasattr(technology, "value") else str(technology)
            researched, _ = self.execute(0, self.player_index, name)
            if not isinstance(researched, bool):
                raise RuntimeError(f"Could not inspect research {name}: {researched}")
            return researched, {
                "kind": kind,
                "technology": name,
                "researched": researched,
            }
        if kind == "craft_queue":
            result = self.game_state.get_craft_queue()
            observed = {"kind": kind, **result}
            return bool(result.get("active")) is bool(
                condition.get("active", False)
            ), observed
        product = condition["item"]
        window = int(condition.get("window_seconds", 60))
        result = self.game_state._get_recent_rate(
            product.value[0] if hasattr(product, "value") else str(product), window
        )
        rate = float(result.get("dynamic_per_minute", 0))
        observed = {
            "kind": kind,
            "rate_per_minute": rate,
            "at_least": float(condition["at_least"]),
            "window_seconds": window,
        }
        return rate >= observed["at_least"], observed

    def _tick(self):
        if getattr(self.game_state, "_cancel_requested", False):
            raise TimeoutError("Wait cancelled by program execution timeout")
        value, _ = self.execute(0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(f"Expected a native game tick, received {value!r}")
        return int(value)
