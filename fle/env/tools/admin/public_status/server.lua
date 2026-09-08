storage.actions.public_status = function(player_index, after_sequence)
    local character = storage.agent_characters[player_index]
    if not character or not character.valid then
        return {available=false, reason="character_unavailable"}
    end
    return storage.utils.read_public_status(character.force.index, after_sequence or 0)
end
