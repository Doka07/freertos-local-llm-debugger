import json
import pathlib
import pytest
import jsonschema

ROOT = pathlib.Path(__file__).parent.parent
SCHEMAS_DIR = ROOT / "schemas"
FIXTURES_DIR = ROOT / "fixtures/synthetic"

@pytest.fixture
def evidence_schema():
    with open(SCHEMAS_DIR / "evidence_pack.schema.json") as f:
        return json.load(f)

@pytest.fixture
def verdict_schema():
    with open(SCHEMAS_DIR / "verdict.schema.json") as f:
        return json.load(f)

def test_evidence_pack_schema_validity(evidence_schema):
    jsonschema.Draft7Validator.check_schema(evidence_schema)

def test_verdict_schema_validity(verdict_schema):
    jsonschema.Draft7Validator.check_schema(verdict_schema)

@pytest.mark.parametrize("case_dir", [
    "case_001_deadlock",
    "case_002_priority_inversion",
    "case_003_missed_isr",
    "case_004_missing_release",
    "case_005_healthy",
])
def test_synthetic_fixtures_conformance(case_dir, evidence_schema, verdict_schema):
    case_path = FIXTURES_DIR / case_dir
    ev_path = case_path / "evidence_pack.json"
    verdict_path = case_path / "mock_verdict.json"

    assert ev_path.exists(), f"Missing {ev_path}"
    assert verdict_path.exists(), f"Missing {verdict_path}"

    with open(ev_path) as f:
        ev_data = json.load(f)
    with open(verdict_path) as f:
        verdict_data = json.load(f)

    # Validate against schemas
    jsonschema.validate(instance=ev_data, schema=evidence_schema)
    jsonschema.validate(instance=verdict_data, schema=verdict_schema)

    # Verify evidence references match actual event IDs in evidence pack
    event_ids = {evt["id"] for evt in ev_data.get("trace_events", [])}
    for item in verdict_data.get("evidence", []):
        ref = item["ref"]
        if ref.startswith("evt-"):
            assert ref in event_ids, f"Verdict reference {ref} not found in trace_events"

def test_canary_leakage_detection():
    FORBIDDEN_MARKERS = ["deadlock_task", "forbidden_path", "bad_isr", "injected_fault"]
    canary_path = FIXTURES_DIR / "canary_leakage/canary_evidence_pack.json"
    with open(canary_path) as f:
        content = f.read()

    leaks_found = [m for m in FORBIDDEN_MARKERS if m in content]
    assert len(leaks_found) > 0, "Canary must trigger forbidden marker detection!"
