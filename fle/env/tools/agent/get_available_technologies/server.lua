storage.actions.get_available_technologies = function(player_index, limit, offset)
    local force = storage.agent_characters[player_index].force
    local names = {}
    for name, tech in pairs(force.technologies) do
        local ready = tech.enabled and not tech.researched and not tech.prototype.hidden
        for _, prerequisite in pairs(tech.prerequisites) do
            if not prerequisite.researched then ready = false; break end
        end
        if ready then names[#names+1] = name end
    end
    table.sort(names)
    local entries = {}
    for i=offset+1,math.min(#names, offset+limit) do
        local tech = force.technologies[names[i]]
        entries[#entries+1] = {name=tech.name, level=tech.level,
            can_queue=tech.prototype.research_trigger == nil,
            research_trigger=tech.prototype.research_trigger}
    end
    return {technologies=entries, total=#names, offset=offset,
        truncated=offset+#entries<#names, tick=game.tick}
end
