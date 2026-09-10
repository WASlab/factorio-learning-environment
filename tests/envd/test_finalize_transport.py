import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import AsyncMock

import aiohttp
import pytest

from fle.envd.client import EnvironmentClientError, HTTPEnvironmentClient
from tests.envd.test_adaptive_contract_backend import _service, _spec

pytestmark = pytest.mark.no_factorio


def test_lost_finalize_response_replays_committed_outcome(monkeypatch):
    service, worker, lease = _service()
    spec = _spec(1)
    service.begin_contract_epoch(lease, spec, request_id="begin")
    worker.tick += 3600
    calls = []

    async def request(method, path, *, json):
        calls.append(dict(json))
        result = service.finalize_contract_epoch(lease, **json)
        if len(calls) == 1:
            raise aiohttp.ServerDisconnectedError("response lost after commit")
        return result.model_dump(mode="json")

    client = HTTPEnvironmentClient("http://unused")
    monkeypatch.setattr(client, "_request", request)
    monkeypatch.setattr("fle.envd.client.asyncio.sleep", AsyncMock())
    result = asyncio.run(
        client.finalize_contract_epoch(
            lease, 1, spec.commitment_hash, request_id="finalize"
        )
    )
    assert result.epoch_index == 1
    assert calls[0] == calls[1]
    assert worker._completed_epochs == 1


@pytest.mark.parametrize(
    "request_id,abandon,attempts", [("id", False, 3), (None, False, 1), ("id", True, 1)]
)
def test_transport_exhaustion_is_bounded_and_classified(
    monkeypatch, request_id, abandon, attempts
):
    client = HTTPEnvironmentClient("http://unused")
    request = AsyncMock(side_effect=aiohttp.ServerDisconnectedError())
    monkeypatch.setattr(client, "_request", request)
    monkeypatch.setattr("fle.envd.client.asyncio.sleep", AsyncMock())
    with pytest.raises(EnvironmentClientError, match="Infrastructure interruption"):
        asyncio.run(
            client.finalize_contract_epoch(
                "lease", 1, "hash", request_id=request_id, abandon=abandon
            )
        )
    assert request.await_count == attempts


def test_validation_errors_are_not_retried(monkeypatch):
    client = HTTPEnvironmentClient("http://unused")
    request = AsyncMock(side_effect=EnvironmentClientError("commitment mismatch"))
    monkeypatch.setattr(client, "_request", request)
    with pytest.raises(EnvironmentClientError, match="commitment mismatch"):
        asyncio.run(client.finalize_contract_epoch("lease", 1, "hash", request_id="id"))
    assert request.await_count == 1


def test_concurrent_finalize_retry_rechecks_cache_under_worker_lock(monkeypatch):
    service, worker, lease = _service()
    spec = _spec(1)
    service.begin_contract_epoch(lease, spec, request_id="begin")
    entered = Event()
    retry_checked = Event()
    finalize = worker.finalize_contract_epoch
    replay = service._replay

    def slow_finalize(*args, **kwargs):
        entered.set()
        assert retry_checked.wait(3)
        return finalize(*args, **kwargs)

    def checked_replay(*args, **kwargs):
        result = replay(*args, **kwargs)
        if entered.is_set():
            retry_checked.set()
        return result

    monkeypatch.setattr(worker, "finalize_contract_epoch", slow_finalize)
    monkeypatch.setattr(service, "_replay", checked_replay)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            service.finalize_contract_epoch,
            lease,
            1,
            spec.commitment_hash,
            request_id="id",
        )
        assert entered.wait(3)
        second = pool.submit(
            service.finalize_contract_epoch,
            lease,
            1,
            spec.commitment_hash,
            request_id="id",
        )
        assert first.result(timeout=5) == second.result(timeout=5)
    assert worker._completed_epochs == 1
