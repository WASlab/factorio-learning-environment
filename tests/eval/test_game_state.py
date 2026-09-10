from pydantic import BaseModel
from fle.env import FactorioInstance
from fle.commons.models.game_state import GameState


def test_game_state_research():
    class DummyObject(BaseModel):
        game_state: GameState = None

    instance = FactorioInstance(
        address="localhost",
        bounding_box=200,
        tcp_port=27019,
        fast=True,
        # cache_scripts=False,
        inventory={},
        all_technologies_researched=True,
    )
    zero_state = GameState.from_instance(instance)
    # this tests for validation errors in the original zero states
    new_object = DummyObject(game_state=zero_state)  # noqa
