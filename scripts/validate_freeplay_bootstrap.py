"""Native freeplay bootstrap acceptance test on the dedicated reference server.

Run: uv run python scripts/validate_freeplay_bootstrap.py
Resets only fle-reference-factory, never the evaluation servers.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fle.envd.backend import FLEWorker
from fle.envd.models import FactorioTaskSpec, VerifierSpec
from fle.env.game_types import Resource, Prototype
from fle.env import Position
from scripts.validate_reference_factory import start_cluster, ARTIFACTS, lua


def validate():
    start_cluster()
    subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            "fle-reference-factory",
            "-f",
            str(ARTIFACTS / "compose.yaml"),
            "restart",
        ],
        check=True,
    )
    # Do not restage mod-list.json while Factorio is loading its mods.
    from factorio_rcon import RCONClient

    deadline = time.monotonic() + 60
    while True:
        try:
            client = RCONClient("127.0.0.1", 27010, "factorio", timeout=2)
            try:
                ready = client.send_command(
                    "/sc rcon.print(remote.interfaces.fle_runtime and 'ready' or 'missing')"
                )
            finally:
                client.close()
            if ready == "ready":
                break
        except Exception:
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("Reference server did not load the FLE runtime")
        time.sleep(1)
    worker = FLEWorker.connect("freeplay-bootstrap-validation", tcp_port=27010)
    worker.start_task(
        FactorioTaskSpec(
            task_id="freeplay-bootstrap-validation",
            goal="Validate freeplay bootstrap",
            scenario="freeplay",
            checkpoint_id="scenario:freeplay",
            verifier=VerifierSpec(implementation="objective_engine_v1"),
        )
    )
    namespace = worker.instance.first_namespace
    report = {
        "factorio_version": "2.0.77",
        "starting_inventory": str(namespace.inspect_inventory()),
    }
    try:
        assert namespace.inspect_inventory()[Prototype.BurnerMiningDrill] == 1
        assert namespace.inspect_inventory()[Prototype.StoneFurnace] == 1
        report["crash_site_ships"] = int(
            lua(
                worker,
                'rcon.print(game.surfaces[1].count_entities_filtered{name="crash-site-spaceship"})',
            )
        )
        assert report["crash_site_ships"] == 1
        worker.instance.set_speed_and_unpause(10)
        for resource, quantity in [
            (Resource.Wood, 5),
            (Resource.Stone, 5),
            (Resource.IronOre, 5),
            (Resource.Coal, 10),
        ]:
            start = worker._read_game_tick()
            before = namespace.inspect_inventory()[resource[0]]
            amount = namespace.harvest_resource(namespace.nearest(resource), quantity)
            delta = namespace.inspect_inventory()[resource[0]] - before
            elapsed = worker._read_game_tick() - start
            report[resource[0]] = {"returned": amount, "delta": delta, "ticks": elapsed}
            print(resource[0], report[resource[0]], flush=True)
            assert amount == delta and delta >= quantity and elapsed < 3600
        try:
            namespace.nearest(Prototype.IronChest)
        except LookupError as error:
            report["absent_entity"] = str(error)
        else:
            raise AssertionError("No iron chest should exist in the fresh world")
        namespace.craft_item(Prototype.StoneFurnace, 1)
        namespace.craft_item(Prototype.WoodenChest, 1)
        furnace = namespace.place_entity(
            Prototype.StoneFurnace, position=Position(x=20, y=10), exact=False
        )
        namespace.insert_item(Prototype.Coal, furnace, 5)
        namespace.insert_item(Prototype.IronOre, furnace, 5)
        drill = namespace.place_entity(
            Prototype.BurnerMiningDrill,
            position=namespace.nearest(Resource.Coal),
            exact=False,
        )
        namespace.insert_item(Prototype.Coal, drill, 5)
        time.sleep(4)
        report["smelted_plates"] = namespace.inspect_inventory(furnace)[
            Prototype.IronPlate
        ]
        assert report["smelted_plates"] > 0
        report["drill"] = str(
            namespace.get_entity(Prototype.BurnerMiningDrill, drill.position)
        )
        report["passed"] = True
        return report
    finally:
        worker.instance.pause()
        (ARTIFACTS / "freeplay-bootstrap-validation.json").write_text(
            json.dumps(report, indent=2)
        )


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
