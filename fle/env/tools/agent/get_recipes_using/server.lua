storage.actions.get_recipes_using = function(player_index, name, category, limit, offset)
    if not prototypes[category][name] then error("Unknown " .. category .. ": " .. name) end
    local force = storage.agent_characters[player_index].force
    local names = {}
    for id, recipe in pairs(force.recipes) do
        if not recipe.hidden then
            for _, ingredient in pairs(recipe.ingredients) do
                if ingredient.name == name and ingredient.type == category then
                    names[#names+1] = id; break
                end
            end
        end
    end
    table.sort(names)
    local entries = {}
    for i=offset+1,math.min(#names, offset+limit) do
        local recipe = force.recipes[names[i]]
        entries[#entries+1] = {name=recipe.name, enabled=recipe.enabled,
            category=recipe.category, ingredients=recipe.ingredients, products=recipe.products,
            energy_seconds=recipe.energy}
    end
    return {recipes=entries, total=#names, offset=offset, truncated=offset+#entries<#names, tick=game.tick}
end
