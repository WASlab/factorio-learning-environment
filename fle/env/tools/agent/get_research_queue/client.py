from fle.env.tools.observation import ObservationTool


class GetResearchQueue(ObservationTool):
    def __call__(self):
        """Read the native ordered research queue and current progress."""
        return self.read(arrays=("queue",))
