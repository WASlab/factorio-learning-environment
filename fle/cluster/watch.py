"""Validate and launch a local read-only Factorio observer client."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from factorio_rcon import RCONClient
import psutil

from fle.cluster.run_envs import (
    FACTORIO_VERSION,
    OBSERVER_NAME,
    RCON_PASSWORD,
    START_GAME_PORT,
    START_RCON_PORT,
    resolve_state_dir,
)


def _factorio_candidates(explicit: str | None = None) -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if os.getenv("FACTORIO_EXE"):
        candidates.append(Path(os.environ["FACTORIO_EXE"]).expanduser())
    candidates.extend(
        [
            Path(r"E:\GameFiles\Factorio\bin\x64\factorio.exe"),
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
            / "Steam/steamapps/common/Factorio/bin/x64/factorio.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Factorio/bin/x64/factorio.exe",
        ]
    )
    return candidates


def find_factorio_executable(explicit: str | None = None) -> Path:
    for candidate in _factorio_candidates(explicit):
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError(
        "Factorio executable not found. Pass --factorio-exe or set FACTORIO_EXE."
    )


def factorio_version(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    match = re.search(r"Version:\s+(\d+\.\d+\.\d+)", completed.stdout)
    if not match:
        raise RuntimeError("Could not read the local Factorio version.")
    return match.group(1)


def server_version(rcon_port: int) -> str:
    client = RCONClient("127.0.0.1", rcon_port, RCON_PASSWORD)
    try:
        return client.send_command("/sc rcon.print(script.active_mods.base)").strip()
    finally:
        client.close()


def observer_policy_ready(rcon_port: int) -> bool:
    client = RCONClient("127.0.0.1", rcon_port, RCON_PASSWORD)
    try:
        response = client.send_command(
            "/sc rcon.print(helpers.table_to_json("
            "remote.call('fle_runtime', 'dispatch', '__observer_status')))"
        )
        policy = json.loads(response)
        return bool(
            policy.get("runtime")
            and policy.get("connected")
            and policy.get("spectator")
            and policy.get("read_only")
        )
    finally:
        client.close()


def runtime_ready(rcon_port: int) -> bool:
    client = RCONClient("127.0.0.1", rcon_port, RCON_PASSWORD)
    try:
        response = client.send_command(
            "/sc rcon.print(remote.interfaces['fle_runtime'] and "
            "remote.interfaces['fle_runtime']['dispatch'] and 'true' or 'false')"
        )
        return response.strip() == "true"
    finally:
        client.close()


def observer_password() -> str:
    settings_path = resolve_state_dir() / "config" / "server-settings.json"
    try:
        password = json.loads(settings_path.read_text(encoding="utf-8"))[
            "game_password"
        ]
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(
            "Observer credentials are unavailable. Regenerate the cluster first."
        ) from exc
    if not password:
        raise RuntimeError("The running cluster has no observer password.")
    return str(password)


def prepare_observer_mods() -> Path:
    """Create an isolated client mod directory matching the local FLE server."""

    state_dir = resolve_state_dir()
    server_mods = state_dir / "mods"
    server_mod_list = server_mods / "mod-list.json"
    try:
        mod_config = json.loads(server_mod_list.read_text(encoding="utf-8"))
    except (FileNotFoundError, TypeError, ValueError):
        # Factorio can truncate a bind-mounted mod-list before its atomic
        # replacement fails on Windows. The mounted archives remain the
        # authoritative description of the runtime in that case.
        mods = [{"name": "base", "enabled": True}]
        for archive in sorted(server_mods.glob("*.zip")):
            try:
                with zipfile.ZipFile(archive) as bundle:
                    info_name = next(
                        name
                        for name in bundle.namelist()
                        if name.endswith("/info.json")
                    )
                    mod_name = str(json.loads(bundle.read(info_name))["name"])
            except (
                KeyError,
                StopIteration,
                TypeError,
                ValueError,
                zipfile.BadZipFile,
            ) as exc:
                raise RuntimeError(
                    f"Could not identify server mod archive {archive.name}."
                ) from exc
            mods.append({"name": mod_name, "enabled": True})
        if len(mods) == 1:
            raise RuntimeError(
                "The running cluster mod manifest and archives are unavailable. "
                "Regenerate the cluster first."
            )
        mod_config = {"mods": mods}

    client_mods = state_dir / "observer-mods"
    client_mods.mkdir(parents=True, exist_ok=True)
    for stale in client_mods.glob("*.zip"):
        stale.unlink()
    for archive in server_mods.glob("*.zip"):
        shutil.copy2(archive, client_mods / archive.name)

    mods = list(mod_config.get("mods", []))
    configured_names = {str(mod.get("name")) for mod in mods}
    # Installed expansion mods default to enabled when absent from mod-list.json.
    # The FLE server is base-game only, so make that choice explicit for clients.
    for official_mod in ("elevated-rails", "quality", "space-age"):
        if official_mod not in configured_names:
            mods.append({"name": official_mod, "enabled": False})
    (client_mods / "mod-list.json").write_text(
        json.dumps({"mods": mods}, indent=2) + "\n",
        encoding="utf-8",
    )
    return client_mods.resolve()


def prepare_observer_profile(executable: Path) -> Path:
    """Create an isolated Factorio profile so normal clients do not hold its lock."""

    profile = resolve_state_dir() / "observer-client"
    profile.mkdir(parents=True, exist_ok=True)
    source_player_data = (
        Path(os.environ.get("APPDATA", "")) / "Factorio" / "player-data.json"
    )
    player_data: dict = {}
    if source_player_data.is_file():
        try:
            player_data = json.loads(source_player_data.read_text(encoding="utf-8"))
        except (TypeError, ValueError):
            player_data = {}
    player_data["service-username"] = OBSERVER_NAME
    player_data["service-token"] = ""
    (profile / "player-data.json").write_text(
        json.dumps(player_data, indent=2) + "\n", encoding="utf-8"
    )

    read_data = (executable.parents[2] / "data").as_posix()
    config_path = profile / "config.ini"
    config_path.write_text(
        f"[path]\nread-data={read_data}\nwrite-data={profile.resolve().as_posix()}\n",
        encoding="utf-8",
    )
    return config_path.resolve()


def observer_connected(rcon_port: int) -> bool:
    client = RCONClient("127.0.0.1", rcon_port, RCON_PASSWORD)
    try:
        return (
            client.send_command(
                "/sc local p=game.get_player('fle-observer'); "
                "rcon.print(p and p.connected and 'true' or 'false')"
            ).strip()
            == "true"
        )
    finally:
        client.close()


def enabled_client_mods() -> list[str]:
    appdata = os.getenv("APPDATA")
    if not appdata:
        return []
    path = Path(appdata) / "Factorio/mods/mod-list.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        str(mod["name"])
        for mod in data.get("mods", [])
        if mod.get("enabled") and mod.get("name") != "base"
    ]


def check_observer(
    *, instance: int = 0, factorio_exe: str | None = None
) -> tuple[Path, int]:
    executable = find_factorio_executable(factorio_exe)
    local_version = factorio_version(executable)
    rcon_port = START_RCON_PORT + instance
    try:
        remote_version = server_version(rcon_port)
    except Exception as exc:
        raise RuntimeError(
            f"Factorio instance {instance} is not reachable on RCON port {rcon_port}."
        ) from exc
    if local_version != remote_version:
        raise RuntimeError(
            f"Version mismatch: local client is {local_version}, server is {remote_version}."
        )
    if remote_version != FACTORIO_VERSION:
        raise RuntimeError(
            f"Server is {remote_version}, but this checkout requires {FACTORIO_VERSION}."
        )
    if not runtime_ready(rcon_port):
        raise RuntimeError(
            "This cluster predates the joinable FLE runtime. Restart the cluster once; "
            "future observer sessions can join and reconnect during evaluations."
        )

    extras = enabled_client_mods()
    print(f"Observer client: {executable}")
    print(f"Factorio version: {local_version} (client and server match)")
    print(f"Observer identity: {OBSERVER_NAME}")
    if extras:
        print(
            "Client has enabled DLC/mods: "
            + ", ".join(extras)
            + ". Factorio may ask to synchronize to the base-game server."
        )
    return executable, START_GAME_PORT + instance


def launch_camera(instance: int = 0) -> None:
    """Keep one companion palette per observed instance."""
    for process in psutil.process_iter(["cmdline"]):
        command = process.info["cmdline"] or []
        if "fle.cluster.observer_camera" not in command:
            continue
        try:
            index = command.index("--instance")
            existing_instance = int(command[index + 1])
        except ValueError:
            existing_instance = 0
        except IndexError:
            continue
        if existing_instance == instance:
            return
    executable = Path(sys.executable)
    if os.name == "nt" and executable.with_name("pythonw.exe").exists():
        executable = executable.with_name("pythonw.exe")
    subprocess.Popen(
        [
            str(executable),
            "-m",
            "fle.cluster.observer_camera",
            "--instance",
            str(instance),
        ],
        cwd=str(Path(__file__).resolve().parents[2]),
    )


def watch(
    *,
    instance: int = 0,
    factorio_exe: str | None = None,
    check_only: bool = False,
) -> None:
    executable, game_port = check_observer(instance=instance, factorio_exe=factorio_exe)
    if check_only:
        print(f"Observer connection ready at 127.0.0.1:{game_port}.")
        return
    rcon_port = START_RCON_PORT + instance
    if observer_connected(rcon_port):
        if not observer_policy_ready(rcon_port):
            raise RuntimeError(
                "The connected observer does not have the required policy."
            )
        print("fle-observer is already connected in read-only spectator mode.")
        launch_camera(instance)
        return
    print(
        "Launching Factorio with the isolated FLE observer runtime. The server "
        "accepts only the reserved fle-observer identity."
    )
    observer_mods = prepare_observer_mods()
    observer_config = prepare_observer_profile(executable)
    process = subprocess.Popen(
        [
            str(executable),
            "--config",
            str(observer_config),
            "--mod-directory",
            str(observer_mods),
            "--mp-connect",
            f"127.0.0.1:{game_port}",
            "--password",
            observer_password(),
        ],
        cwd=str(executable.parent),
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
    )
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"Factorio observer client exited before connecting (code {return_code})."
            )
        try:
            connected = observer_connected(rcon_port)
        except Exception:
            connected = False
        if connected:
            if not observer_policy_ready(rcon_port):
                raise RuntimeError("The scenario did not apply the observer policy.")
            print("fle-observer connected in read-only spectator mode.")
            launch_camera(instance)
            return
        time.sleep(1)
    raise RuntimeError("Timed out waiting for fle-observer to join the server.")
