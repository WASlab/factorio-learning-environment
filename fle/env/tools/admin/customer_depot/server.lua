-- Contract delivery boundaries. Fixed-mode depots are customer-owned sinks;
-- designated-mode depots temporarily bind an empty player chest and consume
-- only accepted contract items, leaving surplus for the player after release.

storage.customer = storage.customer or {
    depots = {},           -- unit_number -> LuaEntity reference
    depot_specs = {},      -- unit_number -> {position = {x, y}, surface = name}
    delivered_total = {},  -- item -> cumulative count consumed by sinks
    manual_delivered_total = {}, -- item -> direct agent insertions (not credited)
    manual_pending = {},   -- unit_number -> item -> direct insertions awaiting drain
    delta_log = {},        -- array of {start_tick = t, items = {item = delta}}
    tamper_events = {},    -- array of {tick, unit_number, reason}
    tamper_reported = {},  -- unit_number -> true (dedupe)
    handlers_installed = false,
    epoch_tick = nil,      -- absolute game.tick at episode start
    mode = "fixed",       -- fixed | designated
    active_products = {},  -- product -> {limit, accepted}
    product_bindings = {}, -- product -> {unit_number = true}
    retained_contents = {}, -- unit_number -> item -> unconsumed chest count
}

-- Populate fields added after an episode was created. Scenario tool files can
-- be reloaded without reconstructing the shared storage table.
storage.customer.delivered_total = storage.customer.delivered_total or {}
storage.customer.manual_delivered_total = storage.customer.manual_delivered_total or {}
storage.customer.manual_pending = storage.customer.manual_pending or {}
storage.customer.mode = storage.customer.mode or "fixed"
storage.customer.active_products = storage.customer.active_products or {}
storage.customer.product_bindings = storage.customer.product_bindings or {}
storage.customer.retained_contents = storage.customer.retained_contents or {}

-- Runtime upgrades may encounter the former product -> unit_number shape.
for product, bindings in pairs(storage.customer.product_bindings) do
    if type(bindings) ~= "table" then
        storage.customer.product_bindings[product] = {[bindings] = true}
    end
end

local BUCKET_TICKS = 60
local DRAIN_EVERY_TICKS = 6

-- The canonical episode clock: game.tick minus the episode epoch. Schedules,
-- buckets, and telemetry all use this so contract timing cannot drift against
-- the resettable task clock used by objectives.
local function episode_tick()
    local epoch = storage.customer.epoch_tick or game.tick
    return game.tick - epoch
end

local function ensure_bucket(tick)
    local start_tick = math.floor(tick / BUCKET_TICKS) * BUCKET_TICKS
    for _, bucket in ipairs(storage.customer.delta_log) do
        if bucket.start_tick == start_tick then
            return bucket
        end
    end
    local bucket = {start_tick = start_tick, items = {}}
    table.insert(storage.customer.delta_log, bucket)
    return bucket
end

local function make_depot(surface, position)
    local entity = surface.create_entity({
        name = "steel-chest",
        position = position,
        force = game.forces.player,
    })
    if not entity then
        return nil
    end
    entity.destructible = false
    entity.operable = false
    pcall(function()
        entity.minable_flag = false
    end)
    storage.customer.depots[entity.unit_number] = entity
    storage.customer.depot_specs[entity.unit_number] = {
        position = {x = entity.position.x, y = entity.position.y},
        surface = surface.name,
        entity_name = entity.name,
        customer_owned = true,
    }
    return entity
end

local function restore_designated_depot(unit_number, entity)
    local spec = storage.customer.depot_specs[unit_number]
    if not spec or spec.customer_owned ~= false or not entity or not entity.valid then
        return
    end
    entity.destructible = spec.original_destructible
    entity.operable = spec.original_operable
    pcall(function() entity.minable_flag = spec.original_minable end)
end

local function unbind_all_designated_depots()
    for unit_number, entity in pairs(storage.customer.depots) do
        restore_designated_depot(unit_number, entity)
    end
    storage.customer.depots = {}
    storage.customer.depot_specs = {}
    storage.customer.manual_pending = {}
    storage.customer.product_bindings = {}
    storage.customer.retained_contents = {}
end

