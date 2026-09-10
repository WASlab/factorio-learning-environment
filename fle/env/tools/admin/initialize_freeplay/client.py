from fle.env.tools import Tool


class InitializeFreeplay(Tool):
    def __call__(self):
        response, _ = self.execute(self.player_index)
        if not isinstance(response, dict):
            raise RuntimeError(f"Freeplay initialization failed: {response}")
        return response
