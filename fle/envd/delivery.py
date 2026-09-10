"""Pure delivery-accounting helpers for the envd worker.

These functions carry the physical-delivery ledger math: raw Lua telemetry
normalization, customer-depot parsing, telemetry snapshots, and delivery
receipt construction. They take explicit ledger slices rather than worker
state so the accounting stays deterministic and unit-testable without
constructing a live FLEWorker.
"""

from __future__ import annotations

from typing import Any

from fle.envd.customer import DELIVERY_BUCKET_TICKS
from fle.envd.models import (
    CustomerDepotView,
    DeliveryReceipt,
    DepotDeliveryTelemetry,
    OpenContractView,
)


def lua_array(value: Any) -> list[Any]:
    """Normalize a Lua array-like value to a list."""

    if isinstance(value, dict):

        def sort_key(key: Any) -> tuple[int, str]:
            try:
                return (0, f"{int(key):020d}")
            except (TypeError, ValueError):
                return (1, str(key))

        return [value[key] for key in sorted(value, key=sort_key)]
    return list(value or [])


def parse_customer_depots(telemetry: Any) -> list[CustomerDepotView] | None:
    """Parse depot metadata; None means the payload carries no depot field."""

    if not isinstance(telemetry, dict) or "depots" not in telemetry:
        return None
    raw_depots = lua_array(telemetry.get("depots"))
    depots: list[CustomerDepotView] = []
    for index, raw in enumerate(raw_depots, start=1):
        if not isinstance(raw, dict) or not raw.get("valid", True):
            continue
        position = raw.get("position") or {}
        if not isinstance(position, dict):
            continue
        try:
            x = float(position["x"])
            y = float(position["y"])
        except (KeyError, TypeError, ValueError):
            continue
        unit_number = raw.get("unit_number")
        try:
            parsed_unit = int(unit_number) if unit_number is not None else None
        except (TypeError, ValueError):
            parsed_unit = None
        depot_id = (
            f"customer-depot-{parsed_unit}"
            if parsed_unit is not None
            else f"customer-depot-{index}"
        )
        entity_names = raw.get("entity_names") or {}
        entity_name = raw.get("entity_name") or "steel-chest"
        if isinstance(entity_names, dict) and entity_names:
            entity_name = next(iter(entity_names))
        surfaces = raw.get("surfaces") or {}
        surface = raw.get("surface")
        if isinstance(surfaces, dict) and surfaces:
            surface = next(iter(surfaces))
        products = raw.get("products") or {}
        product = raw.get("product")
        if isinstance(products, dict) and products:
            product = next(iter(products))
        depots.append(
            CustomerDepotView(
                depot_id=depot_id,
                unit_number=parsed_unit,
                entity_name=str(entity_name),
                position={"x": x, "y": y},
                surface=(str(surface) if surface else None),
                customer_owned=bool(raw.get("customer_owned", True)),
                product=(str(product) if product else None),
                acceptance_limit=(
                    float(raw["acceptance_limit"])
                    if raw.get("acceptance_limit") is not None
                    else None
                ),
                accepted=(
                    float(raw["accepted"]) if raw.get("accepted") is not None else None
                ),
            )
        )
    return depots


def parse_delivery_buckets(
    telemetry: dict[str, Any],
    *,
    item_field: str = "items",
) -> tuple[int, list[tuple[int, dict[str, float]]]]:
    """Normalize Lua/RCON delivery buckets to chronological samples."""

    current_tick = int(telemetry.get("tick") or 0)
    raw_buckets = telemetry.get("buckets") or []
    if isinstance(raw_buckets, dict):
        raw_buckets = [
            raw_buckets[key] for key in sorted(raw_buckets, key=lambda key: int(key))
        ]
    samples: list[tuple[int, dict[str, float]]] = []
    for bucket in raw_buckets:
        if not isinstance(bucket, dict):
            continue
        start = int(bucket.get("start_tick") or 0)
        end = start + DELIVERY_BUCKET_TICKS - 1
        sample_tick = min(max(current_tick, start), end)
        items = {
            str(item): float(count)
            for item, count in (bucket.get(item_field) or {}).items()
            if float(count or 0.0) > 0
        }
        if items:
            samples.append((sample_tick, items))
    return current_tick, sorted(samples, key=lambda sample: sample[0])


