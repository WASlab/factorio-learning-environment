storage.actions.cancel_craft = function(player_index, index, count)
    local player = storage.utils.ensure_valid_character(player_index)
    storage.utils.sync_native_crafting(player_index)
    local queue = player.crafting_queue or {}
    local entry = queue[index]
    if not entry then error("No crafting queue entry at index " .. tostring(index)) end
    local amount = count and count > 0 and math.min(count, entry.count) or entry.count
    player.cancel_crafting{index=index, count=amount}
    -- Cancelled entries are not completed crafts, including their intermediates.
    storage.utils.track_native_crafting(player_index)
    return {cancelled=amount, index=index, tick=game.tick}
end
