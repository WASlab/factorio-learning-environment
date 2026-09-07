# queue_craft

`queue_craft(entity: Prototype, quantity: int = 1) -> dict` starts native
handcrafting and returns immediately. Quantity is a positive integer number of
recipe executions; recipes such as copper cable can produce multiple items per
execution. Factorio queues required handcraftable intermediates automatically.

The receipt includes `handle`, `recipe`, `requested`, `queued`, and `tick`.
`queued` can be less than requested when ingredients limit the craft. Inspect
`get_craft_queue()` or use `wait(..., until={"craft_queue": {"active": False}})`
to observe completion. Production and craft-trigger research credit are recorded
only when crafting completes, not when the request is queued.
