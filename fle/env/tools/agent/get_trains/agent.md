## get_trains

`get_trains(limit=32, offset=0)`

Returns this force's trains on the current surface, sorted by ID: state, manual_mode, speed (tiles/tick), has_path, position, current_station, destination, native schedule records/current index, cargo, fluids and locomotive fuel. Destination may be absent when there is no path. Rail schedule references are represented by entity_id and position. Fuel includes stored stacks, currently_burning and remaining_burning_energy (joules). No route optimization is performed.


Paginated results include total, offset and truncated. Advance offset by the number of returned entries. limit is 1–128 (get_trains: 1–64); offset is nonnegative. Pagination is a fresh live read, not a snapshot across calls.
