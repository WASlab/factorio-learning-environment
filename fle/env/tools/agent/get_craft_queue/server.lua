storage.actions.get_craft_queue = function(player_index)
    local player = storage.utils.ensure_valid_character(player_index)
    local entries = {}
    for index, item in pairs(player.crafting_queue or {}) do
        local recipe_name = type(item.recipe) == "string" and item.recipe
            or (item.recipe and item.recipe.name or "unknown")
        table.insert(entries, {index=index, recipe="\"" .. recipe_name .. "\"", count=item.count})
    end
    return {active=#entries > 0, queue=entries, tick=game.tick}
end
