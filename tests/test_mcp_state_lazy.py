"""MCP state construction must not connect to a live Factorio server."""

import importlib

import pytest

mcp_state_module = importlib.import_module("fle.env.protocols._mcp.state")

pytestmark = pytest.mark.no_factorio


def test_factorio_mcp_state_construction_is_side_effect_free(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("construction must not enumerate or connect to servers")

    monkeypatch.setattr(mcp_state_module, "list_available_environments", boom)
    state = mcp_state_module.FactorioMCPState()
    assert state.gym_env is None
