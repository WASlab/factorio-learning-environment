import pytest

from fle.envd.program_policy import ProgramPolicyViolation
from fle.envd.service import EnvironmentService
from fle.envd.templates import (
    ProgramTemplateStore,
    TemplateInvalid,
    TemplateNotFound,
    TemplateQuotaExceeded,
    expand_template,
    validate_parameters,
)
from tests.envd.conftest import FakeWorker

pytestmark = pytest.mark.no_factorio


def test_expand_template_defaults_literals_and_overrides():
    body = "move_to(Position(x={{x}}, y={{y}}))"
    params = [{"name": "x", "default": 1}, {"name": "y", "default": 2}]

    assert expand_template(body, params, None) == "move_to(Position(x=1, y=2))"
    assert (
        expand_template(body, params, {"y": -4.5}) == "move_to(Position(x=1, y=-4.5))"
    )

    literals = "print({{label}}, {{flags}}, {{data}})"
    specs = [
        {"name": "label", "default": 'a "quoted" string'},
        {"name": "flags", "default": [True, None, 3]},
        {"name": "data", "default": {"k": [1, 2]}},
    ]
    assert expand_template(literals, specs, None) == (
        'print("a \\"quoted\\" string", [True, None, 3], {"k": [1, 2]})'
    )


def test_expand_template_rejects_undeclared_unknown_and_bad_parameters():
    params = [{"name": "x", "default": 1}]
    with pytest.raises(TemplateInvalid):
        expand_template("print({{x}}, {{y}})", params, None)
    with pytest.raises(TemplateInvalid):
        expand_template("print({{x}})", params, {"z": 3})
    with pytest.raises(TemplateInvalid):
        validate_parameters([{"name": "x"}])
    with pytest.raises(TemplateInvalid):
        validate_parameters([{"name": "9bad", "default": 1}])


def test_store_roundtrip_versions_usage_and_delete():
    store = ProgramTemplateStore(scope=None)
    saved = store.save(
        "refuel",
        "insert_item(Prototype.Coal, drill, quantity={{n}})",
        description="top up fuel",
        parameters=[{"name": "n", "default": 5}],
    )
    assert saved.version == 1
    assert store.count() == 1

    got = store.get("refuel")
    assert got.code == saved.code
    assert got.parameter_names() == ["n"]

    updated = store.save("refuel", "print(1)")
    assert updated.version == 2
    assert updated.times_run == 0

    store.record_run("refuel", 120, "lease-1")
    assert store.get("refuel").times_run == 1
    assert store.list_summaries()[0]["body_sha256"] == updated.body_sha256[:12]

    assert store.delete("refuel") is True
    assert store.count() == 0
    with pytest.raises(TemplateNotFound):
        store.get("refuel")


def test_store_quota_and_persistent_scope(tmp_path):
    db = tmp_path / "templates.db"
    store = ProgramTemplateStore(scope="lineage-1", db_path=db, max_per_scope=2)
    store.save("a", "print(1)")
    store.save("b", "print(2)")
    with pytest.raises(TemplateQuotaExceeded):
        store.save("c", "print(3)")

    reopened = ProgramTemplateStore(scope="lineage-1", db_path=db)
    assert {summary["name"] for summary in reopened.list_summaries()} == {
        "a",
        "b",
    }


def test_service_save_validates_policy_and_run_expands(task_spec):
    worker = FakeWorker()
    service = EnvironmentService([worker], lease_ttl_seconds=60)
    lease = service.lease(task_spec)

    saved = service.save_template(
        lease.lease_id,
        "greet",
        code="print({{message}})",
        description="say hi",
        parameters=[{"name": "message", "default": "hello"}],
    )
    assert saved["name"] == "greet"
    assert saved["parameters"] == ["message"]
    assert saved["code"] == "print({{message}})"

    with pytest.raises(ProgramPolicyViolation):
        service.save_template(lease.lease_id, "evil", code="import os")

    result = service.run_template(lease.lease_id, "greet", arguments={"message": "hi"})
    assert 'print("hi")' in result.event.result
    assert result.event.template == "greet"
    assert worker.template_store.get("greet").times_run == 1

    listed = service.list_templates(lease.lease_id)
    assert [entry["name"] for entry in listed["templates"]] == ["greet"]
    fetched = service.get_template(lease.lease_id, "greet")
    assert fetched["parameter_specs"][0]["default"] == "hello"
    assert service.delete_template(lease.lease_id, "greet")["deleted"] is True
