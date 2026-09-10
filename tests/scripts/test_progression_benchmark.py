import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fle.envd.evaluation_modes import progression_progress, progression_task_spec
from scripts import adaptive_contract_benchmark as harness
from scripts import progression_benchmark as runner
from tests.envd.test_objective_engine import frame

pytestmark = pytest.mark.no_factorio


def arguments(tmp_path, mode="technology"):
    return harness.build_parser().parse_args(
        [
            "--mode",
            mode,
            "--run-id",
            "test-progression",
            "--output",
            str(tmp_path / "session.json"),
            "--recipe-dump",
            str(
                Path(__file__).resolve().parents[2]
                / "benchmark/data/factorio-2.0.77-contract-game-data.json"
            ),
        ]
    )


class Client:
    def __init__(self, *args):
        self.released = False
        self.completed = False
        self.lease_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def health(self):
        return SimpleNamespace(capabilities=SimpleNamespace(factorio_version="2.0.77"))

    async def lease(self, task):
        self.task = task
        self.lease_calls += 1
        return SimpleNamespace(lease_id="test-lease")

    def progress(self):
        final = frame(
            researched={
                o.target: self.completed for o in self.task.objectives if o.target
            },
            rocket_launches=int(self.completed),
        )
        return progression_progress(self.task, frame(), final)

    async def observe(self, lease):
        return SimpleNamespace(
            evaluation_progress=self.progress(), task_id=self.task.task_id
        )

    async def checkpoint(self, lease, name):
        return SimpleNamespace(
            model_dump=lambda **kw: {
                "checkpoint_id": "lifecycle:test:1",
                "lease_id": lease,
                "created_at": "2026-09-07T00:00:00+00:00",
            }
        )

    async def finalize(self, lease):
        progress = self.progress()
        return SimpleNamespace(
            success=progress["success"],
            metrics={"evaluation_progress": progress},
            model_dump=lambda **kw: {"success": progress["success"]},
            action_events=[],
            termination_reason=progress["terminal_reason"] or "finalized",
        )

    async def release(self, lease):
        self.released = True


class Agent:
    harness_version = "fake-progress-agent"
    failure_category = None

    def __init__(self, client, complete=True):
        self.client = client
        self.complete = complete
        self.closed = False

    async def start(self, prompt):
        self.prompt = prompt

    async def run_epoch(self, prompt):
        if not self.complete:
            await asyncio.sleep(60)
        self.client.completed = self.complete
        return SimpleNamespace(
            model_seconds=0.01,
            tool_seconds=0.02,
            failure_category=self.failure_category,
        )

    async def close(self):
        self.closed = True


@pytest.mark.parametrize("mode", ["technology", "rocket_launch"])
def test_session_uses_verified_completion_and_persists_independent_record(
    tmp_path, monkeypatch, mode
):
    client = Client()
    agent = Agent(client)
    monkeypatch.setattr(runner, "HTTPEnvironmentClient", lambda _: client)
    monkeypatch.setattr(harness, "create_agent_session", lambda *a, **kw: agent)
    result = asyncio.run(harness.run_session(arguments(tmp_path, mode)))
    assert result.success
    assert result.evaluation_mode == mode
    assert result.termination_reason == "objective_completed"
    assert client.released and agent.closed
    saved = json.loads((tmp_path / "session.json").read_text())
    assert saved["schema_version"] == "factorio-progression-session-v1"
    assert "final_rating" not in saved and "epochs" not in saved
    assert "Required goals" in agent.prompt


def test_wall_limit_cancels_agent_and_finalizes_failure(tmp_path, monkeypatch):
    client = Client()
    agent = Agent(client, complete=False)
    monkeypatch.setattr(runner, "HTTPEnvironmentClient", lambda _: client)
    monkeypatch.setattr(harness, "create_agent_session", lambda *a, **kw: agent)
    args = arguments(tmp_path)
    args.wall_clock_failsafe_seconds = 0.1
    result = asyncio.run(runner.run_progression_session(args))
    assert not result.success
    assert result.termination_reason == "wall_clock_failsafe"
    assert not result.timing_complete
    assert agent.closed and client.released


def test_infrastructure_failure_leaves_resumable_partial_not_scored_loss(
    tmp_path, monkeypatch
):
    client = Client()
    agent = Agent(client)
    agent.failure_category = "provider_timeout"
    monkeypatch.setattr(runner, "HTTPEnvironmentClient", lambda _: client)
    monkeypatch.setattr(harness, "create_agent_session", lambda *a, **kw: agent)
    with pytest.raises(RuntimeError, match="provider_timeout"):
        asyncio.run(runner.run_progression_session(arguments(tmp_path)))
    assert not (tmp_path / "session.json").exists()
    partial = json.loads((tmp_path / "session.partial.json").read_text())
    assert partial["status"] == "interrupted"
    assert client.released


def test_catalog_rejects_unknown_technology_before_leasing(tmp_path):
    export = tmp_path / "catalog.json"
    export.write_text(json.dumps({"factorio_version": "2.0.77", "technologies": []}))
    with pytest.raises(ValueError, match="Unknown technology"):
        runner.validate_game_data(export, progression_task_spec("technology"))


def test_opencode_start_writes_selected_system_prompt(tmp_path):
    agent = harness.OpenCodePersistentAgentSession(
        envd_url="http://localhost:8172",
        lease_id="fake",
        model="provider/model",
        reasoning="max",
        timeout_seconds=60,
        artifacts_dir=tmp_path,
        command="unused-opencode",
    )
    asyncio.run(agent.start("Research every technology milestone."))
    config = json.loads((agent.scratch / "opencode.json").read_text())
    assert (
        config["agent"]["factorio-eval"]["prompt"]
        == "Research every technology milestone."
    )
    assert config["agent"]["factorio-eval"]["permission"]["*"] == "deny"
