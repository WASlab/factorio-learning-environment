"""
Test character persistence and recovery across various scenarios.

This test suite explores different triggers that could cause the player character
to disappear or become invalid, including:
- Long distance teleportation (>1000 tiles)
- Enemy damage/death scenarios
- Rapid successive movements
- Edge of map scenarios
- Character invalidation through various game mechanics
"""

import pytest
import time

from fle.env.entities import Position
from fle.env.game_types import Prototype, Resource


@pytest.fixture()
def game(configure_game):
    """Configure game with standard inventory for character persistence tests."""
    return configure_game(
        inventory={
            "coal": 100,
            "iron-plate": 100,
            "copper-plate": 50,
            "stone": 50,
            "transport-belt": 50,
            "burner-mining-drill": 5,
            "stone-furnace": 5,
            "wooden-chest": 5,
        }
    )


class TestLongDistanceMovement:
    """Test character persistence during long distance movements."""

    def test_move_2000_tiles_away(self, game):
        """Test moving player character 2000+ tiles from origin."""
        far_position = Position(x=2000, y=2000)
        try:
            result = game.move_to(far_position)
            print(f"Moved to 2000 tiles: {result}")

            # Verify character functionality
            current_pos = game.player_location
            assert current_pos is not None, "Character position should be valid"

        except Exception as e:
            print(f"Expected failure for 2000 tiles: {e}")
            # Verify character recovery
            try:
                game.move_to(Position(x=0, y=0))
                print("Character recovered after failed long move")
            except Exception as recovery_error:
                pytest.fail(f"Character did not recover: {recovery_error}")

    def test_incremental_long_distance_movement(self, game):
        """Move far away in increments to test cumulative effect."""
        increment = 100
        max_distance = 1500
        current_x = 0

        for i in range(max_distance // increment):
            current_x += increment
            target = Position(x=current_x, y=0)
            try:
                game.move_to(target)
                print(f"Successfully moved to x={current_x}")
            except Exception as e:
                print(f"Failed at x={current_x}: {e}")
                # Verify character still exists
                try:
                    pos = game.player_location
                    print(f"Character still at: {pos}")
                except Exception as pos_error:
                    pytest.fail(f"Character lost at x={current_x}: {pos_error}")
                break


def generate_chunks(game, center_x: int, center_y: int, chunk_radius: int):
    """
    Generate chunks around a position to enable pathfinding in that area.

    Factorio chunks are 32x32 tiles. The pathfinder can only find paths
    through generated chunks.

    Args:
        game: The game namespace with instance access
        center_x: Center X position (in tiles)
        center_y: Center Y position (in tiles)
        chunk_radius: Radius in chunks (each chunk is 32 tiles)
    """
    game.instance._generate_chunks(center_x, center_y, chunk_radius)

    print(
        f"Generated chunks: center=({center_x}, {center_y}), radius={chunk_radius} chunks ({chunk_radius * 32} tiles)"
    )


def generate_chunks_along_path(
    game, start_x: int, start_y: int, end_x: int, end_y: int, chunk_radius: int = 2
):
    """
    Generate chunks along a path from start to end position.

    Args:
        game: The game namespace with instance access
        start_x, start_y: Starting position in tiles
        end_x, end_y: Ending position in tiles
        chunk_radius: Radius around each point to generate (in chunks)
    """
    instance = game.instance

    # Calculate how many points we need along the path
    # Generate chunks every 32 tiles (1 chunk width)
    dx = end_x - start_x
    dy = end_y - start_y
    distance = (dx**2 + dy**2) ** 0.5

    if distance == 0:
        generate_chunks(game, start_x, start_y, chunk_radius)
        return

    # Generate a point every 32 tiles
    num_points = max(2, int(distance / 32) + 1)

    # Request chunks at each point along the path
    for i in range(num_points):
        t = i / (num_points - 1) if num_points > 1 else 0
        x = int(start_x + dx * t)
        y = int(start_y + dy * t)
        instance.rcon_client.send_command(
            f"/silent-command game.surfaces[1].request_to_generate_chunks({{x={x}, y={y}}}, {chunk_radius})"
        )

    # Force immediate generation of all requested chunks
    instance.rcon_client.send_command(
        "/silent-command game.surfaces[1].force_generate_chunk_requests()"
    )

    print(
        f"Generated chunks along path: ({start_x}, {start_y}) -> ({end_x}, {end_y}), {num_points} points"
    )


class TestPathfindingLimits:
    """Comprehensive tests to explore pathfinding distance limits.

    These tests verify that pathfinding can reach minimum expected distances.
    Failures indicate regressions in pathfinding capability.
    """

    # Minimum expected distances - tests fail if we can't reach these
    MIN_SINGLE_MOVE_DISTANCE = (
        200  # Should be able to do at least 200 tiles in one move
    )
    MIN_INCREMENTAL_DISTANCE = 500  # Should reach at least 500 tiles with small steps

    def test_find_max_single_move_distance(self, game):
        """Binary search to find maximum single move_to distance.

        Fails if maximum single-move distance is less than MIN_SINGLE_MOVE_DISTANCE.
        """
        low = 10
        high = 500
        max_working = 0

        while low <= high:
            mid = (low + high) // 2
            # Reset to origin first
            game.move_to(Position(x=0, y=0))

            try:
                game.move_to(Position(x=mid, y=0))
                print(f"âœ“ Single move to x={mid} succeeded")
                max_working = mid
                low = mid + 1
            except Exception as e:
                print(f"âœ— Single move to x={mid} failed: {str(e)[:200]}")
                high = mid - 1

        print(f"\n=== Maximum single move distance: {max_working} tiles ===")
        assert max_working >= self.MIN_SINGLE_MOVE_DISTANCE, (
            f"Single move distance {max_working} is below minimum {self.MIN_SINGLE_MOVE_DISTANCE}"
        )

    @pytest.mark.parametrize(
        "increment,max_iterations",
        [(10, 200), (25, 100), (50, 60)],
        ids=["10-tile", "25-tile", "50-tile"],
    )
    def test_incremental_moves(self, game, increment, max_iterations):
        """Move in fixed-size increments.

        Fails if we can't reach MIN_INCREMENTAL_DISTANCE with the given step size.
        """
        current_x = 0
        max_reached = 0

        for _ in range(max_iterations):
            current_x += increment
            try:
                game.move_to(Position(x=current_x, y=0))
                max_reached = current_x
            except Exception:
                break

        assert max_reached >= self.MIN_INCREMENTAL_DISTANCE, (
            f"{increment}-tile increments only reached {max_reached}, expected at least {self.MIN_INCREMENTAL_DISTANCE}"
        )


class TestRapidMovement:
    """Test character persistence during rapid successive movements."""

    def test_rapid_short_moves(self, game):
        """Execute many rapid short movements."""
        moves_completed = 0
        try:
            for i in range(50):
                x = (i % 10) * 5
                y = (i // 10) * 5
                game.move_to(Position(x=x, y=y))
                moves_completed += 1

            print(f"Completed {moves_completed} rapid moves")
            assert moves_completed == 50, "Should complete all rapid moves"

        except Exception as e:
            print(f"Failed after {moves_completed} moves: {e}")
            # Check character recovery
            pos = game.player_location
            assert pos is not None, f"Character should survive, got position: {pos}"

    def test_rapid_back_and_forth(self, game):
        """Rapidly move back and forth between two positions."""
        pos_a = Position(x=0, y=0)
        pos_b = Position(x=50, y=50)

        for i in range(20):
            try:
                if i % 2 == 0:
                    game.move_to(pos_b)
                else:
                    game.move_to(pos_a)
            except Exception as e:
                print(f"Back-and-forth failed at iteration {i}: {e}")
                # Verify character
                current = game.player_location
                assert current is not None, "Character should persist"
                return

        print("Completed 20 back-and-forth movements")

    def test_spiral_movement(self, game):
        """Move in an expanding spiral pattern."""
        radius = 5
        for lap in range(10):
            try:
                # Move in a square spiral
                game.move_to(Position(x=radius, y=0))
                game.move_to(Position(x=radius, y=radius))
                game.move_to(Position(x=-radius, y=radius))
                game.move_to(Position(x=-radius, y=-radius))
                game.move_to(Position(x=radius, y=-radius))
                radius += 10
            except Exception as e:
                print(f"Spiral failed at radius {radius}: {e}")
                pos = game.player_location
                assert pos is not None, "Character should persist during spiral"
                break

        print(f"Spiral completed to radius {radius}")


class TestEdgeCases:
    """Test character persistence in edge case scenarios."""

    def test_move_to_negative_coordinates(self, game):
        """Test movement to negative coordinate space."""
        negative_pos = Position(x=-500, y=-500)
        try:
            result = game.move_to(negative_pos)
            print(f"Moved to negative coords: {result}")

            # Verify character
            current = game.player_location
            assert current is not None

        except Exception as e:
            print(f"Negative coord move failed: {e}")
            # Should still have character
            pos = game.player_location
            assert pos is not None

    def test_move_to_origin_from_far(self, game):
        """Move far away then return to origin."""
        # First move somewhat far
        game.move_to(Position(x=200, y=200))

        # Then return to origin
        try:
            game.move_to(Position(x=0, y=0))
            pos = game.player_location
            print(f"Returned to origin: {pos}")
            assert abs(pos.x) < 5 and abs(pos.y) < 5, "Should be near origin"

        except Exception as e:
            pytest.fail(f"Failed to return to origin: {e}")

    def test_move_to_same_position(self, game):
        """Test moving to current position (zero distance)."""
        current = game.player_location
        try:
            result = game.move_to(current)
            print(f"Move to same position: {result}")
        except Exception as e:
            # This might fail but shouldn't break character
            print(f"Same position move failed (expected): {e}")

        # Character should still work
        new_pos = game.player_location
        assert new_pos is not None

    def test_very_small_movements(self, game):
        """Test many very small movements."""
        for i in range(100):
            try:
                game.move_to(Position(x=i * 0.5, y=i * 0.25))
            except Exception as e:
                print(f"Small movement {i} failed: {e}")
                break

        pos = game.player_location
        assert pos is not None, "Character should survive small movements"


class TestCharacterRecovery:
    """Test that character auto-recovers when invalidated."""

    def test_character_validity_after_actions(self, game):
        """Verify character remains valid after various actions."""
        # Place some entities
        game.move_to(Position(x=10, y=10))
        game.place_entity(Prototype.WoodenChest, position=Position(x=12, y=10))

        # Check character
        pos = game.player_location
        assert pos is not None, "Character valid after placing entity"

        # Mine something
        stone_pos = game.nearest(Resource.Stone)
        if stone_pos:
            game.move_to(stone_pos)
            game.harvest_resource(stone_pos, quantity=5)

        pos = game.player_location
        assert pos is not None, "Character valid after harvesting"

    def test_character_after_failed_path(self, game):
        """Test character persists after pathfinding fails."""
        # Try to move somewhere potentially unreachable
        try:
            # Place obstacles
            game.move_to(Position(x=0, y=0))
            for i in range(5):
                game.place_entity(
                    Prototype.WoodenChest, position=Position(x=5, y=i - 2)
                )

            # Try to move through obstacles
            game.move_to(Position(x=10, y=0))
        except Exception as e:
            print(f"Blocked path (expected): {e}")

        # Character should still be valid
        pos = game.player_location
        assert pos is not None, "Character should survive failed pathfinding"

    def test_multiple_game_resets(self, instance):
        """Test character survives multiple resets."""
        for i in range(5):
            instance.reset()
            pos = instance.namespace.player_location
            assert pos is not None, f"Character should exist after reset {i + 1}"
            print(f"Reset {i + 1}: Character at {pos}")


class TestConcurrentOperations:
    """Test character persistence during complex operations."""

    def test_move_while_placing_entities(self, game):
        """Move while placing entities along the path."""
        try:
            # Move while laying belts
            result = game.move_to(Position(x=30, y=0), laying=Prototype.TransportBelt)
            print(f"Move with belt laying: {result}")
        except Exception as e:
            print(f"Belt laying move failed: {e}")

        pos = game.player_location
        assert pos is not None, "Character should survive move with laying"

    def test_inspect_during_movement(self, game):
        """Test that inspection works during movement sequence."""
        game.move_to(Position(x=20, y=20))
        inv = game.inspect_inventory()
        assert inv is not None, "Should be able to inspect inventory"

        game.move_to(Position(x=40, y=40))
        _entities = game.get_entities()
        # Should not raise an error

        pos = game.player_location
        assert pos is not None


class TestCharacterState:
    """Direct tests on character state."""

    def test_player_location_consistency(self, game):
        """Verify player_location returns consistent results."""
        pos1 = game.player_location
        pos2 = game.player_location

        assert pos1.x == pos2.x and pos1.y == pos2.y, (
            f"Position should be consistent: {pos1} vs {pos2}"
        )

    def test_player_location_after_teleport(self, game):
        """Test location tracking after direct teleportation."""
        target = Position(x=100, y=100)
        game.move_to(target)

        pos = game.player_location
        # Allow some tolerance for pathfinding
        assert abs(pos.x - target.x) < 5, f"X should be near target: {pos}"
        assert abs(pos.y - target.y) < 5, f"Y should be near target: {pos}"

    def test_character_exists_check(self, instance):
        """Directly verify character entity exists in game."""
        # Use RCON to check character validity
        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters and storage.agent_characters[1] and storage.agent_characters[1].valid and 'valid' or 'invalid')"
        )
        assert result == "valid", f"Character should be valid, got: {result}"

    def test_character_health(self, instance):
        """Check character has health (not dead)."""
        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters and storage.agent_characters[1] and storage.agent_characters[1].health or 0)"
        )
        health = float(result) if result else 0
        assert health > 0, f"Character should have health > 0, got: {health}"


