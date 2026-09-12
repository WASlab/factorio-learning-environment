-- Follow a transport belt downstream and report lane contents plus the first
-- blocker. Bounded and read-only: never mutates the belt or the character.
storage.actions.trace_belt = function(player_index, x, y, max_tiles)
    max_tiles = math.min(math.max(tonumber(max_tiles) or 64, 1), 256)
    local character = storage.agent_characters[player_index]
    local surface = character.surface
    local position = {x = tonumber(x), y = tonumber(y)}
    local dirs = {[0] = "north", [4] = "east", [8] = "south", [12] = "west"}
    local vectors = {[0] = {0, -1}, [4] = {1, 0}, [8] = {0, 1}, [12] = {-1, 0}}

    local found = surface.find_entities_filtered{
        position = position, radius = 0.71, name = "transport-belt", limit = 1
    }
    local belt = found and found[1]
    if not belt then
        return {error = "no transport-belt at the requested position"}
    end

    local function lanes(entity)
        local result = {}
        for index = 1, 2 do
            local ok, line = pcall(function() return entity.get_transport_line(index) end)
            if ok and line then
                local items = {}
                for _, item in ipairs(line.get_contents() or {}) do
                    items[#items + 1] = {name = item.name, count = item.count}
                end
                result[#result + 1] = {index = index, items = items}
            end
        end
        return result
    end

    local tiles = {}
    local blocker = nil
    local current = belt
    for _ = 1, max_tiles do
        tiles[#tiles + 1] = {
            position = {x = current.position.x, y = current.position.y},
            direction = dirs[current.direction] or tostring(current.direction),
            active = current.active,
            lanes = lanes(current),
        }
        local vector = vectors[current.direction] or {0, 0}
        local next_position = {
            x = current.position.x + vector[1],
            y = current.position.y + vector[2],
        }
        local next_entities = surface.find_entities_filtered{
            area = {
                {next_position.x - 0.5, next_position.y - 0.5},
                {next_position.x + 0.5, next_position.y + 0.5},
            },
            limit = 8,
        }
        local next_belt = nil
        local other = nil
        for _, entity in ipairs(next_entities) do
            if entity.name == "transport-belt" then
                if not next_belt then next_belt = entity end
            elseif entity.name ~= "item-on-ground" and entity.type ~= "resource" then
                if not other then other = entity end
            end
        end
        if not next_belt then
            blocker = {
                position = next_position,
                reason = other and "blocked_by_entity" or "end_of_line",
            }
            if other then
                blocker.entity = {
                    name = other.name,
                    type = other.type,
                    entity_id = other.unit_number,
                    position = {x = other.position.x, y = other.position.y},
                }
            end
            break
        end
        current = next_belt
    end
    if blocker == nil then
        blocker = {
            position = {x = current.position.x, y = current.position.y},
            reason = "max_tiles_reached",
        }
    end
    return {
        start = {x = belt.position.x, y = belt.position.y},
        tiles = tiles,
        total_tiles = #tiles,
        blocker = blocker,
    }
end
