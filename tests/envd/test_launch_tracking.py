from types import SimpleNamespace

import pytest

from fle.env.entities import Position
from fle.env.tools.agent.launch_rocket.client import LaunchRocket

pytestmark = pytest.mark.no_factorio


def launch_tool(response):
    tool = object.__new__(LaunchRocket)
    tool.player_index = 1
    tool.game_state = SimpleNamespace(instance=SimpleNamespace())
    tool.execute = lambda *_args: (response, 0.01)
    tool.get_entity = lambda *_args: "rocket-silo"
    return tool


def test_accepted_request_does_not_count_as_completed_launch():
    tool = launch_tool(True)

    assert tool(Position(x=0, y=0)) == "rocket-silo"
    assert not hasattr(tool.game_state.instance, "_verified_rocket_launches")


def test_failed_launch_is_not_counted_as_a_verifiable_milestone():
    tool = launch_tool(False)

    with pytest.raises(Exception, match="did not accept the launch request"):
        tool(Position(x=0, y=0))
    assert not hasattr(tool.game_state.instance, "_verified_rocket_launches")
