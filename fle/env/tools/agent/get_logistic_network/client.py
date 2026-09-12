from fle.env.tools.observation import ObservationTool, bounded_integer


class GetLogisticNetwork(ObservationTool):
    def __call__(self, position, limit=64, offset=0):
        """Read network contents and robot counts at a point in logistic coverage."""
        return self.read(
            *self.position_args(position),
            bounded_integer(limit, "limit"),
            bounded_integer(offset, "offset", 0, 1000000),
            arrays=("contents",),
        )