def translate_delivery_clock(
    telemetry: dict[str, Any], worker_epoch: int | None
) -> dict[str, Any]:
    """Translate Lua depot time to the worker's persistent episode clock.

    Depot adoption resets its Lua clock, while checkpoint restoration keeps
    the worker's original epoch. Without this translation, valid post-resume
    arrivals can appear to predate the active order and are discarded.
    Cumulative quantities are unaffected; both automated and manual buckets
    share the same translation.
    """

    depot_epoch = telemetry.get("epoch_tick")
    if depot_epoch is None or worker_epoch is None:
        return telemetry
    offset = int(depot_epoch) - int(worker_epoch)
    if not offset:
        return telemetry
    buckets = telemetry.get("buckets") or []
    if isinstance(buckets, dict):
        buckets = buckets.values()
    return {
        **telemetry,
        "epoch_tick": int(worker_epoch),
        "tick": int(telemetry.get("tick") or 0) + offset,
        "buckets": [
            {**bucket, "start_tick": int(bucket.get("start_tick") or 0) + offset}
            for bucket in buckets
            if isinstance(bucket, dict)
        ],
    }


def build_delivery_telemetry(
    *,
    history: list[tuple[int, dict[str, float]]],
    observed_tick: int,
    raw_totals: dict[str, float],
    manual_history: list[tuple[int, dict[str, float]]],
    manual_totals: dict[str, float],
    contract_delivery_baseline: dict[str, float],
    recent_limit: int = 120,
) -> DepotDeliveryTelemetry:
    """Build a stable raw-delivery view for observations and contexts."""

    history = list(history)
    observed = max(
        observed_tick,
        max((tick for tick, _ in history), default=0),
    )
    totals = {
        str(item): round(float(amount), 6)
        for item, amount in raw_totals.items()
        if amount > 0
    }
    manual_history = list(manual_history)
    manual_totals_view = {
        str(item): round(float(amount), 6)
        for item, amount in manual_totals.items()
        if amount > 0
    }

    def rate(window_ticks: int) -> dict[str, float]:
        cutoff = observed - window_ticks
        values: dict[str, float] = {}
        for tick, items in history:
            if cutoff < tick <= observed:
                for item, amount in items.items():
                    values[item] = values.get(item, 0.0) + amount
        minutes = window_ticks / 3600.0
        return {
            item: round(amount / minutes, 6)
            for item, amount in values.items()
            if amount > 0
        }

    recent = [
        {
            "start_tick": max(tick - DELIVERY_BUCKET_TICKS + 1, 0),
            "end_tick": tick,
            "items": {item: round(float(amount), 6) for item, amount in items.items()},
        }
        for tick, items in history[-max(0, recent_limit) :]
    ]
    return DepotDeliveryTelemetry(
        observed_until_tick=observed,
        bucket_ticks=DELIVERY_BUCKET_TICKS,
        sample_count=len(history),
        raw_totals=totals,
        manual_totals=manual_totals_view,
        raw_rates_60s=rate(3600),
        raw_rates_300s=rate(18000),
        raw_rates_5s=rate(300),
        since_contract_totals={
            str(item): round(
                max(float(amount) - contract_delivery_baseline.get(item, 0.0), 0.0),
                6,
            )
            for item, amount in totals.items()
            if amount > contract_delivery_baseline.get(item, 0.0)
        },
        recent_buckets=recent,
        manual_sample_count=len(manual_history),
        recent_manual_buckets=[
            {
                "start_tick": max(tick - DELIVERY_BUCKET_TICKS + 1, 0),
                "end_tick": tick,
                "items": {
                    item: round(float(amount), 6) for item, amount in items.items()
                },
            }
            for tick, items in manual_history[-max(0, recent_limit) :]
        ],
    )


def record_delivery_samples(
    telemetry: dict[str, Any],
    samples: list[tuple[int, dict[str, float]]],
    history: list[tuple[int, dict[str, float]]],
    raw_totals: dict[str, float],
    observed_tick: int = 0,
) -> int:
    """Append physical sink traffic after the Lua delta log is drained.

    Mutates ``history``/``raw_totals`` in place and returns the updated
    observed tick. Lua's cumulative counter remains authoritative if the
    process has observed a bucket before this Python worker was restarted.
    """

    current_tick = int(telemetry.get("tick") or 0)
    observed = max(observed_tick, current_tick)
    for sample_tick, items in samples:
        history.append((sample_tick, dict(items)))
        for item, amount in items.items():
            raw_totals[item] = raw_totals.get(item, 0.0) + amount
    reported = telemetry.get("raw_delivery_totals") or telemetry.get("delivered_total")
    if isinstance(reported, dict):
        for item, amount in reported.items():
            raw_totals[str(item)] = max(
                raw_totals.get(str(item), 0.0), float(amount or 0.0)
            )
    return observed


