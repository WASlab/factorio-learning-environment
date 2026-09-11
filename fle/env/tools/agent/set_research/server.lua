storage.actions.set_research = function(player_index, technology_name)
    local player = storage.agent_characters[player_index]
    local force = player.force

    local tech = force.technologies[technology_name]
    if not tech then
        error(string.format("\"Technology %s does not exist\"", technology_name))
    end

    if tech.researched then
        error(string.format("\"Technology %s is already researched\"", technology_name))
    end

    if not tech.enabled then
        error(string.format("\"Technology %s is not enabled\"", technology_name))
    end

    local trigger = tech.prototype.research_trigger
    if trigger then
        local what = trigger.entity or trigger.item or trigger.fluid or trigger.type
        error(string.format(
            "\"Technology %s is trigger-gated (%s: %s); complete the trigger in-game to unlock it\"",
            technology_name, trigger.type, what))
    end

    -- Cancel current research if any
    force.cancel_current_research()

    -- Set new research using add_research
    local success = force.add_research(technology_name)
    if not success then
        error(string.format("\"Failed to start research for %s\"", technology_name))
    end

    -- Collect and return the research ingredients
    local ingredients = {}
    local units_required = tech.research_unit_count

    for _, ingredient in pairs(tech.research_unit_ingredients) do
        table.insert(ingredients, {
            name = "\""..ingredient.name.."\"",
            count = ingredient.amount * units_required,
            type = ingredient.type
        })
    end

    return ingredients
end