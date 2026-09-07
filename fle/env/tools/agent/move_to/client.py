import math
from time import sleep
from typing import Iterable

from fle.env.entities import Position
from fle.env.game_types import Prototype
from fle.env.instance import NONE
from fle.env.lua_manager import LuaScriptManager
from fle.env.tools import Tool
from fle.env.tools.admin.get_path.client import GetPath
from fle.env.tools.admin.request_path.client import RequestPath


class MoveTo(Tool):
    """Walk the character over live Factorio ticks."""

    def __init__(self, connection: LuaScriptManager, game_state):
        super().__init__(connection, game_state)
        self.request_path = RequestPath(connection, game_state)
        self.get_path = GetPath(connection, game_state)
        self.last_receipt: dict | None = None

    def __call__(
        self,
        position: Position,
        laying: Prototype = None,
        leading: Prototype = None,
        stop_distance: float = 0,
        mode: str = "walk",
        waypoints: Iterable[Position] | None = None,
        interrupt_on: Iterable[str] | None = None,
        timeout_ticks: int = 60 * 60 * 10,
    ) -> Position:
        if mode.lower() != "walk":
            raise ValueError("move_to currently supports mode='walk' only")
        if stop_distance < 0:
            raise ValueError("stop_distance must be non-negative")
        route = list(waypoints or []) + [position]
        final = self.game_state.player_location
        receipts = []
        for index, target in enumerate(route):
            final, receipt = self._move_one(
                target,
                laying=laying,
                leading=leading,
                stop_distance=stop_distance if index == len(route) - 1 else 0,
                interrupt_on={str(value).lower() for value in (interrupt_on or ())},
                timeout_ticks=timeout_ticks,
            )
            receipts.append(receipt)
            if receipt["status"] != "completed":
                break
        self.last_receipt = {
            "status": receipts[-1]["status"] if receipts else "completed",
            "position": {"x": final.x, "y": final.y},
            "ticks_elapsed": sum(item["ticks_elapsed"] for item in receipts),
            "stop_reason": receipts[-1]["stop_reason"] if receipts else "arrived",
            "segments": receipts,
        }
        return final

    def _move_one(
        self, position, *, laying, leading, stop_distance, interrupt_on, timeout_ticks
    ):
        if not isinstance(position, Position):
            position = getattr(position, "position", None)
        if not isinstance(position, Position):
            raise ValueError("move_to target must be a Position or Entity")
        if timeout_ticks <= 0:
            raise ValueError("timeout_ticks must be positive")

        current = self.game_state.player_location
        dx, dy = position.x - current.x, position.y - current.y
        distance = math.hypot(dx, dy)
        if distance <= stop_distance:
            return current, {
                "status": "completed",
                "ticks_elapsed": 0,
                "stop_reason": "already_in_range",
            }
        # Let the pathfinder choose a reachable approach within the requested
        # radius; a straight-line offset can itself land inside an obstacle.
        goal = position
        for resolution in (0, -1):
            path_handle = self.request_path(
                start=Position(x=current.x, y=current.y),
                finish=goal,
                allow_paths_through_own_entities=False,
                resolution=resolution,
                radius=max(stop_distance, 0.15),
                entity_size=None,
            )
            try:
                self.get_path(path_handle)
                break
            except Exception as exc:
                if resolution == -1 or "not_found" not in str(exc):
                    raise
        start_tick = self._game_tick()
        trailing_name, trailing_mode = NONE, NONE
        if laying is not None:
            trailing_name, trailing_mode = laying.value[0], 1
        elif leading is not None:
            trailing_name, trailing_mode = leading.value[0], 0
        response, _ = self.execute(
            self.player_index, path_handle, trailing_name, trailing_mode, 0
        )
        if isinstance(response, str) or response in ({}, 0, None):
            raise Exception(f"Cannot move to ({goal.x}, {goal.y}): {response}")

        if self.game_state.instance.fast:
            final = Position(x=response["x"], y=response["y"])
            self.game_state.player_location = final
            return final, {
                "status": "completed",
                "ticks_elapsed": max(self._game_tick() - start_tick, 0),
                "stop_reason": "arrived",
            }

        deadline = start_tick + timeout_ticks
        status = {"active": True}
        while status.get("active"):
            sleep(0.05)
            status, _ = self.execute(self.player_index, "__status__", NONE, NONE, 0)
            if not isinstance(status, dict):
                raise Exception(f"Cannot read walking status: {status}")
            if self._game_tick() >= deadline:
                status, _ = self.execute(self.player_index, "__cancel__", NONE, NONE, 0)
                status["stop_reason"] = "timeout"
            event = str(status.get("event") or "").lower()
            if event and event in interrupt_on:
                status, _ = self.execute(self.player_index, "__cancel__", NONE, NONE, 0)
                status["stop_reason"] = event

        final = Position(x=float(status["x"]), y=float(status["y"]))
        self.game_state.player_location = final
        reason = str(status.get("stop_reason") or "arrived")
        if reason == "blocked_no_progress":
            raise RuntimeError(
                f"Movement blocked near ({final.x:.2f}, {final.y:.2f}); "
                "the requested destination may be occupied. Use a positive "
                "stop_distance or call the intended interaction action directly."
            )
        return final, {
            "status": "completed"
            if reason in {"arrived", "already_in_range"}
            else "partial",
            "ticks_elapsed": max(self._game_tick() - start_tick, 0),
            "stop_reason": reason,
        }

    def _game_tick(self) -> int:
        raw = self.connection.rcon_client.send_command("/sc rcon.print(game.tick)")
        return int(raw or 0)