def record_manual_delivery_samples(
    telemetry: dict[str, Any],
    samples: list[tuple[int, dict[str, float]]],
    history: list[tuple[int, dict[str, float]]],
    totals: dict[str, float],
) -> None:
    """Retain direct agent-to-depot traffic as non-crediting audit data.

    Manual traffic follows the same retention rule as raw delivery. It
    remains separate so direct insertion can never become credited flow.
    """

    for sample_tick, items in samples:
        history.append((sample_tick, dict(items)))
        for item, amount in items.items():
            totals[item] = totals.get(item, 0.0) + amount
    reported = telemetry.get("manual_delivery_totals")
    if isinstance(reported, dict):
        for item, amount in reported.items():
            totals[str(item)] = max(totals.get(str(item), 0.0), float(amount or 0.0))


def recent_delivery_rates(
    history: list[tuple[int, dict[str, float]]],
    observed_tick: int,
    window_seconds: int,
) -> dict[str, float]:
    """Return inserter-fed depot rates over an exact recent window."""

    observed = max(observed_tick, max((tick for tick, _ in history), default=0))
    window_ticks = max(int(window_seconds), 1) * 60
    cutoff = observed - window_ticks
    totals: dict[str, float] = {}
    for tick, items in history:
        if cutoff < tick <= observed:
            for item, amount in items.items():
                totals[item] = totals.get(item, 0.0) + float(amount)
    minutes = window_ticks / 3600.0
    return {
        item: round(amount / minutes, 6)
        for item, amount in totals.items()
        if amount > 0
    }


def build_delivery_receipt(
    *,
    contracts: list[OpenContractView],
    attempted_insert: bool,
    delivered_before: dict[str, float],
    throughput_audit_passed: bool,
    customer_depot_ids: list[str],
    contract_delivery_baseline: dict[str, float],
    delivery_raw_totals: dict[str, float],
) -> DeliveryReceipt | None:
    """Build the per-intervention delivery receipt from contract state."""

    delivered_after: dict[str, float] = {}
    for contract in contracts:
        for item, amount in contract.fulfilled.items():
            delivered_after[item] = delivered_after.get(item, 0.0) + float(amount)
    credited = {
        item: round(amount - delivered_before.get(item, 0.0), 4)
        for item, amount in delivered_after.items()
        if amount - delivered_before.get(item, 0.0) > 1e-9
    }
    if not attempted_insert and not credited and not contracts:
        return None
    remaining: dict[str, float] = {}
    for contract in contracts:
        for item, amount in contract.remaining.items():
            remaining[item] = remaining.get(item, 0.0) + float(amount)
    open_contract = next(
        (contract for contract in contracts if contract.status == "open"),
        contracts[-1] if contracts else None,
    )
    sustained = bool(open_contract and open_contract.kind == "sustained")
    throughput_certified = bool(throughput_audit_passed)
    qualification_pending = bool(
        sustained
        and open_contract is not None
        and open_contract.status == "open"
        and not throughput_certified
    )
    if credited:
        if sustained:
            message = (
                "Inserter-fed depot delivery observed. This confirms depot "
                "transport only, not automated production. The sustained "
                "contract remains open until unattended production and depot "
                "throughput pass the autonomous audit; a zero physical "
                "delivery balance is not certification."
            )
        else:
            message = (
                "Inserter-fed customer delivery credited. Contract demand is "
                "consumed; production above the acceptance limit remains in "
                "the bound chest."
            )
    elif contracts:
        message = (
            "No inserter-fed customer delivery was observed for this "
            "intervention. This is an interval measurement, not an audit "
            "failure. Direct insertion into the depot is audit-only; "
            "fueling a machine is not itself a rejected depot delivery."
        )
        if sustained:
            message += (
                " Sustained success requires unattended production and depot "
                "throughput to pass the autonomous audit."
            )
        if not customer_depot_ids:
            message += " No delivery chest is bound. Bind an empty chest for the active product."
        else:
            message += (
                " If traffic remains zero, inspect the depot feeder's pickup/drop "
                "positions and status, then its source's fuel, ingredients, and output."
            )
    else:
        message = "No customer contract is currently active."
    return DeliveryReceipt(
        credited=credited,
        remaining={item: round(amount, 4) for item, amount in remaining.items()},
        contract_status=open_contract.status if open_contract else None,
        delivery_mode="inserter_fed" if credited else "none",
        throughput_certified=throughput_certified,
        qualification_pending=qualification_pending,
        customer_depot_ids=list(customer_depot_ids),
        observed_depot_totals={
            item: round(
                max(
                    float(amount) - float(contract_delivery_baseline.get(item, 0.0)),
                    0.0,
                ),
                6,
            )
            for item, amount in delivery_raw_totals.items()
        },
        message=message,
    )
