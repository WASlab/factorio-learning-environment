import json
from pathlib import Path
from unittest.mock import Mock

from lupa.lua54 import LuaRuntime
import pytest

from fle.env.tools.admin.get_path.client import GetPath

pytestmark = pytest.mark.no_factorio


def test_rotated_footprint_bounds_collision_context_without_mutation():
    lua = LuaRuntime()
    lua.execute("""
        storage={utils={}}
        scanned=0
        surface={
            find_entities_filtered=function(query)
                assert(query.limit==18 and query.collision_mask[1]=='water_tile')
                return {}
            end,
            get_tile=function(x,y)
                scanned=scanned+1
                return {name='water',collides_with=function(layer) return true end}
            end
        }
    """)
    lua.execute(
        (Path(__file__).parents[2] / "fle/env/mods/spatial_diagnostics.lua").read_text()
    )
    lua.execute("""
        d=storage.utils.spatial_diagnostics(surface,{x=10,y=20},
            {left_top={x=-1,y=-2},right_bottom={x=1,y=2}},4,{layers={water_tile=true}})
        assert(math.abs(d.footprint.left_top.x-8)<0.0001)
        assert(math.abs(d.footprint.left_top.y-19)<0.0001)
        assert(d.reason=='terrain_collision' and not d.nearest_reachable_verified)
        scanned=0
        d=storage.utils.spatial_diagnostics(surface,{x=0,y=0},
            {left_top={x=-100,y=-100},right_bottom={x=100,y=100}},0,{layers={water_tile=true}})
        assert(scanned==65 and #d.colliding_tiles==16 and d.terrain_truncated)
    """)


def test_path_failure_preserves_requested_goal_and_obstacles():
    reader = GetPath.__new__(GetPath)
    failure = {
        "status": "not_found",
        "goal": {"x": 10, "y": 20},
        "diagnostics": {"goal": {"center_tile": "water"}},
    }
    reader.execute = Mock(return_value=(failure, 0))
    with pytest.raises(RuntimeError) as error:
        reader(42)
    assert json.loads(str(error.value)) == failure
