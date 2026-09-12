storage.actions.get_logistic_network = function(player_index, x, y, limit, offset)
    local player = storage.agent_characters[player_index]
    local network = player.surface.find_logistic_network_by_position({x=x,y=y}, player.force)
    if not network then return {connected=false, contents={}, tick=game.tick} end
    local contents = network.get_contents()
    table.sort(contents, function(a,b)
        if a.name == b.name then return (a.quality or "normal") < (b.quality or "normal") end
        return a.name < b.name
    end)
    local entries = {}
    for i=offset+1,math.min(#contents, offset+limit) do entries[#entries+1]=contents[i] end
    return {connected=true, network_id=network.network_id,
        roboport_count=#network.cells, contents=entries, total=#contents, offset=offset,
        truncated=offset+#entries<#contents,
        logistics_robots={available=network.available_logistic_robots, total=network.all_logistic_robots},
        construction_robots={available=network.available_construction_robots, total=network.all_construction_robots},
        tick=game.tick}
end
