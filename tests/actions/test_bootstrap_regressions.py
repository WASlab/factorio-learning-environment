from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path

import pytest

from fle.env import Position
from fle.env.game_types import Resource
from fle.env.tools.agent.harvest_resource.client import HarvestResource

pytestmark = pytest.mark.no_factorio


def native_tool(counts, ticks, queues):
    tool = object.__new__(HarvestResource)
    tool.player_index = 1
    tool.get_resource_type_at_position = Mock(return_value=Resource.IronOre)
    tool.inspect_inventory = Mock(side_effect=[{"iron-ore": n} for n in counts])
    tool.ensure_reachable = Mock()
    tool.execute = Mock(return_value=(1, 0))  # One persistent ore entity, not one item.
    tool._native_tick = Mock(side_effect=ticks)
    tool._action_expression = lambda name, *args: name
    connection = Mock()
    connection.send_command.side_effect = queues
    tool.connection = SimpleNamespace(rcon_client=connection)
    return tool


def test_native_harvest_counts_inventory_not_number_of_resource_entities():
    tool = native_tool([0, 5], [0, 600], ["0", None])
    assert tool._harvest_native(Position(1, 1), 5, 10) == 5
    tool.execute.assert_called_once()


def test_stalled_harvest_cancels_mining_and_reports_actual_progress():
    tool = native_tool([0, 0], [0, 1800], ["1", None])
    with pytest.raises(TimeoutError, match="obtained 0/5"):
        tool._harvest_native(Position(1, 1), 5, 10)
    assert (
        tool.connection.rcon_client.send_command.call_args.args[0]
        == "/sc clear_harvest_queue"
    )


def walking_runtime():
    from lupa.lua54 import LuaRuntime

    lua = LuaRuntime()
    lua.execute("""
        game={tick=0}
        player={valid=true,position={x=0,y=0}}
        storage={fast=false,actions={},utils={},walking_queues={}}
        storage.utils.ensure_valid_character=function() return player end
        storage.utils.get_direction_with_diagonals=function() return 0 end
        script={on_nth_tick=function(interval, fn) registered_interval=interval end}
        storage.walking_queues[1]={positions={{x=10,y=0},{x=20,y=0}},
            current_target={x=10,y=0},final_target={x=20,y=0},last_progress_tick=0}
    """)
    lua.execute(
        (
            Path(__file__).parents[2] / "fle/env/tools/agent/move_to/server.lua"
        ).read_text()
    )
    return lua


def test_oscillation_is_not_progress_toward_a_waypoint():
    lua = walking_runtime()
    lua.execute("""
        for tick=1,200 do
            game.tick=tick
            player.position.x=(tick % 2)*0.1
            storage.actions.update_walking_queues()
        end
    """)
    assert lua.eval("storage.walking_queues[1].stop_reason") == "blocked_no_progress"
    assert lua.eval("player.walking_state.walking") is False


def test_walking_does_not_skip_a_corner_from_one_tile_away():
    lua = walking_runtime()
    lua.execute("player.position.x=9.2; storage.actions.update_walking_queues()")
    assert lua.eval("#storage.walking_queues[1].positions") == 2
    lua.execute("player.position.x=9.8; storage.actions.update_walking_queues()")
    assert lua.eval("#storage.walking_queues[1].positions") == 1
