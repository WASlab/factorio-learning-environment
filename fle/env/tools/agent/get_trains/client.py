from fle.env.tools.observation import ObservationTool, bounded_integer


class GetTrains(ObservationTool):
    def __call__(self, limit=32, offset=0):
        """Read this force's trains on the current surface, sorted by train ID."""
        return self.read(
            bounded_integer(limit, "limit", 1, 64),
            bounded_integer(offset, "offset", 0, 1000000),
            arrays=("trains",),
            nested_arrays=("cargo", "fuel", "contents", "records", "wait_conditions"),
        )
