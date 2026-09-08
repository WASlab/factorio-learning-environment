"""Read-only public-view acceptance on the isolated reference server (27010).

Stage the current runtime with validate_freeplay_bootstrap.py first.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fle.envd.backend import FLEWorker
from scripts.validate_reference_factory import lua


def validate():
    worker = FLEWorker.connect("public-view-validation", tcp_port=27010)
    version = lua(worker, "rcon.print(script.active_mods.base)").strip()
    assert version == "2.0.77", version
    namespace = worker.instance.first_namespace
    lua(worker, "game.tick_paused=true")
    before = lua(worker, "rcon.print(game.tick)").strip()
    nearby = namespace._public_view(32, 32)
    wide = namespace._public_view(192, 8)
    after = lua(worker, "rcon.print(game.tick)").strip()
    assert before == after, (before, after)
    assert nearby["available"] and wide["available"], (nearby, wide)
    assert len(nearby["cells"]) <= 256 and len(wide["cells"]) <= 256
    assert len(wide["entities"]) <= 8
    assert nearby["detail"] == "nearby" and wide["detail"] == "map"
    assert all("fuel" not in entity for entity in wide["entities"])
    assert any("status" in entity for entity in nearby["entities"]), nearby
    assert any(not cell.get("unknown") for cell in nearby["cells"]), nearby
    assert any(cell.get("resources") for cell in wide["cells"]), wide
    furnace = next(
        entity for entity in nearby["entities"] if entity["name"] == "stone-furnace"
    )
    assert furnace["furnace_result"]["iron-plate"] == 5, furnace
    assert "chest" not in furnace and "assembling_machine_output" not in furnace, (
        furnace
    )
    report = {
        "passed": True,
        "factorio_version": version,
        "nearby": nearby,
        "wide": wide,
    }
    (ROOT / ".runtime/public-view-validation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps({"passed": True, "cells": len(wide["cells"]), "tick": before}))


if __name__ == "__main__":
    validate()
