from typing import Any

from fle.env.entities import Entity, Position
from fle.env.game_types import Prototype
from fle.env.tools import Tool


class SetDeliveryChest(Tool):
    """Bind an empty player-owned chest to one active contract product."""

    def __call__(
        self,
        chest: Entity | Position,
        product: Prototype | str,
    ) -> dict[str, Any]:
        x, y = self.get_position(chest)
        if isinstance(product, Prototype):
            product_name = product.value[0]
        elif isinstance(product, str) and product:
            product_name = product
        else:
            raise ValueError("product must be a Prototype item or canonical item name")
        response, _ = self.execute(self.player_index, x, y, product_name)
        if not isinstance(response, dict):
            raise RuntimeError(f"Could not bind delivery chest: {response}")
        if response.get("error"):
            raise RuntimeError(f"Could not bind delivery chest: {response['error']}")
        response["product"] = product_name
        response["entity_name"] = getattr(chest, "name", None)
        return response
