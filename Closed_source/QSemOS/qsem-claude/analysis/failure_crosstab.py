"""
Authoritative L2-to-mechanism mapping for OSKernelBench failure taxonomy.

Per checklist section 3, the three mutually-exclusive mechanism classes are:
  1. instruction_following — illegal_changes non-empty in results.jsonl (judged FIRST)
  2. hallucination — compile errors from inventing non-existent symbols/APIs/types
  3. misunderstanding — all other failures (logic errors, missing guards, crashes, etc.)

CRITICAL: integrity_violation entries do NOT belong in whitebox reports.
instruction_following is sourced exclusively from results.jsonl illegal_changes.
The two sources must be disjoint (verified by verify_disjoint.py).

This module is the single source of truth referenced by:
  - gen_riot_whitebox.py (RIOT whitebox generation)
  - whitebox_analysis.py (QSemOS whitebox generation)
"""

# ---------------------------------------------------------------------------
# Per checklist section 3: exactly these L2s = hallucination
# "编译失败，编造不存在的符号/API/类型"
# ---------------------------------------------------------------------------
CHECKLIST_HALLUCINATION_L2 = {
    'undefined_reference',
    'hallucinated_api',
    'hallucinated_symbol',
    'hallucinated_api_and_wrong_architecture',
    'implicit_declaration',
}

# ---------------------------------------------------------------------------
# L2_TO_MECH: maps whitebox classification.L2 to one of the 3 mechanisms.
#
# Rules:
#   integrity_violation is NOT in this mapping — it is tracked via
#     results.jsonl illegal_changes and must be disjoint from whitebox.
#   L2 in CHECKLIST_HALLUCINATION_L2 -> hallucination
#   everything else -> misunderstanding
# ---------------------------------------------------------------------------
L2_TO_MECH = {
    # -- hallucination (compiler errors from non-existent symbols) --
    'undefined_reference': 'hallucination',
    'hallucinated_api': 'hallucination',
    'hallucinated_symbol': 'hallucination',
    'hallucinated_api_and_wrong_architecture': 'hallucination',
    'implicit_declaration': 'hallucination',

    # -- misunderstanding (everything else) --
    'missing_include': 'misunderstanding',
    'type_error': 'misunderstanding',
    'mixed': 'misunderstanding',
    'werror_style': 'misunderstanding',
    'missing_conditional_guard': 'misunderstanding',
    'extra_conditional_guard': 'misunderstanding',
    'wrong_calculation': 'misunderstanding',
    'missing_synchronization': 'misunderstanding',
    'wrong_error_handling': 'misunderstanding',
    'data_structure_misuse': 'misunderstanding',
    'semantic_drift': 'misunderstanding',
    'missing_null_check': 'misunderstanding',
    'wrong_operator': 'misunderstanding',
    'semantic_misunderstanding': 'misunderstanding',
    'algorithm_incomplete': 'misunderstanding',
    'side_effect_error': 'misunderstanding',
    'missing_corner_cases': 'misunderstanding',
    'control_flow_error': 'misunderstanding',
    'accumulator_precision': 'misunderstanding',
    'bit_manipulation_error': 'misunderstanding',
    'architecture_error': 'misunderstanding',
    'loop_logic_error': 'misunderstanding',
    'data_structure_order': 'misunderstanding',
    'mixed_guard_and_loop': 'misunderstanding',
    'validation_logic_inverted': 'misunderstanding',
    'wrong_return_value': 'misunderstanding',
    'wrong_error_semantics': 'misunderstanding',
    'missing_api_call': 'misunderstanding',
    'test_not_executed': 'misunderstanding',
    'needs_manual_inspection': 'misunderstanding',
    'unclassified': 'misunderstanding',
    'logic_deviation': 'misunderstanding',
    'missing_error_path': 'misunderstanding',
    'empty_stub': 'misunderstanding',
    'unknown_crash': 'misunderstanding',
    'hardware_knowledge_gap': 'misunderstanding',
    'incomplete_implementation': 'misunderstanding',
    'bitmask_error': 'misunderstanding',
    'missing_context_switch': 'misunderstanding',
}


def infer_mechanism(classification, is_false_failure=False):
    """Return the 3-class mechanism for a whitebox entry.

    Per checklist: integrity_violation should NOT appear in whitebox —
    it is tracked exclusively via results.jsonl illegal_changes.

    Args:
        classification: dict with at least 'L1' and 'L2' keys
        is_false_failure: if True, this entry is excluded from failure counts

    Returns:
        One of {'hallucination', 'misunderstanding', 'false_failure'}
        (instruction_following is NOT returned — sourced from results.jsonl)
    """
    if is_false_failure:
        return 'false_failure'
    l2 = classification.get('L2', '')
    if l2 == 'integrity_violation':
        raise ValueError(
            f"integrity_violation found in whitebox — this violates the "
            f"disjointness rule. instruction_following must be sourced from "
            f"results.jsonl illegal_changes only."
        )
    return L2_TO_MECH.get(l2, 'misunderstanding')


def extract_illegal_changes_ids(results_jsonl_path):
    """Return set of task_ids with non-empty illegal_changes in results.jsonl.

    Per checklist section 3, illegal_changes is the ONLY source of
    instruction_following failures.
    """
    import json
    ids = set()
    with open(results_jsonl_path, encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get('illegal_changes') and len(r['illegal_changes']) > 0:
                ids.add(r['task_id'])
    return ids


def count_instruction_following(results_jsonl_path):
    """Return count of instruction_following failures from results.jsonl.

    Per checklist: illegal_changes is the ONLY source of instruction_following.
    These must NOT appear in whitebox reports.
    """
    return len(extract_illegal_changes_ids(results_jsonl_path))


def compute_mechanism_distribution(whitebox_entries):
    """Compute mechanism distribution from whitebox entries.

    This covers only hallucination and misunderstanding.
    instruction_following must be added separately from results.jsonl.

    Args:
        whitebox_entries: list of whitebox dicts (each has classification,
                          is_false_failure). Must NOT contain integrity_violation.

    Returns:
        dict: mechanism -> count (excludes instruction_following)
    """
    from collections import Counter
    mech = Counter()
    for w in whitebox_entries:
        m = infer_mechanism(w['classification'], w.get('is_false_failure', False))
        mech[m] += 1
    return dict(mech)
