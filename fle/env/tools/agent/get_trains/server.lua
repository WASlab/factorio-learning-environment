storage.actions.get_trains = function(player_index, limit, offset)
    local player = storage.agent_characters[player_index]
    local trains = game.train_manager.get_trains{surface=player.surface, force=player.force}
    table.sort(trains, function(a,b) return a.id < b.id end)
    local states = {}
    for name, id in pairs(defines.train_state) do states[id] = name end
    local function stop(entity)
        if entity and entity.valid then return {entity_id=entity.unit_number,
            name=entity.backer_name, position=entity.position} end
    end
    local entries = {}
    for i=offset+1,math.min(#trains,offset+limit) do
        local train = trains[i]
        local fuel = {}
        for _, direction in pairs(train.locomotives) do
            for _, locomotive in pairs(direction) do
                local burner = locomotive.burner
                fuel[#fuel+1] = {entity_id=locomotive.unit_number,
                    contents=burner and burner.inventory.get_contents() or {},
                    currently_burning=burner and burner.currently_burning and burner.currently_burning.name,
                    remaining_burning_energy=burner and burner.remaining_burning_fuel}
            end
        end
        -- Native schedule records contain LuaEntity rail references. Copy only plain
        -- public schedule fields, converting rail references to location records.
        local schedule = train.schedule
        local records = {}
        for _, record in ipairs(schedule and schedule.records or {}) do
            records[#records+1] = {station=record.station, temporary=record.temporary,
                wait_conditions=record.wait_conditions,
                rail=record.rail and {entity_id=record.rail.unit_number, position=record.rail.position}}
        end
        entries[#entries+1] = {id=train.id, state=states[train.state], manual_mode=train.manual_mode,
            speed=train.speed, has_path=train.has_path, position=train.front_stock.position,
            current_station=stop(train.station), destination=stop(train.path_end_stop),
            schedule={current=schedule and schedule.current, records=records},
            cargo=train.get_contents(), fluids=train.get_fluid_contents(), fuel=fuel}
    end
    return {trains=entries,total=#trains,offset=offset,truncated=offset+#entries<#trains,tick=game.tick}
end
