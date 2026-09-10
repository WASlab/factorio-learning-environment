import pytest

from fle.env import ResourcePatch
from fle.env.game_types import Resource


@pytest.fixture()
def game(configure_game):
    return configure_game(inventory={"iron-chest": 1})


@pytest.mark.parametrize(
    "resource,check_bbox_order",
    [
        (Resource.Coal, True),
        (Resource.Water, True),
        (Resource.Wood, False),
    ],
)
def test_get_resource_patch(game, resource, check_bbox_order):
    """
    Get the nearest resource patch and verify its reported bounding box.
    :param game:
    :return:
    """
    resource_patch: ResourcePatch = game.get_resource_patch(
        resource, game.nearest(resource)
    )

    assert resource_patch.name == resource[0]
    assert resource_patch.size > 0
    assert resource_patch.bounding_box.left_top.x
    assert resource_patch.bounding_box.right_bottom.x
    assert resource_patch.bounding_box.left_top.y
    assert resource_patch.bounding_box.right_bottom.y
    if check_bbox_order:
        assert (
            resource_patch.bounding_box.left_top.x
            < resource_patch.bounding_box.right_bottom.x
        )
        assert (
            resource_patch.bounding_box.left_top.y
            < resource_patch.bounding_box.right_bottom.y
        )
