"""
Verify checklist disjointness rule:
  whitebox task_ids INTERSECT results.jsonl illegal_changes = EMPTY

Per checklist section 3, instruction_following is sourced exclusively from
results.jsonl illegal_changes and must be disjoint from whitebox reports.
"""
import json
import sys
from collections import Counter
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = SCRIPT_DIR / "results"
RIOT_RESULTS = SCRIPT_DIR / "../../../Open_source/RIOT/riot-claude/results"

CHECKS = [
    ("QSem DS", RESULTS_DIR / "deepseek-v4-pro"),
    ("QSem GLM", RESULTS_DIR / "glm-5.1"),
    ("RIOT DS", RIOT_RESULTS),
]

exit_code = 0

for label, d in CHECKS:
    wb_path = d / "whitebox_report.json"
    # RIOT file has a different naming convention
    if label == "RIOT DS" and not wb_path.exists():
        wb_path = d / "whitebox_report_deepseek-v4-pro.json"
    r_path = d / "results.jsonl"
    if label == "RIOT DS" and not r_path.exists():
        r_path = d / "results_deepseek-v4-pro.jsonl"

    if not wb_path.exists():
        print(f"[SKIP] {label}: whitebox not found at {wb_path}")
        continue
    if not r_path.exists():
        print(f"[SKIP] {label}: results.jsonl not found at {r_path}")
        continue

    with open(wb_path, encoding='utf-8') as f:
        wb = json.load(f)
    wb_ids = {w["task_id"] for w in wb}

    # Extract illegal_changes from results.jsonl
    illegal_ids = set()
    with open(r_path, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get('illegal_changes') and len(r['illegal_changes']) > 0:
                illegal_ids.add(r['task_id'])

    overlap = wb_ids & illegal_ids

    # Check no whitebox entry has mechanism == 'instruction_following'
    wb_if = {w["task_id"] for w in wb
             if w.get("mechanism") == "instruction_following"}

    # Check no whitebox entry has L2 == 'integrity_violation'
    wb_iv = {w["task_id"] for w in wb
             if w['classification'].get('L2') == 'integrity_violation'}

    print(f"--- {label} ---")
    print(f"  Whitebox entries: {len(wb)}")
    print(f"  illegal_changes in results.jsonl: {len(illegal_ids)}")

    ok = True
    if overlap:
        print(f"  FAIL: {len(overlap)} task(s) in both: {overlap}")
        ok = False
    else:
        print(f"  PASS: whitebox and illegal_changes are disjoint")

    if wb_if:
        print(f"  FAIL: {len(wb_if)} task(s) with mechanism=instruction_following: {wb_if}")
        ok = False
    else:
        print(f"  PASS: no whitebox entries have mechanism=instruction_following")

    if wb_iv:
        print(f"  FAIL: {len(wb_iv)} task(s) with L2=integrity_violation: {wb_iv}")
        ok = False
    else:
        print(f"  PASS: no whitebox entries have L2=integrity_violation")

    # Final mechanism distribution
    real = [w for w in wb if not w.get('is_false_failure')]
    mech = Counter(w.get('mechanism', '?') for w in real)
    print(f"  whitebox mechanism (real): {dict(mech)}")
    print(f"  instruction_following from results.jsonl: {len(illegal_ids)}")
    print()

    if not ok:
        exit_code = 1

sys.exit(exit_code)
