-- Public map context. Counts stay in the engine; only bounded cells and tooltips
-- cross RCON. This read neither generates chunks nor advances simulation time.
storage.actions.public_view = function(player_index, radius, entity_limit)
    local character = storage.agent_characters[player_index]
    if not character or not character.valid then
        return {available=false, reason="character_unavailable"}
    end
    radius = math.max(8, math.min(192, math.floor(radius or 32)))
    entity_limit = math.max(1, math.min(128, math.floor(entity_limit or 32)))
    local surface, force = character.surface, character.force
    local cell_size = math.max(4, 2 ^ math.ceil(math.log(radius / 8) / math.log(2)))
    local min_x = math.floor((character.position.x - radius) / cell_size) * cell_size
    local min_y = math.floor((character.position.y - radius) / cell_size) * cell_size
    local width = math.ceil(2 * radius / cell_size)
    local cells = {}
    local resources = {"iron-ore", "copper-ore", "coal", "stone", "uranium-ore", "crude-oil"}
    for row=0,width-1 do
        for column=0,width-1 do
            local x, y = min_x + column * cell_size, min_y + row * cell_size
            local area = {{x,y},{x+cell_size,y+cell_size}}
            local cell = {column=column, row=row}
            -- Detached agent characters do not update player chart state.
            -- Match the existing spatial tools' generated-surface visibility.
            if not surface.is_chunk_generated({math.floor(x/32),math.floor(y/32)}) then
                cell.unknown = true
            else
                cell.water = surface.count_tiles_filtered{area=area,
                    name={"water", "deepwater", "water-green", "deepwater-green"}}
                cell.blocked_tiles = surface.count_tiles_filtered{area=area, collision_mask="player"}
                cell.trees = surface.count_entities_filtered{area=area,type="tree"}
                cell.cliffs = surface.count_entities_filtered{area=area,type="cliff"}
                cell.occupied = surface.count_entities_filtered{area=area,force=force}
                -- Occupancy specifically means character-colliding entities,
                -- independent of ownership; resource deposits are walkable.
                cell.obstacles = surface.count_entities_filtered{area=area,collision_mask="player"}
                cell.resources = {}
                for _, name in ipairs(resources) do
                    local count = surface.count_entities_filtered{area=area,name=name}
                    if count > 0 then cell.resources[name] = count end
                end
                cell.walkable = cell.blocked_tiles == 0 and cell.obstacles == 0
            end
            cells[#cells+1] = cell
        end
    end
    local area = {{min_x,min_y},{min_x+width*cell_size,min_y+width*cell_size}}
    local candidates = surface.find_entities_filtered{area=area,force=force,limit=entity_limit+1}
    local entities = {}
    for index, entity in ipairs(candidates) do
        if index > entity_limit then break end
        local data = {name=entity.name,position={x=entity.position.x,y=entity.position.y},
            entity_id=tostring(surface.index)..":"..tostring(entity.unit_number or entity.name),
            direction=entity.direction}
        if radius < 96 then
            data.status = storage.utils.entity_status_names(entity.status)
            data.warnings = storage.utils.get_issues(entity)
            data.energy = entity.energy
            -- Do not serialize topology or recipe graphs for hover state.
            local inventory_keys = {}
            if entity.burner then inventory_keys[#inventory_keys+1] = "fuel" end
            if entity.type == "furnace" then
                inventory_keys[#inventory_keys+1] = "furnace_source"
                inventory_keys[#inventory_keys+1] = "furnace_result"
            elseif entity.type == "assembling-machine" then
                inventory_keys[#inventory_keys+1] = "assembling_machine_input"
                inventory_keys[#inventory_keys+1] = "assembling_machine_output"
            elseif entity.type == "lab" then
                inventory_keys[#inventory_keys+1] = "lab_input"
            elseif entity.type == "container" or entity.type == "logistic-container" then
                inventory_keys[#inventory_keys+1] = "chest"
            end
            for _, key in ipairs(inventory_keys) do
                local inventory = entity.get_inventory(defines.inventory[key])
                if inventory then
                    local contents = {}
                    for slot=1,math.min(#inventory,128) do
                        local stack = inventory[slot]
                        if stack.valid_for_read then
                            contents[stack.name] = (contents[stack.name] or 0) + stack.count
                        end
                    end
                    data[key] = contents
                    if #inventory > 128 then data.contents_truncated = true end
                end
            end
            if entity.type == "assembling-machine" or entity.type == "furnace" then
                local recipe = entity.get_recipe()
                data.recipe = recipe and recipe.name or nil
            end
            if entity.type == "inserter" and entity.held_stack.valid_for_read then
                data.held_stack = {name=entity.held_stack.name,count=entity.held_stack.count}
            end
        end
        entities[#entities+1] = data
    end
    return {available=true,schema_version="public-view-v1",tick=game.tick,
        center={x=character.position.x,y=character.position.y},radius=radius,
        origin={x=min_x,y=min_y},cell_size=cell_size,width=width,height=width,
        cells=cells,entities=entities,entities_truncated=#candidates>entity_limit,
        detail=radius<96 and "nearby" or "map",
        coverage="generated_chunks_in_view",
        walkability="whole_cell_collision_summary_not_path_reachability"}
end
