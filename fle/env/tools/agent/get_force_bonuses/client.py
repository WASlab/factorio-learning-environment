from fle.env.tools.observation import ObservationTool


class GetForceBonuses(ObservationTool):
    def __call__(self):
        """Read force research bonuses; fractional modifiers are additive."""
        return self.read(arrays=("ammo",))
