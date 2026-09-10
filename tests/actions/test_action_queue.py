import json

import pytest

from fle.commons.models.game_state import filter_serializable_vars
from fle.env.action_queue import (
    cancel_queue,
    inspect_queue,
    submit_queue,
)


class _Rcon:
    def __init__(self):
        self.tick = 10

    def send_command(self, command):
        if "semantic_events" in command:
            return json.dumps({})
        return str(self.tick)


class _Instance:
    def __init__(self):
        self.rcon_client = _Rcon()

    def ensure_connected(self):
        pass


class _Namespace:
    def __init__(self):
        self.instance = _Instance()
        self.persistent_vars = {}
        self.fail = False

    def move_to(self, target):
        self.instance.rcon_client.tick += 60
        if self.fail:
            raise RuntimeError("blocked")
        return {"position": target}

    def insert_item(self, item, target):
        self.instance.rcon_client.tick += 15
        return {"item": item, "target": target}


class _SubmitTool:
    player_index = 1

    def execute(self, *_args):
        return {"errors": {}}, 0

    def clean_response(self, value):
        return value


def test_queue_runs_in_order_and_resolves_prior_result():
    namespace = _Namespace()
    receipt = submit_queue(
        namespace,
        _SubmitTool(),
        [
            {"id": "destination", "action": "move_to", "args": [[4, 8]]},
            {
                "action": "insert_item",
                "args": ["coal", {"$result": "destination"}],
            },
        ],
    )

    assert receipt["status"] == "completed"
    assert receipt["next_index"] == 2
    assert receipt["ticks_elapsed"] == 75
    assert inspect_queue(namespace)["action_count"] == 2
    assert "_action_queue_state" in filter_serializable_vars(namespace.persistent_vars)


def test_queue_halts_and_preserves_pending_suffix():
    namespace = _Namespace()
    namespace.fail = True
    receipt = submit_queue(
        namespace,
        _SubmitTool(),
        [{"action": "move_to", "args": [[4, 8]]}, {"action": "wait", "args": [60]}],
    )

    assert receipt["status"] == "halted"
    assert receipt["next_index"] == 0
    assert receipt["event"]["action_index"] == 0
    cancelled = cancel_queue(namespace)
    assert cancelled["status"] == "cancelled"


def test_queue_rejects_planner_action_and_duplicate_ids():
    namespace = _Namespace()
    with pytest.raises(ValueError, match="unavailable command"):
        submit_queue(namespace, _SubmitTool(), [{"action": "connect_entities"}])
    with pytest.raises(ValueError, match="unique"):
        submit_queue(
            namespace,
            _SubmitTool(),
            [
                {"id": "same", "action": "move_to", "args": [[1, 1]]},
                {"id": "same", "action": "move_to", "args": [[2, 2]]},
            ],
        )
