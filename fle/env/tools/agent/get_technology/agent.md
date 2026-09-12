## get_technology

`get_technology(technology)`

Accepts a Technology enum or canonical name. Returns live researched/enabled/researchable state, can_queue, prerequisites, successors, science_cost (per-unit and total), unit_count, unit_time_seconds, level, effects, unlocks, research_trigger, progress and tick. researchable means enabled with completed prerequisites and not yet researched; trigger research can be researchable but cannot be queued. Costs use the current force/technology level. This is a live read; factorio_get_technology is the separate pinned reference lookup.
