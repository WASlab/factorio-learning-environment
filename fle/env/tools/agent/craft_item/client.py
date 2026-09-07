from time import sleep

from fle.env.game_types import Prototype
from fle.env.tools.agent.inspect_inventory.client import InspectInventory
from fle.env.tools import Tool


class CraftItem(Tool):
    def __init__(self, connection, game_state):
        super().__init__(connection, game_state)
        self.inspect_inventory = InspectInventory(connection, game_state)

    def __call__(self, entity: Prototype, quantity: int = 1) -> int:
        """
        Craft an item from a Prototype if the ingredients exist in your inventory.
        :param entity: Entity to craft
        :param quantity: Quantity to craft
        :return: Number of items crafted
        """

        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("quantity must be a positive integer")
        if hasattr(entity, "value"):
            name, _ = entity.value
        else:
            name = entity

        count_in_inventory = 0
        if not self.game_state.instance.fast:
            count_in_inventory = self.inspect_inventory()[entity]

        # Track elapsed ticks for fast forward
        ticks_before = self.game_state.instance.get_elapsed_ticks()

        success, elapsed = self.execute(self.player_index, name, quantity)

        if success != {} and isinstance(success, str):
            if success is None:
                raise Exception(
                    f"Could not craft a {name} - Ingredients cannot be crafted by hand."
                )
            else:
                result = self.get_error_message(success)
                raise Exception(result)

        # Sleep for the appropriate real-world time based on elapsed ticks
        ticks_after = self.game_state.instance.get_elapsed_ticks()
        ticks_added = ticks_after - ticks_before
        if ticks_added > 0:
            game_speed = self.game_state.instance.get_speed()
            real_world_sleep = ticks_added / 60 / game_speed if game_speed > 0 else 0
            sleep(real_world_sleep)

        if not self.game_state.instance.fast:
            # Compatibility action: wait for the native crafting queue rather
            # than pretending recipe duration elapsed. New programs should use
            # queue_craft so crafting can overlap movement and other options.
            start_tick = int(
                self.connection.rcon_client.send_command("/sc rcon.print(game.tick)")
                or 0
            )
            timeout_tick = start_tick + 60 * 60 * 10
            while self.inspect_inventory()[entity] - count_in_inventory < success:
                now = int(
                    self.connection.rcon_client.send_command(
                        "/sc rcon.print(game.tick)"
                    )
                    or 0
                )
                if now >= timeout_tick:
                    raise TimeoutError(f"Timed out crafting {quantity}x {name}")
                sleep(0.05)

        return success
