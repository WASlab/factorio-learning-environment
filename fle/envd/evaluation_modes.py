"""Public progression goals, separate from adaptive customer ratings."""

from __future__ import annotations

from typing import Literal

from fle.envd.models import (
    ConstraintSpec,
    FactorioTaskSpec,
    ObjectiveSpec,
    ProvisioningSpec,
    VerifierSpec,
)
from fle.envd.objective_engine import TelemetryFrame, evaluate_objective

ProgressionMode = Literal["technology", "rocket_launch"]
TECHNOLOGY_MILESTONES = (
    "automation-science-pack",
    "logistic-science-pack",
    "chemical-science-pack",
    "production-science-pack",
    "utility-science-pack",
    "rocket-silo",
)


def progression_task_spec(
    mode: ProgressionMode,
    *,
    seed: int = 0,
    max_ticks: int | None = None,
    checkpoint_id: str | None = None,
) -> FactorioTaskSpec:
    if mode not in ("technology", "rocket_launch"):
        raise ValueError(f"Unknown progression mode: {mode}")
    if max_ticks is not None and max_ticks <= 0:
        raise ValueError("Simulation budget must be positive")
    objectives = [
        ObjectiveSpec(
            objective_id=f"research:{name}",
            kind="research",
            target=name,
            description=f"Research {name}",
            threshold=1,
            required=mode == "technology",
        )
        for name in TECHNOLOGY_MILESTONES
    ]
    if mode == "rocket_launch":
        objectives.append(
            ObjectiveSpec(
                objective_id="rocket-launch",
                kind="rocket_launch",
                threshold=1,
                parameters={"since_task_start": True},
                description="Complete one engine-confirmed rocket launch",
            )
        )
    return FactorioTaskSpec(
        task_id=f"freeplay-{mode}-v1",
        task_family="progression",
        evaluation_mode=mode,
        goal=(
            "Research every listed technology milestone from fresh freeplay."
            if mode == "technology"
            else "Build a factory from fresh freeplay and complete one rocket launch."
        ),
        objectives=objectives,
        constraints=(
            [
                ConstraintSpec(
                    constraint_id="simulation-budget",
                    kind="max_ticks",
                    description="Maximum simulation ticks",
                    limit=max_ticks,
                )
            ]
            if max_ticks is not None
            else []
        ),
        verifier=VerifierSpec(implementation="objective_engine_v1"),
        provisioning=ProvisioningSpec(all_technologies_researched=False),
        seed=seed,
        max_interventions=None,
        holdout_seconds=0,
        scenario="freeplay",
        checkpoint_id=checkpoint_id or "scenario:freeplay",
    )


def progression_progress(
    task: FactorioTaskSpec,
    initial: TelemetryFrame,
    final: TelemetryFrame,
) -> dict:
    """Use the final verifier's objective evaluator; expose only public goals."""
    milestones = []
    for objective in task.objectives:
        result = evaluate_objective(objective, initial, final)
        milestones.append(
            {
                "id": objective.objective_id,
                "description": objective.description,
                "required": objective.required,
                "completed": result.satisfied,
                "value": result.value,
                "target": objective.threshold,
            }
        )
    ticks = max(final.tick - initial.tick, 0)
    died = final.death_count > initial.death_count or not final.character_alive
    limits = [float(c.limit) for c in task.constraints if c.kind == "max_ticks"]
    exceeded = any(ticks > limit for limit in limits)
    completed = all(m["completed"] for m in milestones if m["required"])
    reason = (
        "character_died"
        if died
        else "session_tick_limit"
        if exceeded
        else "objective_completed"
        if completed
        else "session_tick_limit"
        if any(ticks >= limit for limit in limits)
        else None
    )
    return {
        "mode": task.evaluation_mode,
        "milestones": milestones,
        "completed_count": sum(m["completed"] for m in milestones),
        "milestone_count": len(milestones),
        "simulation_ticks": ticks,
        "rocket_launches": max(final.rocket_launches - initial.rocket_launches, 0),
        "success": reason == "objective_completed",
        "terminal_reason": reason,
    }


def progression_system_prompt(task: FactorioTaskSpec) -> str:
    goals = "\n".join(f"- {o.description}" for o in task.objectives if o.required)
    return (
        "You are a persistent Factorio agent operating a fresh freeplay factory.\n"
        f"{task.goal}\nRequired goals:\n{goals}\n"
        "Use the Factorio MCP tools to inspect the API reference and game data, "
        "observe the factory, and execute Python using the documented game API. "
        "Build and expand production, electricity, science, research and logistics. "
        "Manual crafting and mining are allowed. Research progress and launch "
        "requests do not count as completed goals: engine state verifies completion. "
        "Keep working until the environment reports objective_completed or another "
        "terminal reason. The factory persists throughout this evaluation. "
        "Use only the supplied Factorio tools; do not access host files or shell. "
        "Save useful plans in the memory tools when available."
    )
