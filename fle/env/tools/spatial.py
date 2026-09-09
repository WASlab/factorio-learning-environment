"""Normalize bounded Lua diagnostic arrays without entity-model coercion."""


def normalize_spatial(value):
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if key in {"overlapping_entities", "colliding_tiles"} and isinstance(
                child, dict
            ):
                child = [child[index] for index in sorted(child, key=int)]
            result[key] = normalize_spatial(child)
        return result
    if isinstance(value, list):
        return [normalize_spatial(child) for child in value]
    return value