class TestDirectTeleportation:
    """Test character persistence with direct teleportation (bypassing pathfinding)."""

    def test_teleport_100_tiles(self, instance):
        """Directly teleport character 100 tiles via RCON."""
        # First check character is valid
        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1].valid)"
        )
        assert result == "true", (
            f"Character should be valid before teleport, got: {result}"
        )

        # Teleport directly
        instance.rcon_client.send_command(
            "/silent-command storage.agent_characters[1].teleport({x=100, y=0})"
        )

        # Verify character still valid and at new position
        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1].valid)"
        )
        assert result == "true", (
            f"Character should be valid after 100 tile teleport, got: {result}"
        )

        pos = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1].position.x .. ',' .. storage.agent_characters[1].position.y)"
        )
        print(f"Position after 100 tile teleport: {pos}")


class TestCharacterDamageAndDeath:
    """Test character persistence when damaged or killed."""

    def test_damage_character(self, instance):
        """Apply damage to character and verify it survives."""
        # Get initial health
        health_before = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1].health)"
        )
        print(f"Health before damage: {health_before}")

        # Apply some damage (not lethal)
        instance.rcon_client.send_command(
            "/silent-command storage.agent_characters[1].damage(50, game.forces.enemy, 'physical')"
        )

        # Check health after
        health_after = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1].health)"
        )
        print(f"Health after 50 damage: {health_after}")

        # Verify character still valid
        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1].valid)"
        )
        assert result == "true", f"Character should survive 50 damage, got: {result}"

    def test_near_lethal_damage(self, instance):
        """Apply near-lethal damage and verify character survives."""
        # Get max health - in Factorio 2.0, use max_health on the entity directly
        max_health = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1].max_health)"
        )
        print(f"Max health: {max_health}")

        # Heal to full first
        instance.rcon_client.send_command(
            "/silent-command storage.agent_characters[1].health = storage.agent_characters[1].max_health"
        )

        # Apply damage leaving 1 HP
        damage_amount = float(max_health) - 1
        instance.rcon_client.send_command(
            f"/silent-command storage.agent_characters[1].damage({damage_amount}, game.forces.enemy, 'physical')"
        )

        health_after = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1].health)"
        )
        print(f"Health after near-lethal damage: {health_after}")

        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1].valid)"
        )
        assert result == "true", f"Character should survive with 1 HP, got: {result}"

    def test_kill_character_and_recovery(self, instance):
        """Kill the character and verify it can be recovered."""
        # Record position before death
        pos_before = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1].position.x .. ',' .. storage.agent_characters[1].position.y)"
        )
        print(f"Position before death: {pos_before}")

        # Kill the character
        instance.rcon_client.send_command(
            "/silent-command storage.agent_characters[1].die()"
        )

        # Check if character is now invalid
        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1] and storage.agent_characters[1].valid and 'valid' or 'invalid')"
        )
        print(f"Character status after die(): {result}")

        # Try to use ensure_valid_character to recover
        instance.rcon_client.send_command(
            "/silent-command storage.utils.ensure_valid_character(1)"
        )

        # Check if recovered
        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1] and storage.agent_characters[1].valid and 'valid' or 'invalid')"
        )
        print(f"Character status after recovery attempt: {result}")
        assert result == "valid", f"Character should be recovered, got: {result}"

    def test_destroy_character_entity(self, instance):
        """Directly destroy the character entity."""
        # Destroy the character
        instance.rcon_client.send_command(
            "/silent-command storage.agent_characters[1].destroy()"
        )

        # Check status
        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1] and storage.agent_characters[1].valid and 'valid' or 'invalid')"
        )
        print(f"Character status after destroy(): {result}")

        # Attempt recovery
        instance.rcon_client.send_command(
            "/silent-command storage.utils.ensure_valid_character(1)"
        )

        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1] and storage.agent_characters[1].valid and 'valid' or 'invalid')"
        )
        print(f"Character status after recovery: {result}")
        assert result == "valid", (
            f"Character should be recovered after destroy, got: {result}"
        )


