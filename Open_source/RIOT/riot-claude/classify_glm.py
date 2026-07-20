"""
Classify all RIOT GLM failures and generate whitebox_report.
Reuses DS whitebox L2 for overlapping tasks, auto-classifies compile_errors.
"""
import json, os, re
from collections import Counter

RESULTS_PATH = '/home/carl/RIOT/Open_source/RIOT/riot-claude/results/results_glm5.1.jsonl'
DS_WB_PATH = '/home/carl/RIOT/Open_source/RIOT/riot-claude/results/whitebox_report_deepseek-v4-pro.json'
TRAJ_DIR = '/home/carl/RIOT/Open_source/RIOT/riot-claude/trajectory/results_glm5.1'
OUT_PATH = '/home/carl/RIOT/Open_source/RIOT/riot-claude/results/whitebox_report_glm5.1.json'

# L2_TO_MECH from analysis/failure_crosstab.py (import would require path setup)
L2_TO_MECH = {
    'undefined_reference': 'hallucination',
    'hallucinated_api': 'hallucination',
    'hallucinated_symbol': 'hallucination',
    'hallucinated_api_and_wrong_architecture': 'hallucination',
    'implicit_declaration': 'hallucination',
}

with open(RESULTS_PATH) as f:
    results = [json.loads(l) for l in f if l.strip()]

with open(DS_WB_PATH) as f:
    ds_wb = json.load(f)
ds_l2 = {w['task_id']: w for w in ds_wb}

# GLM failures
glm_failed = {r['task_id']: r for r in results if not r['passed']}
glm_illegal = {tid for tid, r in glm_failed.items()
               if r.get('illegal_changes') and len(r.get('illegal_changes', [])) > 0}

print(f'GLM total: {len(results)}, failed: {len(glm_failed)}, illegal: {len(glm_illegal)}')
print(f'Real failures for whitebox: {len(glm_failed) - len(glm_illegal)}')

# Module classifier (same as gen_riot_whitebox.py)
def riot_module(src):
    p = src.lower()
    if any(k in p for k in ['/net/', 'gnrc', 'coap', 'ipv6', 'ipv4', 'ieee802154',
                              'inet_csum', 'fib/', 'dns/', 'ble/', 'gcoap', 'sixlowpan',
                              'netreg', 'pktbuf', 'pktqueue', 'pkt.h']):
        if 'application_layer' in p or 'nanocoap' in p or 'dns/' in p or 'gcoap' in p:
            return 'net/app'
        if 'link_layer' in p or 'ieee802154' in p or 'ble/' in p:
            return 'net/link'
        if 'network_layer' in p or 'ipv6' in p or 'ipv4' in p or 'fib/' in p:
            return 'net/routing'
        if 'gnrc' in p:
            return 'net/gnrc'
        if 'crosslayer' in p or 'inet_csum' in p or 'pktbuf' in p:
            return 'net/crosslayer'
        return 'net'
    if '/drivers/' in p or '/mtd/' in p or '/saul' in p or '/periph' in p:
        return 'drivers'
    if '/vfs/' in p:
        return 'sys/fs'
    if '/ztimer' in p or '/evtimer' in p or '/rtc' in p or '/timex' in p:
        return 'sys/timer'
    if '/bhp/' in p or '/isrpipe' in p or '/msg' in p:
        return 'sys/ipc'
    if '/core/' in p or 'clist.h' in p or 'cib.h' in p:
        return 'core'
    if '/sys/' in p:
        return 'sys/util'
    return 'other'


def classify_task(tid, r):
    """Classify a single failed task. Returns (L1, L2, L3_detail, mechanism)."""
    ec = r.get('error_category', '?')
    fn = r.get('snapshot', {}).get('task', {}).get('sut_function', '?')
    src = r.get('snapshot', {}).get('task', {}).get('source_path', '?')
    mod = riot_module(src)

    # Reuse DS classification if available
    if tid in ds_l2:
        ds = ds_l2[tid]
        l2 = ds['classification']['L2']
        l3 = ds['classification'].get('L3_detail', [])
        mech = L2_TO_MECH.get(l2, 'misunderstanding')
        return ec, l2, l3, mech, mod

    # --- Classify new (GLM-only) failures ---
    log_path = os.path.join(TRAJ_DIR, f'task_{tid}.log')
    content = ''
    if os.path.exists(log_path):
        with open(log_path, errors='replace') as f:
            content = f.read()

    if ec == 'compile_error':
        return classify_compile_error(tid, r, content, mod)
    elif ec == 'test_not_executed':
        return ec, 'test_not_executed', ['test binary did not execute'], 'misunderstanding', mod
    elif ec == 'crash':
        return ec, 'needs_manual_inspection', ['crash root cause not yet analyzed'], 'misunderstanding', mod
    elif ec == 'test_failure':
        return classify_test_failure(tid, r, content, mod)
    else:
        return ec, 'needs_manual_inspection', [f'unknown error_category: {ec}'], 'misunderstanding', mod


