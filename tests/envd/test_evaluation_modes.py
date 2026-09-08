from dataclasses import replace

import pytest

from fle.envd.evaluation_modes import (
    TECHNOLOGY_MILESTONES,
    progression_progress,
    progression_task_spec,
)
from tests.envd.test_objective_engine import frame

pytestmark = pytest.mark.no_factorio


def test_technology_requires_every_completed_milestone():
    task = progression_task_spec("technology")
    initial = frame()
    current = frame(
        researched={name: True for name in TECHNOLOGY_MILESTONES[:-1]},
        research_progress=1,
    )
    assert not progression_progress(task, initial, current)["success"]
    current.researched[TECHNOLOGY_MILESTONES[-1]] = True
    assert progression_progress(task, initial, current)["success"]


def test_launch_request_and_existing_launches_do_not_count():
    task = progression_task_spec("rocket_launch")
    initial = frame(rocket_launches=3)
    assert not progression_progress(task, initial, initial)["success"]
    launched = replace(initial, rocket_launches=4)
    progress = progression_progress(task, initial, launched)
    assert progress["success"]
    assert progress["rocket_launches"] == 1
    # Research milestones are informative, not additional launch requirements.
    assert progress["completed_count"] == 1


@pytest.mark.parametrize(
    "ticks,death,reason",
    [
        (100, 0, "objective_completed"),
        (101, 0, "session_tick_limit"),
        (100, 1, "character_died"),
    ],
)
def test_terminal_precedence(ticks, death, reason):
    task = progression_task_spec("rocket_launch", max_ticks=100)
    progress = progression_progress(
        task, frame(), frame(tick=ticks, rocket_launches=1, death_count=death)
    )
    assert progress["terminal_reason"] == reason
    assert progress["success"] == (reason == "objective_completed")


def test_modes_use_normal_freeplay_and_no_rating_or_audit():
    for mode in ("technology", "rocket_launch"):
        task = progression_task_spec(mode)
        assert task.scenario == "freeplay"
        assert task.provisioning.starting_inventory is None
        assert task.provisioning.all_technologies_researched is False
        assert not task.adaptive_contract_session
        assert task.max_interventions is None
        assert task.throughput_audit is None
