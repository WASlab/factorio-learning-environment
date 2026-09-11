import pytest
from pydantic import ValidationError

from fle.envd.api import RealtimeRequest
from fle.envd.backend import FLEWorker
from fle.envd.service import EnvironmentService
from tests.envd.conftest import FakeWorker

pytestmark = pytest.mark.no_factorio


class StubInstance:
    def __init__(self):
        self.speed = 10.0
        self.paused = True

    def set_speed_and_unpause(self, speed):
        self.speed = speed
        self.paused = False

    def pause(self):
        self.paused = True

    def is_paused(self):
        return self.paused


def _bare_worker() -> FLEWorker:
    worker = FLEWorker.__new__(FLEWorker)
    worker.instance = StubInstance()
    worker._execution_game_speed = 10.0
    worker._realtime_enabled = False
    return worker


def test_worker_set_realtime_toggles_and_enforces_speed_floor():
    worker = _bare_worker()

    state = worker.set_realtime("lease", enabled=True, speed=4)
    assert state["enabled"] is True
    assert state["speed"] == 4.0
    assert worker.instance.paused is False

    state = worker.set_realtime("lease", enabled=False)
    assert state["enabled"] is False
    assert worker.instance.paused is True

    with pytest.raises(ValueError):
        worker.set_realtime("lease", enabled=True, speed=0.5)
    with pytest.raises(ValueError):
        worker.set_realtime("lease", enabled=True, speed=25)


def test_worker_rejects_realtime_when_task_disallows_it():
    worker = _bare_worker()
    worker._realtime_allowed = False
    with pytest.raises(ValueError):
        worker.set_realtime("lease", enabled=True)
    # Disabling is always allowed, even when realtime is disallowed.
    assert worker.set_realtime("lease", enabled=False)["paused"] is True


def test_realtime_request_schema_never_drops_below_one():
    with pytest.raises(ValidationError):
        RealtimeRequest(enabled=True, speed=0.5)
    with pytest.raises(ValidationError):
        RealtimeRequest(enabled=True, speed=11)
    assert RealtimeRequest(enabled=True, speed=1).speed == 1
    assert RealtimeRequest(enabled=False).enabled is False


def test_service_set_realtime_forwards_to_worker(task_spec):
    worker = FakeWorker()
    service = EnvironmentService([worker], lease_ttl_seconds=60)
    lease = service.lease(task_spec)

    state = service.set_realtime(lease.lease_id, enabled=True, speed=2)
    assert state == {"enabled": True, "speed": 2.0, "paused": False}
    assert worker.realtime_enabled is True

    state = service.set_realtime(lease.lease_id, enabled=False)
    assert state["paused"] is True
