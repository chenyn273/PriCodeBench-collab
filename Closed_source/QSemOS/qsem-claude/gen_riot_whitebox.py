"""
Generate RIOT DS whitebox_report.json from manual classifications.
"""
import json
from collections import Counter
from pathlib import Path

from analysis.failure_crosstab import L2_TO_MECH

SCRIPT_DIR = Path(__file__).resolve().parent
RIOT_RESULTS = SCRIPT_DIR / "../../../Open_source/RIOT/riot-claude/results"

with open(RIOT_RESULTS / "results_deepseek-v4-pro.jsonl", encoding='utf-8') as f:
    ds = [json.loads(l) for l in f if l.strip()]

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

test_failure_map = {
    1:   ("wrong_operator", "used / instead of >> causing signed integer rounding error"),
    37:  ("semantic_misunderstanding", "return value semantics wrong: returned hdr_len+payload_len instead of hdr_len"),
    58:  ("algorithm_incomplete", "recovery algorithm incomplete: output '0' instead of '0123456789AB'"),
    67:  ("side_effect_error", "chunk management state machine error: assertion failed"),
    185: ("missing_corner_cases", "VRB add logic missing tag collision detection and duplicate entry handling"),
    196: ("control_flow_error", "PAN compression conditional logic error"),
    198: ("algorithm_incomplete", "frame header construction systematic deviation: 4 tests all failed"),
    199: ("accumulator_precision", "checksum accumulator precision insufficient + odd/even handling deviation"),
    207: ("bit_manipulation_error", "IID bit manipulation error"),
    213: ("architecture_error", "reimplemented low-level logic instead of reusing isrpipe_read_timeout"),
    227: ("missing_conditional_guard", "missing addr/count alignment check + missing driver->erase direct path"),
    247: ("loop_logic_error", "year/month loop calculation error: tm_hour/tm_min/tm_sec all 0"),
    255: ("data_structure_order", "linked list head-insert instead of tail-append (LIFO vs FIFO)"),
    294: ("mixed_guard_and_loop", "missing count==0 early check + loop boundary differs from oracle"),
    347: ("validation_logic_inverted", "empty segment detection and error return logic inverted"),
    349: ("wrong_return_value", "UUID formatting return value error"),
    355: ("missing_conditional_guard", "missing mountp==NULL guard + missing memset clear"),
    364: ("wrong_error_semantics", "treated optional opendir as error: should return 0 but returned -ENOTSUP"),
    387: ("missing_api_call", "missing clock->ops->cancel(clock) call"),
}

compile_error_map = {
    53:  ("werror_style", "-Werror=sign-compare + -Werror=unused-variable"),
    92:  ("werror_style", "-Werror=unused-function"),
    112: ("werror_style", "-Werror=unused-function"),
    136: ("werror_style", "-Werror=unused-variable"),
    139: ("missing_include", "implicit declaration of IPv6 addr functions"),
    205: ("hallucinated_api", "undefined reference to ipv4_addr_from_buf"),
    390: ("hallucinated_symbol", "_callback_wakeup undeclared"),
    439: ("hallucinated_api", "implicit declaration of cib_get_unsafe"),
    455: ("hallucinated_api", "implicit declaration of clist_find_before"),
    457: ("hallucinated_api", "implicit declaration of clist_more_than_one"),
    465: ("hallucinated_api", "implicit declaration of coap_pkt_tkl_ext_len"),
    512: ("hallucinated_api", "undefined reference to gnrc_sixlowpan_frag_rb_base_rm"),
    522: ("type_error", "invalid operands to binary == (struct comparison)"),
    587: ("mixed", "incompatible type + -Werror=return-type"),
}

crash_map = {
    156: ("needs_manual_inspection", "crash root cause not yet analyzed"),
    168: ("needs_manual_inspection", "crash root cause not yet analyzed"),
    369: ("needs_manual_inspection", "crash root cause not yet analyzed"),
    500: ("needs_manual_inspection", "crash root cause not yet analyzed"),
}

wb = []
failed = [r for r in ds if not r['passed']]

for r in failed:
    tid = int(r['task_id'])
    task = r.get('snapshot', {}).get('task', {})
    src = task.get('source_path', '?')
    fn = task.get('sut_function', '?')
    ec = r.get('error_category', 'unknown')

    # Per checklist: illegal_changes tracked in results.jsonl, NOT whitebox.
    if ec == 'illegal_modifications':
        continue

    mod = riot_module(src)

    clf = {"L1": ec, "L2": "unclassified", "L3_detail": []}
    is_ff = False
    actual_pass = False

    if ec == 'test_failure' and tid in test_failure_map:
        l2, l3 = test_failure_map[tid]
        clf = {"L1": ec, "L2": l2, "L3_detail": [l3]}
    elif ec == 'compile_error' and tid in compile_error_map:
        l2, l3 = compile_error_map[tid]
        clf = {"L1": ec, "L2": l2, "L3_detail": [l3]}
    elif ec == 'crash' and tid in crash_map:
        l2, l3 = crash_map[tid]
        clf = {"L1": ec, "L2": l2, "L3_detail": [l3]}
    elif ec == 'test_not_executed':
        clf = {"L1": ec, "L2": "test_not_executed",
               "L3_detail": ["test binary did not execute or shell error"]}

    mech = L2_TO_MECH.get(clf["L2"], 'misunderstanding')

    wb.append({
        "task_id": str(tid),
        "sut_function": fn,
        "source_path": src,
        "module": mod,
        "actual_pass": actual_pass,
        "is_false_failure": is_ff,
        "mechanism": mech,
        "classification": clf,
    })

out_path = RIOT_RESULTS / "whitebox_report_deepseek-v4-pro.json"
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(wb, f, ensure_ascii=False, indent=2)

l1c = Counter(w['classification']['L1'] for w in wb)
l2c = Counter(w['classification']['L2'] for w in wb)
modc = Counter(w['module'] for w in wb)
mechc = Counter(w['mechanism'] for w in wb)

print("=" * 60)
print("RIOT DS whitebox_report.json")
print(f"  {len(wb)} failed tasks")
print(f"\nL1:")
for k, v in l1c.most_common():
    print(f"  {k}: {v}")
print(f"\nL2:")
for k, v in l2c.most_common():
    print(f"  {k}: {v}")
print(f"\nMechanism:")
for k, v in mechc.most_common():
    print(f"  {k}: {v}")
print(f"\nModule L1:")
for k, v in modc.most_common():
    print(f"  {k}: {v}")

print(f"\nMechanism x Module:")
mech_mod = Counter()
for w in wb:
    mech_mod[(w['mechanism'], w['module'])] += 1
mechs = ['instruction_following', 'hallucination', 'misunderstanding']
mods = sorted(modc.keys())
header = f"{'Module':20s}" + "".join(f"{m:>18s}" for m in mechs) + f"{'Total':>8s}"
print(header)
print("-" * len(header))
for mod in mods:
    row = f"{mod:20s}"
    total = 0
    for m in mechs:
        c = mech_mod.get((m, mod), 0)
        row += f"{c:>18d}"
        total += c
    row += f"{total:>8d}"
    print(row)
print("\nDone.")