local function clear_depots()
    for unit_number, entity in pairs(storage.customer.depots) do
        if entity and entity.valid then
            local spec = storage.customer.depot_specs[unit_number]
            if spec and spec.customer_owned == false then
                restore_designated_depot(unit_number, entity)
            else
                pcall(function() entity.destroy() end)
            end
        end
    end
    storage.customer.depots = {}
    storage.customer.depot_specs = {}
    storage.customer.delivered_total = {}
    storage.customer.manual_delivered_total = {}
    storage.customer.manual_pending = {}
    storage.customer.delta_log = {}
    storage.customer.tamper_events = {}
    storage.customer.tamper_reported = {}
    storage.customer.active_products = {}
    storage.customer.product_bindings = {}
    storage.customer.retained_contents = {}
end

local function record_tamper(unit_number, tick, reason)
    if storage.customer.tamper_reported[unit_number] then
        return
    end
    storage.customer.tamper_reported[unit_number] = true
    table.insert(storage.customer.tamper_events, {
        tick = tick,
        unit_number = unit_number,
        reason = reason,
    })
end

local function sink_contents(inventory)
    -- Factorio 2.0 returns get_contents() as an array of {name, count,
    -- quality} entries; normalise to {item_name = count}.
    if not inventory then
        return {}
    end
    local contents = {}
    for _, item in pairs(inventory.get_contents()) do
        contents[item.name] = (contents[item.name] or 0) + item.count
    end
    return contents
end

local function drain_depots(tick)
    local active_bucket = nil
    local replacements = {}
    local stale_units = {}
    for unit_number, entity in pairs(storage.customer.depots) do
        if not entity or not entity.valid then
            record_tamper(unit_number, tick, "depot_entity_missing")
            local spec = storage.customer.depot_specs[unit_number]
            table.insert(stale_units, unit_number)
            -- A fixed depot belongs to the verifier and may be rebuilt. A
            -- designated depot belongs to the player: if it disappears, the
            -- product becomes unbound and the agent must designate another
            -- chest. Replacing it with a steel chest changes the contract and
            -- can create overlapping depots on every drain tick.
            if spec and spec.customer_owned ~= false and game.surfaces[spec.surface] then
                replacements[unit_number] = spec
            end
        else
            local inventory = entity.get_inventory(defines.inventory.chest)
            if inventory then
                local contents = sink_contents(inventory)
                local pending = storage.customer.manual_pending[unit_number] or {}
                local retained = storage.customer.retained_contents[unit_number] or {}
                local has_items = false
                for name, count in pairs(contents) do
                    local depot_spec = storage.customer.depot_specs[unit_number] or {}
                    local product_state = storage.customer.active_products[name]
                    local designated_match = storage.customer.mode ~= "designated"
                        or depot_spec.product == name
                    local arrived_count = count
                    if storage.customer.mode == "designated" then
                        arrived_count = math.max(count - (retained[name] or 0), 0)
                    end
                    local manual_count = designated_match
                        and math.min(pending[name] or 0, arrived_count) or 0
                    local automated_count = designated_match
                        and math.max(arrived_count - manual_count, 0) or 0
                    local accepted_count = automated_count
                    if storage.customer.mode == "designated" then
                        if not product_state then
                            automated_count = 0
                            accepted_count = 0
                        else
                            local remaining = math.max(
                                (product_state.limit or 0) - (product_state.accepted or 0),
                                0
                            )
                            accepted_count = math.min(automated_count, remaining)
                        end
                    end
                    local consumed = manual_count + accepted_count
                    if consumed > 0 or automated_count > 0 then
                        has_items = true
                        active_bucket = active_bucket or ensure_bucket(tick)
                        active_bucket.manual_items = active_bucket.manual_items or {}
                    end
                    if automated_count > 0 then
                        active_bucket.items[name] =
                            (active_bucket.items[name] or 0) + automated_count
                        storage.customer.delivered_total[name] =
                            (storage.customer.delivered_total[name] or 0) + automated_count
                        if product_state then
                            product_state.accepted =
                                (product_state.accepted or 0) + accepted_count
                        end
                    end
                    if manual_count > 0 then
                        active_bucket.manual_items[name] =
                            (active_bucket.manual_items[name] or 0) + manual_count
                        storage.customer.manual_delivered_total[name] =
                            (storage.customer.manual_delivered_total[name] or 0) + manual_count
                    end
                    if consumed > 0 and storage.customer.mode == "designated" then
                        inventory.remove({name = name, count = consumed})
                    end
                end
                if storage.customer.mode == "designated" then
                    -- Accepted and manual units have been removed. Retain the
                    -- post-drain contents as the baseline so only new inserter
                    -- arrivals are counted on the next pass. This keeps service
                    -- telemetry live after the finite order allowance is full.
                    storage.customer.retained_contents[unit_number] = sink_contents(inventory)
                end
                if has_items then
                    if storage.customer.mode ~= "designated" then
                        inventory.clear()
                    end
                end
                storage.customer.manual_pending[unit_number] = nil
            end
        end
    end
    -- Remove invalid references before rebuilding. Mutating the depot table
    -- while pairs() is traversing it can otherwise revisit or retain entries.
    for _, unit_number in ipairs(stale_units) do
        local spec = storage.customer.depot_specs[unit_number]
        if spec and spec.product then
            local bindings = storage.customer.product_bindings[spec.product]
            if bindings then
                bindings[unit_number] = nil
                if next(bindings) == nil then
                    storage.customer.product_bindings[spec.product] = nil
                end
            end
        end
        storage.customer.depots[unit_number] = nil
        storage.customer.depot_specs[unit_number] = nil
        storage.customer.manual_pending[unit_number] = nil
        storage.customer.retained_contents[unit_number] = nil
    end
    -- Rebuild fixed depots only after cleanup and only when the position is
    -- actually free. This makes recovery single-shot and collision-safe.
    for unit_number, spec in pairs(replacements) do
        local surface = game.surfaces[spec.surface]
        if surface and surface.can_place_entity({
                name = spec.entity_name or "steel-chest",
                position = spec.position,
                force = game.forces.player,
            }) then
            make_depot(surface, spec.position)
        end
    end
