from types import SimpleNamespace

import pytest

from fle.envd.backend import FLEWorker
from fle.envd.customer import ActiveOrder
from fle.envd.delivery import (
    build_delivery_receipt,
    parse_delivery_buckets,
    translate_delivery_clock,
)

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
    data = translate_delivery_clock(
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
        },
        100,
    )
    assert parse_delivery_buckets(data) == (193, [(193, {"iron-plate": 2})])
    assert parse_delivery_buckets(data, item_field="manual_items") == (
        193,
        [(193, {"iron-plate": 3})],
    )


def test_wait_receipt_reports_pending_and_physical_traffic_without_false_certification():
    order = ActiveOrder(
        "iron-plate", 82, 198000, activation_tick=0, order_kind="sustained"
    )
    result = build_delivery_receipt(
        contracts=[order.student_view()],
        attempted_insert=False,
        delivered_before={},
        throughput_audit_passed=False,
        customer_depot_ids=[],
        contract_delivery_baseline={"iron-plate": 10},
        delivery_raw_totals={"iron-plate": 50},
    )
    assert result.observed_depot_totals == {"iron-plate": 40}
    assert result.qualification_pending and not result.throughput_certified
    assert "not an audit failure" in result.message
    assert "No delivery chest is bound" in result.message