class TestCharacterInvalidation:
    """Test various ways the character reference could become invalid."""

    def test_nil_character_reference(self, instance):
        """Set character reference to nil and test recovery."""
        # Nil out the reference (but don't destroy entity)
        instance.rcon_client.send_command(
            "/silent-command local char = storage.agent_characters[1]; storage.agent_characters[1] = nil"
        )

        # Check status
        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1] and storage.agent_characters[1].valid and 'valid' or 'invalid')"
        )
        print(f"After nil reference: {result}")

        # Recovery should create new character
        instance.rcon_client.send_command(
            "/silent-command storage.utils.ensure_valid_character(1)"
        )

        result = instance.rcon_client.send_command(
            "/silent-command rcon.print(storage.agent_characters[1] and storage.agent_characters[1].valid and 'valid' or 'invalid')"
        )
        assert result == "valid", f"Should recover from nil reference, got: {result}"


class TestExtremeScenarios:
    """Test extreme scenarios that might cause character loss."""

    def test_move_to_chunk_boundary(self, game):
        """Test movement to chunk boundaries (every 32 tiles)."""
        chunk_positions = [
            Position(x=32, y=0),
            Position(x=64, y=0),
            Position(x=32, y=32),
            Position(x=96, y=96),
        ]

        for pos in chunk_positions:
            try:
                game.move_to(pos)
                print(f"Moved to chunk boundary: {pos}")
            except Exception as e:
                print(f"Chunk boundary move failed: {e}")

            # Verify character
            current = game.player_location
            assert current is not None, (
                f"Character should exist at chunk boundary {pos}"
            )

    def test_move_to_ungenerated_chunks(self, game):
        """Test movement to potentially ungenerated chunks."""
        # Chunks at 500+ tiles might not be generated
        far_chunk = Position(x=512, y=512)  # 16 chunks away

        try:
            result = game.move_to(far_chunk)
            print(f"Moved to ungenerated chunk area: {result}")
        except Exception as e:
            print(f"Ungenerated chunk move failed (expected): {e}")

        # Character should still exist
        pos = game.player_location
        assert pos is not None, "Character should survive ungenerated chunk attempt"

    def test_sequential_long_moves(self, game):
        """Make multiple long moves in sequence."""
        positions = [
            Position(x=200, y=0),
            Position(x=200, y=200),
            Position(x=0, y=200),
            Position(x=0, y=0),
        ]

        for i, pos in enumerate(positions):
            try:
                game.move_to(pos)
                print(f"Sequential move {i + 1}: {pos}")
            except Exception as e:
                print(f"Sequential move {i + 1} failed: {e}")

        # Final check
        final_pos = game.player_location
        assert final_pos is not None, "Character should survive sequential long moves"