def classify_compile_error(tid, r, content, mod):
    """Auto-classify compile errors from error patterns."""
    undef = re.findall(r'undefined reference to\s+`?(\w+)', content)
    if undef:
        return 'compile_error', 'hallucinated_api', [f'undefined reference to {undef[0]}'], 'hallucination', mod

    implicit = re.findall(r'implicit declaration of function', content)
    if implicit:
        return 'compile_error', 'implicit_declaration', ['implicit declaration of function'], 'hallucination', mod

    # Check for undeclared constants (hallucinated_symbol)
    undeclared = re.findall(r'([A-Z_][A-Z_0-9]{2,})\S* undeclared', content)
    if undeclared:
        return 'compile_error', 'hallucinated_symbol', [f'{undeclared[0]} undeclared'], 'hallucination', mod

    # -Werror= patterns
    unused = re.findall(r'-Werror=unused', content)
    if unused:
        return 'compile_error', 'werror_style', ['unused variable/function triggers -Werror'], 'misunderstanding', mod

    werror = re.findall(r'-Werror=(\S+)', content)
    if werror:
        return 'compile_error', 'werror_style', [f'-Werror={werror[0]}'], 'misunderstanding', mod

    # Type errors
    if 'incompatible' in content.lower() or 'conflicting types' in content:
        return 'compile_error', 'type_error', ['type mismatch'], 'misunderstanding', mod

    # Syntax errors
    if 'expected' in content and ('before' in content or 'token' in content):
        return 'compile_error', 'syntax_error', ['syntax error'], 'misunderstanding', mod

    return 'compile_error', 'compilation_error_other', ['compilation error'], 'misunderstanding', mod


def classify_test_failure(tid, r, content, mod):
    """Attempt basic classification from pass rate."""
    pr_match = re.search(r'Pass-Rate:\s*([\d.]+)%\s*\((\d+)/(\d+)\)', content)
    if pr_match:
        pct = float(pr_match.group(1))
        if pct == 0:
            return 'test_failure', 'algorithm_incomplete', [f'all {pr_match.group(3)} tests failed'], 'misunderstanding', mod
        elif pct < 50:
            return 'test_failure', 'logic_error', [f'Pass-Rate: {pct}% ({pr_match.group(2)}/{pr_match.group(3)})'], 'misunderstanding', mod
        else:
            return 'test_failure', 'missing_corner_cases', [f'Pass-Rate: {pct}% ({pr_match.group(2)}/{pr_match.group(3)})'], 'misunderstanding', mod

    # Check for all-fail patterns
    fails = len(re.findall(r'Result\s*:\s*FAIL', content))
    passes = len(re.findall(r'Result\s*:\s*PASS', content))
    if fails > 0 or passes > 0:
        if fails == 0:
            return 'test_failure', 'test_harness_issue', [f'all {passes} PASS but no Pass-Rate'], 'misunderstanding', mod
        pct = passes / (passes + fails) * 100
        if pct < 50:
            return 'test_failure', 'logic_error', [f'{passes}/{passes+fails} passed ({pct:.0f}%)'], 'misunderstanding', mod
        else:
            return 'test_failure', 'missing_corner_cases', [f'{passes}/{passes+fails} passed ({pct:.0f}%)'], 'misunderstanding', mod

    return 'test_failure', 'needs_manual_inspection', ['could not determine pass rate'], 'misunderstanding', mod


# Generate whitebox
wb = []
for tid, r in sorted(glm_failed.items(), key=lambda x: int(x[0])):
    if tid in glm_illegal:
        continue  # illegal_modifications tracked in results.jsonl only

    l1, l2, l3, mech, mod = classify_task(tid, r)
    fn = r.get('snapshot', {}).get('task', {}).get('sut_function', '?')
    src = r.get('snapshot', {}).get('task', {}).get('source_path', '?')

    wb.append({
        "task_id": tid,
        "sut_function": fn,
        "source_path": src,
        "module": mod,
        "actual_pass": False,
        "is_false_failure": False,
        "mechanism": mech,
        "classification": {
            "L1": l1,
            "L2": l2,
            "L3_detail": l3,
        },
    })

# Save
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(wb, f, ensure_ascii=False, indent=2)

# Stats
l1c = Counter(w['classification']['L1'] for w in wb)
l2c = Counter(w['classification']['L2'] for w in wb)
modc = Counter(w['module'] for w in wb)
mechc = Counter(w['mechanism'] for w in wb)

print(f'\n{"="*60}')
print(f'RIOT GLM whitebox_report.json')
print(f'  {len(wb)} entries (excluded {len(glm_illegal)} illegal)')
print(f'\nL1:')
for k, v in l1c.most_common():
    print(f'  {k}: {v}')
print(f'\nL2:')
for k, v in l2c.most_common():
    print(f'  {k}: {v}')
print(f'\nMechanism:')
for k, v in mechc.most_common():
    print(f'  {k}: {v}')
print(f'\nModule:')
for k, v in modc.most_common():
    print(f'  {k}: {v}')

# Mechanism x Module crosstab
print(f'\nMechanism x Module:')
mech_mod = Counter()
for w in wb:
    mech_mod[(w['mechanism'], w['module'])] += 1
mechs = ['instruction_following', 'hallucination', 'misunderstanding']
mods = sorted(modc.keys())
header = f"{'Module':20s}" + "".join(f"{m:>18s}" for m in mechs) + f"{'Total':>8s}"
print(header)
print("-" * len(header))
row_total = 0
for mod in mods:
    row = f"{mod:20s}"
    total = 0
    for m in mechs:
        c = mech_mod.get((m, mod), 0)
        row += f"{c:>18d}"
        total += c
    row += f"{total:>8d}"
    row_total += total
    print(row)
print("-" * len(header))
print(f"{'TOTAL':20s}{'':18s}{'':18s}{'':18s}{row_total:>8d}")

# Compare with DS
print(f'\nComparison with RIOT DS:')
ds_total = len(ds_wb)
ds_mech = Counter(w['mechanism'] for w in ds_wb)
print(f'  DS: {ds_total} entries, mechanism={dict(ds_mech)}')
print(f'  GLM: {len(wb)} entries, mechanism={dict(mechc)}')
print(f'\nDone. Written to {OUT_PATH}')
