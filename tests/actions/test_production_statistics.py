from unittest.mock import Mock

import pytest

from fle.env.tools.agent.get_production_statistics.client import GetProductionStatistics

pytestmark = pytest.mark.no_factorio


def test_public_statistics_preserves_native_categories_and_arrays():
    tool = GetProductionStatistics.__new__(GetProductionStatistics)
    tool.player_index = 1
    tool.execute = Mock(
        return_value=(
            {
                "entries": {
                    1: {"name": "iron-plate", "produced_total": 5, "consumed_total": 2}
                }
            },
            0,
        )
    )
    result = tool(["iron-plate"], window_seconds=600)
    assert result["entries"] == [
        {"name": "iron-plate", "produced_total": 5, "consumed_total": 2}
    ]
    tool.execute.assert_called_once_with(1, ["iron-plate"], 600, "item", 32)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"window_seconds": 300},
        {"limit": 100},
        {"items": "iron-plate"},
        {"category": "score"},
    ],
)
def test_invalid_statistics_queries_do_not_execute(kwargs):
    tool = GetProductionStatistics.__new__(GetProductionStatistics)
    tool.execute = Mock()
    with pytest.raises(ValueError):
        tool(**kwargs)
    tool.execute.assert_not_called()
