from pathlib import Path
from unittest.mock import Mock

import pytest
from lupa.lua54 import LuaRuntime

from fle.env.entities import Position
from fle.env.tools.agent.trace_belt.client import TraceBelt

pytestmark = pytest.mark.no_factorio


def runtime():
    lua = LuaRuntime()
    lua.execute("""
        storage={actions={},agent_characters={[1]={surface=nil}}}
        belts={}
        blockers={}
        function make_belt(x,y,dir,contents)
            local b={name='transport-belt', type='transport-belt',
                position={x=x,y=y}, direction=dir, active=true, unit_number=100+x}
            b.get_transport_line=function(i)
                local items=(contents and contents[i]) or {}
                return {get_contents=function() return items end}
            end
            belts[string.format('%d,%d',x,y)]=b
        end
        surface={
            find_entities_filtered=function(query)
                local out={}
                if query.position then
                    local key=string.format('%d,%d',query.position.x,query.position.y)
                    local b=belts[key]
                    if b then out[#out+1]=b end
                    return out
                end
                if query.area then
                    local lt=query.area[1]; local rb=query.area[2]
                    local x=(lt[1]+rb[1])/2; local y=(lt[2]+rb[2])/2
                    local key=string.format('%d,%d',x,y)
                    local b=belts[key]
                    if b then out[#out+1]=b end
                    local other=blockers[key]
                    if other then out[#out+1]=other end
                    return out
                end
                return out
            end,
        }
        storage.agent_characters[1].surface=surface
    """)
    lua.execute(
        (
            Path(__file__).parents[2] / "fle/env/tools/agent/trace_belt/server.lua"
        ).read_text()
    )
    return lua


def test_trace_follows_turns_and_reports_first_blocker():
    lua = runtime()
    lua.execute("""
        make_belt(29,-80,8,{[1]={},[2]={{name='coal',count=3}}})
        make_belt(29,-79,8,{[1]={name='coal',count=2},[2]={}})
        make_belt(29,-78,4,nil)
        result=storage.actions.trace_belt(1,29,-80,64)
        assert(result.total_tiles==3)
        assert(result.tiles[1].direction=='south' and result.tiles[1].active)
        assert(result.tiles[1].lanes[2].items[1].name=='coal')
        assert(result.tiles[3].direction=='east')
        assert(result.blocker.reason=='end_of_line')
        assert(result.blocker.position.x==30 and result.blocker.position.y==-78)
    """)


def test_trace_reports_blocking_entity_in_next_tile():
    lua = runtime()
    lua.execute("""
        make_belt(0,0,4,nil)
        blockers['1,0']={name='small-electric-pole', type='electric-pole',
            position={x=1,y=0}, unit_number=42}
        result=storage.actions.trace_belt(1,0,0,16)
        assert(result.total_tiles==1)
        assert(result.blocker.reason=='blocked_by_entity')
        assert(result.blocker.entity.name=='small-electric-pole')
        assert(result.blocker.entity.entity_id==42)
    """)


def test_trace_requires_a_belt_and_caps_max_tiles():
    lua = runtime()
    lua.execute("""
        missing=storage.actions.trace_belt(1,5,5,16)
        assert(missing.error ~= nil)
        make_belt(0,0,4,nil)
        make_belt(1,0,4,nil)
        make_belt(2,0,4,nil)
        capped=storage.actions.trace_belt(1,0,0,2)
        assert(capped.total_tiles==2)
        assert(capped.blocker.reason=='max_tiles_reached')
    """)


def test_client_validates_arguments_and_surfaces_errors():
    tool = TraceBelt.__new__(TraceBelt)
    tool.player_index = 1
    tool.execute = Mock(return_value=({"tiles": []}, 0))
    with pytest.raises(ValueError, match="position must be a Position"):
        tool((1, 2))
    with pytest.raises(ValueError, match="max_tiles"):
        tool(Position(x=0, y=0), max_tiles=0)
    tool.execute = Mock(return_value=({"error": "no transport-belt"}, 0))
    with pytest.raises(Exception, match="Could not trace belt"):
        tool(Position(x=0, y=0))
