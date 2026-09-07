# get_craft_queue

`get_craft_queue() -> dict` reports `active`, `queue`, and the current `tick`.
Each queue entry contains its one-based `index`, recipe name, and remaining
recipe execution `count`. Native intermediate crafts appear as their own entries.
An empty queue has `active=False`; use current inventory to inspect finished items.
