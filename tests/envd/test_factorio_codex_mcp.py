import json
import base64
import urllib.error

import pytest

from scripts import factorio_codex_mcp

pytestmark = pytest.mark.no_factorio


@pytest.fixture(autouse=True)
def reset_repetition_state(monkeypatch):
    monkeypatch.setattr(
        factorio_codex_mcp, "_camera_call", lambda settings=None: {"enabled": False}
    )
    factorio_codex_mcp._reset_repetition_state()
    yield
    factorio_codex_mcp._reset_repetition_state()


def test_mcp_tool_schemas_expose_world_and_throughput_controls():
    tools = {tool["name"]: tool for tool in factorio_codex_mcp.TOOLS}

    assert set(tools) == {
        "factorio_observe_factory",
        "factorio_execute_program",
        "factorio_check_throughput",
    }
    execute_schema = tools["factorio_execute_program"]["inputSchema"]
    assert execute_schema["required"] == ["code"]
    assert execute_schema["additionalProperties"] is False
    throughput_schema = tools["factorio_check_throughput"]["inputSchema"]
    assert throughput_schema["properties"] == {}
    assert throughput_schema["additionalProperties"] is False


def test_mcp_state_query_schema_is_typed_and_available_in_full_profile():
    tools = {
        tool["name"]: tool
        for tool in factorio_codex_mcp.tools_for_profile(memory_enabled=False)
    }

    query = tools["factorio_query_state"]
    schema = query["inputSchema"]
    assert schema["required"] == ["kind"]
    assert schema["properties"]["kind"]["enum"] == [
        "inventory",
        "production",
        "delivery",
        "entities",
        "research",
        "contracts",
        "errors",
        "alerts",
    ]
    assert schema["properties"]["limit"]["maximum"] == 128
    assert schema["properties"]["area"]["additionalProperties"] is False


def test_mcp_render_returns_image_content_and_persists_artifact(monkeypatch, tmp_path):
    png = b"\x89PNG\r\n\x1a\nrender-fixture"
    monkeypatch.setenv("LEASE_ID", "lease-render")
    monkeypatch.setenv("FACTORIO_TOOL_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setattr(
        factorio_codex_mcp,
        "_envd",
        lambda method, path, payload=None: {
            "schema_version": "factorio-factory-render-v1",
            "media_type": "image/png",
            "image_base64": base64.b64encode(png).decode("ascii"),
            "image_sha256": "fixture",
            "image_bytes": len(png),
            "ticks": 120,
            "viewport": {"center_x": 0, "center_y": 0},
        },
    )

    payload, is_error = factorio_codex_mcp._call_tool(
        "factorio_render_factory", {"radius": 24}
    )
    result = factorio_codex_mcp._mcp_tool_result(payload, is_error)

    assert is_error is False
    assert [item["type"] for item in result["content"]] == ["text", "image"]
    assert result["content"][1]["data"] == base64.b64encode(png).decode("ascii")
    assert "image_base64" not in result["structuredContent"]
    assert result["structuredContent"]["artifact"]["retrievable"] is True
    assert len(list((tmp_path / "renders").glob("*.png"))) == 1


def test_mcp_throughput_check_uses_dedicated_idempotent_endpoint(monkeypatch):
    calls = []

    def fake_envd(method, path, payload=None):
        calls.append((method, path, payload))
        return {"contract_status": "open", "performance_score": 0.75}

    monkeypatch.setenv("LEASE_ID", "lease-throughput")
    monkeypatch.setattr(factorio_codex_mcp, "_envd", fake_envd)

    text, is_error = factorio_codex_mcp._call_tool(
        "factorio_check_throughput", {}, request_id="check-1"
    )

    assert is_error is False
    assert json.loads(text)["performance_score"] == 0.75
    assert calls == [
        (
            "POST",
            "/v1/leases/lease-throughput/throughput-check",
            {"request_id": "mcp-throughput:check-1"},
        )
    ]


def test_mcp_execute_uses_lease_path_and_code_only_body(monkeypatch):
    calls = []

    def fake_envd(method, path, payload=None):
        calls.append((method, path, payload))
        return {"ok": True}

    monkeypatch.setenv("LEASE_ID", "lease-123")
    monkeypatch.setattr(factorio_codex_mcp, "_envd", fake_envd)

    text, is_error = factorio_codex_mcp._call_tool(
        "factorio_execute_program", {"code": "print(1)"}
    )

    assert is_error is False
    receipt = json.loads(text)
    assert receipt["schema_version"] == "factorio-execution-receipt-v1"
    assert receipt["status"] == "success"
    assert calls == [("POST", "/v1/leases/lease-123/execute", {"code": "print(1)"})]


