import json
import argparse
import pathlib
from typing import Dict, List, Tuple, Any, Optional

ROOT = pathlib.Path(__file__).parent.parent.parent
SCHEMAS_DIR = ROOT / "schemas"

def detect_cycle_dfs(graph: Dict[str, List[str]]) -> Optional[List[str]]:
    visited = set()
    rec_stack = []

    def dfs(node: str) -> Optional[List[str]]:
        visited.add(node)
        rec_stack.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                res = dfs(neighbor)
                if res:
                    return res
            elif neighbor in rec_stack:
                cycle_start_idx = rec_stack.index(neighbor)
                return rec_stack[cycle_start_idx:]

        rec_stack.pop()
        return None

    for n in list(graph.keys()):
        if n not in visited:
            cycle = dfs(n)
            if cycle:
                return cycle
    return None

def analyze_evidence_pack(pack: Dict[str, Any]) -> Dict[str, Any]:
    case_id = pack["case_id"]
    task_table = {t["task_id"]: t for t in pack.get("task_table", [])}
    resource_table = {r["res_id"]: r for r in pack.get("resource_table", [])}
    trace_events = pack.get("trace_events", [])

    # Build Wait-For Graph: Task -> Task
    # Edge T_waiter -> T_owner exists if T_waiter is blocked on a resource owned by T_owner
    wait_for_graph = {}
    task_to_res = {}

    for tid, tinfo in task_table.items():
        blocked_on = tinfo.get("blocked_on")
        if blocked_on and blocked_on in resource_table:
            owner = resource_table[blocked_on].get("owner")
            if owner and owner != tid:
                wait_for_graph.setdefault(tid, []).append(owner)
                task_to_res[(tid, owner)] = blocked_on

    cycle = detect_cycle_dfs(wait_for_graph)

    if cycle:
        contested_resources = []
        evidence = []
        for i in range(len(cycle)):
            u = cycle[i]
            v = cycle[(i + 1) % len(cycle)]
            res = task_to_res.get((u, v))
            if res and res not in contested_resources:
                contested_resources.append(res)

        # Find supporting trace events
        for evt in trace_events:
            if evt.get("event") == "MTX_TAKE" and evt.get("task") in cycle and evt.get("res") in contested_resources:
                evidence.append({
                    "ref": evt["id"],
                    "claim": f"{evt["task"]} MTX_TAKE on {evt["res"]} returned {evt["ret"]}"
                })

        cycle_str = " -> ".join(cycle + [cycle[0]])
        return {
          "schema_version": "1.0",
          "case_id": case_id,
          "is_fault": True,
          "failure_class": "DEADLOCK_LOCK_ORDER",
          "confidence": 1.0,
          "culprit_tasks": sorted(list(set(cycle))),
          "culprit_objects": sorted(contested_resources),
          "evidence": evidence if evidence else [{"ref": "reg-status", "claim": f"Deterministic cycle: {cycle_str}"}],
          "recommended_fix": f"Break circular wait ({cycle_str}) by enforcing strict lock acquisition hierarchy."
        }

    return {
      "schema_version": "1.0",
      "case_id": case_id,
      "is_fault": False,
      "failure_class": "NONE",
      "confidence": 0.99,
      "culprit_tasks": [],
      "culprit_objects": [],
      "evidence": [],
      "recommended_fix": "No deadlock cycle detected by deterministic wait-for-graph detector."
    }

def main():
    parser = argparse.ArgumentParser(description="Deterministic Wait-For-Graph Cycle Detector")
    parser.add_argument("--evidence", required=True, help="Path to evidence_pack.json")
    parser.add_argument("--output", help="Path to output verdict.json")
    args = parser.parse_args()

    with open(args.evidence) as f:
        pack = json.load(f)

    verdict = analyze_evidence_pack(pack)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(verdict, f, indent=2)
    else:
        print(json.dumps(verdict, indent=2))

if __name__ == "__main__":
    main()
