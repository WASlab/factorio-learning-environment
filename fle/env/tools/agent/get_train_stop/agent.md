## get_train_stop

`get_train_stop(position, limit=64, offset=0)`

Position must identify one train stop belonging to the character's force. Returns name, entity_id, position, trains_limit, inbound_or_stopped_count, stopped_train_id when present, and scheduled_train_ids. Scheduled trains may target another same-named stop; they are not all inbound. inbound_or_stopped_count uses the engine's association count, which may count a train more than once. get_trains supplies train details.


Paginated results include total, offset and truncated. Advance offset by the number of returned entries. limit is 1–128 (get_trains: 1–64); offset is nonnegative. Pagination is a fresh live read, not a snapshot across calls.
