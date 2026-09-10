import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from fle.envd.api import create_app
from fle.envd.backend import FLEWorker
from fle.envd.camera import (
    compact_terrain,
    normalize_render_direction,
    persist_camera_snapshot,
    render_coarse_map,
)
from fle.envd.service import EnvironmentService
from scripts import factorio_codex_mcp as mcp
from tests.envd.conftest import FakeWorker

pytestmark = pytest.mark.no_factorio


def test_camera_artifacts_deduplicate_and_keep_objective_without_image(tmp_path):
    payload = {"image_base64": "aW1hZ2U=", "objective": {"goal": "Launch a rocket"}}
    first = persist_camera_snapshot(tmp_path, payload)
    second = persist_camera_snapshot(tmp_path, payload)
    assert first["artifact"] == second["artifact"]
    assert len(list((tmp_path / "renders").glob("*.png"))) == 1
    metadata = json.loads((tmp_path / "camera-latest.json").read_text())
    assert "image_base64" not in metadata
    assert metadata["objective"]["goal"] == "Launch a rocket"
    assert "artifact" not in payload
    persist_camera_snapshot(
        tmp_path, {"enabled": False, "objective": payload["objective"]}
    )
    assert json.loads((tmp_path / "camera-latest.json").read_text())["enabled"] is False


def test_mcp_keeps_objective_when_camera_is_disabled(monkeypatch):
    monkeypatch.setattr(
        mcp,
        "_camera_call",
        lambda: {"enabled": False, "objective": {"goal": "Research science"}},
    )
    result = json.loads(mcp._with_camera('{"sequence":1}'))
    assert result["sequence"] == 1
    assert result["objective"]["goal"] == "Research science"


def view():
    return {
        "available": True,
        "width": 2,
        "height": 1,
        "cell_size": 4,
        "origin": {"x": 0, "y": 0},
        "center": {"x": 4, "y": 2},
        "cells": [
            {
                "row": 0,
                "column": 0,
                "water": 3,
                "trees": 1,
                "resources": {"iron-ore": 1},
            },
            {"row": 0, "column": 1, "unknown": True},
        ],
        "entities": [],
    }


def test_camera_preserves_overlapping_layers_and_renders_bounded_png():
    raw = view()
    compact = compact_terrain(raw)
    assert compact["terrain_layers"]["water"] == ["1."]
    assert compact["terrain_layers"]["trees"] == ["1."]
    assert compact["terrain_layers"]["unknown"] == [".1"]
    assert "cells" not in compact
    assert render_coarse_map(raw).startswith(b"\x89PNG\r\n\x1a\n")


def test_camera_opt_out_persists_and_wide_view_avoids_detailed_renderer():
    worker = FLEWorker.__new__(FLEWorker)
    reader = Mock(return_value=view())
    worker.instance = SimpleNamespace(
        first_namespace=SimpleNamespace(_public_view=reader)
    )
    worker.render_factory = Mock(side_effect=AssertionError("wide view must be coarse"))
    image = worker.camera("lease", settings={"radius": 96})
    assert base64.b64decode(image["image_base64"]).startswith(b"\x89PNG")
    worker.camera("lease", settings={"enabled": False})
    worker.camera("lease")
    assert reader.call_count == 1
    with pytest.raises(ValueError):
        worker.camera("lease", settings={"radius": 1000})


def test_render_direction_normalization_accepts_every_encoding():
    assert normalize_render_direction(0) == 0
    assert normalize_render_direction(4) == 4
    assert normalize_render_direction(12.0) == 12
    assert normalize_render_direction(2) == 4
    assert normalize_render_direction(6) == 8
    assert normalize_render_direction(14) == 0
    assert normalize_render_direction(None) == 0
    assert normalize_render_direction("junk") == 0


def test_camera_normalizes_entity_directions_before_rendering():
    worker = FLEWorker.__new__(FLEWorker)
    raw = view()
    raw["entities"] = [
        {"name": "burner-mining-drill", "direction": 2.0},
        {"name": "character", "direction": 6},
        {"name": "stone-furnace", "direction": 0},
    ]
    worker.instance = SimpleNamespace(
        first_namespace=SimpleNamespace(_public_view=Mock(return_value=raw))
    )
    captured: dict = {}

    def fake_render(lease, **kwargs):
        captured.update(kwargs)
        return {
            "image_base64": base64.b64encode(b"\x89PNG").decode(),
            "media_type": "image/png",
            "image_sha256": "x",
            "image_bytes": 4,
            "viewport": {},
        }

    worker.render_factory = fake_render
    result = worker.camera("lease")
    directions = [entity["direction"] for entity in captured["camera_entities"]]
    assert directions == [4, 8, 0]
    assert "image_error" not in result


def test_camera_api_validates_bounds_and_forwards_partial_settings(task_spec):
    worker = FakeWorker()
    worker.camera = Mock(return_value={"enabled": False})
    client = TestClient(create_app(EnvironmentService([worker])))
    lease = client.post(
        "/v1/leases",
        json={"task": task_spec.model_dump(mode="json", exclude_computed_fields=True)},
    ).json()
    path = f"/v1/leases/{lease['lease_id']}/camera"
    assert client.post(path, json={"radius": 400}).status_code == 422
    assert client.post(path, json={"enabled": False}).status_code == 200
    assert worker.camera.call_args.kwargs["settings"] == {"enabled": False}


def test_mcp_automatic_camera_preserves_structured_execution_receipt(monkeypatch):
    monkeypatch.setattr(
        mcp, "_camera_call", lambda: {"available": True, "image_base64": "aW1hZ2U="}
    )
    result = mcp._mcp_tool_result(
        mcp._with_camera(json.dumps({"sequence": 7, "status": "error"})), True
    )
    assert result["structuredContent"]["sequence"] == 7
    assert result["content"][1]["type"] == "image"
    assert result["isError"]


def test_bounded_receipts_retain_alerts_when_output_is_large():
    payload = {
        "output": "x" * 10000,
        "status_changes": {"revision": 9, "events": [{"to_status": "no_fuel"}]},
    }
    result = json.loads(mcp._bounded_json_text(payload, max_chars=1000))
    assert result["summary"]["status_changes"]["events"][0]["to_status"] == "no_fuel"


def test_native_harness_sends_current_camera_each_turn_without_image_history():
    from scripts.adaptive_contract_benchmark import OpenAICompatibleAgentSession

    call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(
            name="submit_program", arguments='{"code":"print(1)"}'
        ),
    )
    replies = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[call]))
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="done", tool_calls=[]))
            ]
        ),
    ]
    requests = []

    async def create(**kwargs):
        requests.append(kwargs)
        return replies.pop(0)

    session = OpenAICompatibleAgentSession.__new__(OpenAICompatibleAgentSession)
    session._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    session.model, session.temperature, session.max_turns = "vision-test", 0, 2
    session.messages = []
    session._executor = AsyncMock(return_value="ok")
    session._state_executor = AsyncMock(
        return_value={"available": True, "image_base64": "aW1hZ2U="}
    )
    telemetry = asyncio.run(session.run_epoch("order"))
    assert telemetry.transport_errors == 0
    assert len(requests) == 2
    for request in requests:
        assert request["messages"][-1]["content"][1]["type"] == "image_url"
    assert "aW1hZ2U=" not in json.dumps(session.messages)
