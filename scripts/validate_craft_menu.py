"""Validate native crafting-menu arithmetic on the isolated reference instance."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fle.envd.backend import FLEWorker
from scripts.validate_reference_factory import lua


def validate():
    worker = FLEWorker.connect("craft-menu-validation", tcp_port=27010)
    assert lua(worker, "rcon.print(script.active_mods.base)").strip() == "2.0.77"
    lua(
        worker,
        """
        game.tick_paused=true
        local c=game.surfaces[1].find_entities_filtered{name='character',force='player'}[1]
        c.get_main_inventory().clear()
        c.insert{name='iron-plate',count=6}
    """,
    )
    ns = worker.instance.first_namespace
    before = lua(worker, "rcon.print(game.tick)").strip()
    plan = ns.get_craft_plan("transport-belt", 3)
    after = lua(worker, "rcon.print(game.tick)").strip()
    assert before == after
    assert plan["craftable_now"] == 4, plan
    assert plan["crafts_required"] == 2 and plan["output_quantity"] == 4, plan
    assert any(
        row["item"] == "iron-gear-wheel" and row["missing"] == 2
        for row in plan["ingredients"]
    ), plan
    queued = ns.queue_craft("transport-belt", 3)
    assert queued["queued"] == 4 and queued["queued_crafts"] == 2, queued
    try:
        ns.queue_craft("transport-belt", 3)
    except ValueError as exc:
        failure = json.loads(str(exc))
        assert failure["craft_plan"]["craftable_now"] == 0, failure
    else:
        raise AssertionError("Expected an ingredient-difference failure")
    report = {"passed": True, "plan": plan, "queued": queued, "failure": failure}
    (ROOT / ".runtime/craft-menu-validation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    validate()
