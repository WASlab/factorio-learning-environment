storage.actions.wait = function(ticks, player_index, technology_name)
    if technology_name then
        local character = storage.utils.ensure_valid_character(player_index)
        local technology = character.force.technologies[technology_name]
        if not technology then error("Unknown technology: " .. technology_name) end
        return technology.researched
    end
    return game.tick
end
