import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from fle.env.instance import FactorioInstance

pytestmark = pytest.mark.no_factorio


class _BlockingNamespace:
    _cancel_requested = False

    def eval_with_timeout(self, _expr):
        while not self._cancel_requested:
            time.sleep(0.001)
        raise TimeoutError("cancelled")


class _FakeRconClient:
    def __init__(self):
        self.closed = 0
        self.connected = 0

    def close(self):
        self.closed += 1

    def connect(self):
        self.connected += 1


def test_eval_timeout_stops_worker_and_reconnects_rcon():
    instance = FactorioInstance.__new__(FactorioInstance)
    namespace = _BlockingNamespace()
    rcon = _FakeRconClient()
    instance.namespaces = [namespace]
    instance.rcon_client = rcon
    instance._executor = ThreadPoolExecutor(max_workers=1)
    try:
        with pytest.raises(TimeoutError):
            instance.eval_with_error("wait_forever()", timeout=0.01)
        assert rcon.closed == 1
        assert rcon.connected == 1
        assert namespace._cancel_requested is False
    finally:
        instance._executor.shutdown(wait=True, cancel_futures=True)
