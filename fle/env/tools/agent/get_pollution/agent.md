## get_pollution

`get_pollution(position, radius_chunks=0)`

Returns a square of chunks centered on the position, each with chunk x/y, generated and pollution, plus chunk_size=32, surface and tick. Radius is 0–8 chunks (at most 289 entries). Ungenerated chunks omit pollution. This follows the camera's generated-surface visibility because detached agent characters do not maintain a player chart. Values are native pollution amounts per chunk, not emissions rates, forecasts, enemy positions or attack predictions.
