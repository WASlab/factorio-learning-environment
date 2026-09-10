"""Persistent technology and rocket-launch evaluations over the shared harness."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from fle.envd.client import HTTPEnvironmentClient
from fle.envd.evaluation_modes import progression_system_prompt, progression_task_spec
from fle.envd.knowledge import ApiReference, load_game_data
from fle.envd.models import ParticipantIdentity


class ProgressionSessionRecord(BaseModel):
    schema_version: str = "factorio-progression-session-v1"
    benchmark_version: str = "freeplay-progression-v1"
    repository_commit: str = "unknown"
    run_id: str
    evaluation_mode: str
    started_at: str
    participant: dict[str, Any]
    task: dict[str, Any]
    status: str = "running"
    success: bool = False
    termination_reason: str | None = None
    progress: dict[str, Any] = Field(default_factory=dict)
    model_seconds: float = 0
    tool_seconds: float = 0
    runner_wall_seconds: float = 0
    interventions: int = 0
    verification: dict[str, Any] | None = None
    infrastructure_error: str | None = None
    timing_complete: bool = True


def validate_game_data(path: str | Path | None, task) -> None:
    if path is None:
        raise ValueError("Progression evaluations require --recipe-dump")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("factorio_version") != task.factorio_version:
        raise ValueError("Game-data version does not match the task")
    names = {item["name"] for item in data.get("technologies", [])}
    missing = {o.target for o in task.objectives if o.kind == "research"} - names
    if missing:
        raise ValueError(f"Unknown technology milestones: {sorted(missing)}")


async def run_progression_session(args) -> ProgressionSessionRecord:
    from scripts.adaptive_contract_benchmark import (
        OpenCodePersistentAgentSession,
        _atomic_json,
        _git_commit,
        _heartbeat_loop,
        _sha256_json,
        _sha256_text,
        create_agent_session,
    )

    path = Path(args.output).resolve()
    if not args.resume_from and (
        path.exists() or path.with_name(f"{path.stem}.partial.json").exists()
    ):
        raise ValueError(
            "Output already contains an evaluation; resume it or use a new output directory"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.stem}.partial.json")
    checkpoint_path = path.with_suffix(path.suffix + ".checkpoint.json")
    artifacts = path.parent / f"{path.stem}-epochs"
    artifacts.mkdir(parents=True, exist_ok=True)
    tool_artifacts = artifacts / "tool-results"
    tool_artifacts.mkdir(parents=True, exist_ok=True)
    os.environ["FACTORIO_TOOL_ARTIFACT_DIR"] = str(tool_artifacts)
    task = progression_task_spec(
        args.mode, seed=args.seed, max_ticks=args.max_session_ticks
    )
    validate_game_data(args.recipe_dump, task)
    api_reference_hash = ApiReference().reference_hash
    game_data, _ = load_game_data(args.recipe_dump)
    if args.max_session_ticks is not None and args.max_session_ticks <= 0:
        raise ValueError("Simulation budget must be positive")
    if args.wall_clock_failsafe_seconds <= 0:
        raise ValueError("Wall-clock budget must be positive")
    resume = None
    if args.resume_from:
        resume = json.loads(Path(args.resume_from).read_text(encoding="utf-8"))
        if resume.get("schema_version") != "factorio-progression-checkpoint-v1":
            raise ValueError("Unsupported progression checkpoint")
        if resume.get("phase") != "active" or args.harness != "opencode":
            raise ValueError("Only unfinished OpenCode evaluations can resume")
        for key in (
            "mode",
            "model",
            "provider",
            "harness",
            "seed",
            "memory_profile",
            "reasoning",
        ):
            if resume.get(key) != getattr(args, key):
                raise ValueError(f"Resume {key} mismatch")
        if resume["task_fingerprint"] != task.fingerprint:
            raise ValueError("Resume task or simulation budget mismatch")
        args.run_id = resume["record"]["run_id"]
        if path.exists():
            raise ValueError("A finalized evaluation cannot resume")
        if partial.exists():
            latest = json.loads(partial.read_text(encoding="utf-8"))
            if (
                latest.get("run_id") == args.run_id
                and latest.get("task", {}).get("fingerprint")
                == resume["task_fingerprint"]
            ):
                resume["record"] = latest

    prompt = progression_system_prompt(task)
    record = (
        ProgressionSessionRecord.model_validate(resume["record"])
        if resume
        else ProgressionSessionRecord(
            run_id=args.run_id,
            evaluation_mode=args.mode,
            started_at=datetime.now(timezone.utc).isoformat(),
            repository_commit=_git_commit(),
            participant={
                "provider": args.provider,
                "model_snapshot": args.model,
                "harness_version": args.harness,
                "system_prompt_hash": _sha256_text(prompt),
            },
            task=task.model_dump(mode="json"),
        )
    )
    record.status = "running"
    record.infrastructure_error = None
    base_wall = record.runner_wall_seconds
    wall_start = time.monotonic()

    def persist():
        record.runner_wall_seconds = base_wall + time.monotonic() - wall_start
        _atomic_json(partial, record.model_dump(mode="json"))

    def on_execution(result):
        if result.evaluation_progress:
            record.progress = result.evaluation_progress
        record.interventions = result.event.sequence
        persist()

    async with HTTPEnvironmentClient(args.envd_url) as client:
        health = await client.health()
        if health.capabilities.factorio_version != task.factorio_version:
            raise ValueError("Environment Factorio version does not match the task")
        if resume:
            # The per-tool pointer can be newer than the runner's checkpoint.
            chosen = resume["checkpoint"]
            pointer_path = path.parent / args.harness / "resume/world-checkpoint.json"
            if pointer_path.exists():
                pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
                candidate = pointer.get("checkpoint") or {}
                if candidate.get("created_at", "") > chosen.get("created_at", ""):
                    chosen = candidate
            task = task.model_copy(update={"checkpoint_id": chosen["checkpoint_id"]})
        lease = None
        if resume:
            old_lease = chosen.get("lease_id")
            if old_lease:
                try:
                    active = await client.observe(old_lease)
                except Exception:
                    active = None
                if active is not None:
                    if active.task_id != task.task_id:
                        raise ValueError("Resume lease has a different task")
                    from types import SimpleNamespace

                    lease = SimpleNamespace(lease_id=old_lease)
        if lease is None:
            lease = await client.lease(task)
        agent = None
        heartbeat = None
        world_checkpoint = None
        try:
            agent = create_agent_session(
                args, client, lease, path, artifacts, on_execution=on_execution
            )
            if resume and isinstance(agent, OpenCodePersistentAgentSession):
                agent.restore_state(resume.get("agent") or {})
            await agent.start(prompt)
            participant = ParticipantIdentity(
                provider=args.provider,
                model_snapshot=args.model,
                harness_version=agent.harness_version,
                system_prompt_hash=_sha256_text(prompt),
                tool_manifest_hash=getattr(
                    agent, "TOOL_MANIFEST_SHA256", _sha256_json([])
                ),
                inference_settings_hash=_sha256_json(agent.inference_settings())
                if hasattr(agent, "inference_settings")
                else _sha256_json({}),
                api_reference_hash=api_reference_hash,
                game_data_reference_hash=game_data.reference_hash,
                memory_implementation_version="session-memory-v1"
                if args.memory_profile == "stateful"
                else "disabled",
                memory_initial_state_hash=_sha256_json(
                    {"profile": args.memory_profile, "entries": []}
                ),
            )
            if resume and participant.participant_id != record.participant.get(
                "participant_id"
            ):
                raise ValueError(
                    "Resume participant references or inference settings changed"
                )
            record.participant = participant.model_dump(mode="json")
            observation = await client.observe(lease.lease_id)
            record.progress = observation.evaluation_progress or {}
            if not record.progress:
                raise RuntimeError(
                    "Environment does not expose progression goals; update envd"
                )

            async def keepalive():
                await client.observe(lease.lease_id)

            heartbeat = asyncio.create_task(
                _heartbeat_loop(path.parent, args.run_id, lease_keepalive=keepalive)
            )

            async def save_checkpoint():
                nonlocal world_checkpoint
                world_checkpoint = await client.checkpoint(
                    lease.lease_id, f"runner-active-progression-{args.run_id}"
                )
                persist()
                _atomic_json(
                    checkpoint_path,
                    {
                        "schema_version": "factorio-progression-checkpoint-v1",
                        "phase": "active",
                        **{
                            key: getattr(args, key)
                            for key in (
                                "mode",
                                "model",
                                "provider",
                                "harness",
                                "seed",
                                "memory_profile",
                                "reasoning",
                            )
                        },
                        "task_fingerprint": record.task["fingerprint"],
                        "checkpoint": world_checkpoint.model_dump(mode="json"),
                        "record": record.model_dump(mode="json"),
                        "agent": {
                            "session_id": getattr(agent, "session_id", None),
                            "invocation_count": getattr(agent, "invocation_count", 0),
                        },
                    },
                )

            await save_checkpoint()
            while not record.progress.get("terminal_reason"):
                remaining = args.wall_clock_failsafe_seconds - (
                    base_wall + time.monotonic() - wall_start
                )
                if remaining <= 0:
                    record.termination_reason = "wall_clock_failsafe"
                    break
                if (
                    args.max_session_interventions
                    and record.interventions >= args.max_session_interventions
                ):
                    record.termination_reason = "intervention_limit"
                    break
                call = asyncio.create_task(
                    agent.run_epoch(
                        f"Continue the {args.mode} evaluation. Current verified progress: "
                        + json.dumps(record.progress)
                    )
                )
                pointer_path = (
                    path.parent / args.harness
                    if args.harness in {"opencode", "hermes"}
                    else artifacts
                ) / "resume/world-checkpoint.json"
                seen_pointer = None
                try:
                    deadline = time.monotonic() + remaining
                    while not call.done():
                        await asyncio.wait(
                            {call},
                            timeout=min(1.0, max(deadline - time.monotonic(), 0)),
                        )
                        if pointer_path.exists():
                            raw = pointer_path.read_text(encoding="utf-8")
                            if raw != seen_pointer:
                                seen_pointer = raw
                                pointer = json.loads(raw)
                                if pointer.get("evaluation_progress"):
                                    record.progress = pointer["evaluation_progress"]
                                record.interventions = int(
                                    pointer.get("sequence", record.interventions)
                                )
                                persist()
                        if time.monotonic() >= deadline and not call.done():
                            record.termination_reason = "wall_clock_failsafe"
                            record.timing_complete = False
                            call.cancel()
                            await agent.close()
                            with contextlib.suppress(asyncio.CancelledError):
                                await call
                            break
                    if not call.cancelled():
                        telemetry = await call
                        record.model_seconds += telemetry.model_seconds
                        record.tool_seconds += telemetry.tool_seconds
                        if telemetry.failure_category:
                            raise RuntimeError(
                                f"Harness failure: {telemetry.failure_category}"
                            )
                finally:
                    if not call.done():
                        call.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await call
                observation = await client.observe(lease.lease_id)
                record.progress = observation.evaluation_progress or record.progress
                await save_checkpoint()
                if record.termination_reason:
                    break
                # A harness may yield a text response before completing the goal.
                # Continue the same conversation; never treat that as success.
                await asyncio.sleep(0.05)

            await agent.close()
            verification = await client.finalize(lease.lease_id)
            record.verification = verification.model_dump(mode="json")
            record.progress = verification.metrics.get(
                "evaluation_progress", record.progress
            )
            budget_stop = record.termination_reason in {
                "wall_clock_failsafe",
                "intervention_limit",
            }
            record.success = verification.success and not budget_stop
            if record.progress.get("terminal_reason") == "character_died":
                record.termination_reason = "character_died"
            elif not budget_stop:
                record.termination_reason = (
                    record.progress.get("terminal_reason")
                    or verification.termination_reason
                )
            record.status = "completed"
            record.interventions = len(verification.action_events)
            persist()
            _atomic_json(path, record.model_dump(mode="json"))
            return record
        except BaseException as exc:
            record.status = "interrupted"
            record.infrastructure_error = f"{type(exc).__name__}: {exc}"
            persist()
            raise
        finally:
            if heartbeat:
                heartbeat.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat
            if agent:
                await agent.close()
            await client.release(lease.lease_id)