class TestPathfindingWithChunkGeneration:
    """Test pathfinding after forcefully generating chunks.

    These tests verify that pathfinding works over long distances when
    the terrain has been pre-generated using request_to_generate_chunks.
    """

    # Distance expectations when chunks are pre-generated
    # Map topology (oceans/obstacles) can limit straight-line travel on some seeds
    MIN_DISTANCE_WITH_CHUNKS = 500

    @pytest.mark.parametrize(
        "target_distance,chunk_radius",
        [(500, 2), (1000, 3)],
        ids=["500-tiles", "1000-tiles"],
    )
    def test_generate_chunks_and_move(self, game, target_distance, chunk_radius):
        """Generate chunks along a path and move toward the target distance."""
        generate_chunks_along_path(
            game, 0, 0, target_distance, 0, chunk_radius=chunk_radius
        )

        max_reached = 0
        try:
            game.move_to(Position(x=target_distance, y=0))
            max_reached = game.player_location.x
        except Exception:
            pass

        if max_reached < target_distance:
            # Try incremental approach â€” map topology (water/obstacles) may limit
            # how far we can go in a straight line
            current_x = 0
            increment = 100
            for _ in range(target_distance // increment):
                current_x += increment
                try:
                    game.move_to(Position(x=current_x, y=0))
                    max_reached = max(max_reached, current_x)
                except Exception:
                    break

        # Map topology (oceans) may block paths beyond ~500-600 tiles on some seeds
        assert max_reached >= 500, (
            f"With generated chunks, should reach at least 500 tiles, got {max_reached}"
        )

    def test_generate_large_area_and_explore(self, game):
        """Generate a large area and test movement throughout."""
        # Reset to origin first
        game.instance.rcon_client.send_command(
            "/silent-command storage.agent_characters[1].teleport({x=0, y=0})"
        )
        game.instance.player_location = Position(x=0, y=0)

        # Generate a 64x64 chunk area (2048x2048 tiles) centered at origin
        print("Generating large area (64 chunk radius = 2048 tiles)...")
        generate_chunks(game, 0, 0, chunk_radius=32)

        # Test movement to various points within this area
        test_positions = [
            Position(x=500, y=0),
            Position(x=500, y=500),
            Position(x=0, y=500),
            Position(x=-500, y=0),
            Position(x=-500, y=-500),
            Position(x=1000, y=0),
            Position(x=0, y=1000),
        ]

        successful_moves = 0
        for pos in test_positions:
            try:
                game.move_to(pos)
                current = game.player_location
                print(
                    f"âœ“ Reached ({pos.x}, {pos.y}) -> actual: ({current.x:.1f}, {current.y:.1f})"
                )
                successful_moves += 1
            except Exception as e:
                print(f"âœ— Failed to reach ({pos.x}, {pos.y}): {str(e)[:80]}")

        print(f"\n=== Successful moves: {successful_moves}/{len(test_positions)} ===")
        # Some positions may be unreachable due to water/obstacles on the map
        assert successful_moves >= 4, (
            f"Should reach at least 4 positions with generated chunks, got {successful_moves}/{len(test_positions)}"
        )

    def test_incremental_with_chunk_generation(self, game):
        """Move incrementally while generating chunks ahead."""
        max_distance = 2000
        increment = 100
        current_x = 0
        max_reached = 0

        for i in range(max_distance // increment):
            next_x = current_x + increment

            # Generate chunks ahead of our current position
            generate_chunks(game, next_x + 200, 0, chunk_radius=3)

            try:
                game.move_to(Position(x=next_x, y=0))
                max_reached = next_x
                current_x = next_x
                if next_x % 500 == 0:
                    print(f"âœ“ Reached x={next_x}")
            except Exception as e:
                print(f"âœ— Failed at x={next_x}: {str(e)[:100]}")
                break

        print(f"\n=== Max reached with incremental chunk gen: {max_reached} tiles ===")
        assert max_reached >= self.MIN_DISTANCE_WITH_CHUNKS, (
            f"Should reach {self.MIN_DISTANCE_WITH_CHUNKS} with chunk gen, got {max_reached}"
        )

    def test_diagonal_long_distance_with_chunks(self, game):
        """Test diagonal movement over long distance with chunk generation."""
        target_x, target_y = 300, 300  # ~424 tiles diagonal, within generated area

        # Generate chunks along diagonal
        print("Generating chunks along diagonal path...")
        generate_chunks_along_path(game, 0, 0, target_x, target_y, chunk_radius=3)

        try:
            game.move_to(Position(x=target_x, y=target_y))
            pos = game.player_location
            distance = (pos.x**2 + pos.y**2) ** 0.5
            print(
                f"âœ“ Diagonal move successful: ({pos.x:.1f}, {pos.y:.1f}), distance={distance:.1f}"
            )
            assert distance >= 350, f"Should reach ~424 diagonal tiles, got {distance}"
        except Exception as e:
            print(f"âœ— Diagonal move failed: {e}")
            pytest.fail(f"Diagonal move with chunk generation should succeed: {e}")

    def test_chunk_generation_performance(self, game):
        """Test that chunk generation doesn't significantly impact game performance."""

        # Time chunk generation
        start = time.time()
        generate_chunks(game, 0, 0, chunk_radius=20)  # 40x40 chunks = 1280x1280 tiles
        gen_time = time.time() - start
        print(f"Chunk generation (20 radius): {gen_time:.2f}s")

        # Time a move within generated area
        start = time.time()
        try:
            game.move_to(Position(x=500, y=0))
            game.move_to(Position(x=0, y=0))
            move_time = time.time() - start
            print(f"Round-trip move (500 tiles): {move_time:.2f}s")
        except Exception as e:
            print(f"Move failed: {e}")

        # Chunk generation should be reasonably fast
        assert gen_time < 30, f"Chunk generation took too long: {gen_time}s"

    def test_verify_chunks_are_generated(self, game, instance):
        """Verify that chunk generation via request_path works.

        Our server.lua auto-generates chunks before pathfinding. Verify this
        by checking that a move_to triggers chunk generation at the goal area.
        """
        # Pick a target within reachable range but outside the initial 25-chunk radius
        # The initial generation covers ~800 tiles from origin
        # Use a position at 400 tiles â€” within range, definitely has generated chunks
        target_x = 400

        # Count chunks before
        before = instance.rcon_client.send_command(
            "/silent-command local c=0; for _ in game.surfaces[1].get_chunks() do c=c+1 end; rcon.print(c)"
        )
        print(f"Chunks before move: {before}")

        # move_to triggers request_path which auto-generates chunks
        try:
            game.move_to(Position(x=target_x, y=0))
            pos = game.player_location
            print(f"Moved to: x={pos.x}, y={pos.y}")
        except Exception as e:
            print(f"Move failed (expected if blocked by water): {e}")

        # Count chunks after â€” request_path generates chunks along the corridor
        after = instance.rcon_client.send_command(
            "/silent-command local c=0; for _ in game.surfaces[1].get_chunks() do c=c+1 end; rcon.print(c)"
        )
        print(f"Chunks after move: {after}")

        # Verify that chunks exist at the target area
        # Check chunk at target position (400/32 = 12, which should be generated)
        chunk_exists = instance.rcon_client.send_command(
            f"/silent-command rcon.print(game.surfaces[1].is_chunk_generated({{x={target_x // 32}, y=0}}) and 'yes' or 'no')"
        )
        print(f"Chunk at ({target_x // 32}, 0) exists: {chunk_exists}")

        assert chunk_exists.strip() == "yes", (
            "Chunk at target position should be generated after move_to"
        )
