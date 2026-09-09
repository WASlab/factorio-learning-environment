# Public crafting menu

`get_craft_plan(product, quantity=1, depth=2)` is a stateless read of a named
recipe producing the matching item. Quantity means output items. The response
reports whole recipe batches, output rounding, ingredient counts and deficits,
research/category restrictions, and Factorio's native craftable count.

Native craftability includes intermediate handcrafts. A missing direct ingredient
therefore does not necessarily prevent crafting. Subrecipes are independent
previews of the same inventory, bounded to depth three and 32 nodes; they are not
a shared inventory allocation or an automatically executed production plan.

`queue_craft` uses the same output-item units, reports actual queued items and
recipe executions, and marks partial queues. Zero-craft failures include the same
menu response. The engine still selects and queues native intermediate crafts.

Validation: Lua unit tests cover batch rounding, native intermediate craftability,
depth limits, locked recipes and failure transport. The isolated Factorio 2.0.77
test in `scripts/validate_craft_menu.py` checks six plates producing a native
four-belt capacity, read-only ticks, whole-batch queueing, and exhausted-inventory
failure differences.
