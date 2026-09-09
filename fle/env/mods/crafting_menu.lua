-- Read-only handcrafting menu. Native craftability is authoritative; subrecipe
-- rows are independent previews, never an allocation or an automatic plan.
storage.utils.get_craft_plan = function(player_index, product, quantity, max_depth)
    local character = storage.agent_characters[player_index]
    if not character or not character.valid then error("Character unavailable") end
    quantity = math.max(1, math.min(1000000, math.floor(quantity or 1)))
    max_depth = math.max(0, math.min(3, math.floor(max_depth or 2)))
    local nodes, active = 0, {}
    local function read(name, requested, depth)
        nodes = nodes + 1
        local result = {product=name,quantity=requested,craftable_now=0,
            ingredients={},missing_subrecipes={}}
        local recipe = character.force.recipes[name]
        if not recipe then
            result.reason = "no_matching_recipe"
            return result
        end
        result.recipe = recipe.name
        result.enabled = recipe.enabled
        result.category = recipe.category
        local amount = nil
        for _, output in pairs(recipe.products) do
            if output.name == name and output.type == "item" then
                amount = output.amount
                if output.probability and output.probability ~= 1 then amount = nil end
                break
            end
        end
        if not amount or amount <= 0 then
            result.reason = "recipe_has_no_fixed_matching_item_output"
            return result
        end
        local crafts = math.ceil(requested / amount)
        result.items_per_craft, result.crafts_required = amount, crafts
        result.output_quantity = crafts * amount
        result.handcraftable = not not (character.prototype.crafting_categories or {})[recipe.category]
        local native_count = 0
        if recipe.enabled and result.handcraftable then
            native_count = character.get_craftable_count(recipe)
        end
        result.native_craftable_crafts = native_count
        result.craftable_now = native_count * amount
        if not recipe.enabled then result.reason = "recipe_not_researched"
        elseif not result.handcraftable then result.reason = "requires_machine"
        elseif native_count < crafts then result.reason = "insufficient_ingredients" end
        active[name] = true
        for _, ingredient in pairs(recipe.ingredients) do
            local have = ingredient.type == "item" and character.get_item_count(ingredient.name) or 0
            local need = ingredient.amount * crafts
            local missing = math.max(0, need - have)
            result.ingredients[#result.ingredients+1] = {
                item=ingredient.name,type=ingredient.type,have=have,need=need,missing=missing}
            if missing > 0 and character.force.recipes[ingredient.name] then
                if depth < max_depth and nodes < 32 and not active[ingredient.name] then
                    result.missing_subrecipes[#result.missing_subrecipes+1] = read(ingredient.name,missing,depth+1)
                else result.subrecipes_truncated = true end
            end
        end
        active[name] = nil
        return result
    end
    local result = read(product, quantity, 0)
    result.tick = game.tick
    result.schema_version = "craft-menu-v1"
    result.subrecipe_semantics = "independent_previews_shared_inventory_native_craftability_authoritative"
    return result
end
