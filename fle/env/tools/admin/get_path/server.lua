-- Return path data through the shared action serializer.
storage.actions.get_path = function(request_id)
    local request_data = storage.path_requests[request_id]
    if not request_data then
        return {status = "invalid_request"}
    end

    -- Check if path has been computed yet
    local path = storage.paths[request_id]
    if not path then
        -- Request exists but path not yet computed - still pending
        return {status = "pending"}
    end

    if path == "busy" then
        return {status = "busy"}
    elseif path == "not_found" then
        local surface = game.surfaces[request_data.surface_index]
        local box = request_data.bounding_box
        box = {left_top={x=box[1][1],y=box[1][2]},right_bottom={x=box[2][1],y=box[2][2]}}
        local player = storage.agent_characters[request_data.player_index]
        return {status="not_found", start=request_data.start, goal=request_data.goal,
            radius=request_data.radius, diagnostics={
                start=storage.utils.spatial_diagnostics(surface,request_data.start,box,0,request_data.collision_mask,player),
                goal=storage.utils.spatial_diagnostics(surface,request_data.goal,box,0,request_data.collision_mask,player)}}
    else
        local waypoints = {}
        for _, waypoint in ipairs(path) do
            table.insert(waypoints, {
                x = waypoint.position.x,
                y = waypoint.position.y
            })
        end
        return {
            status = "success",
            waypoints = waypoints
        }
    end
end
