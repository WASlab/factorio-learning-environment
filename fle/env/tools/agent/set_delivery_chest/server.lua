storage.actions.set_delivery_chest = function(player_index, x, y, product)
    if not storage.actions.customer_depot then
        error("Customer delivery service is unavailable")
    end
    return storage.actions.customer_depot(
        player_index,
        "bind",
        {x = x, y = y},
        product,
        0,
        false
    )
end