def test_mcp_execute_assigns_unique_idempotency_key_per_logical_call(monkeypatch):
    calls = []

    def fake_envd(method, path, payload=None):
        calls.append((method, path, payload))
        return {"ok": True}

    monkeypatch.setenv("LEASE_ID", "lease-idempotent")
    monkeypatch.setattr(factorio_codex_mcp, "_envd", fake_envd)

    factorio_codex_mcp._call_tool(
        "factorio_execute_program",
        {"code": "print(1)"},
        request_id="tool-call-17",
    )
    factorio_codex_mcp._call_tool(
        "factorio_execute_program",
        {"code": "print(1)"},
        request_id="tool-call-17",
    )

    first_payload = calls[0][2]
    assert first_payload["code"] == "print(1)"
    assert first_payload["request_id"].startswith("mcp:")
    assert calls[1][2]["request_id"] != first_payload["request_id"]


def test_mcp_large_payload_is_a_valid_bounded_json_envelope():
    payload = {"inventory": {"iron-plate": "x" * 100_000}}

    text = factorio_codex_mcp._bounded_json_text(payload, max_chars=1_000)
    bounded = json.loads(text)
    result = factorio_codex_mcp._mcp_tool_result(text, False)

    assert len(text) <= 1_000
    assert bounded["truncated"] is True
    assert bounded["original_json_chars"] > 100_000
    assert len(bounded["original_json_sha256"]) == 64
    assert result["structuredContent"] == bounded


def test_model_observation_aggregates_unbounded_craft_history():
    history = [
        {
            "crafted_count": 2,
            "inputs": {"iron-plate": 4},
            "outputs": {"iron-gear-wheel": 2},
        }
        for _ in range(2_000)
    ]
    payload = {
        "lease_id": "lease-observe",
        "ticks": 12_000,
        "production": {
            "input": {"iron-gear-wheel": 4_000},
            "output": {"iron-plate": 8_000},
            "crafted": history,
        },
    }

    shaped = json.loads(factorio_codex_mcp._bounded_json_text(payload))
    crafted = shaped["production"]["crafted"]

    assert crafted["total_operations"] == len(history)
    assert crafted["total_crafts"] == 4_000
    assert crafted["inputs"] == {"iron-plate": 8_000}
    assert crafted["outputs"] == {"iron-gear-wheel": 4_000}
    assert len(crafted["recent"]) <= factorio_codex_mcp.MAX_MODEL_CRAFT_ITEMS
    assert crafted["recent_truncated"] is True
    # The object retained for privileged consumers is not rewritten in place.
    assert isinstance(payload["production"]["crafted"], list)
    assert len(payload["production"]["crafted"]) == len(history)


def test_mcp_execute_bounds_large_event_stream_and_keeps_terminal_error(monkeypatch):
    events = [
        {
            "event_id": f"event-{index}",
            "kind": "contract_progress",
            "tick": index,
            "source": "verifier",
            "payload": {"delivered": index},
        }
        for index in range(1_000)
    ]
    events[400] = {
        "event_id": "event-error",
        "kind": "invalid_action",
        "tick": 400,
        "source": "environment",
        "payload": {"error": "corrective detail"},
    }
    events[-1] = {
        "event_id": "event-terminal",
        "kind": "contract_expired",
        "tick": 999,
        "source": "verifier",
        "payload": {"reason": "deadline"},
    }

    monkeypatch.setenv("LEASE_ID", "lease-events")
    monkeypatch.setattr(
        factorio_codex_mcp,
        "_envd",
        lambda method, path, payload=None: {
            "lease_id": "lease-events",
            "event": {"error": False, "result": "ok"},
            "events": events,
            "terminal_reason": "contract_expired",
        },
    )

    text, is_error = factorio_codex_mcp._call_tool(
        "factorio_execute_program", {"code": "wait(1)"}
    )
    shaped = json.loads(text)

    assert is_error is False
    assert len(text) <= factorio_codex_mcp.MAX_TOOL_RESULT_CHARS
    assert shaped["event_count"] == len(events)
    assert shaped["events_omitted"] > 0
    assert len(shaped["events"]) <= factorio_codex_mcp.MAX_MODEL_EVENT_ITEMS
    assert shaped["terminal_reason"] == "contract_expired"
    assert any(event["kind"] == "invalid_action" for event in shaped["events"])
    assert any(event["kind"] == "contract_expired" for event in shaped["events"])
    assert shaped["event_kind_counts"]["contract_progress"] == 998


