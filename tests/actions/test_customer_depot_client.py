import pytest

from fle.env.tools.admin.customer_depot.client import CustomerDepot


pytestmark = pytest.mark.no_factorio


def test_customer_depot_rejects_non_mapping_lua_response():
    depot = CustomerDepot.__new__(CustomerDepot)
    depot.player_index = 1
    depot.execute = lambda *args: (
        "ERR:LuaEntity API call when LuaEntity was invalid.",
        0.0,
    )

    with pytest.raises(RuntimeError, match="malformed telemetry"):
        depot.telemetry()
