"""Validate passive status receipts on the isolated reference server, port 27010.

Stage the current runtime with validate_freeplay_bootstrap.py first.
This fixture resets only the dedicated reference instance.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fle.envd.backend import FLEWorker
from fle.envd.models import FactorioTaskSpec, VerifierSpec
from scripts.validate_reference_factory import lua


def validate():
    worker = FLEWorker.connect("public-status-validation", tcp_port=27010)
    version = lua(worker, "rcon.print(script.active_mods.base)").strip()
    assert version == "2.0.77", version
    worker.start_task(
        FactorioTaskSpec(
            task_id="public-status-validation",
            goal="Validate public status transitions",
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
            if e.type ~= 'character' then e.destroy() end
        end
        local tiles={}
        for x=9,13 do for y=9,13 do
            tiles[#tiles+1]={name='grass-1',position={x,y}}
        end end
        s.set_tiles(tiles)
        s.create_entity{name='stone-furnace',position={11,11},force='player'}
    """,
    )
    initial = worker.observe("public-status-validation")
    assert initial.status_changes["available"], initial.status_changes
    assert any(
        entity["prototype"] == "stone-furnace"
        for entity in initial.status_changes["current"]
    ), initial.status_changes
    lua(
        worker,
        """
        local f=game.surfaces[1].find_entity('stone-furnace',{11,11})
        f.insert{name='coal',count=5}
        f.insert{name='iron-ore',count=1}
    """,
    )
    receipt = worker.execute("public-status-validation", "print(wait(300))", 1)
    assert receipt.status_changes["available"], receipt.status_changes
    events = receipt.status_changes["events"]
    assert any(
        event["prototype"] == "stone-furnace" and event["to_status"] == "working"
        for event in events
    ), receipt.status_changes
    assert any(
        event["prototype"] == "stone-furnace" and event["to_status"] == "no_ingredients"
        for event in events
    ), receipt.status_changes
    recovered = worker.query_state(
        "public-status-validation", kind="alerts", since_revision=initial.revision
    )
    assert sorted(recovered["events"], key=lambda event: event["sequence"]) == events, (
        recovered
    )
    report = {
        "passed": True,
        "factorio_version": version,
        "receipt": receipt.status_changes,
    }
    destination = ROOT / ".runtime/public-status-validation.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    validate()