def test_execution_receipt_normalizes_event_derived_contract_result():
    shaped = factorio_codex_mcp._execution_receipt(
        {
            "event": {"error": False, "result": "done"},
            "research": {
                "current_research": None,
                "research_progress": 0.0,
                "newly_researched": ["automation"],
            },
            "terminal_reason": None,
            "events": [
                {
                    "kind": "contract_expired",
                    "tick": 900,
                    "payload": {
                        "status": "expired",
                        "requested": {"iron-plate": 100},
                        "delivered": {"iron-plate": 64},
                        "remaining": {"iron-plate": 36},
                        "completion_ratio": 0.64,
                    },
                }
            ],
        }
    )

    assert shaped["terminal_reason"] == "contract_expired"
    assert shaped["research"]["newly_researched"] == ["automation"]
    assert shaped["contract_result"] == {
        "status": "expired",
        "terminal_reason": "contract_expired",
        "tick": 900,
        "requested_by_product": {"iron-plate": 100},
        "delivered_by_product": {"iron-plate": 64},
        "remaining_by_product": {"iron-plate": 36},
        "completion_ratio": 0.64,
    }


def test_terminal_finalization_mode_allows_only_memory_tools(monkeypatch, tmp_path):
    marker = tmp_path / "terminal-finalization.lock"
    marker.write_text("terminal", encoding="utf-8")
    monkeypatch.setenv("MCP_TERMINAL_FINALIZATION_FILE", str(marker))
    monkeypatch.setenv("MEMORY_ENABLED", "1")
    monkeypatch.setattr(
        factorio_codex_mcp,
        "_memory_call",
        lambda name, arguments: {"name": name, "entries": []},
    )

    denied, denied_is_error = factorio_codex_mcp._call_tool(
        "factorio_execute_program", {"code": "wait(1)"}
    )
    allowed, allowed_is_error = factorio_codex_mcp._call_tool(
        "factorio_memory_list", {}
    )

    assert denied_is_error is True
    assert "only factorio_memory_* tools" in denied
    assert allowed_is_error is False
    assert json.loads(allowed)["name"] == "factorio_memory_list"


def test_mcp_execute_large_error_result_keeps_corrective_tail(monkeypatch):
    monkeypatch.setenv("LEASE_ID", "lease-error-tail")
    monkeypatch.setattr(
        factorio_codex_mcp,
        "_envd",
        lambda method, path, payload=None: {
            "event": {
                "error": True,
                "result": "prefix " + ("x" * 20_000) + " corrective detail",
            }
        },
    )

    text, is_error = factorio_codex_mcp._call_tool(
        "factorio_execute_program", {"code": "bad_action()"}
    )
    shaped = json.loads(text)

    assert is_error is True
    assert shaped["output"]["truncated"] is True
    assert "prefix" in shaped["output"]["preview"]
    assert "corrective detail" in shaped["output"]["preview"]


def test_execution_receipt_archives_full_output_for_bounded_retrieval(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LEASE_ID", "lease-artifact")
    monkeypatch.setenv("FACTORIO_TOOL_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setattr(
        factorio_codex_mcp,
        "_envd",
        lambda method, path, payload=None: {
            "event": {
                "sequence": 9,
                "error": False,
                "result": "z" * 10_000,
            },
            "events": [],
        },
    )

    text, _ = factorio_codex_mcp._call_tool(
        "factorio_execute_program", {"code": "print('large')"}
    )
    receipt = json.loads(text)
    first = factorio_codex_mcp._read_execution_artifact(
        {
            "execution_id": receipt["execution_id"],
            "section": "output",
            "max_chars": 1_000,
        }
    )

    assert receipt["output"]["truncated"] is True
    assert first["next_cursor"] is not None
    assert first["total_chars"] > 10_000
    assert (
        factorio_codex_mcp._tool_route("factorio_get_recipe")["route"]
        == "parallel_read"
    )
    assert (
        factorio_codex_mcp._tool_route("factorio_execute_program")["route"]
        == "exclusive_mutation"
    )


def test_small_generic_bound_preserves_terminal_and_error_summary():
    payload = {
        "lease_id": "lease-small-bound",
        "terminal_reason": "contract_expired",
        "event": {"error": True, "result": "action failed: fix the inserter"},
        "events": [
            {"kind": "contract_progress", "tick": index} for index in range(1_000)
        ],
        "inventory": {"iron-plate": "x" * 100_000},
    }

    text = factorio_codex_mcp._bounded_json_text(payload, max_chars=1_000)
    bounded = json.loads(text)

    assert len(text) <= 1_000
    assert bounded["truncated"] is True
    assert bounded["summary"]["terminal_reason"] == "contract_expired"
    assert bounded["summary"]["event"]["error"] is True
    assert "fix the inserter" in bounded["summary"]["event"]["result"]
    assert bounded["summary"]["event_count"] == 1_000


def test_mcp_envd_retries_keyed_ambiguous_transport_failure(monkeypatch):
    attempts = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"ok":true}'

    def urlopen(request, timeout):
        attempts.append((request, timeout))
        if len(attempts) == 1:
            raise urllib.error.URLError("response lost")
        return Response()

    monkeypatch.setenv("ENVD_URL", "http://envd.invalid")
    monkeypatch.setattr(factorio_codex_mcp.urllib.request, "urlopen", urlopen)

    result = factorio_codex_mcp._envd(
        "POST",
        "/v1/leases/lease/execute",
        {"code": "print(1)", "request_id": "mcp:key"},
    )

    assert result == {"ok": True}
    assert len(attempts) == 2


