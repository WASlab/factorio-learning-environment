## get_circuit_network

`get_circuit_network(position, wire='red', connector_id=None, limit=64, offset=0)`

Position must identify one wired entity on the character's surface and force. wire is red or green. Returns networks separately per connector, each with connector_id, network_id, connected_circuit_count and live signals (including type and quality). Optional connector_id selects one connector. An empty networks list means no connected network of the requested color/connector. Inputs and outputs of combinators are never merged. Arithmetic, decider and selector combinators also return their native configuration. No connections are created.


Paginated results include total, offset and truncated. Advance offset by the number of returned entries. limit is 1–128 (get_trains: 1–64); offset is nonnegative. Pagination is a fresh live read, not a snapshot across calls.
