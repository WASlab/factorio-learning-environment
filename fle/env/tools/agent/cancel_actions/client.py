from fle.env.action_queue import cancel_queue
from fle.env.tools import Tool


class CancelActions(Tool):
    def __call__(self, from_index=None):
        return cancel_queue(self.game_state, from_index)
