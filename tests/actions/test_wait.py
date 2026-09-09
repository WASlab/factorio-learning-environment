from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from lupa.lua54 import LuaRuntime
import pytest

from fle.env.tools.agent.wait.client import Wait

pytestmark = pytest.mark.no_factorio


def runtime():
    lua = LuaRuntime()
    lua.execute("""
        game={tick=100}
        defines={events={on_tick=1},entity_status={working=1,no_fuel=2}}
        script={on_event=function(_,f) tick_handler=f end}
        machine={valid=true,status=2,get_item_count=function() return count end}
        count=0
        storage={actions={},agent_characters={[1]={valid=true}},entity_handles={[42]=machine}}
    """)
    lua.execute(
        (Path(__file__).parents[2] / "fle/env/tools/agent/wait/server.lua").read_text()
    )
    return lua


def test_wait_latches_condition_before_it_disappears():
    lua = runtime()
    lua.execute("""
        storage.actions.wait('start',1,{ticks=90,poll_ticks=30,condition={kind='machine_status',entity_id=42,status='working'}})
        game.tick=130; machine.status=1; tick_handler{}
        game.tick=160; machine.status=2; tick_handler{}
        result=storage.actions.wait('poll',1)
        assert(result.status=='condition_met' and result.decision_tick==130)
        assert(result.observed.status=='working' and result.tick==160)
        storage.actions.wait('cancel',1)
        assert(storage.public_waits[1]==nil)
    """)


def test_wait_samples_at_deadline_even_between_poll_intervals():
    lua = runtime()
    lua.execute("""
        storage.actions.wait('start',1,{ticks=5,poll_ticks=30,condition={kind='inventory',entity_id=42,item='plate',at_least=1}})
        game.tick=105; tick_handler{}
        count=3; game.tick=106; tick_handler{}
        result=storage.actions.wait('poll',1)
        assert(result.status=='timeout' and result.decision_tick==105 and result.observed.count==0)
    """)


def test_client_reports_transport_latency_and_cleans_up():
    tool = Wait.__new__(Wait)
    tool.player_index = 1
    tool.game_state = SimpleNamespace(instance=SimpleNamespace(get_speed=lambda: 10))
    tool.execute = Mock(
        side_effect=[
            ({"start_tick": 100, "deadline_tick": 105}, 0),
            ({"status": "completed", "decision_tick": 105, "tick": 108}, 0),
            (True, 0),
        ]
    )
    result = tool(5)
    assert (
        result["poll_latency_ticks"] == 3 and result["simulation_ticks_advanced"] == 8
    )
    assert result["condition_met"] is None
    tool.execute.assert_called_with("cancel", 1)


@pytest.mark.parametrize("ticks", [0, -1, 1.5, True])
def test_wait_rejects_invalid_ticks(ticks):
    with pytest.raises(ValueError, match="ticks must be a positive integer"):
        Wait.__new__(Wait)(ticks)


def test_condition_does_not_accept_kind_override_or_nonfinite_threshold():
    with pytest.raises(ValueError):
        Wait._validate(
            {"inventory": {"kind": "research", "item": "plate", "at_least": 1}}
        )
    with pytest.raises(ValueError):
        Wait._validate({"delivery": {"item": "plate", "at_least": float("nan")}})
