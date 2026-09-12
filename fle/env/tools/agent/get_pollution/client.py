from fle.env.tools.observation import ObservationTool, bounded_integer


class GetPollution(ObservationTool):
    def __call__(self, position, radius_chunks=0):
        """Read pollution in generated chunks around a point; no enemy inference."""
        return self.read(
            *self.position_args(position),
            bounded_integer(radius_chunks, "radius_chunks", 0, 8),
            arrays=("chunks",),
        )
