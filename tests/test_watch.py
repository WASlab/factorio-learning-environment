import json
from pathlib import Path
from unittest.mock import patch

import pytest

from fle.cluster.watch import (
    FACTORIO_VERSION,
    check_observer,
    prepare_observer_mods,
    prepare_observer_profile,
)

pytestmark = pytest.mark.no_factorio


@patch("fle.cluster.watch.enabled_client_mods", return_value=[])
@patch("fle.cluster.watch.runtime_ready", return_value=True)
@patch("fle.cluster.watch.server_version", return_value=FACTORIO_VERSION)
@patch("fle.cluster.watch.factorio_version", return_value=FACTORIO_VERSION)
@patch("fle.cluster.watch.find_factorio_executable")
def test_observer_check_requires_matching_versions(
    find_executable, _local_version, _server_version, _runtime, _mods
):
    find_executable.return_value = Path("factorio.exe")

    executable, port = check_observer(instance=2)

    assert executable == Path("factorio.exe")
    assert port == 34199


@patch("fle.cluster.watch.server_version", return_value="2.0.76")
@patch("fle.cluster.watch.factorio_version", return_value=FACTORIO_VERSION)
@patch("fle.cluster.watch.find_factorio_executable", return_value=Path("factorio.exe"))
def test_observer_check_rejects_version_mismatch(*_mocks):
    with pytest.raises(RuntimeError, match="Version mismatch"):
        check_observer()


@patch("fle.cluster.watch.enabled_client_mods", return_value=[])
@patch("fle.cluster.watch.runtime_ready", return_value=False)
@patch("fle.cluster.watch.server_version", return_value=FACTORIO_VERSION)
@patch("fle.cluster.watch.factorio_version", return_value=FACTORIO_VERSION)
@patch("fle.cluster.watch.find_factorio_executable", return_value=Path("factorio.exe"))
def test_observer_check_rejects_legacy_runtime(*_mocks):
    with pytest.raises(RuntimeError, match="predates the joinable FLE runtime"):
        check_observer()


def test_observer_mods_match_server_and_disable_installed_expansions(tmp_path):
    server_mods = tmp_path / "mods"
    server_mods.mkdir()
    (server_mods / "fle-runtime_0.1.0.zip").write_bytes(b"runtime")
    (server_mods / "mod-list.json").write_text(
        json.dumps(
            {
                "mods": [
                    {"name": "base", "enabled": True},
                    {"name": "fle-runtime", "enabled": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    with patch("fle.cluster.watch.resolve_state_dir", return_value=tmp_path):
        client_mods = prepare_observer_mods()

    assert (client_mods / "fle-runtime_0.1.0.zip").read_bytes() == b"runtime"
    mods = {
        mod["name"]: mod["enabled"]
        for mod in json.loads((client_mods / "mod-list.json").read_text())["mods"]
    }
    assert mods == {
        "base": True,
        "fle-runtime": True,
        "elevated-rails": False,
        "quality": False,
        "space-age": False,
    }


def test_observer_mods_recover_from_truncated_server_manifest(tmp_path):
    import zipfile

    server_mods = tmp_path / "mods"
    server_mods.mkdir()
    (server_mods / "mod-list.json").write_text("")
    with zipfile.ZipFile(server_mods / "fle-runtime_0.1.0.zip", "w") as bundle:
        bundle.writestr(
            "fle-runtime_0.1.0/info.json",
            json.dumps({"name": "fle-runtime", "version": "0.1.0"}),
        )

    with patch("fle.cluster.watch.resolve_state_dir", return_value=tmp_path):
        client_mods = prepare_observer_mods()

    mods = {
        mod["name"]: mod["enabled"]
        for mod in json.loads((client_mods / "mod-list.json").read_text())["mods"]
    }
    assert mods == {
        "base": True,
        "fle-runtime": True,
        "elevated-rails": False,
        "quality": False,
        "space-age": False,
    }


def test_observer_profile_uses_reserved_identity_and_isolated_write_data(
    tmp_path, monkeypatch
):
    appdata = tmp_path / "appdata"
    source = appdata / "Factorio" / "player-data.json"
    source.parent.mkdir(parents=True)
    source.write_text(
        json.dumps({"service-username": "human", "service-token": "secret"}),
        encoding="utf-8",
    )
    executable = tmp_path / "Factorio" / "bin" / "x64" / "factorio.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setenv("APPDATA", str(appdata))

    with patch("fle.cluster.watch.resolve_state_dir", return_value=tmp_path):
        config = prepare_observer_profile(executable)

    profile = tmp_path / "observer-client"
    player_data = json.loads((profile / "player-data.json").read_text())
    assert player_data["service-username"] == "fle-observer"
    assert player_data["service-token"] == ""
    assert f"write-data={profile.resolve().as_posix()}" in config.read_text()
