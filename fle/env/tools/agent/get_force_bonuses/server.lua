storage.actions.get_force_bonuses = function(player_index)
    local force = storage.agent_characters[player_index].force
    local result = {tick=game.tick, ammo={}}
    for _, name in ipairs({"mining_drill_productivity_bonus", "laboratory_speed_modifier",
        "laboratory_productivity_bonus", "worker_robots_speed_modifier", "worker_robots_storage_bonus",
        "worker_robots_battery_modifier", "inserter_stack_size_bonus", "bulk_inserter_capacity_bonus",
        "train_braking_force_bonus", "manual_mining_speed_modifier", "manual_crafting_speed_modifier",
        "character_running_speed_modifier", "character_inventory_slots_bonus"}) do
        result[name] = force[name]
    end
    local categories = {}
    for name in pairs(prototypes.ammo_category) do categories[#categories+1]=name end
    table.sort(categories)
    for _, name in ipairs(categories) do
        result.ammo[#result.ammo+1] = {category=name, damage_modifier=force.get_ammo_damage_modifier(name),
            gun_speed_modifier=force.get_gun_speed_modifier(name)}
    end
    return result
end
