"""A companion camera palette for the read-only Factorio spectator.

Run with ``uv run python -m fle.cluster.observer_camera`` after ``fle watch``.
RCON camera updates work while tick_paused; no simulation step is requested.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor

from factorio_rcon import RCONClient

from fle.cluster.run_envs import RCON_PASSWORD, START_RCON_PORT


def camera_command(action: str, step: int = 16) -> str:
    if action not in {"left", "right", "up", "down", "home", "in", "out", "status"}:
        raise ValueError("Unknown camera action")
    if type(step) is not int or not 1 <= step <= 64:
        raise ValueError("Camera step must be 1–64 tiles")
    # Only constant action names and validated integers enter the Lua source.
    return " ".join(
        f"""/sc
local p=game.get_player('fle-observer')
if not p or not p.connected then error('Connect fle-observer with fle watch first') end
if p.controller_type ~= defines.controllers.spectator or p.admin or p.cheat_mode then
    error('Camera requires a non-admin, read-only spectator')
end
local group=p.permission_group
if not group or group.allows_action(defines.input_action.build)
    or group.allows_action(defines.input_action.craft) then
    error('Observer permission policy is missing')
end
local tick,paused,speed=game.tick,game.tick_paused,game.speed
local action='{action}'
local target={{x=p.position.x,y=p.position.y}}
local surface=p.surface
if action=='home' then
    if not remote.call('fle_runtime','dispatch','__follow_agent','fle-observer') then
        error('Agent is unavailable')
    end
elseif action=='left' then target.x=target.x-{step}
elseif action=='right' then target.x=target.x+{step}
elseif action=='up' then target.y=target.y-{step}
elseif action=='down' then target.y=target.y+{step}
end
if action=='in' then p.zoom=math.min(4,p.zoom*1.25)
elseif action=='out' then p.zoom=math.max(0.15,p.zoom/1.25)
elseif action~='status' and action~='home' then
    if not surface.is_chunk_generated({{math.floor(target.x/32),math.floor(target.y/32)}}) then
        error('Camera destination is outside generated terrain')
    end
    if not p.teleport(target,surface) then error('Camera movement failed') end
end
rcon.print(helpers.table_to_json({{position=p.position,zoom=p.zoom,
    paused=game.tick_paused,tick=game.tick,
    clock_unchanged=game.tick==tick and game.tick_paused==paused and game.speed==speed}}))
""".splitlines()
    )


def move_camera(action: str, step: int = 16, *, instance: int = 0) -> dict:
    command = camera_command(action, step)
    client = RCONClient(
        "127.0.0.1", START_RCON_PORT + instance, RCON_PASSWORD, timeout=3
    )
    try:
        response = client.send_command(command)
    finally:
        client.close()
    try:
        result = json.loads(response)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(str(response).strip() or "No camera response") from exc
    if not result.get("clock_unchanged"):
        raise RuntimeError("Camera clock invariant failed")
    return result


def main() -> None:
    import tkinter as tk
    from tkinter import ttk

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", type=int, choices=range(33), default=0)
    args = parser.parse_args()
    root = tk.Tk()
    root.title("Factorio observer camera")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    panel = ttk.Frame(root, padding=14)
    panel.grid()
    ttk.Label(panel, text="Look around while the factory is paused").grid(
        row=0, column=0, columnspan=3, pady=(0, 12)
    )
    status = tk.StringVar(value="Connect with fle watch, then use the camera controls.")
    step = tk.IntVar(value=16)
    pool = ThreadPoolExecutor(max_workers=1)
    pending = None

    def submit(action):
        nonlocal pending
        if pending is not None:
            return
        pending = pool.submit(move_camera, action, step.get(), instance=args.instance)
        root.after(30, finish)

    def finish():
        nonlocal pending
        if not pending.done():
            root.after(30, finish)
            return
        try:
            result = pending.result()
            pos = result["position"]
            state = "Paused" if result["paused"] else "Running"
            status.set(
                f"{state} · tick {result['tick']:,}\n"
                f"Camera {pos['x']:.1f}, {pos['y']:.1f} · clock unchanged"
            )
        except Exception as exc:
            status.set(str(exc)[:240])
        pending = None

    for label, action, row, col in (
        ("↑", "up", 1, 1),
        ("←", "left", 2, 0),
        ("Agent", "home", 2, 1),
        ("→", "right", 2, 2),
        ("↓", "down", 3, 1),
        ("Zoom −", "out", 4, 0),
        ("Refresh", "status", 4, 1),
        ("Zoom +", "in", 4, 2),
    ):
        ttk.Button(panel, text=label, command=lambda a=action: submit(a)).grid(
            row=row, column=col, padx=3, pady=3, sticky="ew"
        )
    ttk.Label(panel, text="Pan step (tiles)").grid(
        row=5, column=0, columnspan=2, pady=8
    )
    ttk.Combobox(
        panel, textvariable=step, values=(4, 16, 32, 64), state="readonly", width=6
    ).grid(row=5, column=2)
    ttk.Label(
        panel,
        text="Arrow keys / WASD while this panel has focus.\n"
        "Agent returns to the model. Home does the same.",
    ).grid(row=6, column=0, columnspan=3, pady=8)
    ttk.Label(panel, textvariable=status, wraplength=340).grid(
        row=7, column=0, columnspan=3, sticky="w", pady=(6, 0)
    )
    for key, action in {
        "Left": "left",
        "a": "left",
        "Right": "right",
        "d": "right",
        "Up": "up",
        "w": "up",
        "Down": "down",
        "s": "down",
        "Home": "home",
    }.items():
        root.bind(f"<{key}>", lambda event, a=action: submit(a))

    def close():
        pool.shutdown(wait=False, cancel_futures=True)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    submit("status")
    root.mainloop()


if __name__ == "__main__":
    main()
