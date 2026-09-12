from pathlib import Path
from unittest.mock import Mock

import pytest
from lupa.lua54 import LuaRuntime

from fle.env.entities import Position
from fle.env.tools.agent.get_tile_map.client import GetTileMap

pytestmark = pytest.mark.no_factorio


def runtime():
    lua = LuaRuntime()
    lua.execute("""
        storage={actions={},agent_characters={[1]={surface=nil}}}
        entities={}
        tiles={}
        function add_entity(x,y,entity)
            entities[string.format('%d,%d',x,y)]=entity
        end
        surface={
            find_entities_filtered=function(query)
                local lt=query.area[1]; local rb=query.area[2]
                local x=math.floor((lt[1]+rb[1])/2); local y=math.floor((lt[2]+rb[2])/2)
                local e=entities[string.format('%d,%d',x,y)]
                if e then return {e} end
                return {}
            end,
            get_tile=function(x,y)
                local name=tiles[string.format('%d,%d',x,y)] or 'grass-1'
                return {name=name, collides_with=function(layer)
                    return name=='water' or name=='cliff'
                end}
            end,
        }
        storage.agent_characters[1].surface=surface
    """)
    lua.execute(
        (
            Path(__file__).parents[2] / "fle/env/tools/agent/get_tile_map/server.lua"
        ).read_text()
    )
    return lua


def test_tile_map_marks_machines_resources_and_terrain():
    lua = runtime()
    lua.execute("""
        add_entity(0,0,{name='transport-belt', type='transport-belt',
            position={x=0,y=0}, direction=4, unit_number=1, status=1})
        add_entity(1,0,{name='small-electric-pole', type='electric-pole',
            position={x=1,y=0}, direction=0, unit_number=2, status=1})
        add_entity(-1,0,{name='iron-ore', type='resource',
            position={x=-1,y=0}, direction=0, unit_number=3, status=1})
        add_entity(0,-1,{name='stone-furnace', type='furnace',
            position={x=0,y=-1}, direction=0, unit_number=4, status=1})
        add_entity(0,1,{name='inserter', type='inserter',
            position={x=0,y=1}, direction=0, unit_number=5, status=1})
        tiles['1,1']='water'
        tiles['-1,-1']='cliff'
        result=storage.actions.get_tile_map(1,0,0,2)
        assert(#result.rows==5)
        assert(result.rows[1]=='.....')
        assert(result.rows[2]=='.#F..')
        assert(result.rows[3]=='.*>P.')
        assert(result.rows[4]=='..I~.')
        assert(result.rows[5]=='.....')
        assert(#result.entities==4 and result.entities_truncated==false)
        assert(result.legend:find('belts') ~= nil)
    """)


def test_tile_map_bounds_are_clamped():
    lua = runtime()
    lua.execute("""
        small=storage.actions.get_tile_map(1,10,10,0)
        assert(small.radius==1 and #small.rows==3)
        large=storage.actions.get_tile_map(1,10,10,1000)
        assert(large.radius==32 and #large.rows==65)
    """)


def test_client_validates_center_and_radius():
    tool = GetTileMap.__new__(GetTileMap)
    tool.player_index = 1
    tool.execute = Mock(return_value=({"rows": []}, 0))
    with pytest.raises(ValueError, match="center must be a Position"):
        tool((0, 0))
    with pytest.raises(ValueError, match="radius"):
        tool(Position(x=0, y=0), radius=0)
    tool.execute = Mock(return_value=(True, 0))
    with pytest.raises(Exception, match="Could not build tile map"):
        tool(Position(x=0, y=0))
