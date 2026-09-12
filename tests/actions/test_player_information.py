"""Focused acceptance checks; live tests require an isolated Factorio instance."""

from unittest.mock import Mock

import pytest

from fle.env import Position
from fle.env.tools.agent.get_technology.client import GetTechnology


@pytest.mark.no_factorio
def test_technology_boundary_normalizes_empty_arrays_and_propagates_errors():
    tool = GetTechnology.__new__(GetTechnology)
    tool.player_index = 1
    tool.execute = Mock(
        return_value=(
            {
                "name": "automation",
                "prerequisites": {},
                "unlocks": {1: "assembling-machine-1"},
            },
            0,
        )
    )
    result = tool("automation")
    assert result["unlocks"] == ["assembling-machine-1"]
    assert result["prerequisites"] == []
    tool.execute.return_value = ("Unknown technology", 0)
    with pytest.raises(RuntimeError, match="Unknown technology"):
        tool("missing")


def test_player_information(instance, namespace):
    def lua(source):
        response = instance.rcon_client.send_command("/sc " + source)
        assert not response or "Error" not in response, response

    lua(
        "game.tick_paused=true; local f=game.forces.player; f.reset_technologies(); f.research_all_technologies(); f.technologies.automation.researched=false; f.add_research('automation')"
    )
    technology = namespace.get_technology("automation")
    assert technology["researchable"] and technology["can_queue"]
    assert "assembling-machine-1" in technology["unlocks"]
    assert technology["unit_count"] == 10
    assert technology["unit_time_seconds"] == 10
    assert namespace.get_research_queue()["queue"][0]["name"] == "automation"
    assert "automation" in [
        item["name"] for item in namespace.get_available_technologies()["technologies"]
    ]
    assert not namespace.get_technology("oil-processing")["can_queue"]

    recipes = namespace.get_recipes_using("advanced-circuit")["recipes"]
    assert "processing-unit" in [recipe["name"] for recipe in recipes]

    lua(
        "local s=game.surfaces[1]; for _,e in pairs(s.find_entities_filtered{area={{18,18},{60,60}}}) do if e.type~='character' then e.destroy() end end; s.create_entity{name='roboport',position={20,20},force='player'}; local c=s.create_entity{name='passive-provider-chest',position={24,20},force='player'}; c.insert{name='iron-plate',count=42}; game.forces.player.chart(s,{{0,0},{64,64}}); s.pollute({20,20},100)"
    )
    network = namespace.get_logistic_network(Position(x=20, y=20))
    assert network["connected"] and network["roboport_count"] == 1
    assert any(
        item["name"] == "iron-plate" and item["count"] == 42
        for item in network["contents"]
    )
    assert not namespace.get_logistic_network(Position(x=1000, y=1000))["connected"]
    lua("game.tick_paused=false")
    namespace.sleep(1)
    lua("game.tick_paused=true; game.surfaces[1].pollute({20,20},100)")
    assert (
        namespace.get_pollution(Position(x=20, y=20))["chunks"][0]["pollution"] >= 100
    )
    assert "mining_drill_productivity_bonus" in namespace.get_force_bonuses()

    lua(
        "local s=game.surfaces[1]; local c=s.create_entity{name='constant-combinator',position={30,30},force='player'}; local p=s.create_entity{name='small-electric-pole',position={32,30},force='player'}; c.get_wire_connector(defines.wire_connector_id.circuit_red,true).connect_to(p.get_wire_connector(defines.wire_connector_id.circuit_red,true)); c.get_control_behavior().add_section().set_slot(1,{value={type='item',name='iron-plate',quality='normal'},min=7}); game.tick_paused=false"
    )
    # Native circuit signals propagate on simulation ticks.
    namespace.sleep(1)
    lua("game.tick_paused=true")
    circuit = namespace.get_circuit_network(Position(x=32, y=30))
    assert any(
        signal["signal"]["name"] == "iron-plate" and signal["count"] == 7
        for signal in circuit["networks"][0]["signals"]
    )

    lua(
        "local s=game.surfaces[1]; for y=40,56,2 do s.create_entity{name='straight-rail',position={40,y},direction=defines.direction.north,force='player'} end; local l=s.create_entity{name='locomotive',position={40,48},direction=defines.direction.north,force='player'}; l.insert{name='coal',count=5}; local stop=s.create_entity{name='train-stop',position={42,44},direction=defines.direction.north,force='player'}; stop.backer_name='Information test'; l.train.schedule={current=1,records={{station='Information test',wait_conditions={{type='time',compare_type='and',ticks=60}}}}}"
    )
    trains = namespace.get_trains()["trains"]
    assert len(trains) == 1 and trains[0]["manual_mode"]
    assert trains[0]["schedule"]["records"][0]["station"] == "Information test"
    assert trains[0]["fuel"][0]["contents"][0]["count"] == 5
    stop = namespace.get_train_stop(Position(x=43, y=45))
    assert stop["scheduled_train_ids"] == [trains[0]["id"]]
    assert stop["inbound_or_stopped_count"] == 0
