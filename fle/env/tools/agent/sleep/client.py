import threading

from fle.env.tools import Tool


class Sleep(Tool):
    # Thread-local storage for tracking accumulated sleep durations per step
    _local = threading.local()

    def __init__(self, connection, game_state):
        super().__init__(connection, game_state)

    @classmethod
    def reset_step_sleep_duration(cls):
        """Reset the accumulated sleep duration for a new step. Call before each step."""
        cls._local.step_sleep_duration = 0.0

    @classmethod
    def get_step_sleep_duration(cls) -> float:
        """Get the accumulated sleep duration for the current step in seconds."""
        return getattr(cls._local, "step_sleep_duration", 0.0)

    @classmethod
    def _add_sleep_duration(cls, duration: float):
        """Add to the accumulated sleep duration for the current step."""
        if not hasattr(cls._local, "step_sleep_duration"):
            cls._local.step_sleep_duration = 0.0
        cls._local.step_sleep_duration += duration

    def __call__(self, seconds: int) -> bool:
        """
        Sleep for up to 15 seconds before continuing. Useful for waiting for actions to complete.
        :param seconds: Number of seconds to sleep.
        :return: True if sleep was successful.
        """
        if seconds <= 0 or seconds > 15:
            raise ValueError("seconds must be between 1 and 15")
        from fle.env.tools.agent.wait.client import Wait

        started = __import__("time").monotonic()
        Wait(self.connection, self.game_state)(int(seconds * 60))
        Sleep._add_sleep_duration(__import__("time").monotonic() - started)
        return True
