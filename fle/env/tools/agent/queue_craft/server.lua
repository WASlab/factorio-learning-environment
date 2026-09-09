storage.actions.queue_craft = function(player_index, recipe_name, count)
    local player = storage.utils.ensure_valid_character(player_index)
    local plan = storage.utils.get_craft_plan(player_index, recipe_name, count, 2)
    if (plan.reason and plan.reason ~= "insufficient_ingredients") or plan.craftable_now == 0 then
        return {error=true,reason=plan.reason,craft_plan=plan,queued=0,tick=game.tick}
    end
    local queued = storage.utils.begin_native_crafting(player_index, recipe_name, plan.crafts_required)
    if queued == 0 then
        return {error=true,reason="native_crafting_rejected",craft_plan=plan,queued=0,tick=game.tick}
    end
    storage.semantic_craft_sequence = (storage.semantic_craft_sequence or 0) + 1
    return {handle="\"craft-" .. storage.semantic_craft_sequence .. "\"", recipe="\"" .. recipe_name .. "\"",
        requested=count, queued=queued*plan.items_per_craft, queued_crafts=queued,
        partial=queued*plan.items_per_craft<count, tick=game.tick}
end
