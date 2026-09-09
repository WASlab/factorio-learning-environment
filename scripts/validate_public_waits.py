"""Validate public statistics and event waits on the isolated reference server."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fle.envd.backend import FLEWorker
from fle.envd.models import FactorioTaskSpec, VerifierSpec
from fle.env import Position
from fle.env.game_types import Prototype
from scripts.validate_reference_factory import lua


def validate():
    worker = FLEWorker.connect("public-waits-validation", tcp_port=27010)
    assert lua(worker, "rcon.print(script.active_mods.base)").strip() == "2.0.77"
    worker.start_task(
        FactorioTaskSpec(
            task_id="public-waits-validation",
            goal="Validate public waits and statistics",
            scenario="freeplay",
            checkpoint_id="scenario:freeplay",
            verifier=VerifierSpec(implementation="objective_engine_v1"),
        )
    )
    lua(
        worker,
        """
        local s=game.surfaces[1]
        for _,e in pairs(s.find_entities_filtered{area={{9,9},{13,13}}}) do
            if e.type~='character' then e.destroy() end
        end
        local tiles={}
        for x=9,13 do for y=9,13 do tiles[#tiles+1]={name='grass-1',position={x,y}} end end
        s.set_tiles(tiles)
        local f=s.create_entity{name='stone-furnace',position={11,11},force='player'}
        f.insert{name='coal',count=5}; f.insert{name='iron-ore',count=1}
        local stats=game.forces.player.get_item_production_statistics(s)
        stats.on_flow('copper-plate',10); stats.on_flow('copper-plate',-3)
    """,
    )
    ns = worker.instance.first_namespace
    furnace = ns.get_entity(Prototype.StoneFurnace, Position(x=11, y=11))
    worker.instance.set_speed_and_unpause(10)
    try:
        completed = ns.wait(15)
        result = ns.wait(
            600,
            until={"machine_status": {"entity": furnace, "status": "no_ingredients"}},
        )
        timeout = ns.wait(
            5,
            until={
                "inventory": {
                    "entity": furnace,
                    "item": Prototype.IronPlate,
                    "at_least": 100,
                }
            },
        )
    finally:
        worker.instance.pause()
    assert completed["status"] == "completed", completed
    assert result["status"] == "condition_met", result
    assert result["decision_tick"] <= result["deadline_tick"], result
    assert timeout["status"] == "timeout", timeout
    assert timeout["decision_tick"] == timeout["deadline_tick"], timeout
    stats = ns.get_production_statistics([Prototype.CopperPlate], window_seconds=5)
    entry = stats["entries"][0]
    assert entry["produced_total"] == 10 and entry["consumed_total"] == 3, stats
    assert entry["produced_per_minute"] > entry["consumed_per_minute"] > 0, stats
    report = {
        "passed": True,
        "completed": completed,
        "machine": result,
        "timeout": timeout,
        "statistics": stats,
    }
    (ROOT / ".runtime/public-waits-validation.json").write_text(
        json.dumps(report, indent=2)
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    validate()
