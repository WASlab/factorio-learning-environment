# queue_craft

`queue_craft(entity: Prototype, quantity: int = 1) -> dict` handcrafts items for
the character. Quantity is a positive integer number of output items; recipes
such as copper cable can produce multiple items per execution. Factorio resolves
required handcraftable intermediates automatically.

The craft completes within the same intervention, so the returned items are
immediately available for placement or insertion in the same program. The
receipt includes `handle`, `recipe`, `requested`, `crafted`, `queued`,
`queued_crafts`, `partial`, and `tick`. `crafted` can be less than requested
when ingredients limit the craft; inspect `craft_plan` on failures. Crafting
never creates items the character cannot afford, because every ingredient is
consumed from the existing inventory.
