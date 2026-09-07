-- Function to find a rocket silo at the given position
local function find_rocket_silo(surface, position)
    local silo = surface.find_entities_filtered{
        name = "rocket-silo",
        position = position,
        limit = 1,
        radius=0.1
    }
    return silo[1]
end

-- Function to check if the silo has a rocket ready to launch
local function is_rocket_ready(silo)
    if not silo then return false end
    if not silo.valid then return false end

    -- Check if rocket is ready for launch
    return silo.rocket_silo_status == defines.rocket_silo_status.rocket_ready
end

-- Function to launch rocket from specified position
storage.actions.launch_rocket = function(player_index, x, y)
    -- Get the current game surface
    local character = storage.utils.ensure_valid_character(player_index)
    local surface = character.surface
    local position = {x=x, y=y}
    -- Find rocket silo at the given position
    local silo = find_rocket_silo(surface, position)

    if not silo or silo.force ~= character.force then
        error("No player-owned rocket silo at the specified position")
    end

    -- Check if silo has a rocket ready
    if not is_rocket_ready(silo) then
        error("Rocket is not ready for launch")
    end

    -- Launch the rocket
    return silo.launch_rocket()
end
