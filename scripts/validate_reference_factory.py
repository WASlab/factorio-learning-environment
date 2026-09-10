"""Build and validate the native reference factory on an isolated Docker pair.

Run: uv run python scripts/validate_reference_factory.py
Only the dedicated fle-reference-factory Compose project is used.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fle.cluster.run_envs import ComposeGenerator
from fle.commons.models.game_state import GameState
from fle.env.entities import Position
from fle.env.game_types import Prototype
from fle.envd.backend import FLEWorker, ThroughputAuditCandidate
from fle.envd.models import FactorioTaskSpec, ThroughputAuditSpec, VerifierSpec
from fle.envd.service import EnvironmentService
from fle.envd.contract_features import extract_difficulty_features
from fle.envd.models import ContractEpochSpec

ARTIFACTS = ROOT / ".runtime/reference-factory"
LAYOUT = ROOT / "tests/fixtures/reference_iron_factory.lua"


def start_cluster():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    generator = ComposeGenerator(state_dir=ARTIFACTS / "state", work_dir=ARTIFACTS)
    services = generator.services_dict(2)
    for index, service in enumerate(services.values()):
        service["ports"] = [
            f"127.0.0.1:{34207 + index}:34197/udp",
            f"127.0.0.1:{27010 + index}:27015/tcp",
        ]
        service["restart"] = "no"
        service["labels"]["fle.reference-factory"] = "true"
    # Retain the existing dedicated service name from early layout validation.
    services = dict(zip(("reference", "audit"), services.values()))
    compose = ARTIFACTS / "compose.yaml"
    compose.write_text(yaml.safe_dump({"services": services}, sort_keys=False))
    subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            "fle-reference-factory",
            "-f",
            str(compose),
            "up",
            "-d",
        ],
        check=True,
    )
    from factorio_rcon import RCONClient

    for port in (27010, 27011):
        deadline = time.monotonic() + 60
        while True:
            try:
                c = RCONClient("127.0.0.1", port, "factorio", timeout=2)
                try:
                    version = c.send_command(
                        "/sc rcon.print(script.active_mods.base)"
                    ).strip()
                    assert version == "2.0.77", version
                finally:
                    c.close()
                break
            except Exception:
                if time.monotonic() > deadline:
                    raise
                time.sleep(1)


def lua(worker, source):
    code = " ".join(
        line for line in source.splitlines() if not line.lstrip().startswith("--")
    )
    result = worker.instance.rcon_client.send_command("/sc " + code) or ""
    if "Cannot execute" in result or "Error" in result:
        raise RuntimeError(result)
    return result


def build(worker):
    return json.loads(lua(worker, LAYOUT.read_text()))


def advance(worker, ticks):
    start = worker._read_game_tick()
    deadline = time.monotonic() + max(30, ticks / 300)
    worker.instance.set_speed_and_unpause(20)
    try:
        while worker._read_game_tick() - start < ticks:
            if time.monotonic() > deadline:
                raise TimeoutError("Reference simulation stalled")
            time.sleep(0.05)
    finally:
        worker.instance.pause()
    worker._sync_active_order()
    return worker._read_game_tick() - start


def candidate(worker, spec, observed_rate):
    state = GameState.from_instance(worker.instance)
    return ThroughputAuditCandidate(
        lease_id="reference",
        session_id=spec.session_id,
        epoch_index=1,
        state=state,
        state_hash=hashlib.sha256(state.to_raw().encode()).hexdigest(),
        candidate_tick=worker._episode_tick(),
        detector_rates={"iron-plate": observed_rate},
        target_rates={"iron-plate": 10},
        depot_specs=[
            {
                "position": {"x": 18.5, "y": 10.5},
                "surface": "nauvis",
                "entity_name": "iron-chest",
                "product": "iron-plate",
                "limit": 1000000,
            }
        ],
        audit_spec=ThroughputAuditSpec(),
        commitment_hash=spec.commitment_hash,
    )


def validate():
    os.environ["FLE_LIFECYCLE_DIR"] = str(ARTIFACTS / "checkpoints")
    start_cluster()
    source = FLEWorker.connect("reference-source", tcp_port=27010)
    auditor = FLEWorker.connect("reference-audit", tcp_port=27011)
    task = FactorioTaskSpec(
        task_id="reference-iron-v1",
        goal="Validate autonomous iron production",
        verifier=VerifierSpec(implementation="objective_engine_v1"),
        adaptive_contract_session=True,
        holdout_seconds=0,
    )
    service = EnvironmentService([source], lease_ttl_seconds=3600)
    lease = service.lease(task)
    auditor.start_task(task)
    build(auditor)  # The audit world uses the identical controlled terrain.
    report = {
        "fixture": "reference-iron-v1",
        "factorio_version": "2.0.77",
        "layout_sha256": hashlib.sha256(LAYOUT.read_bytes()).hexdigest(),
    }
    try:
        report["build"] = build(source)
        context = source.capture_contract_context("reference-iron-v1", 1)
        features = extract_difficulty_features(
            snapshot=context,
            product_id="iron-plate",
            quantity=1000,
            deadline_ticks=360000,
            catalog=source.contract_catalog,
        )
        spec = ContractEpochSpec.create(
            session_id="reference-iron-v1",
            epoch_index=1,
            template_id="reference-iron-v1",
            generation_seed=1,
            selection_seed=1,
            item_name="iron-plate",
            quantity=1000,
            deadline_ticks=360000,
            context=context,
            features=features,
            raw_difficulty=1.0,
            state_advantage=0.0,
            effective_difficulty=1.0,
            order_kind="sustained",
            throughput_audit=ThroughputAuditSpec(),
        )
        service.begin_contract_epoch(lease.lease_id, spec, request_id="reference-begin")
        namespace = source.instance.first_namespace
        chest = namespace.get_entity(Prototype.IronChest, Position(x=18.5, y=10.5))
        binding = namespace.set_delivery_chest(chest, Prototype.IronPlate)
        assert binding["bound"], binding
        print(
            "Built and bound; running 10 simulated minutes without interventions",
            flush=True,
        )
        measured_ticks = advance(source, 36000)
        report["before_resume"] = source._active_order.student_view().model_dump(
            mode="json"
        )
        assert report["before_resume"]["fulfilled"]["iron-plate"] >= 120, report
        print("Testing canonical isolated E2E audit", flush=True)
        audit = auditor.run_throughput_audit(
            candidate(
                source,
                spec,
                report["before_resume"]["fulfilled"]["iron-plate"]
                * 3600
                / measured_ticks,
            )
        )
        report["audit"] = audit.model_dump(mode="json")
        assert audit.passed, report["audit"]
        checkpoint = service.checkpoint(lease.lease_id, name="reference-iron-v1")
        report["checkpoint"] = checkpoint.model_dump(mode="json")
        before = source._active_order.student_view().fulfilled["iron-plate"]
        service.release(lease.lease_id)
        service.lease(
            task.model_copy(update={"checkpoint_id": checkpoint.checkpoint_id})
        )
        advance(source, 7200)
        after = source._active_order.student_view().fulfilled["iron-plate"]
        report["resume_delivery_delta"] = after - before
        assert after - before >= 25, report
        report["resumed_audit"] = auditor.run_throughput_audit(
            candidate(source, spec, (after - before) / 2)
        ).model_dump(mode="json")
        assert report["resumed_audit"]["passed"], report["resumed_audit"]
        print("Checking broken delivery and depleted bootstrap fuel", flush=True)
        # Mutate only the isolated audit clone; the healthy source remains paused.
        lua(auditor, 'game.surfaces[1].find_entity("inserter", {18.5,9.5}).destroy()')
        broken = auditor.run_throughput_audit(candidate(auditor, spec, 0))
        report["broken_delivery"] = broken.model_dump(mode="json")
        assert not broken.passed and broken.depot_rates_per_minute["iron-plate"] == 0
        # Rebuild a fresh fuel-starved factory: five bootstrap coal, no coal miner.
        build(auditor)
        lua(
            auditor,
            'game.surfaces[1].find_entity("electric-mining-drill", {0.5,0.5}).destroy()',
        )
        advance(auditor, 36000)
        starved = auditor.run_throughput_audit(candidate(auditor, spec, 0))
        report["broken_fuel"] = starved.model_dump(mode="json")
        assert (
            not starved.passed
            and starved.production_rates_per_minute["iron-plate"] == 0
        )
        state = GameState.from_instance(source.instance)
        (ARTIFACTS / "reference-iron-v1.json").write_text(state.to_raw())
        report["passed"] = True
        print(
            json.dumps({"passed": True, "report": str(ARTIFACTS / "validation.json")}),
            flush=True,
        )
        return report
    finally:
        (ARTIFACTS / "validation.json").write_text(json.dumps(report, indent=2))
        source.instance.pause()
        auditor.instance.pause()


if __name__ == "__main__":
    validate()
