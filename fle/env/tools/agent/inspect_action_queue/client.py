from fle.env.action_queue import inspect_queue
from fle.env.tools import Tool


class InspectActionQueue(Tool):
    def __call__(self):
        return inspect_queue(self.game_state)
