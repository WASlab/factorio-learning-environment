-- Use the pinned game's own freeplay defaults and crash-site implementation.
-- The benchmark controls a LuaEntity, not a GUI LuaPlayer. Do not initialize
-- the spectator or attach freeplay's player/cutscene handlers to it.
local freeplay = require('__base__/script/freeplay/freeplay')
local crash_site = require('crash-site')
local util = require('util')

storage.actions.initialize_freeplay = function(player_index)
    local character = storage.agent_characters[player_index]
    if not character or not character.valid then error('Agent character unavailable') end
    local surface = character.surface
    for _, entity in pairs(surface.find_entities_filtered{area={{-80,-80},{80,80}}}) do
        if string.find(entity.name, 'crash-site-', 1, true) == 1 then entity.destroy() end
    end
    freeplay.on_init()
    character.force.reset()
    character.get_main_inventory().clear()
    local items = util.copy(storage.created_items)
    for name, count in pairs(storage.crashed_ship_items) do
        items[name] = (items[name] or 0) - count
    end
    for name, count in pairs(storage.crashed_debris_items) do
        items[name] = (items[name] or 0) - count
    end
    for name, count in pairs(items) do
        if count > 0 then character.insert{name=name,count=count} end
    end
    surface.request_to_generate_chunks({0,0}, 2)
    surface.force_generate_chunk_requests()
    crash_site.create_crash_site(surface, {-5,-6}, util.copy(storage.crashed_ship_items),
        util.copy(storage.crashed_debris_items), util.copy(storage.crashed_ship_parts))
    surface.daytime = 0.7
    character.force.chart(surface, {{-200,-200},{200,200}})
    storage.init_ran = true
    return {initialized=true, scenario='freeplay', starter_items=items}
end
