import argparse
import json
import logging
import pathlib
import re
import sys
from typing import Dict, List, Any, Optional
import jsonschema

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("trace_reducer")

ROOT = pathlib.Path(__file__).parent.parent
SCHEMAS_DIR = ROOT / "schemas"

TYPE_MAP = {
    1: ("BOOT", "OK"),
    2: ("CTX_SWITCH", "OK"),
    3: ("CTX_SWITCH", "OK"),
    4: ("Q_SEND", "OK"),
    5: ("Q_RECV", "OK"),
    6: ("MTX_TAKE", "OK"),
    7: ("MTX_GIVE", "OK"),
    8: ("CTX_SWITCH", "OK"),
    9: ("SNAPSHOT_DUMP", "ERR"),
    10: ("SNAPSHOT_DUMP", "ERR")
}

LINE_RE = re.compile(
    r"^TRC\s+seq=(?P<seq>\d+)\s+ts=(?P<ts>\d+)\s+type=(?P<type>\d+)\s+prio=(?P<prio>\d+)\s+task=(?P<task>\S*)\s+obj=(?P<obj>\S*)\s+value=(?P<val>\d+)"
)

def reduce_uart_log(
    uart_log_text: str,
    case_id: str,
    max_events: int = 100
) -> Dict[str, Any]:
    task_table: Dict[str, Dict[str, Any]] = {}
    resource_table: Dict[str, Dict[str, Any]] = {}
    parsed_events: List[Dict[str, Any]] = []

    for line in uart_log_text.splitlines():
        line = line.strip()
        m = LINE_RE.match(line)
        if not m:
            continue

        seq = int(m.group("seq"))
        ts = int(m.group("ts"))
        evt_type_num = int(m.group("type"))
        prio = int(m.group("prio"))
        task_name = m.group("task") or "system"
        obj_name = m.group("obj") or None
        val = int(m.group("val"))

        event_name, default_ret = TYPE_MAP.get(evt_type_num, ("CTX_SWITCH", "OK"))

        # Update task table
        if task_name not in task_table and task_name != "system":
            task_table[task_name] = {
                "task_id": task_name,
                "base_priority": prio,
                "effective_priority": prio,
                "state": "READY",
                "blocked_on": None
            }
        elif task_name in task_table:
            task_table[task_name]["effective_priority"] = prio

        # State machine for mutexes and resources
        ret_status = default_ret
        TAKE_EVENT_LABELS = {"MUTEX": "MTX_TAKE", "BINARY_SEMAPHORE": "SEM_TAKE", "QUEUE": "Q_RECV"}
        # A resource_table entry (and the ownership state machine) must only be
        # created for events that actually represent a take/give against a real
        # synchronization object -- MTX_TAKE (type=6), CTX_SWITCH-with-object
        # (type=3, the pre-attempt marker -- see below), and MTX_GIVE (type=7).
        # Every other event type can still carry a non-"none" object as a plain
        # descriptive tag (e.g. HEARTBEAT events tagging which task/activity they
        # belong to) without that tag being mistaken for a real resource. Without
        # this gate, infrastructure events like the monitor's own stall-detection
        # SNAPSHOT_DUMP (res="stall") or progress heartbeat (res="progress",
        # truncated to "progres" by the 7-char object field) were leaking into
        # resource_table as fake MUTEX-typed resources -- confirmed to directly
        # cause a real model misdiagnosis (Gate 4 run, case_002: the model built
        # an entire wrong theory around "task 'monitor' blocked on mutex 'stall'").
        # type=3 (TRACE_TASK_RUN) is the only raw type used as a pre-attempt
        # marker; type=2 (TRACE_TASK_READY) and type=8 (TRACE_HEARTBEAT) also
        # map to the same "CTX_SWITCH" label but must never be treated as
        # resource events even when they carry a non-"none" descriptive tag
        # (e.g. a heartbeat naming which task it belongs to) -- so this checks
        # the raw type, not the collapsed output label.
        is_pre_attempt_marker = ( evt_type_num == 3 )
        is_resource_event = (
            obj_name is not None and obj_name != "none" and
            ( event_name in ( "MTX_TAKE", "MTX_GIVE" ) or is_pre_attempt_marker )
        )
        if is_resource_event:
            if obj_name.startswith("mtx"):
                res_type = "MUTEX"
            elif obj_name.startswith("sem"):
                res_type = "BINARY_SEMAPHORE"
            elif obj_name.startswith("q"):
                res_type = "QUEUE"
            else:
                res_type = "MUTEX"

            if obj_name not in resource_table:
                resource_table[obj_name] = {
                    "res_id": obj_name,
                    "type": res_type,
                    "owner": None,
                    "wait_list": []
                }

            res = resource_table[obj_name]
            # A real *_TAKE (type=6) always represents a confirmed successful
            # acquisition. A CTX_SWITCH carrying a resource object (type=3) is
            # an "about to attempt" pre-marker emitted immediately before a
            # blocking take call whose outcome isn't known yet when it fires
            # -- firmware emits this so a permanently-blocked attempt still
            # produces trace evidence even though the real success event can
            # never fire for it. Both are resolved against current ownership
            # the same way, and the reported event is normalized to the
            # resource's real take label instead of being left as a generic
            # CTX_SWITCH (which previously hid every permanent block as
            # ordinary, non-blocking activity).
            if event_name == "MTX_TAKE" or is_pre_attempt_marker:
                event_name = TAKE_EVENT_LABELS.get(res_type, "MTX_TAKE")
                if res["owner"] is None or res["owner"] == task_name:
                    res["owner"] = task_name
                    ret_status = "OK"
                else:
                    ret_status = "BLOCK"
                    if task_name not in res["wait_list"]:
                        res["wait_list"].append(task_name)
                    if task_name in task_table:
                        task_table[task_name]["state"] = "BLOCKED"
                        task_table[task_name]["blocked_on"] = obj_name

            elif event_name == "MTX_GIVE":
                if res["owner"] == task_name:
                    res["owner"] = None
                ret_status = "OK"
                if task_name in task_table and task_table[task_name]["blocked_on"] == obj_name:
                    task_table[task_name]["blocked_on"] = None
                    task_table[task_name]["state"] = "READY"

        evt_id = f"evt-{seq:06d}"
        parsed_events.append({
            "id": evt_id,
            "seq": seq,
            "tick": ts,
            "task": task_name,
            "prio": prio,
            "event": event_name,
            "res": obj_name,
            "ret": ret_status
        })

    # Window trimming: keep the last N events, but ensure un-matched MTX_TAKE events survive!
    critical_indices = set()
    for idx, e in enumerate(parsed_events):
        if e["event"] == "MTX_TAKE" and e["ret"] == "OK":
            # Check if matching give exists later
            has_give = any(e2["event"] == "MTX_GIVE" and e2["res"] == e["res"] for e2 in parsed_events[idx+1:])
            if not has_give:
                critical_indices.add(idx)

    tail_indices = set(range(max(0, len(parsed_events) - max_events), len(parsed_events)))
    selected_indices = sorted(list(critical_indices | tail_indices))
    selected_events = [parsed_events[i] for i in selected_indices]

    evidence_pack = {
        "schema_version": "1.0",
        "case_id": case_id,
        "system_info": {
            "target": "ARM Cortex-M3 (QEMU mps2-an385)",
            "tick_rate_hz": 1000,
            "max_priorities": 5
        },
        "task_table": sorted(list(task_table.values()), key=lambda x: x["task_id"]),
        "resource_table": sorted(list(resource_table.values()), key=lambda x: x["res_id"]),
        "fault_registers": {
            "hardfault_active": False,
            "cfsr": "0x00000000",
            "hfsr": "0x00000000",
            "mmfar": None,
            "bfar": None,
            "pc": None,
            "lr": None,
            "active_irq": None
        },
        "trace_events": selected_events
    }

    # Validate against schema
    with open(SCHEMAS_DIR / "evidence_pack.schema.json") as f:
        schema = json.load(f)
    jsonschema.validate(instance=evidence_pack, schema=schema)
    return evidence_pack

def main():
    parser = argparse.ArgumentParser(description="Deterministic Trace Reducer")
    parser.add_argument("--uart-log", required=True, help="Path to raw uart.log")
    parser.add_argument("--case-id", required=True, help="Opaque case ID")
    parser.add_argument("--output", required=True, help="Path to write evidence_pack.json")
    parser.add_argument("--max-events", type=int, default=100, help="Maximum events to preserve")
    args = parser.parse_args()

    with open(args.uart_log) as f:
        text = f.read()

    pack = reduce_uart_log(text, args.case_id, max_events=args.max_events)
    with open(args.output, "w") as f:
        json.dump(pack, f, indent=2)
    logger.info(f"Generated {args.output} ({len(pack["trace_events"])} events, {len(pack["task_table"])} tasks)")

if __name__ == "__main__":
    main()
