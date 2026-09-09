"""Validate exact failure behavior on the dedicated Factorio 2.0.77 server."""

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
    worker = FLEWorker.connect("spatial-validation", tcp_port=27010)
    assert lua(worker, "rcon.print(script.active_mods.base)").strip() == "2.0.77"
    worker.start_task(
        FactorioTaskSpec(
            task_id="spatial-validation",
            goal="Validate spatial diagnostics",
            scenario="freeplay",
            checkpoint_id="scenario:freeplay",
            verifier=VerifierSpec(implementation="objective_engine_v1"),
        )
    )
    lua(
        worker,
        """
        local s=game.surfaces[1]
        for _,e in pairs(s.find_entities_filtered{area={{-8,-8},{8,8}}}) do
            if e.type~='character' then e.destroy() end
        end
        local tiles={}
        for x=-8,8 do for y=-8,8 do
            tiles[#tiles+1]={name='grass-1',position={x,y}}
        end end
        s.set_tiles(tiles)
        local c=s.find_entities_filtered{type='character'}[1]
        c.teleport({0,0}); c.insert{name='stone-furnace',count=5}
        s.create_entity{name='transport-belt',position={3.5,0.5},force='player'}
        s.set_tiles{{name='water',position={0,3}},{name='water',position={1,3}},
            {name='water',position={0,4}},{name='water',position={1,4}}}
    """,
    )
    ns = worker.instance.first_namespace
    ns.player_location = Position(x=0, y=0)
    before = ns.inspect_inventory()[Prototype.StoneFurnace]
    failures = []
    for target in (Position(x=3, y=1), Position(x=1, y=4)):
        try:
            ns.place_entity(Prototype.StoneFurnace, position=target)
        except RuntimeError as error:
            failures.append(json.loads(str(error)))
        else:
            raise AssertionError("Blocked placement succeeded")
    assert failures[0]["diagnostics"]["overlapping_entities"], failures
    assert failures[1]["diagnostics"]["colliding_tiles"], failures
    assert ns.inspect_inventory()[Prototype.StoneFurnace] == before
    worker.instance.set_speed_and_unpause(10)
    try:
        try:
            ns.move_to(Position(x=0.5, y=3.5))
        except RuntimeError as error:
            path = json.loads(str(error))
        else:
            raise AssertionError("Water destination unexpectedly reached")
    finally:
        worker.instance.pause()
    assert path["goal"] == {"x": 0.5, "y": 3.5}, path
    assert path["diagnostics"]["goal"]["colliding_tiles"], path
    actual = json.loads(
        lua(
            worker,
            "local c=game.surfaces[1].find_entities_filtered{type='character'}[1]; rcon.print(helpers.table_to_json(c.position))",
        )
    )
    assert actual == {"x": 0, "y": 0}, actual
    report = {"passed": True, "placements": failures, "path": path, "position": actual}
    (ROOT / ".runtime/spatial-diagnostics-validation.json").write_text(
        json.dumps(report, indent=2)
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    validate()
