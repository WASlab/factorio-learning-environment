import pickle
from types import SimpleNamespace

import pytest

from fle.commons.models.game_state import GameState

pytestmark = pytest.mark.no_factorio


def _fake_namespace() -> SimpleNamespace:
    return SimpleNamespace(
        persistent_vars=None,
        _set_inventory=lambda inventory: None,
        load_messages=lambda messages: None,
        _load_entity_state=lambda *args, **kwargs: None,
        _load_research_state=lambda state: None,
    )


def _fake_instance(namespaces) -> SimpleNamespace:
    first = namespaces[0]
    return SimpleNamespace(
        namespaces=namespaces,
        first_namespace=first,
        num_agents=len(namespaces),
    )


def _state(namespace_blobs) -> GameState:
    return GameState(
        entities="",
        inventories=[{} for _ in namespace_blobs],
        research=None,
        namespaces=namespace_blobs,
        agent_messages=[[] for _ in namespace_blobs],
    )


@pytest.mark.parametrize(
    ("blobs", "initial_vars", "expected_vars"),
    [
        pytest.param(
            [pickle.dumps({"gear_count": 42, "plan": "main-bus"})],
            None,
            [{"gear_count": 42, "plan": "main-bus"}],
            id="restores_namespace_vars",
        ),
        pytest.param(
            [bytes()],
            {"kept": True},
            [{"kept": True}],
            id="skips_empty_blobs",
        ),
        pytest.param(
            [pickle.dumps({"agent": 1}), pickle.dumps({"agent": 2})],
            None,
            [{"agent": 1}, {"agent": 2}],
            id="maps_blobs_per_agent",
        ),
    ],
)
def test_to_instance_restores_persistent_vars(blobs, initial_vars, expected_vars):
    namespaces = [_fake_namespace() for _ in blobs]
    if initial_vars is not None:
        namespaces[0].persistent_vars = initial_vars
    instance = _fake_instance(namespaces)

    _state(blobs).to_instance(instance)

    for namespace, expected in zip(namespaces, expected_vars):
        assert namespace.persistent_vars == expected


def test_to_instance_never_pickles_the_live_namespace():
    """Regression: the old code called pickle.loads() on the live namespace
    object (always truthy) instead of the stored blob."""

    namespace = _fake_namespace()
    instance = _fake_instance([namespace])

    broken_state = GameState(
        entities="",
        inventories=[{}],
        research=None,
        namespaces=[namespace],  # type: ignore[list-item]
        agent_messages=[[]],
    )
    with pytest.raises((TypeError, AttributeError, pickle.UnpicklingError)):
        broken_state.to_instance(instance)
