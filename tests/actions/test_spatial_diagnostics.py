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


def test_mining_drill_without_resources_reports_dedicated_reason():
    lua = LuaRuntime()
    lua.execute("""
        storage={utils={}}
        resource_result={}
        surface={
            find_entities_filtered=function(query)
                if query.type=='resource' then return resource_result end
                return {}
            end,
            get_tile=function(x,y)
                return {name='grass',collides_with=function(layer) return false end}
            end
        }
        prototype={type='mining-drill',tile_width=2,tile_height=2,
            collision_mask={layers={player=true}}}
    """)
    lua.execute(
        (Path(__file__).parents[2] / "fle/env/mods/spatial_diagnostics.lua").read_text()
    )
    lua.execute("""
        d=storage.utils.spatial_diagnostics(surface,{x=3,y=-70},
            {left_top={x=-0.7,y=-0.7},right_bottom={x=0.7,y=0.7}},4,
            prototype.collision_mask,nil,prototype)
        assert(d.reason=='no_minable_resources')
        assert(d.mining_area and d.mining_resources and next(d.mining_resources)==nil)
        resource_result={{name='iron-ore'}}
        d=storage.utils.spatial_diagnostics(surface,{x=3,y=-64},
            {left_top={x=-0.7,y=-0.7},right_bottom={x=0.7,y=0.7}},4,
            prototype.collision_mask,nil,prototype)
        assert(d.reason=='engine_rules_or_route_obstruction')
        assert(d.mining_resources['iron-ore']==1)
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


def test_diagnostics_promote_nearest_blocker_entity():
    lua = LuaRuntime()
    lua.execute("""
        storage={utils={}}
        surface={
            find_entities_filtered=function(query)
                return {{name='small-electric-pole', type='electric-pole', valid=true,
                    position={x=1,y=0}, unit_number=7}}
            end,
            get_tile=function(x,y)
                return {name='grass',collides_with=function(layer) return false end}
            end
        }
    """)
    lua.execute(
        (Path(__file__).parents[2] / "fle/env/mods/spatial_diagnostics.lua").read_text()
    )
    lua.execute("""
        d=storage.utils.spatial_diagnostics(surface,{x=0,y=0},
            {left_top={x=-0.5,y=-0.5},right_bottom={x=0.5,y=0.5}},0,{layers={player=true}})
        assert(d.reason=='occupied')
        assert(d.blocked_by.prototype=='small-electric-pole')
        assert(d.blocked_by.entity_id==7)
        assert(d.blocked_by.position.x==1)
    """)
