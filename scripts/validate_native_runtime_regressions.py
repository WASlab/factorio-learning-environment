"""Validate error fixes on the dedicated reference server after bootstrap staging.

Run validate_freeplay_bootstrap.py first. This resets only localhost:27010.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fle.envd.backend import FLEWorker
from fle.envd.models import FactorioTaskSpec, VerifierSpec
from fle.env.game_types import Prototype
from fle.env import Position

ARTIFACTS = ROOT / ".runtime/reference-factory"


def lua(worker, source):
    code = " ".join(
        line for line in source.splitlines() if not line.lstrip().startswith("--")
    )
    result = worker.instance.rcon_client.send_command("/sc " + code) or ""
    if "Cannot execute" in result or "Error" in result:
        raise RuntimeError(result)
    return result


def validate():
    worker = FLEWorker.connect("native-runtime-regressions", tcp_port=27010)
    assert lua(worker, "rcon.print(script.active_mods.base)").strip() == "2.0.77"
    worker.start_task(
        FactorioTaskSpec(
            task_id="native-runtime-regressions",
            goal="Validate runtime fixes",
            scenario="freeplay",
            checkpoint_id="scenario:freeplay",
            verifier=VerifierSpec(implementation="objective_engine_v1"),
        )
    )
    ns = worker.instance.first_namespace
    report = {}
    try:
        lua(
            worker,
            """
            local c=game.surfaces[1].find_entities_filtered{name='character'}[1]
            c.force.technologies['steam-power'].researched=true
            c.force.technologies['electronics'].researched=true
            c.insert{name='iron-plate',count=100}
            c.insert{name='copper-plate',count=100}
        """,
        )

        def stats():
            return json.loads(
                lua(
                    worker,
                    """
                local f=game.forces.player
                rcon.print(helpers.table_to_json({
                    lab=f.get_item_production_statistics(game.surfaces[1]).get_input_count('lab'),
                    researched=f.technologies['automation-science-pack'].researched
                }))
            """,
                )
            )

        before = stats()
        assert before == {"lab": 0, "researched": False}, before
        ns.queue_craft(Prototype.Lab, 1)
        assert stats() == before, "Queued requests must not count as completed crafts"
        worker.instance.set_speed_and_unpause(10)
        receipt = ns.wait(12000, until={"craft_queue": {"active": False}})
        assert receipt["condition_met"], receipt
        ns.wait(60)
        worker.instance.pause()
        report["native_lab_craft"] = stats()
        assert report["native_lab_craft"] == {"lab": 1, "researched": True}, report
        assert ns.get_prototype_recipe(Prototype.AutomationSciencePack).enabled
        ns.queue_craft(Prototype.Lab, 1)
        while ns.get_craft_queue().get("active"):
            ns.cancel_craft(1)
        worker.instance.set_speed_and_unpause(10)
        ns.wait(120)
        worker.instance.pause()
        assert stats()["lab"] == 1, "Cancelled crafts must not earn production credit"
        worker.instance.set_speed_and_unpause(10)
        started = time.monotonic()
        try:
            worker.instance.eval_with_error(
                "wait(183000, poll_ticks=183000)", timeout=0.2
            )
        except TimeoutError:
            pass
        else:
            raise AssertionError("Program timeout was not enforced")
        report["timeout_recovery_seconds"] = time.monotonic() - started
        assert report["timeout_recovery_seconds"] < 5
        assert ns.wait(60)["simulation_ticks_advanced"] >= 60
        # Fixture an enclosed courtyard with a narrow, physically walkable gate.
        worker.instance.pause()
        lua(
            worker,
            """
            local s=game.surfaces[1]
            local c=s.find_entities_filtered{name='character'}[1]
            for _,e in pairs(s.find_entities_filtered{area={{15,-10},{45,10}}}) do
                if e~=c then e.destroy() end
            end
            local tiles={}
            for x=15,45 do for y=-10,10 do
                table.insert(tiles,{name='grass-1',position={x,y}})
            end end
            s.set_tiles(tiles)
            c.teleport{20,0}
            for y=-3,3 do
                s.create_entity{name='stone-wall',position={18.5,y+0.5},force='player'}
                if y~=0 and y~=1 then s.create_entity{name='stone-wall',position={22.5,y+0.5},force='player'} end
            end
            for x=19,21 do for _,y in pairs({-2.5,3.5}) do
                s.create_entity{name='stone-wall',position={x+0.5,y},force='player'}
            end end
            s.create_entity{name='small-electric-pole',position={22.5,0},force='player'}
            s.create_entity{name='small-electric-pole',position={22.5,1},force='player'}
        """,
        )
        ns.player_location = Position(20, 0)
        worker.instance.set_speed_and_unpause(10)
        result = ns.move_to(Position(25, 1))
        report["narrow_gate_position"] = {"x": result.x, "y": result.y}
        assert abs(result.x - 25) < 0.5 and abs(result.y - 1) < 0.5, result
        worker.instance.pause()
        lua(
            worker,
            """
            local s=game.surfaces[1]
            local silo=s.create_entity{name='rocket-silo',position={35.5,0.5},force='player'}
            silo.rocket_parts=100
            silo.energy=1000000000
            s.create_entity{name='electric-energy-interface',position={40,0},force='player'}
            s.create_entity{name='substation',position={40,3},force='player'}
        """,
        )
        try:
            ns.launch_rocket(Position(34, 0))
        except Exception as exc:
            assert "No player-owned rocket silo" in str(exc), exc
        else:
            raise AssertionError("Wrong coordinates launched a nearby silo")
        worker.instance.set_speed_and_unpause(10)
        for _ in range(40):
            ready = lua(
                worker,
                """
                local silo=game.surfaces[1].find_entity('rocket-silo',{35.5,0.5})
                rcon.print(silo.rocket_silo_status==defines.rocket_silo_status.rocket_ready)
            """,
            ).strip()
            if ready == "true":
                break
            time.sleep(0.25)
        assert ready == "true", "Fixture rocket did not become ready"
        ns.launch_rocket(Position(35.5, 0.5))
        for _ in range(80):
            launches = int(
                lua(worker, "rcon.print(game.forces.player.rockets_launched)")
            )
            if launches:
                break
            time.sleep(0.25)
        assert launches == 1, launches
        report["engine_rocket_launches"] = launches
        report["passed"] = True
        return report
    finally:
        worker.instance.pause()
        (ARTIFACTS / "native-runtime-regressions.json").write_text(
            json.dumps(report, indent=2)
        )


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
