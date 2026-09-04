import json
import pathlib
import pytest
from evaluation.scorer import score_case, aggregate_scores

ROOT = pathlib.Path(__file__).parent.parent
FIXTURES_DIR = ROOT / "fixtures/synthetic"

def test_score_case_deadlock():
    with open(FIXTURES_DIR / "case_001_deadlock/mock_verdict.json") as f:
        verdict = json.load(f)
    with open(FIXTURES_DIR / "case_001_deadlock/evidence_pack.json") as f:
        evidence = json.load(f)

    label = {
        "case_id": "case_001",
        "is_fault": True,
        "failure_class": "DEADLOCK_LOCK_ORDER",
        "culprit_tasks": ["taskA", "taskB"],
        "culprit_objects": ["mtx1", "mtx2"]
    }

    res = score_case(verdict, label, evidence)
    assert res["class_match"] is True
    assert res["is_fault_match"] is True
    assert res["task_score"] == 1.0
    assert res["object_score"] == 1.0
    assert res["evidence_valid"] is True
    assert res["is_false_positive"] is False

def test_score_case_healthy():
    with open(FIXTURES_DIR / "case_005_healthy/mock_verdict.json") as f:
        verdict = json.load(f)
    with open(FIXTURES_DIR / "case_005_healthy/evidence_pack.json") as f:
        evidence = json.load(f)

    label = {
        "case_id": "case_005",
        "is_fault": False,
        "failure_class": "NONE",
        "culprit_tasks": [],
        "culprit_objects": []
    }

    res = score_case(verdict, label, evidence)
    assert res["class_match"] is True
    assert res["is_fault_match"] is True
    assert res["is_false_positive"] is False

def test_aggregation():
    case1 = {
        "case_id": "case_001", "expected_class": "DEADLOCK_LOCK_ORDER", "predicted_class": "DEADLOCK_LOCK_ORDER",
        "class_match": True, "is_fault_match": True, "task_score": 1.0, "object_score": 1.0,
        "evidence_valid": True, "invalid_refs": [], "is_false_positive": False, "confidence": 0.95
    }
    case2 = {
        "case_id": "case_005", "expected_class": "NONE", "predicted_class": "NONE",
        "class_match": True, "is_fault_match": True, "task_score": 1.0, "object_score": 1.0,
        "evidence_valid": True, "invalid_refs": [], "is_false_positive": False, "confidence": 0.99
    }
    agg = aggregate_scores([case1, case2])
    assert agg["class_accuracy"] == 1.0
    assert agg["false_positive_count"] == 0
