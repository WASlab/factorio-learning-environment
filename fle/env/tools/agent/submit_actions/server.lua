storage.actions.submit_actions = function(player_index, operation, checks)
    if operation ~= "preflight" then error("\"Unsupported queue operation\"") end
    local force = storage.agent_characters[player_index].force
    local errors = {}
    for _, check in ipairs(checks or {}) do
        if check.kind == "recipe" then
            local recipe = force.recipes[check.name]
            if not recipe or not recipe.enabled then
                table.insert(errors, {index=check.index, kind="locked_recipe", name="\""..check.name.."\""})
            end
        elseif check.kind == "technology" then
            local technology = force.technologies[check.name]
            local available = technology and technology.enabled and not technology.researched
            if available then
                for _, prerequisite in pairs(technology.prerequisites or {}) do
                    if not prerequisite.researched then available = false break end
                end
            end
            if not available then
                table.insert(errors, {index=check.index, kind="unavailable_technology", name="\""..check.name.."\""})
            end
        end
    end
    return {errors=errors, tick=game.tick}
end
