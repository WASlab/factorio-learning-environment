from fle.env.tools.observation import ObservationTool, name_of


class GetTechnology(ObservationTool):
    def __call__(self, technology):
        """Inspect live research state, prerequisites, cost, trigger and effects."""
        return self.read(
            name_of(technology),
            arrays=(
                "prerequisites",
                "successors",
                "science_cost",
                "effects",
                "unlocks",
            ),
        )
