## get_recipes_using

`get_recipes_using(item, category='item', limit=64, offset=0)`

Accepts a Prototype enum or canonical item/fluid name. category is item or fluid. Returns non-hidden consuming recipes, including locked recipes, with enabled state, category, ingredients, products and energy_seconds. Names are sorted. Use get_prototype_recipe or factorio_get_recipe for the forward direction and factorio_get_prototype for the pinned prototype facts.


Paginated results include total, offset and truncated. Advance offset by the number of returned entries. limit is 1–128 (get_trains: 1–64); offset is nonnegative. Pagination is a fresh live read, not a snapshot across calls.
