from pathlib import Path
from unittest.mock import Mock

from lupa.lua54 import LuaRuntime
import pytest

from fle.env.tools.admin.public_status.client import PublicStatus


pytestmark = pytest.mark.no_factorio


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
        storage={utils={}}
        game={tick=0}
        defines={entity_status={working=1,no_fuel=2}}
        script={on_nth_tick=function(interval, callback)
            assert(interval == 60)
            sample_tick=callback
        end}
        entity={valid=true,unit_number=7,type='furnace',name='stone-furnace',
            surface={index=1},force={index=1},position={x=-23,y=-69},status=1}
    """)
    lua.execute(
        (Path(__file__).parents[2] / "fle/env/mods/status_monitor.lua").read_text(
            encoding="utf-8"
        )
    )
    return lua


def test_native_sampler_captures_stall_without_observation_and_tracks_removal():
    lua = runtime()
    lua.execute("""
        storage.utils.track_public_status(entity)
        game.tick=60; entity.status=2; sample_tick()
        game.tick=120; sample_tick()
        result=storage.utils.read_public_status(1, 1)
        assert(#result.samples == 1)
        assert(result.samples[1].status == 'no_fuel')
        assert(result.samples[1].tick == 60)
        assert(result.samples[1].entity_id == '1:7')
        entity.valid=false; game.tick=180; sample_tick()
        result=storage.utils.read_public_status(1, 2)
        assert(#result.samples == 1 and result.samples[1].removed)
        assert(next(storage.public_status_monitor.entities) == nil)
    """)


def test_engine_ring_reports_overrun_and_force_scoped_keyframe():
    lua = runtime()
    lua.execute("""
        storage.utils.track_public_status(entity)
        for i=1,4100 do
            game.tick=i*60; entity.status=(i % 2)+1; sample_tick()
        end
        result=storage.utils.read_public_status(1, 0)
        assert(#result.samples == 4096)
        assert(result.retained_after_sequence > 0)
        assert(#result.current == 1)
        assert(#storage.utils.read_public_status(2, -1).current == 0)
        assert(#storage.utils.read_public_status(1, -1).current == 1)
    """)


def test_client_normalizes_lua_arrays_before_json_serialization():
    tool = PublicStatus.__new__(PublicStatus)
    tool.player_index = 1
    tool.execute = Mock(
        return_value=({"samples": {2: {"tick": 2}, 1: {"tick": 1}}, "current": {}}, 0)
    )
    assert tool(-1) == {"samples": [{"tick": 1}, {"tick": 2}], "current": []}
