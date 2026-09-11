import json
import zipfile
from pathlib import Path

import pytest

from importlib import resources

from fle.cluster.run_envs import FACTORIO_VERSION, ComposeGenerator
from fle.cluster.runtime_scenario import compile_control, runtime_sources

pytestmark = pytest.mark.no_factorio


def test_bundled_mod_config_is_staged_in_runtime_state(tmp_path):
    generator = ComposeGenerator(state_dir=tmp_path)

    volume = generator._bundled_mods_volume()

    runtime_mods_dir = tmp_path / "mods"
    runtime_mod_list = runtime_mods_dir / "mod-list.json"
    assert volume["source"] == str(runtime_mods_dir.resolve())
    assert volume["target"] == "/opt/factorio/mods"
    assert json.loads(runtime_mod_list.read_text())["mods"][0] == {
        "name": "base",
        "enabled": True,
    }
    assert json.loads(runtime_mod_list.read_text())["mods"][-1] == {
        "name": "fle-runtime",
        "enabled": True,
    }
    assert len(list(runtime_mods_dir.glob("fle-runtime_*.zip"))) == 1


def test_runtime_mod_aligns_burner_drill_drop_point(tmp_path):
    generator = ComposeGenerator(state_dir=tmp_path)
    generator._bundled_mods_volume()

    archive = next((tmp_path / "mods").glob("fle-runtime_*.zip"))
    with zipfile.ZipFile(archive) as bundle:
        entry = next(
            name for name in bundle.namelist() if name.endswith("data-updates.lua")
        )
        source = bundle.read(entry).decode("utf-8")
    assert 'data.raw["mining-drill"]["burner-mining-drill"]' in source
    assert "vector_to_place_result = {0, -1.5}" in source


def test_cluster_mounts_generated_runtime_mod_directory(tmp_path):
    generator = ComposeGenerator(state_dir=tmp_path)
    service = generator.services_dict(1)["factorio_0"]

    mods = [
        volume
        for volume in service["volumes"]
        if volume["target"] == "/opt/factorio/mods"
    ]
    assert mods == [
        {
            "source": str((tmp_path / "mods").resolve()),
            "target": "/opt/factorio/mods",
            "type": "bind",
        }
    ]


def test_cluster_records_normal_map_identity(tmp_path):
    generator = ComposeGenerator(state_dir=tmp_path, map_gen_seed=8675309)
    service = generator.services_dict(1)["factorio_0"]

    assert generator.scenario == "open_world"
    assert "--map-gen-seed 8675309" in service["command"]
    assert service["labels"] == {
        "fle.scenario": "open_world",
        "fle.map-seed": "8675309",
    }


def test_cluster_pins_supported_factorio_and_packages_observer_policy(tmp_path):
    generator = ComposeGenerator(state_dir=tmp_path)

    assert generator.image == f"factoriotools/factorio:{FACTORIO_VERSION}"
    assert "--use-server-whitelist" in generator._command()
    config = resources.files("fle.cluster") / "config/server-whitelist.json"
    assert json.loads(config.read_text()) == ["fle-observer"]
    server_settings = resources.files("fle.cluster") / "config/server-settings.json"
    assert json.loads(server_settings.read_text())["allow_commands"] == "admins-only"

    scenario = (resources.files("fle") / "env/mods/observer.lua").read_text()
    assert 'local observer_name = "fle-observer"' in scenario
    assert "defines.controllers.spectator" in scenario
    assert "storage.agent_characters[1]" in scenario


def test_cluster_uses_packaged_scenario_with_runtime_supplied_by_mod(tmp_path):
    generator = ComposeGenerator(state_dir=tmp_path)

    volume = generator._scenarios_volume()

    packaged = Path(resources.files("fle.cluster") / "scenarios")
    assert volume["source"] == str(packaged.resolve())


def test_runtime_compiler_multiplexes_callbacks_and_keeps_callables_local():
    env_dir = Path(resources.files("fle") / "env")

    control = compile_control('util = require("util")', env_dir, "fle-observer")

    assert len(runtime_sources(env_dir)) > 50
    assert "fle_on_event('mods/alerts.lua', defines.events.on_tick" in control
    assert "fle_on_event('mods/utils.lua', defines.events.on_tick" in control
    assert 'remote.add_interface("fle_runtime"' in control
    assert "storage.actions" not in control
    assert "storage.utils" not in control
    assert "player.opened" not in control
    assert 'error = "product_depot_capacity_reached"' in control
    assert "bindings[entity.unit_number] = true" in control


def test_cluster_stages_persistent_observer_password(tmp_path):
    generator = ComposeGenerator(state_dir=tmp_path)

    first = generator._config_volume()
    first_password = json.loads(
        (tmp_path / "config" / "server-settings.json").read_text()
    )["game_password"]
    second = generator._config_volume()
    second_password = json.loads(
        (tmp_path / "config" / "server-settings.json").read_text()
    )["game_password"]

    assert first["source"] == str((tmp_path / "config").resolve())
    assert second["source"] == first["source"]
    assert first_password
    assert second_password == first_password
