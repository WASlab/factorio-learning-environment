storage.actions.get_technology = function(player_index, name)
    local force = storage.agent_characters[player_index].force
    local tech = force.technologies[name]
    if not tech or tech.prototype.hidden then error("Unknown or hidden technology: " .. name) end
    local prerequisites, successors, science, unlocks = {}, {}, {}, {}
    local ready = tech.enabled and not tech.researched
    for id, prerequisite in pairs(tech.prerequisites) do
        prerequisites[#prerequisites+1] = id
        if not prerequisite.researched then ready = false end
    end
    for id, successor in pairs(tech.successors) do
        if not successor.prototype.hidden then successors[#successors+1] = id end
    end
    table.sort(prerequisites)
    table.sort(successors)
    local trigger = tech.prototype.research_trigger
    local count = trigger and 0 or tech.research_unit_count
    for _, ingredient in pairs(tech.research_unit_ingredients) do
        science[#science+1] = {name=ingredient.name, type=ingredient.type,
            per_unit=ingredient.amount, total=ingredient.amount * count}
    end
    for _, effect in pairs(tech.prototype.effects) do
        if effect.type == "unlock-recipe" then unlocks[#unlocks+1] = effect.recipe end
    end
    table.sort(unlocks)
    local current = force.current_research and force.current_research.name == name or false
    return {name=name, researched=tech.researched, enabled=tech.enabled,
        researchable=ready, can_queue=ready and not trigger, level=tech.level,
        prerequisites=prerequisites, successors=successors, science_cost=science,
        unit_count=count, unit_time_seconds=tech.research_unit_energy / 60,
        research_trigger=trigger, effects=tech.prototype.effects, unlocks=unlocks,
        current=current, progress=tech.researched and 1 or
            (current and force.research_progress or tech.saved_progress), tick=game.tick}
end
