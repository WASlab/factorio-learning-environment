from time import sleep as wall_sleep
import math
import sys
from typing import Any

from fle.env.tools import Tool


class Wait(Tool):
    """Wait for a simulation-tick condition, retaining its first sampled result."""

    def __call__(
        self, ticks: int, until: dict[str, Any] | None = None, poll_ticks: int = 30
    ) -> dict[str, Any]:
        ticks = self._positive("ticks", ticks)
        poll_ticks = self._positive("poll_ticks", poll_ticks)
        condition = self._validate(until)
        interval = min(
            max(
                poll_ticks / 60 / max(self.game_state.instance.get_speed(), 0.01), 0.025
            ),
            0.25,
        )
        started, _ = self.execute(
            "start",
            self.player_index,
            {"ticks": ticks, "poll_ticks": poll_ticks, "condition": condition},
        )
        if not isinstance(started, dict) or "start_tick" not in started:
            raise RuntimeError(f"Could not start wait: {started}")
        try:
            while True:
                if getattr(self.game_state, "_cancel_requested", False):
                    raise TimeoutError("Wait cancelled by program execution timeout")
                result, _ = self.execute("poll", self.player_index)
                if not isinstance(result, dict) or result.get("status") == "error":
                    raise RuntimeError(f"Wait failed: {result}")
                if result["status"] != "pending":
                    break
                wall_sleep(interval)
            decision = int(result["decision_tick"])
            end = int(result["tick"])
            elapsed_ticks = end - started["start_tick"]
            return {
                "status": result["status"],
                "requested_ticks": ticks,
                "requested_seconds": round(ticks / 60, 3),
                "start_tick": started["start_tick"],
                "deadline_tick": started["deadline_tick"],
                "decision_tick": decision,
                "simulation_ticks_advanced": elapsed_ticks,
                "elapsed_seconds": round(elapsed_ticks / 60, 3),
                "poll_latency_ticks": max(0, end - decision),
                "condition_met": result["status"] == "condition_met"
                if condition
                else None,
                "observed": result.get("observed"),
                "stop_reason": result["status"],
            }
        finally:
            active_error = sys.exception()
            try:
                self.execute("cancel", self.player_index)
            except Exception:
                if active_error is None:
                    raise

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
        fields = {
            "inventory": {"entity", "item", "at_least"},
            "research": {"technology"},
            "craft_queue": {"active"},
            "production_rate": {"item", "at_least", "window_seconds"},
            "machine_status": {"entity", "status"},
            "delivery": {"item", "at_least"},
            "event": {"type"},
        }
        if (
            kind not in fields
            or not isinstance(payload, dict)
            or set(payload) - fields[kind]
        ):
            raise ValueError("Invalid wait condition or fields")
        result = {"kind": kind, **payload}
        for key in ("item", "technology"):
            if key in result:
                value = getattr(result[key], "value", result[key])
                result[key] = value[0] if isinstance(value, tuple) else value
                if not isinstance(result[key], str) or not result[key]:
                    raise ValueError(f"{key} must name a prototype")
        if kind in {"inventory", "production_rate", "delivery"}:
            threshold = result.get("at_least")
            if (
                "item" not in result
                or isinstance(threshold, bool)
                or not isinstance(threshold, (int, float))
                or not math.isfinite(threshold)
                or threshold < 0
            ):
                raise ValueError("item and finite nonnegative at_least are required")
        if kind == "research" and "technology" not in result:
            raise ValueError("technology is required")
        entity = result.pop("entity", None)
        if entity is not None:
            entity_id = getattr(entity, "id", None)
            if not isinstance(entity_id, int) or entity_id <= 0:
                raise ValueError("entity must have a stable entity id")
            result["entity_id"] = entity_id
        if kind == "machine_status" and (
            "entity_id" not in result or not isinstance(result.get("status"), str)
        ):
            raise ValueError("machine_status requires entity and status")
        if kind == "craft_queue":
            result.setdefault("active", False)
            if not isinstance(result["active"], bool):
                raise ValueError("active must be boolean")
        if kind == "production_rate":
            result.setdefault("window_seconds", 60)
            if result["window_seconds"] not in {5, 60, 600, 3600}:
                raise ValueError("window_seconds must be 5, 60, 600, or 3600")
        if kind == "event" and result.get("type") not in {
            "new_order",
            "research_completed",
            "under_attack",
        }:
            raise ValueError(
                "event type must be new_order, research_completed, or under_attack"
            )
        return result
