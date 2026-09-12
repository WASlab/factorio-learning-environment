storage.actions.get_circuit_network = function(player_index, x, y, wire, connector_id, limit, offset)
    local player = storage.agent_characters[player_index]
    local entities = player.surface.find_entities_filtered{position={x=x,y=y}, radius=0.71, force=player.force}
    local candidates = {}
    for _, entity in pairs(entities) do
        if next(entity.get_wire_connectors(false) or {}) then candidates[#candidates+1] = entity end
    end
    if #candidates ~= 1 then error("Position must identify exactly one wired entity") end
    local entity, entries = candidates[1], {}
    for id, connector in pairs(entity.get_wire_connectors(false)) do
        if connector.wire_type == defines.wire_type[wire] and (not connector_id or id == connector_id) then
            local network = entity.get_circuit_network(id)
            if network then
                local signals = network.signals or {}
                table.sort(signals, function(a,b)
                    local function key(s) return (s.type or "item") .. ":" .. s.name .. ":" .. (s.quality or "normal") end
                    return key(a.signal) < key(b.signal)
                end)
                local selected = {}
                for i=offset+1,math.min(#signals,offset+limit) do selected[#selected+1]=signals[i] end
                entries[#entries+1] = {connector_id=id, network_id=network.network_id,
                    connected_circuit_count=network.connected_circuit_count,
                    signals=selected, total=#signals, offset=offset, truncated=offset+#selected<#signals}
            end
        end
    end
    table.sort(entries, function(a,b) return a.connector_id < b.connector_id end)
    local behavior = entity.get_control_behavior()
    local configuration
    if behavior and (entity.type == "arithmetic-combinator" or entity.type == "decider-combinator" or
        entity.type == "selector-combinator") then configuration = behavior.parameters end
    return {entity_id=entity.unit_number, name=entity.name, position=entity.position,
        wire=wire, networks=entries, configuration=configuration, tick=game.tick}
end
