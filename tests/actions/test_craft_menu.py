from pathlib import Path
from unittest.mock import Mock

from lupa.lua54 import LuaRuntime
import pytest

from fle.env.tools.agent.get_craft_plan.client import GetCraftPlan
from fle.env.tools.agent.queue_craft.client import QueueCraft


pytestmark = pytest.mark.no_factorio
ROOT = Path(__file__).parents[2]


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
        game={tick=0}
        storage={utils={},actions={},agent_characters={}}
        recipes={
            belt={name='belt',enabled=true,category='crafting',
                products={{name='belt',type='item',amount=2}},
                ingredients={{name='gear',type='item',amount=1},{name='plate',type='item',amount=1}}},
            gear={name='gear',enabled=true,category='crafting',
                products={{name='gear',type='item',amount=1}},
                ingredients={{name='plate',type='item',amount=2}}}}
        character={valid=true,force={recipes=recipes},prototype={crafting_categories={crafting=true}},
            get_item_count=function(name) return name=='plate' and 6 or 0 end,
            get_craftable_count=function(recipe) return recipe.name=='belt' and 2 or 3 end}
        storage.agent_characters[1]=character
        storage.utils.ensure_valid_character=function() return character end
        storage.utils.begin_native_crafting=function(_, name, count)
            queued_count=count; return math.min(count,2)
        end
        storage.actions.craft_item=function(_, name, count)
            last_craft={name=name, count=count}
            return count
        end
    """)
    for relative in (
        "fle/env/mods/crafting_menu.lua",
        "fle/env/tools/agent/queue_craft/server.lua",
    ):
        lua.execute((ROOT / relative).read_text(encoding="utf-8"))
    return lua


def test_menu_native_intermediates_batch_rounding_and_depth_bound():
    lua = runtime()
    lua.execute("""
        plan=storage.utils.get_craft_plan(1,'belt',3,2)
        assert(plan.crafts_required==2 and plan.output_quantity==4)
        assert(plan.craftable_now==4 and plan.reason==nil)
        assert(plan.ingredients[1].missing==2)
        assert(plan.missing_subrecipes[1].ingredients[1].need==4)
        assert(game.tick==0 and queued_count==nil and last_craft==nil)
        shallow=storage.utils.get_craft_plan(1,'belt',3,0)
        assert(#shallow.missing_subrecipes==0 and shallow.subrecipes_truncated)
        queued=storage.actions.queue_craft(1,'belt',3)
        assert(last_craft.count==3 and queued.crafted==3 and queued.queued==3)
        assert(queued.partial==false and queued.error==nil)
    """)


def test_queue_craft_completes_within_the_intervention():
    lua = runtime()
    lua.execute("""
        result = storage.actions.queue_craft(1, 'belt', 3)
        assert(last_craft.name == 'belt' and last_craft.count == 3)
        assert(result.crafted == 3 and result.queued == 3)
        assert(result.partial == false and result.error == nil)
    """)


def test_queue_craft_reports_partial_when_ingredients_limit():
    lua = runtime()
    lua.execute("""
        result = storage.actions.queue_craft(1, 'belt', 9)
        assert(last_craft.count == 4)
        assert(result.crafted == 4 and result.partial == true)
        assert(result.error == nil)
    """)


def test_locked_recipe_failure_has_same_menu_and_does_not_craft():
    lua = runtime()
    lua.execute("""
        recipes.belt.enabled=false
        result=storage.actions.queue_craft(1,'belt',3)
        assert(result.error and result.reason=='recipe_not_researched')
        assert(result.craft_plan.ingredients[1].need==2)
        assert(queued_count==nil and last_craft==nil and game.tick==0)
    """)


def test_menu_wire_normalization_and_queue_failure_detail():
    plan = {
        "ingredients": {1: {"item": "plate", "missing": 6}},
        "missing_subrecipes": {},
    }
    read = GetCraftPlan.__new__(GetCraftPlan)
    read.player_index = 1
    read.execute = Mock(return_value=(plan, 0))
    assert read("belt")["ingredients"][0]["missing"] == 6
    queue = QueueCraft.__new__(QueueCraft)
    queue.player_index = 1
    queue.execute = Mock(
        return_value=(
            {"error": True, "reason": "insufficient_ingredients", "craft_plan": plan},
            0,
        )
    )
    with pytest.raises(ValueError, match='"missing":6'):
        queue("belt", 3)
