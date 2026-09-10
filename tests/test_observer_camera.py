import pytest
from lupa import LuaRuntime

from fle.cluster.observer_camera import camera_command

pytestmark = pytest.mark.no_factorio


def world():
    lua = LuaRuntime()
    lua.execute("""
        defines={controllers={spectator=5},input_action={build=1,craft=2}}
        p={connected=true,controller_type=5,admin=false,cheat_mode=false,
           position={x=10,y=20},zoom=1,
           permission_group={allows_action=function() return false end},
           surface={is_chunk_generated=function() return true end}}
        p.teleport=function(target,surface) p.position=target; return true end
        game={tick=123,tick_paused=true,speed=10,get_player=function() return p end}
        remote={call=function() p.position={x=100,y=200}; return true end}
        helpers={table_to_json=function(t) return t end}
        rcon={print=function(t) result=t end}
    """)
    return lua


@pytest.mark.parametrize(
    "action", ["left", "right", "up", "down", "home", "in", "out", "status"]
)
def test_camera_changes_only_view_without_advancing_clock(action):
    lua = world()
    lua.execute(camera_command(action)[4:])
    result = lua.globals().result
    assert result.clock_unchanged
    assert result.tick == 123 and result.paused
    if action == "right":
        assert result.position.x == 26
    if action == "home":
        assert result.position.x == 100
    if action == "in":
        assert result.zoom == 1.25


@pytest.mark.parametrize(
    "unsafe",
    [
        "p.admin=true",
        "p.cheat_mode=true",
        "p.controller_type=4",
        "p.connected=false",
        "p.permission_group=nil",
        "p.permission_group.allows_action=function() return true end",
        "p.surface.is_chunk_generated=function() return false end",
    ],
)
def test_unsafe_observer_or_ungenerated_destination_is_rejected(unsafe):
    lua = world()
    lua.execute(unsafe)
    with pytest.raises(Exception):
        lua.execute(camera_command("right")[4:])
    assert lua.globals().p.position.x == 10
    assert lua.globals().game.tick == 123


@pytest.mark.parametrize(
    "action,step", [("build", 16), ("right", 0), ("right", 65), ("right", True)]
)
def test_invalid_commands_rejected(action, step):
    with pytest.raises(ValueError):
        camera_command(action, step)
