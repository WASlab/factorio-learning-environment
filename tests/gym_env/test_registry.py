"""
Tests for the Factorio Gym Registry.
"""

from fle.env.gym_env.registry import list_available_environments, get_environment_info


def test_registry_functions():
    """Test the registry utility functions"""
    print("=== Testing Registry Functions ===")

    # Test list_available_environments
    env_ids = list_available_environments()
    assert isinstance(env_ids, list)
    assert len(env_ids) > 0
    print(f"✓ list_available_environments() returned {len(env_ids)} environments")

    # Test get_environment_info
    if env_ids:
        info = get_environment_info(env_ids[0])
        assert info is not None
        assert "env_id" in info
        assert "description" in info
        assert "task_key" in info
        print(f"✓ get_environment_info() returned valid info for {env_ids[0]}")

    print()
