from fle.env.action_queue import insert_queue
from fle.env.tools import Tool


class InsertActions(Tool):
    def __call__(self, before_index, actions):
        submit_tool = self.game_state.instance.controllers["submit_actions"]
        return insert_queue(self.game_state, submit_tool, before_index, actions)
