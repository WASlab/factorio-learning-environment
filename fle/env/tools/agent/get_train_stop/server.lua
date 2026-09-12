storage.actions.get_train_stop = function(player_index, x, y, limit, offset)
    local player = storage.agent_characters[player_index]
    local entities = player.surface.find_entities_filtered{position={x=x,y=y},type="train-stop",force=player.force}
    if #entities ~= 1 then error("Position must identify exactly one train stop") end
    local entity = entities[1]
    local trains = entity.get_train_stop_trains()
    table.sort(trains, function(a,b) return a.id < b.id end)
    local ids = {}
    for i=offset+1,math.min(#trains,offset+limit) do ids[#ids+1]=trains[i].id end
    local stopped = entity.get_stopped_train()
    return {entity_id=entity.unit_number,name=entity.backer_name,position=entity.position,
        trains_limit=entity.trains_limit, inbound_or_stopped_count=entity.trains_count,
        stopped_train_id=stopped and stopped.id,scheduled_train_ids=ids,
        total=#trains,offset=offset,truncated=offset+#ids<#trains,tick=game.tick}
end
