# wait

```python
wait(ticks: int, until: dict | None = None, poll_ticks: int = 30) -> dict
```

Wait over native Factorio ticks. Machines, research, crafting, and deliveries
continue while the simulation runs. An optional condition stops the wait early:

```python
wait(1800, until={"inventory": {
    "entity": furnace, "item": Prototype.IronPlate, "at_least": 5,
}})
wait(1800, until={"research": {"technology": Technology.AutomationSciencePack}})
wait(1800, until={"craft_queue": {"active": False}})
```

Research conditions check the engine's researched flag, including technologies
unlocked by crafting an item. The result reports `requested_ticks`,
`simulation_ticks_advanced`, `condition_met`, `observed`, and `stop_reason`.
An unmet condition at the tick limit returns `status="timeout"`.

The enclosing program's wall-time limit still applies. At 10x simulation speed,
183,000 ticks require at least 305 seconds, exceeding a 120-second program
budget. Use shorter waits and inspect progress between calls. Program timeout
cancels polling and raises an error; it does not return a successful wait.