def test_mcp_execute_accepts_known_weak_model_argument_alias(monkeypatch):
    calls = []

    def fake_envd(method, path, payload=None):
        calls.append((method, path, payload))
        return {"ok": True}

    monkeypatch.setenv("LEASE_ID", "lease-123")
    monkeypatch.setattr(factorio_codex_mcp, "_envd", fake_envd)

    _, is_error = factorio_codex_mcp._call_tool(
        "factorio_execute_program", {"program": "print(2)"}
    )

    assert is_error is False
    assert calls[0][2] == {"code": "print(2)"}


def test_mcp_marks_environment_execution_error_as_tool_error(monkeypatch):
    monkeypatch.setenv("LEASE_ID", "lease-error")
    monkeypatch.setattr(
        factorio_codex_mcp,
        "_envd",
        lambda method, path, payload=None: {
            "event": {"error": True, "result": "specific corrective error"}
        },
    )

    text, is_error = factorio_codex_mcp._call_tool(
        "factorio_execute_program", {"code": "nearest(Resource)"}
    )

    assert is_error is True
    assert "specific corrective error" in text


def test_mcp_blocks_fourth_identical_failed_program_without_intervention(monkeypatch):
    calls = []

    def fake_envd(method, path, payload=None):
        calls.append((method, path, payload))
        return {"event": {"error": True, "result": "bad argument"}}

    monkeypatch.setenv("LEASE_ID", "lease-repeat")
    monkeypatch.setattr(factorio_codex_mcp, "_envd", fake_envd)

    responses = [
        factorio_codex_mcp._call_tool(
            "factorio_execute_program",
            {"code": code},
        )
        for code in (
            "nearest(Resource)",
            "nearest( Resource )  # same AST",
            "nearest(Resource)\n",
            "nearest(Resource)",
        )
    ]

    assert len(calls) == 3
    assert all(is_error for _, is_error in responses)
    assert "failed 3 consecutive times" in responses[2][0]
    assert "was not executed again" in responses[3][0]


def test_mcp_different_program_resets_identical_failure_block(monkeypatch):
    calls = []

    def fake_envd(method, path, payload=None):
        calls.append(payload["code"])
        return {"event": {"error": True, "result": "bad argument"}}

    monkeypatch.setenv("LEASE_ID", "lease-reset")
    monkeypatch.setattr(factorio_codex_mcp, "_envd", fake_envd)
    for _ in range(3):
        factorio_codex_mcp._call_tool(
            "factorio_execute_program", {"code": "nearest(Resource)"}
        )

    _, is_error = factorio_codex_mcp._call_tool(
        "factorio_execute_program", {"code": "nearest(Resource.Coal)"}
    )

    assert is_error is True
    assert calls[-1] == "nearest(Resource.Coal)"


def test_mcp_observe_and_unknown_tool(monkeypatch):
    calls = []

    def fake_envd(method, path, payload=None):
        calls.append((method, path, payload))
        return {"inventory": {}}

    monkeypatch.setenv("LEASE_ID", "lease-456")
    monkeypatch.setattr(factorio_codex_mcp, "_envd", fake_envd)

    text, is_error = factorio_codex_mcp._call_tool("factorio_observe_factory", {})
    assert is_error is False
    assert json.loads(text) == {"inventory": {}}
    assert calls == [("GET", "/v1/leases/lease-456/observe", None)]

    text, is_error = factorio_codex_mcp._call_tool("missing", {})
    assert is_error is True
    assert "unknown tool" in text


