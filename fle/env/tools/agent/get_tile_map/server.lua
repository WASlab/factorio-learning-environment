-- Compact structured tile/entity map around a point. Bounded and read-only.
-- Glyphs: ^ > v < belts by flow direction; i/I inserters (i = burner) with
-- drop-side glyph; A assembler, F furnace, D drill, L lab, G generator,
-- B boiler, p pump, P pole, C chest, | pipe, ~ water, # blocked terrain,
-- * ore tile without an entity, . clear ground.
storage.actions.get_tile_map = function(player_index, x, y, radius)
    radius = math.min(math.max(tonumber(radius) or 16, 1), 32)
    local character = storage.agent_characters[player_index]
    local surface = character.surface
    local cx, cy = math.floor(tonumber(x)), math.floor(tonumber(y))
    local belt_glyph = {[0] = "^", [4] = ">", [8] = "v", [12] = "<"}
    -- Inserters are drawn by where they drop, so the map shows material flow.
    local inserter_glyph = {[0] = "v", [4] = "<", [8] = "^", [12] = ">"}
    local fixed = {
        ["assembling-machine-1"] = "A",
        ["assembling-machine-2"] = "A",
        ["assembling-machine-3"] = "A",
        ["stone-furnace"] = "F",
        ["steel-furnace"] = "F",
        ["electric-furnace"] = "F",
        ["lab"] = "L",
        ["steam-engine"] = "G",
        ["boiler"] = "B",
        ["offshore-pump"] = "p",
        ["wooden-chest"] = "C",
        ["iron-chest"] = "C",
        ["steel-chest"] = "C",
        ["pipe"] = "|",
        ["pipe-to-ground"] = "|",
    }
    local rows = {}
    local entities = {}
    local entities_truncated = false
    for tile_y = cy - radius, cy + radius do
        local row = {}
        for tile_x = cx - radius, cx + radius do
            local glyph = nil
            local found = surface.find_entities_filtered{
                area = {{tile_x, tile_y}, {tile_x + 1, tile_y + 1}}, limit = 4
            }
            for _, entity in ipairs(found) do
                if entity.type ~= "resource" and entity.type ~= "item-on-ground" then
                    if entity.name == "transport-belt" then
                        glyph = belt_glyph[entity.direction] or ">"
                    elseif entity.type == "inserter" then
                        glyph = entity.name == "inserter" and "I" or "i"
                    elseif entity.type == "electric-pole" then
                        glyph = "P"
                    elseif entity.type == "mining-drill" then
                        glyph = "D"
                    else
                        glyph = fixed[entity.name]
                    end
                    if glyph ~= nil then
                        if #entities < 128 then
                            entities[#entities + 1] = {
                                name = entity.name,
                                type = entity.type,
                                entity_id = entity.unit_number,
                                position = {x = entity.position.x, y = entity.position.y},
                                direction = entity.direction,
                                status = entity.status,
                            }
                        else
                            entities_truncated = true
                        end
                        break
                    end
                end
            end
            if glyph == nil and #found > 0 and found[1].type == "resource" then
                glyph = "*"
            end
            if glyph == nil then
                local tile = surface.get_tile(tile_x, tile_y)
                if tile.name == "water" or tile.name:find("^water") then
                    glyph = "~"
                elseif tile.collides_with("player") then
                    glyph = "#"
                else
                    glyph = "."
                end
            end
            row[#row + 1] = glyph
        end
        rows[#rows + 1] = table.concat(row)
    end
    return {
        center = {x = cx, y = cy},
        radius = radius,
        rows = rows,
        entities = entities,
        entities_truncated = entities_truncated,
        legend = "^>v< belts; i/I inserters (drop side); A assembler; F furnace; "
            .. "D drill; L lab; B boiler; G engine; p pump; P pole; C chest; "
            .. "| pipe; * ore; ~ water; # blocked; . clear",
    }
end
