"""
Re-test the 17 false-failure tasks using Claude's implementation from trajectory logs.

Extracts the injected body, replaces the function body in func_under_test.c,
compiles, and runs the test to verify pass/fail with the fixed harness.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TRAJECTORY_DIR = SCRIPT_DIR / "trajectory" / "deepseek-v4-pro"
CHECK_TESTS_DIR = Path("/home/carl/RIOT/Closed_source/QSemOS/check_tests/tasks")
RESULTS_PATH = SCRIPT_DIR / "results" / "deepseek-v4-pro" / "results.jsonl"

# 17 false-failure tasks from CONTEXT.md section 7
FALSE_FAILURE_TASKS = [
    75, 76, 78, 79, 81, 83, 84, 85, 87, 89,
    124, 125, 126, 127, 129, 130, 131,
]


def extract_body_from_trajectory(task_id: int) -> str | None:
    """Extract Claude's injected body from trajectory log."""
    log_path = TRAJECTORY_DIR / f"task_{task_id}.log"
    if not log_path.exists():
        print(f"  [SKIP] No trajectory log at {log_path}")
        return None

    with open(log_path, encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Find === Injected Body === section
    match = re.search(
        r'=== Injected Body ===\s*\n=+\n(.*?)\n=+\n=+\n=== Test Output ===',
        content, re.DOTALL
    )
    if not match:
        print(f"  [WARN] Could not find Injected Body section in {log_path}")
        return None

    body = match.group(1).strip()
    if not body:
        print(f"  [WARN] Empty injected body in {log_path}")
        return None

    return body


def inject_body_and_test(task_id: int, body: str) -> dict:
    """Inject body into func_under_test.c, compile, and test."""
    task_dir = CHECK_TESTS_DIR / f"task_{task_id:03d}"
    fut_path = task_dir / "func_under_test.c"
    bak_path = task_dir / "func_under_test.c.bak"

    if not fut_path.exists():
        return {"status": "error", "reason": "func_under_test.c not found"}

    # Read original
    with open(fut_path, encoding='utf-8', errors='replace') as f:
        original = f.read()

    # Save backup if not already present
    if not bak_path.exists():
        with open(bak_path, 'w', encoding='utf-8') as f:
            f.write(original)

    # Find function body: first { after signature through last }
    first_brace = original.find('{')
    last_brace = original.rfind('}')

    if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
        return {"status": "error", "reason": "could not find function body"}

    # Build new file: signature + new body + closing brace
    new_content = original[:first_brace + 1] + '\n' + body + '\n' + original[last_brace:]

    with open(fut_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    # Compile and test (run directly since we're inside WSL)
    try:
        result = subprocess.run(
            f"cd {task_dir} && make clean 2>/dev/null && make 2>&1 && ./test 2>&1",
            shell=True, capture_output=True, text=True, timeout=60,
            cwd=str(task_dir)
        )
    except subprocess.TimeoutExpired:
        # Restore original
        with open(fut_path, 'w', encoding='utf-8') as f:
            f.write(original)
        return {"status": "timeout"}

    stdout = result.stdout
    stderr = result.stderr

    # Check for pass rate (some tests use custom stubs that disable Pass-Rate output)
    pass_match = re.search(r'Pass-Rate:\s*([\d.]+)%\s*\((\d+)/(\d+)\)', stdout)
    compile_ok = "error:" not in stdout.lower() and "error:" not in stderr.lower()

    # Fallback: count individual PASS/FAIL results
    pass_count = len(re.findall(r'Result\s*:\s*PASS', stdout))
    fail_count = len(re.findall(r'Result\s*:\s*FAIL', stdout))
    total_count = pass_count + fail_count

    if pass_match:
        all_passed = float(pass_match.group(1)) == 100.0
        passed_tests = int(pass_match.group(2))
        total_tests = int(pass_match.group(3))
        pass_rate = float(pass_match.group(1))
    elif total_count > 0:
        all_passed = fail_count == 0
        passed_tests = pass_count
        total_tests = total_count
        pass_rate = (pass_count / total_count * 100.0) if total_count > 0 else None
    else:
        all_passed = False
        passed_tests = 0
        total_tests = 0
        pass_rate = None

    # Crash detection (same logic as fixed agent.py)
    crash = bool(re.search(r"(?:Segmentation\s+fault|Aborted)", stdout)) or \
            ("Segmentation fault" in stderr or "Aborted" in stderr)

    # Restore original
    with open(fut_path, 'w', encoding='utf-8') as f:
        f.write(original)

    return {
        "status": "ok",
        "compile_ok": compile_ok,
        "crash": crash,
        "pass_rate": pass_rate,
        "passed_tests": passed_tests,
        "total_tests": total_tests,
        "all_passed": all_passed,
        "stdout": stdout[-500:] if len(stdout) > 500 else stdout,
        "stderr": stderr[-300:] if len(stderr) > 300 else stderr,
    }


def main():
    # Load current results.jsonl to get current state
    results_by_id = {}
    with open(RESULTS_PATH, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            results_by_id[r['task_id']] = r

    print("=" * 60)
    print("Re-testing 17 false-failure tasks")
    print("=" * 60)

    outcomes = {}
    for task_id in FALSE_FAILURE_TASKS:
        tid_str = str(task_id)
        current = results_by_id.get(tid_str, {})
        print(f"\nTask {task_id} ({current.get('error_category', '?')})")

        body = extract_body_from_trajectory(task_id)
        if body is None:
            continue

        result = inject_body_and_test(task_id, body)
        outcomes[task_id] = result

        if result["status"] == "error":
            print(f"  [ERROR] {result.get('reason', 'unknown')}")
        elif result["status"] == "timeout":
            print(f"  [TIMEOUT]")
        else:
            pr = result.get("pass_rate")
            status = "PASS" if result["all_passed"] else "FAIL"
            print(f"  Compile: {'OK' if result['compile_ok'] else 'FAIL'}")
            print(f"  Pass-Rate: {pr}% ({result['passed_tests']}/{result['total_tests']})")
            print(f"  Verdict: {status}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in outcomes.values() if r.get("all_passed"))
    failed = sum(1 for r in outcomes.values()
                 if r.get("status") == "ok" and not r.get("all_passed"))
    errors = sum(1 for r in outcomes.values() if r.get("status") != "ok")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Errors: {errors}")
    print(f"  Total:  {len(outcomes)}")

    # Show which ones still fail
    if failed or errors:
        print("\nStill failing / errors:")
        for tid in sorted(outcomes.keys()):
            r = outcomes[tid]
            if not r.get("all_passed"):
                reason = r.get("reason", f"pass_rate={r.get('pass_rate')}%")
                print(f"  task_{tid}: {reason}")


if __name__ == "__main__":
    main()
