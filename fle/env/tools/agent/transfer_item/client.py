from fle.env.tools import Tool


class TransferItem(Tool):
    def __call__(self, item, source, target, quantity=5):
        taken = self.game_state.extract_item(item, source, quantity)
        self.game_state.insert_item(item, target, taken)
        return {"status": "completed", "transferred": taken, "item": item.value[0]}
