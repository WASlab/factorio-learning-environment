storage.actions.queue_craft = function(player_index, recipe_name, count)
    local plan = storage.utils.get_craft_plan(player_index, recipe_name, count, 2)
    if (plan.reason and plan.reason ~= "insufficient_ingredients") or plan.craftable_now == 0 then
        return {error=true,reason=plan.reason,craft_plan=plan,queued=0,tick=game.tick}
    end

    -- Complete the craft within this intervention so the product can be used
    -- immediately. craft_item's fast path consumes only ingredients the
    -- character already has (and books the crafting time), so no item can be
    -- created that the character could not afford. Force it on for this call
    -- and restore the mode immediately; no other code runs in between.
    local previous_fast = storage.fast
    storage.fast = true
    local target = math.min(count, plan.craftable_now)
    local ok, crafted_or_error = pcall(
        storage.actions.craft_item, player_index, recipe_name, target
    )
    storage.fast = previous_fast

    if not ok then
        return {error=true,reason="native_crafting_rejected",
            message=tostring(crafted_or_error),craft_plan=plan,queued=0,tick=game.tick}
    end
    local crafted = tonumber(crafted_or_error) or 0
    if crafted == 0 then
        return {error=true,reason=plan.reason or "native_crafting_rejected",
            craft_plan=plan,queued=0,tick=game.tick}
    end
    storage.semantic_craft_sequence = (storage.semantic_craft_sequence or 0) + 1
    return {handle="\"craft-" .. storage.semantic_craft_sequence .. "\"",
        recipe="\"" .. recipe_name .. "\"", requested=count, crafted=crafted,
        queued=crafted, queued_crafts=math.floor(crafted / math.max(plan.items_per_craft, 1)),
        partial=crafted < count, tick=game.tick}
end
