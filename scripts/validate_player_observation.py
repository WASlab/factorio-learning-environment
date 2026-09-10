"""Exercise player observation HTTP boundaries on isolated Factorio port 27010."""

import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from fle.envd.api import create_app
from fle.envd.backend import FLEWorker
from fle.envd.camera import persist_camera_snapshot
from fle.envd.evaluation_modes import progression_task_spec
from fle.envd.service import EnvironmentService
from scripts.validate_reference_factory import lua


def validate():
    output = ROOT / ".runtime/player-observation-validation"
    output.mkdir(parents=True, exist_ok=True)
    os.environ["FLE_LIFECYCLE_DIR"] = str(output / "checkpoints")
    worker = FLEWorker.connect("player-observation-validation", tcp_port=27010)
    assert lua(worker, "rcon.print(script.active_mods.base)").strip() == "2.0.77"
    service = EnvironmentService([worker])
    api = TestClient(create_app(service))
    task = progression_task_spec("technology", max_ticks=36000)
    lease = service.lease(task)
    prefix = f"/v1/leases/{lease.lease_id}"
    try:
        near = api.get(prefix + "/camera").json()
        assert near["settings"]["enabled"] and near["settings"]["radius"] == 32, near
        png = base64.b64decode(near["image_base64"])
        assert png.startswith(b"\x89PNG"), near
        (output / "near.png").write_bytes(png)
        assert near["objective"]["mode"] == "technology", near
        assert len(near["objective"]["progress"]["milestones"]) == 6, near
        wide = api.post(prefix + "/camera", json={"radius": 96}).json()
        assert "image_base64" in wide and wide["settings"]["radius"] == 96, wide
        (output / "wide.png").write_bytes(base64.b64decode(wide["image_base64"]))
        craft = api.get(
            prefix + "/craft-plan", params={"product": "transport-belt", "quantity": 3}
        ).json()
        assert craft["crafts_required"] == 2 and craft["ingredients"], craft
        production = service.query_state(
            lease.lease_id, kind="production", item="iron-plate", window_seconds=60
        )
        assert production["statistics"]["item"]["entries"][0]["name"] == "iron-plate", (
            production
        )
        assert production["statistics"]["fluid"]["unknown_products"] == [
            "iron-plate"
        ], production
        disabled = api.post(prefix + "/camera", json={"enabled": False}).json()
        assert disabled["enabled"] is False and "image_base64" not in disabled, disabled
        assert disabled["objective"]["mode"] == "technology", disabled
        checkpoint = service.checkpoint(lease.lease_id, "player-observation-validation")
        service.release(lease.lease_id)
        lease = service.lease(
            task.model_copy(update={"checkpoint_id": checkpoint.checkpoint_id})
        )
        restored = service.camera(lease.lease_id)
        assert restored["enabled"] is False and restored["settings"]["radius"] == 96, (
            restored
        )
        fixture = output / "ui-results" / "isolated-player-view-validation"
        fixture.mkdir(parents=True, exist_ok=True)
        persist_camera_snapshot(fixture / "session-epochs/tool-results", near)
        (fixture / "session.json").write_text(
            json.dumps(
                {
                    "run_id": "isolated-player-view-validation",
                    "schema_version": "factorio-progression-session-v1",
                    "evaluation_mode": "technology",
                    "started_at": "2026-09-09T00:00:00Z",
                    "status": "completed",
                    "success": False,
                    "termination_reason": "Isolated UI validation fixture",
                    "participant": {
                        "model_snapshot": "Validation fixture (not an agent evaluation)",
                        "provider": "test",
                        "harness_version": "test",
                    },
                    "task": task.model_dump(mode="json"),
                    "progress": near["objective"]["progress"],
                    "runner_wall_seconds": 0,
                    "interventions": 0,
                }
            ),
            encoding="utf-8",
        )
        report = {
            "passed": True,
            "factorio_version": "2.0.77",
            "near_image_bytes": len(png),
            "wide_image_bytes": wide["image_bytes"],
            "restored_settings": restored["settings"],
            "craft_plan": craft,
            "production": production["statistics"],
        }
        (output / "validation.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
    finally:
        service.release(lease.lease_id)
        worker.instance.pause()


if __name__ == "__main__":
    validate()
