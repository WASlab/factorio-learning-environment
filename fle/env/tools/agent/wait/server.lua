local function check_wait(job)
    local c = job.condition
    if not c then return false, nil end
    local player = storage.agent_characters[job.player_index]
    if not player or not player.valid then error("Wait character is unavailable") end
    local observed = {kind=c.kind}
    if c.kind == "inventory" then
        local entity = c.entity_id and storage.entity_handles and storage.entity_handles[c.entity_id] or nil
        if c.entity_id and (not entity or not entity.valid) then error("Wait entity was removed") end
        observed.count = (entity or player).get_item_count(c.item)
        observed.at_least = c.at_least
        return observed.count >= c.at_least, observed
    elseif c.kind == "research" then
        local technology = player.force.technologies[c.technology]
        if not technology then error("Unknown technology: " .. c.technology) end
        observed.technology, observed.researched = c.technology, technology.researched
        return technology.researched, observed
    elseif c.kind == "craft_queue" then
        observed.active = #(player.crafting_queue or {}) > 0
        return observed.active == c.active, observed
    elseif c.kind == "production_rate" then
        local stats = storage.actions.get_production_statistics(job.player_index,{c.item},c.window_seconds,"item",1)
        observed.rate_per_minute = stats.entries[1].produced_per_minute
        observed.window_seconds, observed.at_least = c.window_seconds, c.at_least
        observed.includes_manual_production = true
        return observed.rate_per_minute >= c.at_least, observed
    elseif c.kind == "machine_status" then
        local entity = storage.entity_handles and storage.entity_handles[c.entity_id]
        if not entity or not entity.valid then error("Wait entity was removed") end
        local status = "unknown"
        for name, value in pairs(defines.entity_status) do
            if value == entity.status then status=name; break end
        end
        observed.entity_id, observed.status = c.entity_id, status
        return status == c.status, observed
    elseif c.kind == "delivery" then
        local product = storage.customer and storage.customer.active_products and storage.customer.active_products[c.item]
        if not product then error("No active order for " .. c.item) end
        observed.item, observed.accepted, observed.at_least = c.item, product.accepted or 0, c.at_least
        return observed.accepted >= c.at_least, observed
    elseif c.kind == "event" then
        for _, event in ipairs(storage.semantic_events or {}) do
            if event.tick > job.start_tick and event.type == c.type then return true, event end
        end
        return false, observed
    end
    error("Unknown wait condition")
end

local function sample_wait(job)
    local ok, met, observed = pcall(check_wait, job)
    job.observed = observed
    if not ok then
        job.status, job.error = "error", tostring(met)
    elseif met then
        job.status = "condition_met"
    elseif game.tick >= job.deadline_tick then
        job.status = job.condition and "timeout" or "completed"
    end
    if job.status ~= "pending" then job.decision_tick = game.tick end
end

storage.actions.wait = function(operation, player_index, payload)
    if operation == 0 then return game.tick end
    storage.public_waits = storage.public_waits or {}
    if operation == "start" then
        local job = {player_index=player_index,start_tick=game.tick,
            deadline_tick=game.tick+payload.ticks,condition=payload.condition,
            poll_ticks=payload.poll_ticks,next_tick=game.tick+payload.poll_ticks,status="pending"}
        sample_wait(job)
        storage.public_waits[player_index] = job
        return {start_tick=job.start_tick,deadline_tick=job.deadline_tick}
    elseif operation == "cancel" then
        storage.public_waits[player_index] = nil
        return true
    elseif operation == "poll" then
        local job = storage.public_waits[player_index]
        if not job then return {status="error",error="Wait is unavailable"} end
        return {status=job.status,start_tick=job.start_tick,deadline_tick=job.deadline_tick,
            decision_tick=job.decision_tick,observed=job.observed,error=job.error,tick=game.tick}
    end
    error("Invalid wait operation")
end

script.on_event(defines.events.on_tick, function(event)
    for _, job in pairs(storage.public_waits or {}) do
        if job.status == "pending" and (game.tick >= job.next_tick or game.tick >= job.deadline_tick) then
            sample_wait(job)
            job.next_tick = game.tick + job.poll_ticks
        end
    end
end)