end

local HANDLER_VERSION = 5
if storage.customer.handler_version ~= HANDLER_VERSION then
    script.on_nth_tick(DRAIN_EVERY_TICKS, function(event)
        -- A telemetry bug must degrade to missing data, never kill the
        -- simulation: an unhandled error inside a scenario event handler is
        -- fatal for the running multiplayer game.
        local ok, err = pcall(function()
            if storage.customer and storage.customer.depots then
                drain_depots(episode_tick())
            end
        end)
        if not ok and storage.customer then
            storage.customer.last_error = tostring(err)
        end
    end)
    storage.customer.handlers_installed = true
    storage.customer.handler_version = HANDLER_VERSION
end

storage.actions.customer_depot = function(player_index, command, x, y, chest_count, relative)
    command = command or "telemetry"

    if command == "place" then
        clear_depots()
        storage.customer.mode = "fixed"
        -- Pin the episode epoch: all contract scheduling runs on
        -- game.tick - epoch_tick so buckets are episode-relative.
        storage.customer.epoch_tick = game.tick
        local character = storage.agent_characters
            and storage.agent_characters[player_index] or nil
        local surface = character and character.valid
            and character.surface or game.surfaces[1]
        chest_count = math.max(1, math.min(chest_count or 8, 64))
        local anchor_x = x or 0
        local anchor_y = y or 0
        if relative and character and character.valid then
            anchor_x = character.position.x + (x or 0)
            anchor_y = character.position.y + (y or 0)
        end
        local placed = 0
        local slot = 0
        while placed < chest_count and slot < chest_count * 8 do
            local position = {x = anchor_x + slot * 2, y = anchor_y}
            if surface.can_place_entity({name = "steel-chest", position = position}) then
                if make_depot(surface, position) then
                    placed = placed + 1
                end
            end
            slot = slot + 1
        end
        return {
            placed = placed,
            requested = chest_count,
            depots = storage.customer.depot_specs,
        }
    elseif command == "designated" then
        clear_depots()
        storage.customer.mode = "designated"
        storage.customer.epoch_tick = game.tick
        return {mode = storage.customer.mode}
    elseif command == "configure" then
        unbind_all_designated_depots()
        storage.customer.mode = "designated"
        storage.customer.active_products = {}
        for _, product in pairs(x or {}) do
            if product.name and (product.limit or 0) > 0 then
                storage.customer.active_products[product.name] = {
                    limit = product.limit,
                    accepted = 0,
                    max_depots = math.max(math.floor(product.max_depots or 1), 1),
                }
            end
        end
        storage.semantic_events = storage.semantic_events or {}
        table.insert(storage.semantic_events, {
            type = "new_order",
            tick = game.tick,
            products = x or {},
        })
        while #storage.semantic_events > 128 do
            table.remove(storage.semantic_events, 1)
        end
        return {mode = storage.customer.mode, active_products = storage.customer.active_products}
    elseif command == "bind" then
        if storage.customer.mode ~= "designated" then
            return {error = "designated_delivery_not_enabled"}
        end
        local position = x
        local product = y
        if not position or not product or not storage.customer.active_products[product] then
            return {error = "product_not_in_active_contract"}
        end
        local bindings = storage.customer.product_bindings[product] or {}
        local binding_count = 0
        local matching_unit = nil
        for existing_unit, _ in pairs(bindings) do
            local existing = storage.customer.depots[existing_unit]
            if existing and existing.valid then
                binding_count = binding_count + 1
                if existing.position.x == position.x and existing.position.y == position.y then
                    matching_unit = existing_unit
                end
            end
        end
        local max_depots = storage.customer.active_products[product].max_depots or 1
        if matching_unit then
            local existing_spec = storage.customer.depot_specs[matching_unit]
            return {
                bound = true,
                unit_number = matching_unit,
                position = existing_spec.position,
                idempotent = true,
                bound_count = binding_count,
                max_depots = max_depots,
            }
        end
        if binding_count >= max_depots then
            return {
                error = "product_depot_capacity_reached",
                product = product,
                bound_count = binding_count,
                max_depots = max_depots,
            }
        end
        local player = storage.utils.ensure_valid_character(player_index)
        local candidates = player.surface.find_entities_filtered({
            position = position,
            force = player.force,
            type = {"container", "logistic-container"},
        })
        local entity = candidates[1]
        if not entity or not entity.valid then
            return {error = "delivery_chest_not_found"}
        end
        local inventory = entity.get_inventory(defines.inventory.chest)
        if not inventory then
            return {error = "entity_has_no_chest_inventory"}
        end
        if not inventory.is_empty() then
            return {error = "delivery_chest_must_be_empty"}
        end
        if storage.customer.depots[entity.unit_number] then
            return {error = "chest_already_bound"}
        end
        storage.customer.depots[entity.unit_number] = entity
        storage.customer.depot_specs[entity.unit_number] = {
            position = {x = entity.position.x, y = entity.position.y},
            surface = entity.surface.name,
            entity_name = entity.name,
            product = product,
            customer_owned = false,
            original_destructible = entity.destructible,
            original_operable = entity.operable,
            original_minable = entity.minable_flag,
        }
        bindings[entity.unit_number] = true
        storage.customer.product_bindings[product] = bindings
        storage.customer.retained_contents[entity.unit_number] = {}
        entity.destructible = false
        entity.operable = false
        pcall(function() entity.minable_flag = false end)
        return {
            bound = true,
            unit_number = entity.unit_number,
            position = storage.customer.depot_specs[entity.unit_number].position,
            idempotent = false,
            bound_count = binding_count + 1,
            max_depots = max_depots,
        }
    elseif command == "telemetry" then
        local buckets = storage.customer.delta_log
        storage.customer.delta_log = {}
        -- Do not return the same Lua table under two keys. Serpent represents
        -- aliases with a placeholder that the legacy controller parser cannot
        -- decode reliably.
        local delivered_compat = {}
        for product, amount in pairs(storage.customer.delivered_total) do
            delivered_compat[product] = amount
        end
        local depot_summary = {}
        for unit_number, entity in pairs(storage.customer.depots) do
            local spec = storage.customer.depot_specs[unit_number] or {}
            local valid = entity and entity.valid or false
            local entity_name = spec.entity_name or "unknown"
            local surface_name = spec.surface
            if valid then
                entity_name = entity.name
                surface_name = surface_name or entity.surface.name
            end
            table.insert(depot_summary, {
                unit_number = unit_number,
                valid = valid,
                entity_names = {[entity_name] = true},
                position = spec.position,
                surfaces = surface_name and {[surface_name] = true} or {},
                customer_owned = spec.customer_owned ~= false,
                consumes_deliveries = true,
                products = spec.product and {[spec.product] = true} or {},
                acceptance_limit = spec.product
                    and storage.customer.active_products[spec.product]
                    and storage.customer.active_products[spec.product].limit or nil,
                accepted = spec.product
                    and storage.customer.active_products[spec.product]
                    and storage.customer.active_products[spec.product].accepted or nil,
            })
        end
        return {
            tick = episode_tick(),
            epoch_tick = storage.customer.epoch_tick,
            delivery_bucket_ticks = BUCKET_TICKS,
            -- Automated traffic is the crediting channel. Direct insertion is
            -- exposed separately for audit and cannot satisfy a contract.
            raw_delivery_totals = storage.customer.delivered_total,
            delivered_total = delivered_compat,
            manual_delivery_totals = storage.customer.manual_delivered_total,
            buckets = buckets,
            depots = depot_summary,
            tamper_events = storage.customer.tamper_events,
            last_errors = storage.customer.last_error
                and {[storage.customer.last_error] = true} or {},
            designated = storage.customer.mode == "designated",
            active_products = storage.customer.active_products,
        }
    elseif command == "adopt" then
        -- Reattach verifier state after GameState restores the physical world
        -- into an isolated audit instance. No new entities are created.
        local specs = x or {}
        storage.customer.depots = {}
        storage.customer.depot_specs = {}
        storage.customer.delivered_total = {}
        storage.customer.manual_delivered_total = {}
        storage.customer.manual_pending = {}
        storage.customer.delta_log = {}
        storage.customer.tamper_events = {}
        storage.customer.tamper_reported = {}
        storage.customer.mode = "designated"
        storage.customer.active_products = {}
        storage.customer.product_bindings = {}
        storage.customer.retained_contents = {}
        storage.customer.epoch_tick = game.tick
        local adopted = 0
        for _, spec in pairs(specs) do
            local surface = game.surfaces[spec.surface or 1]
            local position = spec.position
            if surface and position then
                local entities = surface.find_entities_filtered({
                    position = position,
                    name = spec.entity_name or "steel-chest",
                    force = game.forces.player,
                })
                local entity = entities[1]
                if entity and entity.valid then
                    local inventory = entity.get_inventory(defines.inventory.chest)
                    if inventory then
                        -- Snapshot state cannot carry manual-delivery provenance.
                        -- Discard candidate-time contents conservatively so a
                        -- preloaded depot cannot become autonomous audit credit.
                        inventory.clear()
                    end
                    entity.destructible = false
                    entity.operable = false
                    pcall(function() entity.minable_flag = false end)
                    storage.customer.depots[entity.unit_number] = entity
                    storage.customer.depot_specs[entity.unit_number] = {
                        position = {x = entity.position.x, y = entity.position.y},
                        surface = surface.name,
                        entity_name = entity.name,
                        product = spec.product,
                        customer_owned = false,
                        original_destructible = entity.destructible,
                        original_operable = entity.operable,
                        original_minable = entity.minable_flag,
                    }
                    if spec.product then
                        local bindings = storage.customer.product_bindings[spec.product] or {}
                        bindings[entity.unit_number] = true
                        storage.customer.product_bindings[spec.product] = bindings
                        local product_state = storage.customer.active_products[spec.product]
                        if not product_state then
                            product_state = {
                                limit = spec.limit or 1000000000,
                                accepted = 0,
                                max_depots = 1,
                            }
                            storage.customer.active_products[spec.product] = product_state
                        end
                        product_state.max_depots = math.max(
                            product_state.max_depots or 1,
                            -- Audit adoption must accept every depot captured
                            -- from the candidate state.
                            1
                        )
                    end
                    storage.customer.retained_contents[entity.unit_number] = {}
                    entity.destructible = false
                    entity.operable = false
                    pcall(function() entity.minable_flag = false end)
                    adopted = adopted + 1
                end
            end
        end
        return {adopted = adopted, requested = #specs}
    elseif command == "clear" then
        clear_depots()
        return {cleared = true}
    end

    return {error = "unknown command: " .. tostring(command)}
end
