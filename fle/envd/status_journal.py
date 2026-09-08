"""Bounded public machine-status history, independent of benchmark scoring."""

from collections import deque
from copy import deepcopy
from typing import Any


_SEVERITY = {
    "no_power": 3,
    "no_fuel": 3,
    "no_ingredients": 2,
    "waiting_for_space_in_destination": 2,
    "full_output": 2,
    "no_recipe": 1,
    "low_power": 1,
}


class StatusJournal:
    """Store immutable published transitions and an independently current keyframe.

    Input samples must be public engine observations in nondecreasing tick order.
    Coalescing is restricted to a single publication: an already issued cursor
    must never miss a later update to an earlier event.
    """

    def __init__(self, capacity: int = 2048):
        if capacity < 1:
            raise ValueError("status journal capacity must be positive")
        self.capacity = capacity
        self.events: deque[dict[str, Any]] = deque()
        self.current: dict[str, dict[str, Any]] = {}
        self.sequence = 0
        self.revision = 0
        self.tick = 0
        self.evicted_revision = -1

    def publish(self, samples: list[dict[str, Any]], *, revision: int) -> None:
        if revision <= self.revision:
            raise ValueError("status revisions must increase")
        # Validate the whole batch before changing the journal.
        last_tick = self.tick
        for sample in samples:
            tick = int(sample["tick"])
            if tick < last_tick:
                raise ValueError("status sample ticks must not go backwards")
            last_tick = tick
            if not sample.get("entity_id"):
                raise ValueError("status samples require stable entity_id")
        pending: dict[tuple[str, int], dict[str, Any]] = {}
        for raw in samples:
            sample = deepcopy(raw)
            entity_id = str(sample["entity_id"])
            before = self.current.get(entity_id)
            if sample.get("removed"):
                self.current.pop(entity_id, None)
            else:
                self.current[entity_id] = sample
            old = (before or {}).get("status")
            new = sample.get("status")
            old_warning = (before or {}).get("warning_key")
            warning = sample.get("warning_key")
            if before is None or (old, old_warning) == (new, warning):
                continue
            key = (entity_id, int(sample["tick"]) // 60)
            event = pending.get(key)
            if event is None:
                event = pending[key] = {
                    "entity_id": entity_id,
                    "prototype": sample.get("prototype"),
                    "position": sample.get("position"),
                    "surface": sample.get("surface"),
                    "from_status": old,
                    "from_warning_key": old_warning,
                    "first_tick": sample["tick"],
                    "revision": revision,
                    "transition_count": 0,
                    "peak_severity": 0,
                    "observed_statuses": [],
                }
            severity = _SEVERITY.get(str(new).lower(), 0)
            if new not in event["observed_statuses"]:
                event["observed_statuses"].append(new)
            event.update(
                tick=sample["tick"],
                to_status=new,
                warning_key=warning,
                severity=severity,
                peak_severity=max(event["peak_severity"], severity),
                transition_count=event["transition_count"] + 1,
            )
        for event in sorted(
            pending.values(), key=lambda value: (value["tick"], value["entity_id"])
        ):
            self.sequence += 1
            event["sequence"] = self.sequence
            self.events.append(event)
            if len(self.events) > self.capacity:
                self.evicted_revision = self.events.popleft()["revision"]
        self.revision = revision
        self.tick = last_tick

    def query(
        self,
        *,
        since_revision: int | None = None,
        from_tick: int | None = None,
        to_tick: int | None = None,
        limit: int = 128,
        severity_first: bool = False,
        keyframe: bool = False,
    ) -> dict[str, Any]:
        if not 1 <= limit <= self.capacity:
            raise ValueError(f"status limit must be between 1 and {self.capacity}")
        if since_revision is not None and not 0 <= since_revision <= self.revision:
            raise ValueError("status revision is outside this journal")
        if from_tick is not None and to_tick is not None and from_tick > to_tick:
            raise ValueError("status tick window is reversed")
        matching = [
            event
            for event in self.events
            if (since_revision is None or event["revision"] > since_revision)
            and (from_tick is None or event["tick"] >= from_tick)
            and (to_tick is None or event["first_tick"] <= to_tick)
        ]
        if severity_first:
            matching.sort(
                key=lambda event: (-event["peak_severity"], event["sequence"])
            )
        result = {
            "revision": self.revision,
            "tick": self.tick,
            "retained_after_revision": self.evicted_revision,
            "history_expired": since_revision is not None
            and since_revision < self.evicted_revision,
            "truncated": len(matching) > limit,
            "events": matching[:limit],
        }
        if keyframe:
            current = sorted(
                self.current.values(),
                key=lambda value: (
                    -_SEVERITY.get(str(value.get("status")).lower(), 0),
                    str(value["entity_id"]),
                ),
            )
            result["current"] = current[:limit]
            result["current_truncated"] = len(current) > limit
        return deepcopy(result)

    def export(self) -> dict[str, Any]:
        return deepcopy(
            {
                "capacity": self.capacity,
                "events": list(self.events),
                "current": self.current,
                "sequence": self.sequence,
                "revision": self.revision,
                "tick": self.tick,
                "evicted_revision": self.evicted_revision,
            }
        )

    @classmethod
    def restore(cls, state: dict[str, Any]) -> "StatusJournal":
        journal = cls(capacity=int(state["capacity"]))
        journal.events = deque(deepcopy(state["events"])[-journal.capacity :])
        journal.current = deepcopy(state["current"])
        journal.sequence = int(state["sequence"])
        journal.revision = int(state["revision"])
        journal.tick = int(state["tick"])
        journal.evicted_revision = int(state["evicted_revision"])
        return journal
