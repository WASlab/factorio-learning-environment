## get_logistic_network

`get_logistic_network(position, limit=64, offset=0)`

Position must be inside the current force's logistic coverage on the character's surface. Returns connected, network_id, roboport_count, contents (name, quality, count), logistics_robots and construction_robots (available/total). Outside coverage returns connected=False. Contents are native network inventory counts, not unreserved quantities or a delivery promise. No per-entity scan or routing plan is produced.


Paginated results include total, offset and truncated. Advance offset by the number of returned entries. limit is 1–128 (get_trains: 1–64); offset is nonnegative. Pagination is a fresh live read, not a snapshot across calls.
