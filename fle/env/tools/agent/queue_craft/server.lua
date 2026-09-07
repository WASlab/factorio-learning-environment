storage.actions.queue_craft = function(player_index, recipe_name, count)
    local player = storage.utils.ensure_valid_character(player_index)
    local recipe = player.force.recipes[recipe_name]
    if not recipe then error("Unknown recipe " .. tostring(recipe_name)) end
    if not recipe.enabled then error("Recipe is not researched: " .. recipe_name) end
    local queued = storage.utils.begin_native_crafting(player_index, recipe_name, count)
    if queued == 0 then error("Unable to queue craft; inspect the recipe and inventory") end
    storage.semantic_craft_sequence = (storage.semantic_craft_sequence or 0) + 1
    return {handle="\"craft-" .. storage.semantic_craft_sequence .. "\"", recipe="\"" .. recipe_name .. "\"",
        requested=count, queued=queued, tick=game.tick}
end