def test_mcp_observe_forwards_cursor_and_keyframe_request(monkeypatch):
    calls = []

    def fake_envd(method, path, payload=None):
        calls.append((method, path, payload))
        return {"contracts": []}

    monkeypatch.setenv("LEASE_ID", "lease-cursor")
    monkeypatch.setattr(factorio_codex_mcp, "_envd", fake_envd)

    text, is_error = factorio_codex_mcp._call_tool(
        "mcp__factorio__factorio_observe_factory",
        {"cursor": "nonce.4", "keyframe": True},
    )

    assert is_error is False
    assert json.loads(text) == {"contracts": []}
    assert calls == [
        (
            "GET",
            "/v1/leases/lease-cursor/observe?cursor=nonce.4&keyframe=true",
            None,
        )
    ]


def test_mcp_state_query_forwards_bounded_filters(monkeypatch):
    calls = []

    def fake_envd(method, path, payload=None):
        calls.append((method, path, payload))
        return {"kind": "entities", "mutations": []}

    monkeypatch.setenv("LEASE_ID", "lease-query")
    monkeypatch.setattr(factorio_codex_mcp, "_envd", fake_envd)

    text, is_error = factorio_codex_mcp._call_tool(
        "factorio_query_state",
        {
            "kind": "entities",
            "entity_type": "assembling-machine-1",
            "area": {"x": 1, "y": -2, "radius": 40},
            "changed_since": 7,
            "limit": 8,
        },
    )

    assert is_error is False
    assert json.loads(text)["kind"] == "entities"
    assert calls == [
        (
            "GET",
            "/v1/leases/lease-query/state/query?kind=entities&entity_type=assembling-machine-1&area=%7B%22x%22%3A1%2C%22y%22%3A-2%2C%22radius%22%3A40%7D&changed_since=7&limit=8",
            None,
        )
    ]


def test_mcp_accepts_prefixed_names_and_rejects_empty_program(monkeypatch):
    calls = []

    def fake_envd(method, path, payload=None):
        calls.append((method, path, payload))
        return {"ok": True}

    monkeypatch.setenv("LEASE_ID", "lease-789")
    monkeypatch.setattr(factorio_codex_mcp, "_envd", fake_envd)

    _, observe_error = factorio_codex_mcp._call_tool(
        "mcp__factorio__factorio_observe_factory", {}
    )
    _, execute_error = factorio_codex_mcp._call_tool(
        "mcp__factorio__factorio_execute_program", {"code": "print(3)"}
    )
    empty, empty_error = factorio_codex_mcp._call_tool(
        "factorio_execute_program", {"code": ""}
    )

    assert observe_error is False
    assert execute_error is False
    assert calls == [
        ("GET", "/v1/leases/lease-789/observe", None),
        ("POST", "/v1/leases/lease-789/execute", {"code": "print(3)"}),
    ]
    assert empty_error is True
    assert "non-empty" in empty


@pytest.mark.parametrize(
    ("tool_name", "result", "expected_reason"),
    [
        (
            "factorio_observe_factory",
            {"contracts": [{"order_id": "epoch-order", "status": "fulfilled"}]},
            "contract_fulfilled",
        ),
        (
            "factorio_execute_program",
            {"terminal_reason": "contract_expired"},
            "contract_expired",
        ),
        (
            "factorio_execute_program",
            {
                "terminal_reason": None,
                "events": [{"kind": "contract_fulfilled"}],
            },
            "contract_fulfilled",
        ),
    ],
)
def test_mcp_signals_closed_contract(
    monkeypatch, tmp_path, tool_name, result, expected_reason
):
    terminal_file = tmp_path / "terminal.json"
    monkeypatch.setenv("LEASE_ID", "lease-terminal")
    monkeypatch.setenv("MCP_TERMINAL_FILE", str(terminal_file))
    monkeypatch.setattr(
        factorio_codex_mcp,
        "_envd",
        lambda method, path, payload=None: result,
    )

    arguments = {"code": "sleep(1)"} if "execute" in tool_name else {}
    _, is_error = factorio_codex_mcp._call_tool(tool_name, arguments)

    assert is_error is False
    assert json.loads(terminal_file.read_text(encoding="utf-8"))["reason"] == (
        expected_reason
    )


def test_mcp_does_not_treat_empty_static_contract_view_as_terminal(
    monkeypatch, tmp_path
):
    terminal_file = tmp_path / "terminal.json"
    monkeypatch.setenv("LEASE_ID", "lease-terminal")
    monkeypatch.setenv("MCP_TERMINAL_FILE", str(terminal_file))
    monkeypatch.setattr(
        factorio_codex_mcp,
        "_envd",
        lambda method, path, payload=None: {"contracts": []},
    )

    _, is_error = factorio_codex_mcp._call_tool("factorio_observe_factory", {})

    assert is_error is False
    assert not terminal_file.exists()
