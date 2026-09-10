from typing import Any

from fle.env.tools import Tool


class CustomerDepot(Tool):
    """Admin interface to customer-owned sink depots (contract fulfillment)."""

    @staticmethod
    def _require_mapping(response: Any) -> dict[str, Any]:
        if not isinstance(response, dict):
            raise RuntimeError(
                "Customer depot returned malformed telemetry: "
                f"expected an object, received {type(response).__name__}: "
                f"{str(response)[:240]}"
            )
        return response

    def __call__(
        self,
        command: str = "telemetry",
        x: float = 0,
        y: float = 0,
        chest_count: int = 8,
        relative: bool = True,
    ) -> dict[str, Any]:
        response, _ = self.execute(
            self.player_index, command, x, y, chest_count, relative
        )
        return self._require_mapping(response)

    def place(self, x: float, y: float, chest_count: int = 8) -> dict[str, Any]:
        return self.__call__("place", x, y, chest_count)

    def telemetry(self) -> dict[str, Any]:
        return self.__call__("telemetry")

    def clear(self) -> dict[str, Any]:
        return self.__call__("clear")

    def designated(self) -> dict[str, Any]:
        return self.__call__("designated")

    def configure(self, products: list[dict[str, Any]]) -> dict[str, Any]:
        response, _ = self.execute(
            self.player_index, "configure", products, 0, 0, False
        )
        return self._require_mapping(response)

    def adopt(self, depot_specs: list[dict[str, Any]]) -> dict[str, Any]:
        response, _ = self.execute(self.player_index, "adopt", depot_specs, 0, 0, False)
        return self._require_mapping(response)
