from types import SimpleNamespace

import pytest

from fle.envd.backend import FLEWorker
from fle.envd.customer import ActiveOrder

pytestmark = pytest.mark.no_factorio


def test_resumed_depot_arrivals_are_credited_on_persistent_order_clock():
    worker = FLEWorker.__new__(FLEWorker)
    worker._epoch_game_tick = 1000
    worker._active_epoch_index = 2
    worker._active_order = ActiveOrder(
        "iron-plate", 82, 198000, activation_tick=233777, order_kind="sustained"
    )
    worker._customer_depots_cache = []
    worker._customer_events = []
    worker._read_game_tick = lambda: 234837
    raw = {
        "epoch_tick": 234777,
        "tick": 60,
        "buckets": [
            {
                "start_tick": 60,
                "items": {"iron-plate": 5},
                "manual_items": {"iron-plate": 7},
            }
        ],
    }
    values = iter([raw, {"epoch_tick": 234777, "tick": 60, "buckets": []}])
    worker.instance = SimpleNamespace(
        first_namespace=SimpleNamespace(_customer_depot=lambda command: next(values))
    )
    worker._sync_active_order()
    assert worker._active_order.student_view().fulfilled == {"iron-plate": 5}
    assert worker._delivery_history == [(233837, {"iron-plate": 5})]
    assert worker._manual_delivery_totals == {"iron-plate": 7}
    worker._sync_active_order()
    assert worker._active_order.student_view().fulfilled == {"iron-plate": 5}
    assert raw["tick"] == 60  # caller's raw evidence remains intact


def test_non_aligned_epoch_offset_preserves_bucket_time_and_manual_fields():
    worker = FLEWorker.__new__(FLEWorker)
    worker._epoch_game_tick = 100
    data = worker._delivery_on_episode_clock(
        {
            "epoch_tick": 223,
            "tick": 70,
            "buckets": {
                1: {
                    "start_tick": 60,
                    "items": {"iron-plate": 2},
                    "manual_items": {"iron-plate": 3},
                }
            },
        }
    )
    assert worker._parse_delivery_buckets(data) == (193, [(193, {"iron-plate": 2})])
    assert worker._parse_delivery_buckets(data, item_field="manual_items") == (
        193,
        [(193, {"iron-plate": 3})],
    )


def test_wait_receipt_reports_pending_and_physical_traffic_without_false_certification():
    worker = FLEWorker.__new__(FLEWorker)
    worker.customer_engine = None
    worker._active_order = ActiveOrder(
        "iron-plate", 82, 198000, activation_tick=0, order_kind="sustained"
    )
    worker._customer_depots_cache = []
    worker._delivery_raw_totals = {"iron-plate": 50}
    worker._contract_delivery_baseline = {"iron-plate": 10}
    result = worker._delivery_receipt(["wait"], {})
    assert result.observed_depot_totals == {"iron-plate": 40}
    assert result.qualification_pending and not result.throughput_certified
    assert "not an audit failure" in result.message
    assert "No delivery chest is bound" in result.message
