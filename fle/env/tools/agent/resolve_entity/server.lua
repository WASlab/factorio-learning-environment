storage.actions.resolve_entity = function(player_index, unit_number)
    storage.utils.ensure_valid_character(player_index)
    local entity = storage.entity_handles and storage.entity_handles[unit_number]
    if entity and entity.valid then
        return {id=entity.unit_number, name="\"" .. entity.name .. "\"",
            position={x=entity.position.x, y=entity.position.y}}
    end
    error("No live entity for unit number " .. tostring(unit_number))
end
