-- Bounded, read-only context. The engine decides placement/path validity;
-- overlapping collision layers are evidence, not a substitute for that check.
storage.utils.spatial_diagnostics = function(surface, position, box, direction, mask, ignored, prototype)
    local angle = (direction or 0) * math.pi / 8
    local c, s = math.cos(angle), math.sin(angle)
    local left, top, right, bottom = math.huge, math.huge, -math.huge, -math.huge
    for _, x in ipairs({box.left_top.x, box.right_bottom.x}) do
        for _, y in ipairs({box.left_top.y, box.right_bottom.y}) do
            local rx, ry = position.x + x*c-y*s, position.y + x*s+y*c
            left, top = math.min(left, rx), math.min(top, ry)
            right, bottom = math.max(right, rx), math.max(bottom, ry)
        end
    end
    local area = {{left, top}, {right, bottom}}
    local layers = {}
    for name, enabled in pairs((mask and mask.layers) or {}) do
        if enabled then layers[#layers+1] = name end
    end
    local entities, terrain = {}, {}
    local candidates = #layers > 0 and surface.find_entities_filtered{
        area=area, collision_mask=layers, limit=18
    } or {}
    for _, entity in ipairs(candidates) do
        if entity.valid and entity ~= ignored and #entities < 16 then
            local dx, dy = entity.position.x - position.x, entity.position.y - position.y
            entities[#entities+1] = {prototype=entity.name,
                position={x=entity.position.x,y=entity.position.y},
                entity_id=entity.unit_number, type=entity.type,
                distance=math.floor(math.sqrt(dx*dx+dy*dy)*10+0.5)/10}
        end
    end
    table.sort(entities, function(a, b) return a.distance < b.distance end)
    local examined = 0
    local total = math.max(0, math.ceil(right)-math.floor(left)) *
        math.max(0, math.ceil(bottom)-math.floor(top))
    for x=math.floor(left),math.ceil(right)-1 do
        for y=math.floor(top),math.ceil(bottom)-1 do
            if examined >= 64 then break end
            examined = examined + 1
            local tile = surface.get_tile(x,y)
            local collision = false
            for _, layer in ipairs(layers) do
                if tile.collides_with(layer) then collision = true; break end
            end
            if collision and #terrain < 16 then
                terrain[#terrain+1] = {name=tile.name,position={x=x,y=y}}
            end
        end
        if examined >= 64 then break end
    end
    -- Mining drills can only be placed on resources; the engine refusal is
    -- otherwise indistinguishable from generic placement rules.
    local mining_area, mining_resources = nil, nil
    if prototype and prototype.type == "mining-drill" then
        local width = prototype.tile_width or 2
        local height = prototype.tile_height or 2
        mining_area = {
            {position.x - width / 2, position.y - height / 2},
            {position.x + width / 2, position.y + height / 2},
        }
        mining_resources = {}
        for _, resource in ipairs(surface.find_entities_filtered{
            area=mining_area, type="resource", limit=16
        }) do
            mining_resources[resource.name] = (mining_resources[resource.name] or 0) + 1
        end
    end
    local reason
    if #entities > 0 then
        reason = "occupied"
    elseif #terrain > 0 then
        reason = "terrain_collision"
    elseif mining_resources ~= nil and next(mining_resources) == nil then
        reason = "no_minable_resources"
    else
        reason = "engine_rules_or_route_obstruction"
    end
    local result = {position=position, footprint={left_top={x=left,y=top},right_bottom={x=right,y=bottom}},
        overlapping_entities=entities, colliding_tiles=terrain,
        center_tile=surface.get_tile(position).name,
        entities_truncated=#candidates>16, terrain_truncated=total>examined or #terrain>=16,
        reason=reason,
        evidence="local_collision_context", nearest_reachable_verified=false}
    -- Promote the nearest blocker so callers can surface a single actionable
    -- entity name/position instead of burying it in the entity list.
    if #entities > 0 then
        result.blocked_by = entities[1]
    end
    if mining_area ~= nil then
        result.mining_area = mining_area
        result.mining_resources = mining_resources
    end
    return result
end
