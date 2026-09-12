from fle.env.tools.observation import ObservationTool, bounded_integer


class GetTrainStop(ObservationTool):
    def __call__(self, position, limit=64, offset=0):
        """Inspect a station and its scheduled trains, without choosing routes."""
        return self.read(
            *self.position_args(position),
            bounded_integer(limit, "limit"),
            bounded_integer(offset, "offset", 0, 1000000),
            arrays=("scheduled_train_ids",),
        )
