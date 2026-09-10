local precisions = {
    [5]=defines.flow_precision_index.five_seconds,
    [60]=defines.flow_precision_index.one_minute,
    [600]=defines.flow_precision_index.ten_minutes,
    [3600]=defines.flow_precision_index.one_hour
}

storage.actions.get_production_statistics = function(player_index, names, seconds, category, limit)
    local character = storage.utils.ensure_valid_character(player_index)
    if not precisions[seconds] or (category~="item" and category~="fluid") or
        type(limit)~="number" or limit<1 or limit>64 or #names>64 then
        return {error="Invalid statistics query"}
    end
    local force, surface = character.force, character.surface
    local stats = category=="item" and force.get_item_production_statistics(surface) or
        force.get_fluid_production_statistics(surface)
    -- Statistics maps contain active products, not every possible prototype.
    local produced, consumed = stats.input_counts, stats.output_counts
    local selected = {}
    local unknown = {}
    if #names>0 then
        local known = category=="item" and prototypes.item or prototypes.fluid
        for _, name in ipairs(names) do
            if known[name] then selected[name]=true else unknown[#unknown+1]=name end
        end
    else
        for name in pairs(produced) do selected[name]=true end
        for name in pairs(consumed) do selected[name]=true end
    end
    local ordered = {}
    for name in pairs(selected) do ordered[#ordered+1]=name end
    table.sort(ordered, function(a,b)
        local av=(produced[a] or 0)+(consumed[a] or 0)
        local bv=(produced[b] or 0)+(consumed[b] or 0)
        return av==bv and a<b or av>bv
    end)
    local entries = {}
    for index=1,math.min(#ordered,limit) do
        local name = ordered[index]
        entries[#entries+1]={name=name,produced_total=produced[name] or 0,
            consumed_total=consumed[name] or 0,
            produced_per_minute=stats.get_flow_count{name=name,category="input",precision_index=precisions[seconds],count=false},
            consumed_per_minute=stats.get_flow_count{name=name,category="output",precision_index=precisions[seconds],count=false}}
    end
    return {available=true,tick=game.tick,surface=surface.name,force=force.name,
        category=category,window_seconds=seconds,entries=entries,truncated=#ordered>limit,
        matching_products=#ordered,unknown_products=unknown,includes_manual_production=true}
end
