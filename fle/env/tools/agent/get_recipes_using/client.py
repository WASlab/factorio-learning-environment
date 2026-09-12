from fle.env.tools.observation import ObservationTool, bounded_integer, name_of


class GetRecipesUsing(ObservationTool):
    def __call__(self, item, category="item", limit=64, offset=0):
        """Find recipes consuming an item or fluid, including locked recipes."""
        if category not in {"item", "fluid"}:
            raise ValueError("category must be item or fluid")
        return self.read(
            name_of(item),
            category,
            bounded_integer(limit, "limit"),
            bounded_integer(offset, "offset", 0, 1000000),
            arrays=("recipes",),
            nested_arrays=("ingredients", "products"),
        )
