from datetime import datetime, timezone
import base64

import pytest

from fle.envd.backend import FactorioWorker
from fle.envd.models import (
    ActionEvent,
    ExecutionResult,
    FactorioTaskSpec,
    Observation,
    RewardVector,
    VerificationSnapshot,
)


class FakeWorker(FactorioWorker):
    def __init__(self, worker_id="worker-0"):
        self.worker_id = worker_id
        self.active_task = None
        self.release_count = 0
        self.score = 0.0

    def start_task(self, task: FactorioTaskSpec) -> str:
        self.active_task = task
        self.score = 0.0
        return f"initial-{task.fingerprint[:12]}"

    def execute(self, lease_id: str, code: str, sequence: int) -> ExecutionResult:
        self.score += 1.0
        event = ActionEvent(
            sequence=sequence,
            code_sha256=f"code-{sequence}",
            started_at=datetime.now(timezone.utc),
            duration_seconds=0.01,
            reward_delta=1.0,
            result=f"executed: {code}",
            ticks=sequence * 60,
        )
        return ExecutionResult(
            lease_id=lease_id,
            event=event,
            production_score=self.score,
            automated_production_score=self.score,
            state_hash=f"state-{sequence}",
        )

    def observe(self, lease_id: str) -> Observation:
        return Observation(
            lease_id=lease_id,
            task_id=self.active_task.task_id,
            ticks=int(self.score * 60),
            production_score=self.score,
            automated_production_score=self.score,
            state_hash=f"state-{int(self.score)}",
        )

    def render_factory(
        self,
        lease_id: str,
        *,
        center_x=None,
        center_y=None,
        radius=32,
        include_status=True,
    ):
        del lease_id, center_x, center_y
        png = b"\x89PNG\r\n\x1a\nfixture"
        return {
            "schema_version": "factorio-factory-render-v1",
            "media_type": "image/png",
            "image_base64": base64.b64encode(png).decode("ascii"),
            "image_sha256": "fixture",
            "image_bytes": len(png),
            "ticks": int(self.score * 60),
            "include_status": include_status,
            "viewport": {
                "center_x": 0,
                "center_y": 0,
                "width_tiles": radius * 2,
                "height_tiles": radius * 2,
            },
        }

    def finalize(self, lease_id, task, events):
        return VerificationSnapshot(
            lease_id=lease_id,
            task_id=task.task_id,
            task_fingerprint=task.fingerprint,
            success=self.score > 0,
            scalar_reward=self.score,
            rewards=RewardVector(task=float(self.score > 0), progress=self.score),
            metrics={"interventions": len(events)},
            terminal_state_hash=f"state-{int(self.score)}",
            action_events=events,
        )

    def release(self) -> None:
        self.active_task = None
        self.release_count += 1


@pytest.fixture
def task_spec():
    return FactorioTaskSpec(
        task_id="iron_plate_throughput",
        goal="Produce iron plates automatically.",
        max_interventions=2,
        holdout_seconds=1,
    )
