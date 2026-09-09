from fle.env.game_types import Prototype
from fle.env.tools import Tool
from fle.env.tools.agent.get_craft_plan.client import normalize_plan
import json


class QueueCraft(Tool):
    """Queue native handcrafting and return immediately."""

    def __call__(self, entity: Prototype, quantity: int = 1) -> dict:
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("quantity must be a positive integer")
        name = entity.value[0] if hasattr(entity, "value") else str(entity)
        response, _ = self.execute(self.player_index, name, quantity)
        if not isinstance(response, dict):
            raise Exception(
                f"Could not queue {quantity}x {name}: {self.get_error_message(response)}"
            )
        if response.get("error"):
            plan = normalize_plan(response["craft_plan"])
            raise ValueError(
                json.dumps(
                    {"reason": response["reason"], "craft_plan": plan},
                    separators=(",", ":"),
                )
            )
        return self.clean_response(response)
