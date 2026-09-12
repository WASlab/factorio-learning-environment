from fle.env.tools.observation import ObservationTool, bounded_integer


class GetAvailableTechnologies(ObservationTool):
    def __call__(self, limit=64, offset=0):
        """List enabled, unresearched technologies with completed prerequisites."""
        return self.read(
            bounded_integer(limit, "limit"),
            bounded_integer(offset, "offset", 0, 1000000),
            arrays=("technologies",),
        )
