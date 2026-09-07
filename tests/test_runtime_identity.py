from pathlib import Path
from unittest.mock import Mock

import pytest

from fle.cluster.runtime_scenario import runtime_build_id, compile_control
from fle.env.lua_manager import LuaScriptManager

pytestmark = pytest.mark.no_factorio


def test_generated_runtime_exposes_identity_of_current_sources():
    env = Path(__file__).parents[1] / "fle/env"
    code = compile_control("", env, "fle-observer")
    assert f"return '{runtime_build_id(env)}'" in code


@pytest.mark.parametrize("identity", ["unversioned", "different-build"])
def test_stale_runtime_rejected_before_loading_or_resetting_world(identity):
    client = Mock()
    client.send_command.side_effect = ["true", identity]
    with pytest.raises(RuntimeError, match="stale FLE Lua runtime"):
        LuaScriptManager(client)
    assert client.send_command.call_count == 2
