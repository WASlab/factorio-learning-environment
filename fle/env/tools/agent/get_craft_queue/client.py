from fle.env.tools import Tool


class GetCraftQueue(Tool):
    def __call__(self) -> dict:
        response, _ = self.execute(self.player_index)
        result = (
            self.clean_response(response)
            if isinstance(response, dict)
            else {"active": False, "queue": []}
        )
        if not isinstance(result.get("queue"), list):
            result["queue"] = []
        return result
