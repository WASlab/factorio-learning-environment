from typing import Any

from fle.env.game_types import Prototype
from fle.env.tools import Tool


def normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    for key in ("ingredients", "missing_subrecipes"):
        value = plan.get(key, [])
        if isinstance(value, dict):
            value = [value[index] for index in sorted(value, key=int)]
        plan[key] = value
    for child in plan["missing_subrecipes"]:
        normalize_plan(child)
    return plan


class GetCraftPlan(Tool):
    """Read native handcraftability and ingredient differences without crafting."""

    def __call__(
        self, product: Prototype | str, quantity: int = 1, depth: int = 2
    ) -> dict[str, Any]:
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or not 1 <= quantity <= 1_000_000
        ):
            raise ValueError("quantity must be an integer between 1 and 1000000")
        if isinstance(depth, bool) or not isinstance(depth, int) or not 0 <= depth <= 3:
            raise ValueError("depth must be an integer between 0 and 3")
        name = product.value[0] if isinstance(product, Prototype) else product
        if not isinstance(name, str) or not name:
            raise ValueError("product must be a Prototype or recipe/item name")
        response, _ = self.execute(self.player_index, name, quantity, depth)
        if not isinstance(response, dict):
            raise RuntimeError(self.get_error_message(response))
        return normalize_plan(response)
