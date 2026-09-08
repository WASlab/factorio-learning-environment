import pytest

from fle.envd.status_journal import StatusJournal


pytestmark = pytest.mark.no_factorio


def sample(tick, status, entity="1"):
    return {
        "entity_id": entity,
        "prototype": "burner-mining-drill",
        "position": {"x": -23, "y": -72},
        "surface": 1,
        "tick": tick,
        "status": status,
        "warning_key": status if status != "working" else None,
    }


def test_initial_state_is_keyframe_not_invented_transition():
    journal = StatusJournal()
    journal.publish([sample(0, "no_fuel")], revision=1)
    assert journal.query()["events"] == []
    assert journal.query(keyframe=True)["current"][0]["status"] == "no_fuel"


def test_coalescing_preserves_stall_and_recovery_without_rewriting_receipts():
    journal = StatusJournal()
    journal.publish([sample(0, "working")], revision=1)
    journal.publish([sample(10, "no_fuel"), sample(20, "working")], revision=2)
    issued = journal.query(since_revision=1)
    event = issued["events"][0]
    assert event["from_status"] == event["to_status"] == "working"
    assert event["transition_count"] == 2
    journal.publish([sample(30, "no_fuel")], revision=3)
    assert len(journal.query(since_revision=2)["events"]) == 1
    assert issued["events"][0] == event
    assert journal.query()["events"][0] == event


def test_eviction_with_multiple_events_in_one_revision_requires_keyframe():
    journal = StatusJournal(capacity=2)
    journal.publish([sample(0, "working", str(i)) for i in range(3)], revision=1)
    journal.publish([sample(60, "no_fuel", str(i)) for i in range(3)], revision=2)
    assert journal.query(since_revision=1, limit=2)["history_expired"]
    assert not journal.query(since_revision=2, limit=2)["history_expired"]
    assert len(journal.query(keyframe=True, limit=2)["current"]) == 2
    assert journal.query(keyframe=True, limit=2)["current_truncated"]


def test_query_order_limits_and_caller_mutation_are_isolated():
    journal = StatusJournal()
    journal.publish([sample(0, "working", str(i)) for i in range(2)], revision=1)
    journal.publish(
        [sample(60, "no_recipe", "0"), sample(61, "no_power", "1")], revision=2
    )
    result = journal.query(limit=1, severity_first=True)
    assert result["truncated"]
    assert result["events"][0]["entity_id"] == "1"
    result["events"][0]["position"]["x"] = 500
    assert journal.query(from_tick=61)["events"][0]["position"]["x"] == -23


def test_invalid_batch_does_not_partially_mutate_state():
    journal = StatusJournal()
    journal.publish([sample(60, "working")], revision=1)
    with pytest.raises(ValueError, match="backwards"):
        journal.publish([sample(80, "no_fuel"), sample(40, "working")], revision=2)
    assert journal.query(keyframe=True)["current"][0]["status"] == "working"
    assert journal.revision == 1


def test_removed_machine_leaves_transition_but_not_current_state():
    journal = StatusJournal()
    journal.publish([sample(0, "working")], revision=1)
    journal.publish([{**sample(60, "removed"), "removed": True}], revision=2)
    result = journal.query(keyframe=True)
    assert result["current"] == []
    assert result["events"][0]["to_status"] == "removed"


def test_json_checkpoint_preserves_history_and_accepts_future_samples():
    import json

    journal = StatusJournal()
    journal.publish([sample(0, "working")], revision=1)
    journal.publish([sample(60, "no_fuel")], revision=2)
    restored = StatusJournal.restore(json.loads(json.dumps(journal.export())))
    assert restored.query(keyframe=True) == journal.query(keyframe=True)
    restored.publish([sample(120, "working")], revision=3)
    assert restored.query(since_revision=2)["events"][0]["from_status"] == "no_fuel"
