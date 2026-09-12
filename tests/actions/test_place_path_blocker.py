import pytest

from fle.env.tools.agent.place_path.client import _blocked_by_from_message

pytestmark = pytest.mark.no_factorio


def test_extracts_promoted_blocked_by_from_diagnostics():
    message = (
        'RuntimeError: {"diagnostics": {"position": {"x": 29, "y": -82}, '
        '"reason": "occupied", "blocked_by": {"prototype": "small-electric-pole", '
        '"position": {"x": 30, "y": -82}, "entity_id": 1019, "type": "electric-pole"}}, '
        '"error": true}'
    )
    assert _blocked_by_from_message(message) == {
        "prototype": "small-electric-pole",
        "position": {"x": 30, "y": -82},
        "entity_id": 1019,
        "type": "electric-pole",
    }


def test_falls_back_to_nearest_overlapping_entity():
    message = (
        "Could not place stone-furnace at (0.0, 4.0): __fle-runtime__/control.lua: "
        '"{"diagnostics": {"overlapping_entities": [{"prototype": "character", '
        '"position": {"x": 0, "y": 0}, "entity_id": 14, "distance": 0.2}], '
        '"reason": "occupied"}, "error": true}"'
    )
    blocked_by = _blocked_by_from_message(message)
    assert blocked_by is not None
    assert blocked_by["prototype"] == "character"
    assert blocked_by["position"] == {"x": 0, "y": 0}


def test_returns_none_without_structured_diagnostics():
    assert _blocked_by_from_message("Could not insert: no coal") is None
    assert _blocked_by_from_message('RuntimeError: {"error": true}') is None
    assert _blocked_by_from_message("prefix {not json") is None
