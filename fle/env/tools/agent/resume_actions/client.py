from fle.env.action_queue import run_queue
from fle.env.tools import Tool


class ResumeActions(Tool):
    def __call__(self):
        return run_queue(self.game_state)
