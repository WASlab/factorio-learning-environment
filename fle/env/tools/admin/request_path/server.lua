storage.actions.request_path = function(player_index, start_x, start_y, goal_x, goal_y, radius, allow_paths_through_own_entities, entity_size, resolution)
    -- Ensure we have a valid character, recreating if necessary
    local player = storage.utils.ensure_valid_character(player_index)
    if not player then return nil end
    local size = entity_size and (entity_size/2 - 0.01) or nil
    local box = player.prototype.collision_box
    local bounding_box = size and {{-size, -size}, {size, size}} or {
        {box.left_top.x - 0.05, box.left_top.y - 0.05},
        {box.right_bottom.x + 0.05, box.right_bottom.y + 0.05}
    }

    local surface = player.surface
    local force = player.force

    -- Ensure chunks are generated along the path corridor from start to goal.
    -- The pathfinder cannot traverse ungenerated chunks, and needs a wide corridor
    -- to route around water, cliffs, and other obstacles.
    local corridor_radius = 5  -- ~160 tile wide corridor for pathfinding flexibility
    local goal_radius = 8  -- Extra corridor coverage around the goal
    surface.request_to_generate_chunks({x = start_x, y = start_y}, corridor_radius)
    surface.request_to_generate_chunks({x = goal_x, y = goal_y}, goal_radius)

    local dx = goal_x - start_x
    local dy = goal_y - start_y
    local distance = math.sqrt(dx * dx + dy * dy)
    if distance > 32 then
        local num_points = math.ceil(distance / 32)
        for i = 1, num_points - 1 do
            local t = i / num_points
            surface.request_to_generate_chunks({x = start_x + dx * t, y = start_y + dy * t}, corridor_radius)
        end
    end
    surface.force_generate_chunk_requests()

    local goal_position = {x = goal_x, y = goal_y}

    local start_position = {y = start_y, x = start_x}

    local path_request = {
        bounding_box = bounding_box,
        -- Factorio 2.0: collision_mask requires {layers = {layer_name = true, ...}} format
        -- Valid layers: is_lower_object, is_object, out_of_map, ground_tile, water_tile, resource,
        -- doodad, floor, rail, transport_belt, item, ghost, object, player, car, train, elevated_rail,
        -- elevated_train, empty_space, lava_tile, meltable, rail_support, trigger_target, cliff
        collision_mask = {
            layers = {
                player = true,
                train = true,
                water_tile = true,
                object = true
            }
        },
        start = start_position,
        goal = goal_position,
        force = force,
        radius = radius or 0,
        entity_to_ignore = player,
        can_open_gates = true,
        path_resolution_modifier = resolution,
        pathfind_flags = {
            cache = false,
            no_break = true,
            prefer_straight_paths = true,
            allow_paths_through_own_entities = allow_paths_through_own_entities
        }
    }
    local request_id = surface.request_path(path_request)


    if not storage.path_requests then
        storage.path_requests = {}
    end
    if not storage.paths then
        storage.paths = {}
    end

    storage.path_requests[request_id] = {player_index=player_index,
        start=start_position, goal=goal_position, radius=radius or 0,
        bounding_box=bounding_box, collision_mask=path_request.collision_mask,
        surface_index=surface.index}

    return request_id
end

script.on_event(defines.events.on_script_path_request_finished, function(event)
    local request_data = storage.path_requests[event.id]
    if not request_data then
        game.print("No request data found for ID: " .. event.id)
        return
    end

    -- local player = storage.agent_characters[request_data]
    -- if not player then
        -- game.print("No player found for request ID: " .. event.id)
        -- return
    -- end

    if event.path then
        storage.paths[event.id] = event.path
    elseif event.try_again_later then
        storage.paths[event.id] = "busy"
        -- game.print("Pathfinder busy for request ID: " .. event.id)
    else
        storage.paths[event.id] = "not_found"
        -- game.print("Path not found for request ID: " .. event.id)
    end
end)
