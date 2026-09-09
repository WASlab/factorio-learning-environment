# wait

`wait(ticks, until=None, poll_ticks=30)` waits while native machines, research,
crafting, and deliveries continue. Conditions are sampled in the engine every
`poll_ticks` simulation ticks, at the start, and at the deadline. The first
satisfied sample is retained even if its state changes before the response arrives.

```python
wait(1800, until={"inventory": {"entity": furnace, "item": Prototype.IronPlate, "at_least": 5}})
wait(1800, until={"research": {"technology": Technology.AutomationSciencePack}})
wait(1800, until={"craft_queue": {"active": False}})
wait(1800, until={"machine_status": {"entity": furnace, "status": "no_fuel"}})
wait(1800, until={"delivery": {"item": Prototype.IronPlate, "at_least": 100}})
wait(1800, until={"production_rate": {"item": Prototype.IronPlate, "at_least": 60, "window_seconds": 60}})
wait(1800, until={"event": {"type": "research_completed"}})
```

Inventory without `entity` means the character's inventory. Machine references
require a stable entity id; removal ends with an error. Delivery means accepted
items for that product in the currently configured public order. Production rates
include manual production, matching the public statistics window; supported native
windows are 5, 60, 600, and 3600 seconds.

Event types are `research_completed`, `under_attack`, and `new_order`. Only events
after the wait starts count. New orders become visible when the controller
configures them; waiting does not cause the controller to generate a new order.

The result reports `status`, `start_tick`, `deadline_tick`, `decision_tick`,
`simulation_ticks_advanced`, `poll_latency_ticks`, `condition_met`, `observed`, and
`stop_reason`. With no condition, reaching the limit is `completed`; an unmet
condition is `timeout`. Condition decisions occur no later than the deadline.
The simulation can advance while Python receives the result; this transport
latency is reported separately. Changes shorter than the sample interval can be
missed. The enclosing program's wall-time limit applies and cancels active waits.
