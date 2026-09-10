"""Validate progression modes on the dedicated reference server, port 27010.

The fixture provisions research and a ready rocket to exercise verification;
it does not represent an agent completing a freeplay evaluation.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fle.envd.backend import FLEWorker
from fle.envd.evaluation_modes import TECHNOLOGY_MILESTONES, progression_task_spec
from fle.envd.service import EnvironmentService
from scripts.validate_native_runtime_regressions import lua


def validate():
    artifacts = ROOT / ".runtime/progression-validation"
    artifacts.mkdir(parents=True, exist_ok=True)
    os.environ["FLE_LIFECYCLE_DIR"] = str(artifacts / "checkpoints")
    worker = FLEWorker.connect("progression-validation", tcp_port=27010)
    service = EnvironmentService([worker])
    report = {"passed": False, "rcon_port": 27010}
    lease = None
    try:
        version = lua(worker, "rcon.print(script.active_mods.base)").strip()
        assert version == "2.0.77", version
        report["factorio_version"] = version
        task = progression_task_spec("technology", max_ticks=36000)
        lease = service.lease(task)
        initial = service.observe(lease.lease_id)
        assert initial.evaluation_progress["completed_count"] == 0
        assert not initial.evaluation_progress["success"]
        first = service.execute(lease.lease_id, "print(wait(60))")
        assert first.evaluation_progress["simulation_ticks"] >= 60
        checkpoint = service.checkpoint(
            lease.lease_id, "runner-active-progression-validation"
        )
        elapsed = first.evaluation_progress["simulation_ticks"]
        service.release(lease.lease_id)
        lease = service.lease(
            task.model_copy(update={"checkpoint_id": checkpoint.checkpoint_id})
        )
        restored = service.observe(lease.lease_id).evaluation_progress
        assert restored["simulation_ticks"] == elapsed, (restored, elapsed)
        for name in TECHNOLOGY_MILESTONES[:-1]:
            lua(
                worker,
                f"game.forces.player.technologies[{json.dumps(name)}].researched=true",
            )
        result = service.execute(lease.lease_id, "print(inspect_inventory())")
        assert (
            result.evaluation_progress["completed_count"]
            == len(TECHNOLOGY_MILESTONES) - 1
        )
        assert result.terminal_reason is None
        lua(worker, "game.forces.player.technologies['rocket-silo'].researched=true")
        result = service.execute(lease.lease_id, "print(inspect_inventory())")
        assert result.terminal_reason == "objective_completed"
        final = service.finalize(lease.lease_id)
        assert final.success
        assert final.metrics["evaluation_progress"]["success"]
        report["technology"] = final.metrics["evaluation_progress"]
        report["restored_simulation_ticks"] = elapsed
        service.release(lease.lease_id)

        task = progression_task_spec("rocket_launch")
        lease = service.lease(task)
        assert not service.observe(lease.lease_id).evaluation_progress["success"]
        lua(
            worker,
            """
            local s=game.surfaces[1]
            local tiles={}
            for x=28,44 do for y=-7,7 do
                table.insert(tiles,{name='grass-1',position={x,y}})
            end end
            s.set_tiles(tiles)
            for _,e in pairs(s.find_entities_filtered{area={{28,-7},{44,7}},type={'tree','simple-entity','cliff'}}) do e.destroy() end
            local silo=s.create_entity{name='rocket-silo',position={35.5,0.5},force='player'}
            silo.rocket_parts=100
            silo.energy=1000000000
            s.create_entity{name='electric-energy-interface',position={40,0},force='player'}
            s.create_entity{name='substation',position={40,3},force='player'}
        """,
        )
        worker.instance.set_speed_and_unpause(10)
        ready = "false"
        for _ in range(40):
            ready = lua(
                worker,
                "local s=game.surfaces[1].find_entity('rocket-silo',{35.5,0.5}); rcon.print(s.rocket_silo_status==defines.rocket_silo_status.rocket_ready)",
            ).strip()
            if ready == "true":
                break
            time.sleep(0.25)
        worker.instance.pause()
        assert ready == "true", "Rocket fixture did not become ready"
        # Launch while paused, so the request cannot masquerade as completion.
        assert (
            lua(
                worker,
                "rcon.print(game.surfaces[1].find_entity('rocket-silo',{35.5,0.5}).launch_rocket())",
            ).strip()
            == "true"
        )
        from fle.envd.evaluation_modes import progression_progress

        requested = progression_progress(
            task, worker.initial_telemetry, worker._capture_frame([])
        )
        assert not requested["success"] and requested["rocket_launches"] == 0
        result = service.execute(lease.lease_id, "print(wait(3000))")
        assert result.terminal_reason == "objective_completed", (
            result.evaluation_progress
        )
        checkpoint = service.checkpoint(
            lease.lease_id, "runner-active-progression-rocket"
        )
        service.release(lease.lease_id)
        lease = service.lease(
            task.model_copy(update={"checkpoint_id": checkpoint.checkpoint_id})
        )
        final = service.finalize(lease.lease_id)
        assert final.success, final.metrics
        assert final.metrics["evaluation_progress"]["rocket_launches"] == 1
        report["rocket_launch"] = final.metrics["evaluation_progress"]
        service.release(lease.lease_id)

        lease = service.lease(progression_task_spec("technology", max_ticks=60))
        result = service.execute(lease.lease_id, "print(wait(120))")
        assert result.terminal_reason == "session_tick_limit"
        assert not service.finalize(lease.lease_id).success
        report["tick_limit"] = result.evaluation_progress
        report["passed"] = True
        return report
    finally:
        if lease:
            service.release(lease.lease_id)
        worker.instance.pause()
        (artifacts / "validation.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
