"""Finite, persistent semantic action queues for the model-facing runtime."""

from __future__ import annotations

import json
import uuid
from typing import Any

from pydantic import BaseModel

from fle.env.entities import Entity, Position


ALLOWED_ACTIONS = {
    "cancel_craft",
    "craft_item",
    "extract_item",
    "harvest_resource",
    "insert_item",
    "move_to",
    "pickup_entity",
    "place_between",
    "place_entity",
    "place_grid",
    "place_offshore_pump",
    "place_path",
    "place_power_line",
    "queue_craft",
    "queue_research",
    "repeat_pattern",
    "rotate_entity",
    "set_delivery_chest",
    "set_entity_recipe",
    "set_research",
    "transfer_item",
    "wait",
}
DEFAULT_INTERRUPTS = {"action_failure", "new_order", "under_attack"}
MAX_QUEUE_ACTIONS = 1024


def _state(namespace) -> dict[str, Any] | None:
    return namespace.persistent_vars.get("_action_queue_state")


def _store(namespace, state: dict[str, Any]) -> None:
    namespace.persistent_vars["_action_queue_state"] = state


def _normalize_action(spec: dict[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise TypeError(f"action {index} must be a dictionary")
    action = str(spec.get("action", "")).strip()
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"action {index} uses unavailable command {action!r}")
    args = spec.get("args", [])
    kwargs = spec.get("kwargs", {})
    if not isinstance(args, (list, tuple)) or not isinstance(kwargs, dict):
        raise TypeError(f"action {index} args must be a list and kwargs a dictionary")
    action_id = spec.get("id", index)
    if not isinstance(action_id, (str, int)):
        raise TypeError(f"action {index} id must be a string or integer")
    return {
        "id": action_id,
        "action": action,
        "args": _freeze(list(args)),
        "kwargs": _freeze(kwargs),
    }


def _freeze(value: Any) -> Any:
    """Store durable references instead of live controller-bound objects."""

    if isinstance(value, Entity):
        if value.id is None:
            raise ValueError("queued entity arguments require a stable entity id")
        return {"$entity_handle": int(value.id)}
    if isinstance(value, Position):
        return {"$position": [float(value.x), float(value.y)]}
    if isinstance(value, list):
        return [_freeze(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return {key: _freeze(item) for key, item in value.items()}
    return value


def _capability_checks(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    for index, spec in enumerate(actions):
        action = spec["action"]
        args = spec["args"]
        kwargs = spec["kwargs"]
        target = args[0] if args else kwargs.get("entity") or kwargs.get("prototype")
        name = getattr(target, "value", target)
        if isinstance(name, tuple):
            name = name[0]
        if action in {"craft_item", "queue_craft"} and isinstance(name, str):
            checks.append({"index": index, "kind": "recipe", "name": name})
        elif action == "set_entity_recipe":
            recipe = args[1] if len(args) > 1 else kwargs.get("recipe")
            recipe = getattr(recipe, "value", recipe)
            if isinstance(recipe, str):
                checks.append({"index": index, "kind": "recipe", "name": recipe})
        elif action in {"set_research", "queue_research"}:
            values = target if isinstance(target, (list, tuple)) else [target]
            for value in values:
                value = getattr(value, "value", value)
                if isinstance(value, str):
                    checks.append({"index": index, "kind": "technology", "name": value})
    return checks


def _resolve(value: Any, results: dict[Any, Any]) -> Any:
    if isinstance(value, dict) and set(value) == {"$result"}:
        key = value["$result"]
        if key not in results:
            raise ValueError(f"result reference {key!r} is not available")
        return _resolve(results[key], results)
    if isinstance(value, dict) and set(value) == {"$entity_handle"}:
        # The namespace resolver returns a fresh entity projection after world
        # mutation or checkpoint restoration.
        return results["__namespace__"].resolve_entity(value["$entity_handle"])
    if isinstance(value, dict) and set(value) == {"$position"}:
        return Position(x=value["$position"][0], y=value["$position"][1])
    if isinstance(value, list):
        return [_resolve(item, results) for item in value]
    if isinstance(value, tuple):
        return tuple(_resolve(item, results) for item in value)
    if isinstance(value, dict):
        return {key: _resolve(item, results) for key, item in value.items()}
    return value


def _result_summary(result: Any) -> Any:
    if isinstance(result, Entity):
        return {
            "id": result.id,
            "name": result.name,
            "position": {"x": result.position.x, "y": result.position.y},
            "status": str(result.status) if result.status is not None else None,
        }
    if isinstance(result, Position):
        return {"x": result.x, "y": result.y}
    if isinstance(result, BaseModel):
        return repr(result)[:300]
    if isinstance(result, dict):
        return {key: _result_summary(value) for key, value in list(result.items())[:16]}
    if isinstance(result, (list, tuple)):
        return [_result_summary(value) for value in list(result)[:16]]
    if isinstance(result, (str, int, float, bool)) or result is None:
        return result
    return repr(result)[:300]


def _public_state(state: dict[str, Any]) -> dict[str, Any]:
    actions = state["actions"]
    return {
        "schema_version": "semantic-action-queue-v1",
        "queue_id": state["queue_id"],
        "status": state["status"],
        "next_index": state["next_index"],
        "action_count": len(actions),
        "ticks_elapsed": state.get("ticks_elapsed", 0),
        "interrupt_on": sorted(state["interrupt_on"]),
        "stop_reason": state.get("stop_reason"),
        "event": state.get("event"),
        "actions": [
            {
                "index": i,
                "id": action["id"],
                "action": action["action"],
                "state": ("completed" if i < state["next_index"] else "pending"),
            }
            for i, action in enumerate(actions)
        ],
        "receipts": state.get("receipts", [])[-32:],
    }


def _event_snapshot(namespace, since_tick: int, interrupt_on: set[str]) -> dict | None:
    if not interrupt_on:
        return None
    namespace.instance.ensure_connected()
    kinds = json.dumps(sorted(interrupt_on))
    wanted_json = kinds.replace("'", "\\'")
    manager = getattr(namespace.instance, "lua_script_manager", None)
    if manager is not None and manager.runtime_bundled:
        command = (
            "/sc local names=helpers.json_to_table('"
            + wanted_json
            + "') local wanted={} for _,v in ipairs(names) do wanted[v]=true end "
            + "rcon.print(helpers.table_to_json(remote.call('fle_runtime', 'dispatch', "
            + "'__semantic_event', "
            + f"{int(since_tick)}, wanted)))"
        )
    else:
        command = (
            "/sc local wanted={} for _,v in ipairs(helpers.json_to_table('"
            + wanted_json
            + "')) do wanted[v]=true end local found=nil "
            + f"for _,e in ipairs(storage.semantic_events or {{}}) do if e.tick>{int(since_tick)} "
            + "and wanted[e.type] then found=e break end end "
            + "rcon.print(helpers.table_to_json(found or {}))"
        )
    response = namespace.instance.rcon_client.send_command(command)
    event = json.loads(response or "{}")
    return event or None


def inspect_queue(namespace) -> dict[str, Any]:
    state = _state(namespace)
    return (
        _public_state(state)
        if state
        else {"schema_version": "semantic-action-queue-v1", "status": "empty"}
    )


def run_queue(namespace) -> dict[str, Any]:
    state = _state(namespace)
    if not state:
        raise ValueError("there is no action queue")
    if state["status"] in {"completed", "cancelled"}:
        return _public_state(state)
    state["status"] = "running"
    state["stop_reason"] = None
    state["event"] = None
    results = state.setdefault("results", {})
    results["__namespace__"] = namespace
    while state["next_index"] < len(state["actions"]):
        index = state["next_index"]
        spec = state["actions"][index]
        start_tick = int(
            namespace.instance.rcon_client.send_command("/sc rcon.print(game.tick)")
            or 0
        )
        try:
            args = _resolve(spec["args"], results)
            kwargs = _resolve(spec["kwargs"], results)
            result = getattr(namespace, spec["action"])(*args, **kwargs)
        except Exception as exc:
            state["status"] = "halted"
            state["stop_reason"] = "action_failure"
            state["event"] = {
                "type": "action_failure",
                "action_index": index,
                "message": str(exc),
            }
            results.pop("__namespace__", None)
            _store(namespace, state)
            return _public_state(state)
        end_tick = int(
            namespace.instance.rcon_client.send_command("/sc rcon.print(game.tick)")
            or start_tick
        )
        frozen_result = _freeze(result)
        results[spec["id"]] = frozen_result
        results[index] = frozen_result
        state["next_index"] += 1
        state["ticks_elapsed"] += max(end_tick - start_tick, 0)
        state["receipts"].append(
            {
                "index": index,
                "id": spec["id"],
                "action": spec["action"],
                "ticks_elapsed": max(end_tick - start_tick, 0),
                "result": _result_summary(result),
            }
        )
        event = _event_snapshot(namespace, start_tick, state["interrupt_on"])
        if event:
            state["status"] = "interrupted"
            state["stop_reason"] = str(event.get("type", "event"))
            state["event"] = event
            results.pop("__namespace__", None)
            _store(namespace, state)
            return _public_state(state)
    state["status"] = "completed"
    state["stop_reason"] = "completed"
    results.pop("__namespace__", None)
    _store(namespace, state)
    return _public_state(state)


def submit_queue(namespace, tool, actions, interrupt_on=None) -> dict[str, Any]:
    current = _state(namespace)
    if current and current["status"] not in {"completed", "cancelled"}:
        raise ValueError(
            "an unfinished action queue already exists; resume or cancel it"
        )
    normalized = [_normalize_action(spec, i) for i, spec in enumerate(actions)]
    if not normalized:
        raise ValueError("actions must not be empty")
    if len(normalized) > MAX_QUEUE_ACTIONS:
        raise ValueError(
            f"an action queue may contain at most {MAX_QUEUE_ACTIONS} actions"
        )
    ids = [spec["id"] for spec in normalized]
    if len(ids) != len(set(ids)):
        raise ValueError("action ids must be unique")
    checks = _capability_checks(normalized)
    response, _ = tool.execute(tool.player_index, "preflight", checks)
    if isinstance(response, dict) and response.get("errors") not in ({}, [], None):
        raise ValueError(
            f"queue capability validation failed: {tool.clean_response(response)['errors']}"
        )
    tick = int(
        namespace.instance.rcon_client.send_command("/sc rcon.print(game.tick)") or 0
    )
    state = {
        "queue_id": str(uuid.uuid4()),
        "status": "pending",
        "actions": normalized,
        "next_index": 0,
        "interrupt_on": {
            str(value).strip().lower() for value in (interrupt_on or DEFAULT_INTERRUPTS)
        },
        "submitted_tick": tick,
        "ticks_elapsed": 0,
        "receipts": [],
        "results": {},
        "stop_reason": None,
        "event": None,
    }
    _store(namespace, state)
    return run_queue(namespace)


def cancel_queue(namespace, from_index: int | None = None) -> dict[str, Any]:
    state = _state(namespace)
    if not state:
        raise ValueError("there is no action queue")
    start = state["next_index"] if from_index is None else int(from_index)
    if start < state["next_index"] or start > len(state["actions"]):
        raise ValueError("from_index must refer to the pending suffix")
    del state["actions"][start:]
    state["status"] = (
        "cancelled" if state["next_index"] >= len(state["actions"]) else "pending"
    )
    state["stop_reason"] = "cancelled"
    _store(namespace, state)
    return _public_state(state)


def insert_queue(namespace, tool, before_index: int, actions) -> dict[str, Any]:
    state = _state(namespace)
    if not state or state["status"] in {"completed", "cancelled"}:
        raise ValueError("there is no unfinished action queue")
    before_index = int(before_index)
    if before_index < state["next_index"] or before_index > len(state["actions"]):
        raise ValueError("before_index must refer to the pending suffix")
    normalized = [
        _normalize_action(spec, before_index + i) for i, spec in enumerate(actions)
    ]
    existing_ids = {spec["id"] for spec in state["actions"]}
    if any(spec["id"] in existing_ids for spec in normalized):
        raise ValueError("inserted action ids must be unique")
    response, _ = tool.execute(
        tool.player_index, "preflight", _capability_checks(normalized)
    )
    if isinstance(response, dict) and response.get("errors") not in ({}, [], None):
        raise ValueError(
            f"queue capability validation failed: {tool.clean_response(response)['errors']}"
        )
    state["actions"][before_index:before_index] = normalized
    state["status"] = "pending"
    state["stop_reason"] = None
    _store(namespace, state)
    return _public_state(state)
