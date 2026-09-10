storage.actions.queue_craft = function(player_index, recipe_name, count)
    local plan = storage.utils.get_craft_plan(player_index, recipe_name, count, 2)
    if (plan.reason and plan.reason ~= "insufficient_ingredients") or plan.craftable_now == 0 then
        return {error=true,reason=plan.reason,craft_plan=plan,queued=0,tick=game.tick}
    end

    -- Fast mode completes the craft within this intervention so the product can
    -- be used immediately; the inventory still gates every ingredient, so no
    -- items can be created that the character could not afford. Temporal mode
    -- keeps the native queue so crafting time remains real.
    if storage.fast and storage.actions.craft_item then
        local target = math.min(count, plan.craftable_now)
        local ok, crafted_or_error = pcall(
            storage.actions.craft_item, player_index, recipe_name, target
        )
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

    local queued = storage.utils.begin_native_crafting(player_index, recipe_name, plan.crafts_required)
    if not queued then
        return {error=true,reason="native_crafting_rejected",craft_plan=plan,queued=0,tick=game.tick}
    end
    storage.semantic_craft_sequence = (storage.semantic_craft_sequence or 0) + 1
    return {handle="\"craft-" .. storage.semantic_craft_sequence .. "\"", recipe="\"" .. recipe_name .. "\"",
        requested=count, queued=queued*plan.items_per_craft, queued_crafts=queued,
        partial=queued*plan.items_per_craft<count, tick=game.tick}
end
