import argparse
import json
import logging
import pathlib
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("benchmark_scorer")

def score_case(
    verdict: Dict[str, Any],
    label: Dict[str, Any],
    evidence_pack: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    case_id = label["case_id"]
    expected_class = label["failure_class"]
    predicted_class = verdict.get("failure_class", "NONE")

    expected_tasks = set(label.get("culprit_tasks", []))
    predicted_tasks = set(verdict.get("culprit_tasks", []))

    expected_objects = set(label.get("culprit_objects", []))
    predicted_objects = set(verdict.get("culprit_objects", []))

    is_fault_expected = label.get("is_fault", False)
    is_fault_predicted = verdict.get("is_fault", False)

    # 1. Classification exact match
    class_match = (expected_class == predicted_class)
    is_fault_match = (is_fault_expected == is_fault_predicted)

    # 2. Culprit task set score (Jaccard similarity)
    if not expected_tasks and not predicted_tasks:
        task_jaccard = 1.0
    else:
        union_tasks = expected_tasks | predicted_tasks
        task_jaccard = len(expected_tasks & predicted_tasks) / len(union_tasks) if union_tasks else 0.0

    # 3. Culprit object set score (Jaccard similarity)
    if not expected_objects and not predicted_objects:
        obj_jaccard = 1.0
    else:
        union_objs = expected_objects | predicted_objects
        obj_jaccard = len(expected_objects & predicted_objects) / len(union_objs) if union_objs else 0.0

    # 4. Evidence reference validity
    evidence_valid = True
    invalid_refs = []
    if evidence_pack:
        valid_evt_ids = {e["id"] for e in evidence_pack.get("trace_events", [])}
        for item in verdict.get("evidence", []):
            ref = item.get("ref", "")
            if ref.startswith("evt-") and ref not in valid_evt_ids:
                evidence_valid = False
                invalid_refs.append(ref)

    # 5. Healthy false positive check
    is_false_positive = (not is_fault_expected and is_fault_predicted)

    return {
        "case_id": case_id,
        "expected_class": expected_class,
        "predicted_class": predicted_class,
        "class_match": class_match,
        "is_fault_match": is_fault_match,
        "task_score": round(task_jaccard, 3),
        "object_score": round(obj_jaccard, 3),
        "evidence_valid": evidence_valid,
        "invalid_refs": invalid_refs,
        "is_false_positive": is_false_positive,
        "confidence": verdict.get("confidence", 0.0)
    }

def aggregate_scores(case_scores: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_cases = len(case_scores)
    if total_cases == 0:
        return {}

    class_matches = sum(1 for s in case_scores if s["class_match"])
    fault_matches = sum(1 for s in case_scores if s["is_fault_match"])
    avg_task_score = sum(s["task_score"] for s in case_scores) / total_cases
    avg_obj_score = sum(s["object_score"] for s in case_scores) / total_cases
    false_positives = sum(1 for s in case_scores if s["is_false_positive"])
    evidence_valid_cases = sum(1 for s in case_scores if s["evidence_valid"])

    # Confusion matrix
    classes = ["DEADLOCK_LOCK_ORDER", "PRIORITY_INVERSION", "MISSED_ISR_NOTIFICATION", "MISSING_MUTEX_RELEASE", "NONE"]
    confusion_matrix = {c: {c2: 0 for c2 in classes} for c in classes}
    for s in case_scores:
        exp = s["expected_class"]
        pred = s["predicted_class"]
        if exp in confusion_matrix and pred in confusion_matrix[exp]:
            confusion_matrix[exp][pred] += 1

    return {
        "total_cases": total_cases,
        "class_accuracy": round(class_matches / total_cases, 3),
        "is_fault_accuracy": round(fault_matches / total_cases, 3),
        "mean_task_jaccard": round(avg_task_score, 3),
        "mean_object_jaccard": round(avg_obj_score, 3),
        "evidence_validity_rate": round(evidence_valid_cases / total_cases, 3),
        "false_positive_count": false_positives,
        "confusion_matrix": confusion_matrix,
        "case_details": case_scores
    }

def generate_markdown_report(summary: Dict[str, Any]) -> str:
    lines = [
        "# Benchmark Evaluation Report",
        f"- **Total Cases Evaluated:** {summary["total_cases"]}",
        f"- **Failure Class Accuracy:** {summary["class_accuracy"] * 100:.1f}%",
        f"- **Fault Detection Accuracy:** {summary["is_fault_accuracy"] * 100:.1f}%",
        f"- **Mean Task Identification (Jaccard):** {summary["mean_task_jaccard"]:.3f}",
        f"- **Mean Resource Identification (Jaccard):** {summary["mean_object_jaccard"]:.3f}",
        f"- **Evidence Reference Validity:** {summary["evidence_validity_rate"] * 100:.1f}%",
        f"- **False Positive Count:** {summary["false_positive_count"]}",
        "",
        "## Case Details",
        "| Case ID | Expected Class | Predicted Class | Match | Task Score | Obj Score | Valid Refs |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for d in summary["case_details"]:
        match_str = "✅ PASS" if d["class_match"] else "❌ FAIL"
        lines.append(f"| {d["case_id"]} | `{d["expected_class"]}` | `{d["predicted_class"]}` | {match_str} | {d["task_score"]} | {d["object_score"]} | {d["evidence_valid"]} |")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="FreeRTOS LLM Benchmark Scorer")
    parser.add_argument("--verdict", required=True, help="Path to verdict JSON")
    parser.add_argument("--label", required=True, help="Path to label JSON")
    parser.add_argument("--evidence", help="Optional path to evidence_pack JSON")
    parser.add_argument("--output", help="Optional path to save score JSON")
    args = parser.parse_args()

    with open(args.verdict) as f:
        verdict = json.load(f)
    with open(args.label) as f:
        label = json.load(f)
    evidence = None
    if args.evidence:
        with open(args.evidence) as f:
            evidence = json.load(f)

    score = score_case(verdict, label, evidence)
    print(json.dumps(score, indent=2))
    if args.output:
        with open(args.output, "w") as f:
            json.dump(score, f, indent=2)

if __name__ == "__main__":
    main()
