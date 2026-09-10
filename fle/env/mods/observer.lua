-- One-shot observer setup, executed only after the graphical client joins.
-- Dynamic event registration here would make the multiplayer script registries differ.
local observer_name = "fle-observer"
local group_name = "fle-observers"
local player = game.get_player(observer_name)
if not player then error("fle-observer has not joined") end

local group = game.permissions.get_group(group_name)
if not group then group = game.permissions.create_group(group_name) end
local mutation_actions = {
    "admin_action", "begin_mining", "begin_mining_terrain", "build",
    "build_rail", "build_terrain", "cancel_craft", "cancel_deconstruct",
    "cancel_research", "cancel_upgrade", "change_arithmetic_combinator_parameters",
    "change_decider_combinator_parameters", "change_entity_label", "change_item_label",
    "change_multiplayer_config", "change_riding_state", "change_shooting_state",
    "change_train_stop_station", "change_train_wait_condition",
    "change_train_wait_condition_data", "connect_rolling_stock", "copy_entity_settings",
    "craft", "create_blueprint_like", "cursor_split", "cursor_transfer",
    "delete_blueprint_library", "destroy_opened_item", "disconnect_rolling_stock",
    "drag_train_schedule", "drop_item", "edit_custom_tag", "fast_entity_split",
    "fast_entity_transfer", "flush_opened_entity_fluid",
    "flush_opened_entity_specific_fluid", "go_to_train_station", "import_blueprint",
    "import_blueprint_string", "inventory_split", "inventory_transfer",
    "launch_rocket", "market_offer", "paste_entity_settings", "place_equipment",
    "remove_cables", "remove_train_station", "reset_assembling_machine",
    "rotate_entity", "set_circuit_condition", "set_circuit_mode_of_operation",
    "set_entity_color", "set_filter", "set_infinity_container_filter_item",
    "set_infinity_pipe_filter", "set_inserter_max_stack_size", "set_inventory_bar",
    "set_logistic_filter_item", "set_recipe", "set_request_from_buffers", "set_signal",
    "set_splitter_priority", "set_train_limit", "setup_assembling_machine",
    "setup_blueprint", "spawn_item", "stack_split", "stack_transfer",
    "start_repair", "start_research", "switch_constant_combinator_state",
    "switch_power_switch_state", "take_equipment", "toggle_driving",
    "toggle_entity_logistic_requests", "toggle_map_editor", "undo", "upgrade",
    "use_artillery_remote", "use_item", "use_spidertron_remote"
}
for _, name in pairs(mutation_actions) do
    local action = defines.input_action[name]
    if action then group.set_allows_action(action, false) end
end

local old_character = player.character
player.set_controller {type = defines.controllers.spectator}
if old_character and old_character.valid then old_character.destroy() end
group.add_player(player)
local agent = storage.agent_characters and storage.agent_characters[1]
if agent and agent.valid then player.teleport(agent.position, agent.surface) end
player.print("FLE observer mode: read-only spectator.")
