from fle.env.action_queue import submit_queue
from fle.env.tools import Tool


class SubmitActions(Tool):
    """Submit and immediately execute a finite queue of semantic actions."""

    def __call__(self, actions, interrupt_on=None):
        return submit_queue(self.game_state, self, actions, interrupt_on)
