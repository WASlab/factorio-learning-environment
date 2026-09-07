import math
from typing import Tuple, Union

from fle.env.entities import Position, Entity
from fle.env.namespace import FactorioNamespace
from fle.env.tools.controller import Controller


class Tool(Controller):
    def __init__(
        self,
        lua_script_manager: "FactorioLuaScriptManager",  # noqa
        game_state: "FactorioNamespace",
        *args,
        **kwargs,
    ):
        super().__init__(lua_script_manager, game_state)
        self.load()

    def get_position(self, position_or_entity: Union[Tuple, Position, Entity]):
        if isinstance(position_or_entity, tuple):
            x, y = position_or_entity
        elif isinstance(position_or_entity, Entity):
            x = position_or_entity.position.x
            y = position_or_entity.position.y
        else:
            x = position_or_entity.x
            y = position_or_entity.y

        return x, y

    def get_error_message(self, response):
        # Colons separate useful diagnostics too (for example, a missing
        # technology and its recipe). Never discard that causal context.
        return response.strip() if isinstance(response, str) else response

    def ensure_reachable(self, target, stop_distance: float = 5.5):
        """Walk into interaction range in live mode without choosing a new target."""

        if self.game_state.instance.fast:
            return self.game_state.player_location
        position = target.position if isinstance(target, Entity) else target
        x, y = self.get_position(position)
        current = self.game_state.player_location
        if math.hypot(x - current.x, y - current.y) <= stop_distance:
            return current
        # Lazy import avoids a module cycle: MoveTo itself derives from Tool.
        from fle.env.tools.agent.move_to.client import MoveTo

        return MoveTo(self.connection, self.game_state)(
            Position(x=x, y=y), stop_distance=stop_distance
        )

    def load(self):
        # self.lua_script_manager.load_action_into_game(self.name)
        self.lua_script_manager.load_tool_into_game(self.name)
        # script = _load_action(self.name)
        # if not script:
        #     raise Exception(f"Could not load {self.name}")
        # self.connection.send_command(f'{COMMAND} '+script)
