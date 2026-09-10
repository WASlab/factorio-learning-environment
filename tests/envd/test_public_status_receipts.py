from types import SimpleNamespace

import pytest

from fle.envd.backend import FLEWorker
from scripts.factorio_codex_mcp import _execution_receipt


pytestmark = pytest.mark.no_factorio


def test_model_receipt_prioritizes_transitions_without_mutating_full_artifact():
    events = [
        {"sequence": index, "peak_severity": int(index == 19)} for index in range(20)
    ]
    source = {"status_changes": {"events": events, "current": [{"status": "no_fuel"}]}}
    receipt = _execution_receipt(source)["status_changes"]
    assert len(receipt["events"]) == 16
    assert receipt["events"][0]["sequence"] == 19
    assert receipt["truncated"]
    assert "current" not in receipt
    assert len(source["status_changes"]["events"]) == 20
    assert source["status_changes"]["current"] == [{"status": "no_fuel"}]


def test_receipts_share_observation_revisions_and_queries_recover_transitions():
    worker = FLEWorker.__new__(FLEWorker)
    working = {"entity_id": "1:7", "status": "working", "tick": 0}
    blocked = {**working, "status": "no_fuel", "tick": 60}
    calls = []

    def read(after):
        calls.append(after)
        return {
            "engine_sequence": 1 if after == -1 else 2,
            "retained_after_sequence": 0,
            "tick": 0 if after == -1 else 120,
            "current": [working] if after == -1 else None,
            "samples": [blocked] if after == 1 else [],
            "coverage": "registered_player_machines",
            "sample_interval_ticks": 60,
        }

    worker.instance = SimpleNamespace(
        first_namespace=SimpleNamespace(_public_status=read)
    )
    initial = worker._public_status_receipt()
    assert not initial["events"]
    assert not initial["engine_history_expired"]
    assert initial["current"] == [working]
    receipt = worker._public_status_receipt()
    assert receipt["revision"] == 2
    assert receipt["tick"] == 120
    assert receipt["events"][0]["from_status"] == "working"
    result = worker.query_state("lease", kind="alerts", since_revision=1)
    assert result["revision"] == 3
    assert len(result["events"]) == 1
    assert calls == [-1, 1, 2]


def test_status_read_failure_is_explicit_and_does_not_break_mutation_receipt():
    worker = FLEWorker.__new__(FLEWorker)

    def read(_after):
        raise OSError("transport offline")

    worker.instance = SimpleNamespace(
        first_namespace=SimpleNamespace(_public_status=read)
    )
    receipt = worker._public_status_receipt()
    assert receipt["available"] is False
    assert receipt["reason"] == "status_monitor_read_failed"
