from fle.env.tools.observation import ObservationTool, bounded_integer


class GetCircuitNetwork(ObservationTool):
    def __call__(self, position, wire="red", connector_id=None, limit=64, offset=0):
        """Read signals per connector; combinator inputs and outputs stay separate."""
        if wire not in {"red", "green"}:
            raise ValueError("wire must be red or green")
        if connector_id is not None:
            bounded_integer(connector_id, "connector_id", 1, 1000)
        return self.read(
            *self.position_args(position),
            wire,
            connector_id,
            bounded_integer(limit, "limit"),
            bounded_integer(offset, "offset", 0, 1000000),
            arrays=("networks",),
            nested_arrays=("signals",),
        )
