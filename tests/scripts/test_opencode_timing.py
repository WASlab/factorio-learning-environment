import json

import pytest

from scripts.adaptive_contract_benchmark import _opencode_tool_seconds

pytestmark = pytest.mark.no_factorio


def test_tool_time_unions_overlaps_retries_and_duplicates():
    def event(start, end):
        return json.dumps(
            {
                "type": "tool_use",
                "part": {"state": {"time": {"start": start, "end": end}}},
            }
        )

    output = "\n".join(
        [
            event(1000, 3000),
            event(1000, 3000),
            event(2000, 4000),
            event(5000, 6000),
            event(8000, 7000),
            event(None, None),
            event(True, 10000),
            "--- retry ---",
        ]
    )
    assert _opencode_tool_seconds(output) == 4.0


def test_absent_tool_timing_is_zero():
    assert _opencode_tool_seconds('{"type":"step_finish"}') == 0.0


def test_epoch_telemetry_separates_tool_time(tmp_path, monkeypatch):
    import asyncio
    import sys
    from types import SimpleNamespace

    import scripts.adaptive_contract_benchmark as runner

    session = runner.OpenCodePersistentAgentSession(
        envd_url="http://127.0.0.1:8172",
        lease_id="test",
        model="test/model",
        reasoning="max",
        timeout_seconds=60,
        artifacts_dir=tmp_path,
        command=sys.executable,
        api_max_retries=0,
    )

    def invoke(_prompt):
        session.terminal_file.write_text(json.dumps({"reason": "contract_fulfilled"}))
        return SimpleNamespace(
            returncode=0,
            timed_out=False,
            stderr="",
            stdout=json.dumps(
                {
                    "type": "tool_use",
                    "sessionID": "timing-test",
                    "part": {"state": {"time": {"start": 1000, "end": 5000}}},
                }
            ),
        )

    session._invoke = invoke
    clock = iter([0.0, 10.0])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(clock))
    try:
        telemetry = asyncio.run(session.run_epoch("order"))
        assert telemetry.tool_seconds == 4.0
        assert telemetry.model_seconds == 6.0
    finally:
        asyncio.run(session.close())
