storage.actions.get_pollution = function(player_index, x, y, radius)
    local player = storage.agent_characters[player_index]
    local cx, cy = math.floor(x/32), math.floor(y/32)
    local entries = {}
    for dy=-radius,radius do
        for dx=-radius,radius do
            local chunk = {x=cx+dx,y=cy+dy}
            -- Detached agent characters do not maintain a LuaPlayer chart.
            -- Match public_view's existing generated-surface visibility.
            local generated = player.surface.is_chunk_generated(chunk)
            entries[#entries+1] = {x=chunk.x,y=chunk.y,generated=generated,
                pollution=generated and player.surface.get_pollution({x=chunk.x*32,y=chunk.y*32}) or nil}
        end
    end
    return {chunks=entries, chunk_size=32, surface=player.surface.name, tick=game.tick}
end
