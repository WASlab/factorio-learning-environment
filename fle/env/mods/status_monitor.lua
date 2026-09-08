-- Public machine status sampling. No objective/verifier fields enter this stream.
-- Registry cost scales with observed machines; discovery reuses the entity census.
local capacity = 4096
local machine_types = {
    ["mining-drill"]=true, furnace=true, ["assembling-machine"]=true,
    inserter=true, lab=true, boiler=true, generator=true, ["rocket-silo"]=true,
    pump=true, ["offshore-pump"]=true, reactor=true, ["electric-energy-interface"]=true,
}

local function monitor()
    storage.public_status_monitor = storage.public_status_monitor or {
        entities={}, current={}, ring={}, sequence=0, count=0,
    }
    return storage.public_status_monitor
end

local function status_name(entity)
    local status = entity.status
    for name, value in pairs(defines.entity_status) do
        if value == status then return name end
    end
    return "unknown"
end

local function append(state, sample)
    state.sequence = state.sequence + 1
    sample.engine_sequence = state.sequence
    state.ring[((state.sequence - 1) % capacity) + 1] = sample
    state.count = math.min(capacity, state.count + 1)
end

local function sample_entity(state, id, entity)
    local previous = state.current[id]
    if not entity.valid then
        if previous then
            append(state, {
                entity_id=id, prototype=previous.prototype, position=previous.position,
                surface=previous.surface, force=previous.force, tick=game.tick,
                status="removed", removed=true,
            })
        end
        state.entities[id] = nil
        state.current[id] = nil
        return
    end
    local status = status_name(entity)
    if previous and previous.status == status then return end
    local sample = {
        entity_id=id, prototype=entity.name,
        position={x=entity.position.x, y=entity.position.y},
        surface=entity.surface.index, force=entity.force.index,
        tick=game.tick, status=status,
        warning_key=(status ~= "working" and status ~= "normal") and status or nil,
    }
    state.current[id] = sample
    append(state, sample)
end

storage.utils.track_public_status = function(entity)
    if not entity or not entity.valid or not entity.unit_number
        or not machine_types[entity.type] then return end
    local state = monitor()
    local id = tostring(entity.surface.index) .. ":" .. tostring(entity.unit_number)
    state.entities[id] = entity
    sample_entity(state, id, entity)
end

storage.utils.sample_public_status = function()
    local state = monitor()
    -- Sort keys so event order is independent of Lua hash iteration.
    local ids = {}
    for id in pairs(state.entities) do ids[#ids+1] = id end
    table.sort(ids)
    for _, id in ipairs(ids) do sample_entity(state, id, state.entities[id]) end
end

storage.utils.read_public_status = function(force_index, after_sequence)
    storage.utils.sample_public_status()
    local state = monitor()
    local first = state.sequence - state.count + 1
    local samples = {}
    for sequence = math.max(first, (after_sequence or 0) + 1), state.sequence do
        local sample = state.ring[((sequence - 1) % capacity) + 1]
        if sample.force == force_index then samples[#samples+1] = sample end
    end
    local current = nil
    if (after_sequence or 0) < first - 1 or after_sequence == -1 then
        current = {}
        for _, sample in pairs(state.current) do
            if sample.force == force_index then current[#current+1] = sample end
        end
        table.sort(current, function(a,b) return a.entity_id < b.entity_id end)
    end
    return {
        samples=samples, engine_sequence=state.sequence,
        current=current,
        retained_after_sequence=first-1, sample_interval_ticks=60,
        coverage="registered_player_machines", tick=game.tick,
    }
end

-- Runtime event multiplexing keeps this independent of crafting and placement.
script.on_nth_tick(60, function() storage.utils.sample_public_status() end)
