"""Compact model-facing reference for the canonical semantic motor profile."""

from __future__ import annotations

import hashlib

ACTION_PROFILE_REFERENCE_ID = "semantic-motor-v1/reference-v1"

ACTION_PROFILE_REFERENCE = """\
Operate and expand a persistent factory, emphasizing autonomous production,
throughput, and research while satisfying the current contract. The harness
submits one short Python program through `factorio_execute_program`; calls,
loops, and conditionals inside it execute in source order and count as one
intervention. Do not import FLE or use reflection. Do not emit MCP calls from
a program or use host/file/network access or private attributes.

This is a turn-based semantic-motor environment. Factorio is paused while you
reason and runs during actions. Walking, mining, native crafting, machines,
belts, research, pollution, power, and deliveries all advance on real game
ticks. Game speed only changes wall-clock execution speed. Interaction actions
auto-approach their exact requested target. The controller routes the character
around obstacles; it never chooses a factory route or silently changes a
placement. Use explicit waypoints or path corners for strategic layout choices.

Execution receipts include public machine `status_changes`, anchored to an
observation revision. Inspect these for no_fuel, no_power, no_ingredients, and
blocked output. Events are sampled every 60 simulation ticks over registered
machines; sub-second changes can be missed. Coalesced events retain observed
statuses and peak severity. `truncated` or `history_expired` means the feed is
incomplete: query public state with kind='alerts' and since_revision, or request
a current observation. Initial/reconnected state is a keyframe, not a transition.

Core inspection and interaction:
- inspect_inventory(entity=None) -> Inventory
- get_entities(entities=set(), position=None, radius=1000) -> list[Entity]
- nearest(Prototype.X or Resource.X) -> Position
- get_entity(Prototype.X, position) -> Entity; resolve_entity(entity.id) -> Entity
- get_entity_ports(entity) -> {inputs, outputs}
- move_to(target, stop_distance=0, mode='walk', waypoints=None,
    interrupt_on=None, timeout_ticks=36000) -> Position
    Open coordinates are exact; occupied coordinates resolve to the nearest
    walkable point in interaction range. stop_distance stops earlier.
- harvest_resource(position, quantity=1) -> int
- insert_item(item, target, quantity=5) -> Entity
- extract_item(item, source, quantity=5) -> int
- transfer_item(item, source, target, quantity=5) -> dict
- pickup_entity(entity), rotate_entity(entity, direction)
- set_entity_recipe(entity, RecipeName.X)

Construction is exact and non-atomic. Earlier successful placements remain
when a later placement fails:
- place_entity(Prototype.X, direction=Direction.UP, position=Position(x,y), exact=True)
- place_path(prototype, points, routing='polyline', on_collision='stop',
    on_insufficient_materials='stop') -> structured partial/completed receipt
    Segments are axis-aligned; specify every corner. The controller infers
    segment orientations but does not route around obstacles.
- place_grid(prototype, origin, rows, columns, spacing=(x,y), direction=...)
- repeat_pattern(pattern, origin, count, stride), where each pattern entry has
    prototype, offset, and optional direction
- place_between(prototype, source, target, position) infers orientation only;
    you still choose the placement tile
- place_power_line(points, pole, spacing=7) places poles along your corridor
- place_offshore_pump(preferred_position, direction=...) provides the one
    explicit shoreline-snapping exception

`connect_entities`, `nearest_buildable`, move_to laying/leading, and generic
non-exact placement belong to `planner-assisted-v1` and are rejected here.

Native asynchronous work and event-oriented waits:
- submit_actions(actions, interrupt_on=None) executes a finite command queue
    immediately and returns when completed, halted, or interrupted. Each action
    is {'id': optional_name, 'action': name, 'args': [...], 'kwargs': {...}}.
    Use {'$result': id} inside later args to consume an earlier result. The
    queue stops on the first execution failure without undoing prior actions.
- inspect_action_queue(); cancel_actions(from_index=None);
    insert_actions(before_index, actions); resume_actions(). Pending actions
    persist across model turns. Indices are zero-based. Capability availability
    is checked when submitted; inventory, geometry, and other state-dependent
    constraints are checked when each action executes. Common interrupts are
    action_failure, research_completed, under_attack, and new_order.
- get_craft_plan(Prototype.X, quantity=1, depth=2) reads the native crafting menu:
    craftable_now counts output items including native intermediate crafting;
    ingredients show have/need/missing. Subrecipes are bounded independent
    previews sharing the same inventory, not a combined allocation plan.
    factorio_get_craft_plan exposes the same read without a program intervention.
- queue_craft(Prototype.X, quantity=1) -> {handle, queued, queued_crafts, partial, tick}
    quantity and queued count output items; recipes round up to whole crafts.
    Partial native queues are reported explicitly. Failures include craft_plan.
- get_craft_queue() -> {active, queue, tick}; cancel_craft(index=1, quantity=None)
- craft_item(...) is blocking compatibility sugar; prefer queue_craft so hand
    crafting overlaps movement and other live actions
- wait(ticks, until=None, poll_ticks=30) waits authoritative game ticks and may
    stop early on exactly one condition: inventory, research, craft_queue,
    production_rate, machine_status, delivery, or event. Engine samples latch the
    first match; decision_tick and poll_latency_ticks separate the decision from
    transport delay. Production rates include manual production. Example:
    wait(18000, until={'inventory': {'entity': chest,
        'item': Prototype.IronPlate, 'at_least': 100}})
    wait(18000, until={'production_rate': {'item': Prototype.IronPlate,
        'at_least': 200, 'window_seconds': 60}})
- get_production_statistics(items=None, window_seconds=60, category='item', limit=32)
    reads native produced/consumed totals and per-minute rates, including manual
    production. Windows: 5/60/600/3600 seconds; category: item/fluid. Results are
    bounded with truncation metadata. query_state(kind='production') includes
    these public statistics as well as observation history.
- queue_research([Technology.X, Technology.Y]) appends enabled technologies to
    Factorio's native queue; set_research(Technology.X) replaces the queue
- get_research_progress(Technology.X)

Customer output:
- set_delivery_chest(chest, product) binds an existing empty player-owned chest;
  high-rate lines may allow multiple chests and report the remaining allowance
  for the current product. Only inserter-fed delivery counts. Excess remains in
  the chest and it becomes ordinary when the order ends.

RecipeName is the recipe namespace; Prototype identifies items/entities. Query
get_prototype_recipe before assuming ingredients. Trigger technologies cannot
be started with set_research: inspect their research_trigger in the game-data
reference and satisfy it. Returned entities include stable integer `id` handles;
use resolve_entity(id) after the world changes instead of trusting stale fields.
Every operation still obeys reach, collision, inventory, native duration, and
partial effects. Inspect the returned receipt or re-query state before assuming
a plan worked.
"""

ACTION_PROFILE_REFERENCE_SHA256 = hashlib.sha256(
    ACTION_PROFILE_REFERENCE.encode("utf-8")
).hexdigest()
