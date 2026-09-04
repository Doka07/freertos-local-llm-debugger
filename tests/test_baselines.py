import json
import pathlib
import pytest
import jsonschema
from evaluation.baselines.graph_detector import analyze_evidence_pack

ROOT = pathlib.Path(__file__).parent.parent
SCHEMAS_DIR = ROOT / "schemas"
FIXTURES_DIR = ROOT / "fixtures/synthetic"

@pytest.fixture
def verdict_schema():
    with open(SCHEMAS_DIR / "verdict.schema.json") as f:
        return json.load(f)

def test_graph_detector_on_deadlock(verdict_schema):
    with open(FIXTURES_DIR / "case_001_deadlock/evidence_pack.json") as f:
        pack = json.load(f)
    verdict = analyze_evidence_pack(pack)
    jsonschema.validate(instance=verdict, schema=verdict_schema)

    assert verdict["is_fault"] is True
    assert verdict["failure_class"] == "DEADLOCK_LOCK_ORDER"
    assert sorted(verdict["culprit_tasks"]) == ["taskA", "taskB"]
    assert sorted(verdict["culprit_objects"]) == ["mtx1", "mtx2"]
    assert len(verdict["evidence"]) >= 2

def test_graph_detector_on_healthy(verdict_schema):
    with open(FIXTURES_DIR / "case_005_healthy/evidence_pack.json") as f:
        pack = json.load(f)
    verdict = analyze_evidence_pack(pack)
    jsonschema.validate(instance=verdict, schema=verdict_schema)

    assert verdict["is_fault"] is False
    assert verdict["failure_class"] == "NONE"
    assert verdict["culprit_tasks"] == []
    assert verdict["culprit_objects"] == []
