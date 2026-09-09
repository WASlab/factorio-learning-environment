-- Helper to convert surface direction to entity direction
local function surface_to_entity_direction(surface_dir)
    -- In Factorio, offshore pumps face opposite to placement direction
    local direction_map = {
        [defines.direction.north] = defines.direction.north,  -- 0 -> 4
        [defines.direction.east] = defines.direction.east,    -- 2 -> 6
        [defines.direction.south] = defines.direction.south,  -- 4 -> 0
        [defines.direction.west] = defines.direction.west     -- 6 -> 2
    }
    return direction_map[surface_dir]
end


-- Helper to check if a tile is water
local function is_water_tile(tile_name)
    return tile_name == "water" or
           tile_name == "deepwater" or
           tile_name == "water-green" or
           tile_name == "deepwater-green" or
           tile_name == "water-shallow" or
           tile_name == "water-mud"
end

local function find_offshore_pump_position(player, center_pos)
    local max_radius = 20
    local search_positions = {
        {dx = 0, dy = 1, dir = defines.direction.north},
        {dx = 1, dy = 0, dir = defines.direction.west},
        {dx = 0, dy = -1, dir = defines.direction.south},
        {dx = -1, dy = 0, dir = defines.direction.east}
    }

    for radius = 1, max_radius do
        for y = -radius, radius do
            for x = -radius, radius do
                if math.abs(x) == radius or math.abs(y) == radius then
                    local check_pos = {
                        x = center_pos.x + x,
                        y = center_pos.y + y
                    }

                    -- Check if position is already occupied
                    -- Factorio 2.0: collision_mask expects a collision layer name string
                    local entities = player.surface.find_entities_filtered{
                        position = check_pos,
                        collision_mask = "player",
                        invert = false
                    }

                    if #entities == 0 then
                        local current_tile = player.surface.get_tile(check_pos.x, check_pos.y)

                        if not is_water_tile(current_tile.name) then
                            for _, search in ipairs(search_positions) do
                                local water_pos = {
                                    x = check_pos.x + search.dx,
                                    y = check_pos.y + search.dy
                                }

                                -- Check for entities at water position
                                -- Factorio 2.0: collision_mask expects a collision layer name string
                                local water_entities = player.surface.find_entities_filtered{
                                    position = water_pos,
                                    collision_mask = "water_tile",
                                    invert = true
                                }

                                if #water_entities == 0 then
                                    local adjacent_tile = player.surface.get_tile(water_pos.x, water_pos.y)

                                    if is_water_tile(adjacent_tile.name) then
                                        local entity_dir = surface_to_entity_direction(search.dir)
                                        local placement = {
                                            name = "offshore-pump",
                                            position = check_pos,
                                            direction = entity_dir,
                                            force = "player"
                                        }

                                        if player.surface.can_place_entity(placement) then
                                            -- Final collision check for the exact pump dimensions
                                            -- Factorio 2.0: collision_mask expects a collision layer name string
                                            local final_check = player.surface.find_entities_filtered{
                                                area = {{check_pos.x - 0.5, check_pos.y - 0.5},
                                                       {check_pos.x + 0.5, check_pos.y + 0.5}},
                                                collision_mask = "player"
                                            }

                                            if #final_check == 0 then
                                                return {
                                                    position = check_pos,
                                                    direction = entity_dir
                                                }
                                            end
                                        end
                                    end
                                end
                            end
                        end
                    end
                end
            end
        end
    end

    return nil
end

storage.actions.place_entity = function(player_index, entity, direction, x, y, exact)
    -- Ensure we have a valid character, recreating if necessary
    local player = storage.utils.ensure_valid_character(player_index)
    local position = {x = x, y = y}

    if not direction then
        direction = 0
    end

    local entity_direction = storage.utils.get_entity_direction(entity, direction)

    -- Common validation functions
    local function validate_distance()
        local max_distance = player.reach_distance or player.build_distance
        local dx = player.position.x - x
        local dy = player.position.y - y or 0
        local distance = math.sqrt(dx * dx + dy * dy)

        if distance > max_distance then
            error("\"The target position is too far away to place the entity. The player position is " ..
                  player.position.x .. ", " .. player.position.y ..
                  " and the target position is " .. x .. ", " .. y ..
                  ". The distance is " .. string.format("%.2f", distance) ..
                  " and the max distance is " .. max_distance .. ". Move closer.\"")
        end
    end

    local function validate_entity()
        if prototypes.entity[entity] == nil then
            local name = entity:gsub(" ", "_"):gsub("-", "_")
            error("\""..name .. " isn't something that exists. Did you make a typo?\"")
        end
    end

    local function validate_inventory()
        local count = player.get_item_count(entity)
        if count == 0 then
            local name = entity:gsub(" ", "_"):gsub("-", "_")
            local inv_contents = storage.utils.format_inventory_for_error(player)
            error("\"No " .. name .. " in inventory. Current inventory: " .. inv_contents .. "\"")
        end
    end

    -- Explicit planner-assisted ablation only; canonical callers require exact.
    local function assisted_place()
        local chosen = position
        if not storage.utils.can_place_entity(player, entity, chosen, entity_direction) then
            chosen = nil
            if entity == "offshore-pump" then
                local found = find_offshore_pump_position(player, position)
                if found then chosen = found.position; entity_direction = found.direction end
            else
                for radius=1,10 do
                    for dx=-radius,radius do
                        for dy=-radius,radius do
                            if math.abs(dx)==radius or math.abs(dy)==radius then
                                local candidate = {x=x+dx,y=y+dy}
                                if storage.utils.can_place_entity(player,entity,candidate,entity_direction) then
                                    chosen = candidate; break
                                end
                            end
                        end
                        if chosen then break end
                    end
                    if chosen then break end
                end
            end
        end
        if not chosen then error("No suitable assisted placement near requested position") end
        local built = player.surface.create_entity{name=entity,position=chosen,
            direction=entity_direction,force=player.force,raise_built=true}
        if not built then error("Assisted placement rejected by engine") end
        player.remove_item{name=entity,count=1}
        return storage.utils.serialize_entity(built)
    end

    -- Main execution flow
    validate_distance()
    validate_entity()
    validate_inventory()
    if exact then
        if not storage.utils.can_place_entity(player, entity, position, entity_direction) then
            local diagnostic = storage.utils.spatial_diagnostics(player.surface, position,
                prototypes.entity[entity].collision_box, entity_direction,
                prototypes.entity[entity].collision_mask)
            return {error=true, reason="placement_rejected", prototype=entity,
                position=position, direction=entity_direction, diagnostics=diagnostic}
        end
        local built = player.surface.create_entity{name=entity, position=position,
            direction=entity_direction, force=player.force, raise_built=true}
        if not built then
            return {error=true,reason="creation_rejected",prototype=entity,position=position}
        end
        player.remove_item{name=entity,count=1}
        return storage.utils.serialize_entity(built)
    end

    -- Placement itself is a single player action. Travel time is paid by the
    -- semantic controller before this call; do not schedule an artificial
    -- one-second delay that can overwrite another on_nth_tick handler.
    return assisted_place()
end
