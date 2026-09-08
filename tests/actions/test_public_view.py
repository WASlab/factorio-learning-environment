from pathlib import Path
from unittest.mock import Mock

from lupa.lua54 import LuaRuntime
import pytest

from fle.env.tools.admin.public_view.client import PublicView


pytestmark = pytest.mark.no_factorio


def test_map_bounds_unknown_coverage_and_no_detailed_serialization():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
        storage={actions={},agent_characters={}}
        game={tick=120}
        surface={index=1,
            is_chunk_generated=function(p) return p[1]>=0 end,
            count_tiles_filtered=function(f) assert(f.area); return 0 end,
            count_entities_filtered=function(f) assert(f.area); return 0 end,
            find_entities_filtered=function(f) assert(f.limit==9); return {} end}
        storage.agent_characters[1]={valid=true,surface=surface,force={},position={x=0,y=0}}
    """)
    lua.execute(
        (
            Path(__file__).parents[2] / "fle/env/tools/admin/public_view/server.lua"
        ).read_text(encoding="utf-8")
    )
    lua.execute("""
        result=storage.actions.public_view(1,192,8)
        assert(#result.cells<=256 and #result.entities==0)
        assert(result.detail=='map' and result.tick==120 and game.tick==120)
        assert(result.cells[1].unknown and result.cells[1].water==nil)
        assert(result.cells[#result.cells].walkable)
        assert(result.cell_size==32)
    """)


def test_public_view_client_normalizes_wire_arrays_and_rejects_unbounded_reads():
    tool = PublicView.__new__(PublicView)
    tool.player_index = 1
    tool.execute = Mock(return_value=({"cells": {1: {"water": 2}}, "entities": {}}, 0))
    assert tool()["cells"] == [{"water": 2}]
    assert tool()["entities"] == []
    with pytest.raises(ValueError, match="radius"):
        tool(1024)
    with pytest.raises(ValueError, match="entity_limit"):
        tool(32, 1024)
