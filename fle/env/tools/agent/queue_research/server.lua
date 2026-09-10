storage.actions.queue_research = function(player_index, technology_names)
    local player = storage.agent_characters[player_index]
    local force = player.force
    local queued = {}
    local skipped = {}

    for _, technology_name in ipairs(technology_names) do
        local technology = force.technologies[technology_name]
        if not technology then
            error(string.format("\"Technology %s does not exist\"", technology_name))
        elseif technology.researched then
            table.insert(skipped, "\"" .. technology_name .. "\"")
        elseif not technology.enabled then
            error(string.format("\"Technology %s is not enabled\"", technology_name))
        elseif force.add_research(technology_name) then
            table.insert(queued, "\"" .. technology_name .. "\"")
        else
            error(string.format("\"Failed to queue research for %s\"", technology_name))
        end
    end

    return {
        queued = queued,
        skipped = skipped,
        tick = game.tick,
    }
end
