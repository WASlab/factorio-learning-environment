## get_available_technologies

`get_available_technologies(limit=64, offset=0)`

Returns technologies with completed prerequisites that are enabled, visible and unresearched. Each entry contains name, level, can_queue and an optional research_trigger. Includes trigger research so the agent can discover its required action. Names are sorted. No recommendation or research selection is performed.


Paginated results include total, offset and truncated. Advance offset by the number of returned entries. limit is 1–128 (get_trains: 1–64); offset is nonnegative. Pagination is a fresh live read, not a snapshot across calls.
