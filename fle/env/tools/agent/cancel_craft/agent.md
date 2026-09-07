# cancel_craft

`cancel_craft(index: int = 1, quantity: int | None = None) -> dict` cancels
native crafting at the one-based queue index returned by `get_craft_queue()`.
Omit quantity to cancel that entry completely. Factorio manages ingredient
refunds and dependent intermediate crafts. The receipt reports `cancelled`,
`index`, and `tick`. Cancelled work receives no production or research credit.
