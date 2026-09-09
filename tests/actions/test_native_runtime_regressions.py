from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from lupa.lua54 import LuaRuntime
import pytest

from fle.env import Position
from fle.env.game_types import Prototype
from fle.env.tools.agent.get_prototype_recipe.client import GetPrototypeRecipe
from fle.env.tools.agent.launch_rocket.client import LaunchRocket
from fle.env.tools.controller import Controller
from fle.env.utils.rcon import _lua2python


pytestmark = pytest.mark.no_factorio
ENV = Path(__file__).parents[2] / "fle/env"


def lua_runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
        storage={utils={},actions={},agent_characters={}}
        game={tick=0}
        defines={events={on_tick=1}}
        script={on_nth_tick=function() end, on_event=function() end}
    """)
    lua.execute((ENV / "mods/utils.lua").read_text())
    return lua


def test_transport_quotes_raw_strings_without_losing_error_fields():
    lua = lua_runtime()
    raw = lua.eval("""dump({a=true,b={error="product_depot_capacity_reached",
        product="copper-plate",bound_count=1,detail='requires: "automation"'}})""")
    result, _ = _lua2python("test", raw)
    assert result["b"] == {
        "error": "product_depot_capacity_reached",
        "product": "copper-plate",
        "bound_count": 1,
        "detail": 'requires: "automation"',
    }
    raw = lua.eval("""dump({a=true,b={name='"iron-plate"'}})""")
    result, _ = _lua2python("test", raw)
    assert result["b"]["name"] == "iron-plate"


def test_transport_failure_is_not_returned_as_an_empty_success():
    controller = Controller.__new__(Controller)
    controller.name = "wait"
    controller._execute_once = Mock(side_effect=OSError("connection closed"))
    with pytest.raises(
        RuntimeError, match="RCON action wait failed: connection closed"
    ):
        controller.execute(0)


def test_recipe_preserves_live_enablement_category_and_duration():
    tool = GetPrototypeRecipe.__new__(GetPrototypeRecipe)
    tool.player_index = 1
    tool.execute = Mock(
        return_value=(
            {
                "ingredients": [{"name": "iron-plate", "amount": 2, "type": "item"}],
                "products": [
                    {"name": "iron-gear-wheel", "amount": 1, "probability": 1}
                ],
                "energy": 0.5,
                "category": "crafting",
                "enabled": True,
            },
            0,
        )
    )
    recipe = tool(Prototype.IronGearWheel)
    assert recipe.enabled is True
    assert recipe.category == "crafting"
    assert recipe.energy == 0.5


def crafting_runtime():
    lua = lua_runtime()
    lua.execute("""
        flows={}
        force={recipes={lab={ingredients={{name='iron-plate',type='item',amount=10}},
            products={{name='lab',type='item',amount=1}}}}}
        force.get_item_production_statistics=function() return {
            on_flow=function(name, amount) flows[name]=(flows[name] or 0)+amount end
        } end
        character={valid=true, force=force, surface={}, crafting_queue={}}
        character.begin_crafting=function(args)
            character.crafting_queue={{recipe=args.recipe,count=args.count}}
            return args.count
        end
        character.cancel_crafting=function(args)
            character.crafting_queue[args.index].count=
                character.crafting_queue[args.index].count-args.count
            if character.crafting_queue[args.index].count==0 then
                table.remove(character.crafting_queue,args.index)
            end
        end
        storage.agent_characters[1]=character
        storage.utils.ensure_valid_character=function() return character end
    """)
    return lua


def test_native_crafting_accounts_only_completed_items_and_excludes_cancellation():
    lua = crafting_runtime()
    lua.execute("storage.utils.begin_native_crafting(1,'lab',3)")
    assert lua.eval("flows.lab") is None
    lua.execute("""
        game.tick=30; character.crafting_queue[1].count=2
        storage.utils.sync_native_crafting(1)
    """)
    assert lua.eval("flows.lab") == 1
    assert lua.eval("flows['iron-plate']") == -10
    assert lua.eval("storage.manual_production_events[1].tick") == 30
    lua.execute((ENV / "tools/agent/cancel_craft/server.lua").read_text())
    lua.execute(
        "storage.actions.cancel_craft(1,1,2); storage.utils.sync_native_crafting(1)"
    )
    assert lua.eval("flows.lab") == 1
    assert lua.eval("storage.native_crafting[1]") is None


def test_player_attached_crafting_does_not_duplicate_engine_flows():
    lua = crafting_runtime()
    lua.execute("""
        character.player={}
        storage.utils.begin_native_crafting(1,'lab',1)
        character.crafting_queue={}
        storage.utils.sync_native_crafting(1)
    """)
    assert lua.eval("flows.lab") is None
    assert lua.eval("storage.manual_production_events[1].outputs.lab") == 1


def test_resource_identity_uses_nearest_center_not_engine_query_order():
    lua = lua_runtime()
    lua.execute("""
        copper={name='copper-ore',position={x=2,y=0}}
        iron={name='iron-ore',position={x=0,y=0}}
        local surface={find_entities_filtered=function() return {copper,iron} end}
        storage.agent_characters[1]={surface=surface,resource_reach_distance=2.7}
    """)
    lua.execute((ENV / "tools/agent/harvest_resource/server.lua").read_text())
    assert (
        lua.eval("storage.actions.get_resource_name_at_position(1,0,0)") == "iron-ore"
    )


def test_rejected_launch_does_not_increment_or_report_a_launch():
    tool = LaunchRocket.__new__(LaunchRocket)
    tool.player_index = 1
    tool.execute = Mock(return_value=(False, 0))
    tool.get_entity = Mock()
    tool.game_state = SimpleNamespace(
        instance=SimpleNamespace(_verified_rocket_launches=0)
    )
    with pytest.raises(Exception, match="did not accept the launch request"):
        tool(Position(10, 20))
    assert tool.game_state.instance._verified_rocket_launches == 0
    tool.get_entity.assert_not_called()
    tool.execute.assert_called_once_with(1, 10, 20)


def test_wait_cancellation_cleans_engine_job_and_preserves_error():
    from fle.env.tools.agent.wait.client import Wait

    tool = Wait.__new__(Wait)
    tool.player_index = 1
    tool.game_state = SimpleNamespace(
        _cancel_requested=True, instance=SimpleNamespace(get_speed=lambda: 10)
    )
    tool.execute = Mock(
        side_effect=[
            ({"start_tick": 0, "deadline_tick": 10}, 0),
            RuntimeError("connection closed"),
        ]
    )
    with pytest.raises(TimeoutError, match="cancelled"):
        tool(10)
    tool.execute.assert_called_with("cancel", 1)


def test_invalid_wait_start_preserves_transport_response():
    from fle.env.tools.agent.wait.client import Wait

    tool = Wait.__new__(Wait)
    tool.player_index = 1
    tool.game_state = SimpleNamespace(instance=SimpleNamespace(get_speed=lambda: 10))
    tool.execute = Mock(return_value=({}, 0))
    with pytest.raises(RuntimeError, match="Could not start wait"):
        tool(10)


def test_score_scripts_do_not_replace_shared_serializer():
    # Tools share globals in both the bundled and legacy runtimes.
    for kind in ("admin", "agent"):
        source = (ENV / f"tools/{kind}/score/server.lua").read_text()
        assert "function dump(" not in source
        assert "return dump(" not in source


def test_path_approach_radius_stays_centered_on_requested_entity():
    lua = lua_runtime()
    lua.execute("""
        rendering={draw_circle=function() end}
        local surface={
            request_to_generate_chunks=function() end,
            force_generate_chunk_requests=function() end,
            find_non_colliding_position=function() return {x=12,y=20} end,
            request_path=function(args) captured=args; return 1 end,
        }
        local character={surface=surface,force={},name='character',
            resource_reach_distance=2.5,
            prototype={collision_box={left_top={x=-0.2,y=-0.2},right_bottom={x=0.2,y=0.2}}}}
        storage.utils.ensure_valid_character=function() return character end
    """)
    lua.execute((ENV / "tools/admin/request_path/server.lua").read_text())
    lua.execute("storage.actions.request_path(1,0,0,10,20,5.5,false,nil,0)")
    assert lua.eval("captured.goal.x") == 10
    assert lua.eval("captured.goal.y") == 20
    assert lua.eval("captured.radius") == 5.5
    assert lua.eval("captured.bounding_box[1][1]") == -0.25
    lua.execute("storage.actions.request_path(1,0,0,10,20,0.15,false,nil,0)")
    assert lua.eval("captured.goal.x") == 10
