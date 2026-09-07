from fle.env.tools import Tool


class CancelCraft(Tool):
    def __call__(self, index: int = 1, quantity: int | None = None) -> dict:
        response, _ = self.execute(self.player_index, index, quantity or -1)
        if not isinstance(response, dict):
            raise Exception(
                f"Could not cancel craft: {self.get_error_message(response)}"
            )
        return self.clean_response(response)
