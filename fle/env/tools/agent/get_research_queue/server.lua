storage.actions.get_research_queue = function(player_index)
    local force = storage.agent_characters[player_index].force
    local queue = {}
    for i, tech in ipairs(force.research_queue or {}) do
        queue[#queue+1] = {index=i, name=tech.name, level=tech.level}
    end
    return {queue=queue,
        current=force.current_research and force.current_research.name,
        progress=force.current_research and force.research_progress or 0, tick=game.tick}
end
