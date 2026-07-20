"""
Unified whitebox report generator for all four model/benchmark pairs.
Applies consistent L2 taxonomy and schema across QSemOS (DS+GLM) and RIOT (DS+GLM).

Single source of truth for L2 classification:
  - 8 QSemOS types + 2 RIOT-specific (werror_style, test_not_executed)
  - L3_detail preserves fine-grained root cause
  - mechanism auto-derived from L2 via L2_TO_MECH
"""
import json
from collections import Counter
from pathlib import Path

BASE = Path('//wsl.localhost/ubuntu/home/carl/RIOT')

REPORTS = {
    'QSem DS': (
        BASE / 'Closed_source/QSemOS/qsem-claude/results/deepseek-v4-pro/whitebox_report.json',
        BASE / 'Closed_source/QSemOS/qsem-claude/results/deepseek-v4-pro/whitebox_report.json',
    ),
    'QSem GLM': (
        BASE / 'Closed_source/QSemOS/qsem-claude/results/glm-5.1/whitebox_report.json',
        BASE / 'Closed_source/QSemOS/qsem-claude/results/glm-5.1/whitebox_report.json',
    ),
    'RIOT DS': (
        BASE / 'Open_source/RIOT/riot-claude/results/whitebox_report_deepseek-v4-pro.json',
        BASE / 'Open_source/RIOT/riot-claude/results/whitebox_report_deepseek-v4-pro.json',
    ),
    'RIOT GLM': (
        BASE / 'Open_source/RIOT/riot-claude/results/whitebox_report_glm5.1.json',
        BASE / 'Open_source/RIOT/riot-claude/results/whitebox_report_glm5.1.json',
    ),
}

# ---- unified L2 taxonomy ----
# Maps granular L2 → consolidated L2 (10 types + false_failure + needs_manual_inspection)
L2_CONSOLIDATED = {
    # -- hallucination (3→2) --
    'undefined_reference':                 'undefined_reference',
    'hallucinated_symbol':                 'undefined_reference',
    'hallucinated_api':                    'hallucinated_api',
    'hallucinated_api_and_wrong_architecture': 'hallucinated_api',
    'implicit_declaration':                'hallucinated_api',

    # -- missing/excess guard (5→2) --
    'missing_conditional_guard':           'missing_conditional_guard',
    'missing_null_check':                  'missing_conditional_guard',
    'missing_corner_cases':                'missing_conditional_guard',
    'missing_synchronization':             'missing_conditional_guard',
    'extra_conditional_guard':             'extra_conditional_guard',

    # -- wrong calculation (5→1) --
    'wrong_calculation':                   'wrong_calculation',
    'wrong_operator':                      'wrong_calculation',
    'bit_manipulation_error':              'wrong_calculation',
    'loop_logic_error':                    'wrong_calculation',
    'accumulator_precision':               'wrong_calculation',

    # -- logic deviation (15→1) --
    'logic_deviation':                     'logic_deviation',
    'architecture_error':                  'logic_deviation',
    'side_effect_error':                   'logic_deviation',
    'validation_logic_inverted':           'logic_deviation',
    'wrong_error_semantics':               'logic_deviation',
    'wrong_error_handling':                'logic_deviation',
    'data_structure_order':                'logic_deviation',
    'data_structure_misuse':               'logic_deviation',
    'control_flow_error':                  'logic_deviation',
    'type_error':                          'logic_deviation',
    'mixed':                               'logic_deviation',
    'algorithm_incomplete':                'logic_deviation',
    'semantic_misunderstanding':           'logic_deviation',
    'mixed_guard_and_loop':                'logic_deviation',
    'missing_include':                     'logic_deviation',
    'missing_context_switch':              'logic_deviation',
    'hardware_knowledge_gap':              'logic_deviation',
    'incomplete_implementation':           'logic_deviation',

    # -- semantic drift (2→1) --
    'semantic_drift':                      'semantic_drift',
    'wrong_return_value':                  'semantic_drift',

    # -- missing error path (2→1) --
    'missing_error_path':                  'missing_error_path',
    'missing_api_call':                    'missing_error_path',

    # -- RIOT-specific (keep) --
    'werror_style':                        'werror_style',
    'test_not_executed':                   'test_not_executed',

    # -- special (keep) --
    'needs_manual_inspection':             'needs_manual_inspection',
    'unclassified':                        'needs_manual_inspection',
    'unknown_crash':                       'needs_manual_inspection',
    'harness_bug_crash_regex':             'harness_bug_crash_regex',
    'empty_stub':                          'logic_deviation',
    'bitmask_error':                       'wrong_calculation',
}

# mechanism derivation
HALLUCINATION_L2 = {'undefined_reference', 'hallucinated_api'}


def remap(wb_entries):
    """Apply unified L2 taxonomy and ensure mechanism/schema consistency."""
    for w in wb_entries:
        clf = w['classification']
        old_l2 = clf['L2']
        new_l2 = L2_CONSOLIDATED.get(old_l2, old_l2)
        clf['L2'] = new_l2

        # derive mechanism
        if w.get('is_false_failure'):
            w['mechanism'] = 'false_failure'
        elif new_l2 in HALLUCINATION_L2:
            w['mechanism'] = 'hallucination'
        elif new_l2 == 'needs_manual_inspection':
            w['mechanism'] = 'misunderstanding'
        else:
            w['mechanism'] = 'misunderstanding'

        # ensure actual_pass / is_false_failure exist
        if 'actual_pass' not in w:
            w['actual_pass'] = False
        if 'is_false_failure' not in w:
            w['is_false_failure'] = False

    return wb_entries


def main():
    for name, (src, dst) in REPORTS.items():
        with open(src, encoding='utf-8') as f:
            wb = json.load(f)

        # Remove false failure entries (白盒不应包含假失败 — CONTEXT.md §7)
        keep = []
        removed_ff = 0
        for w in wb:
            clf = w['classification']
            is_ff = (clf.get('L1') == 'false_failure_detection'
                     or 'harness_bug' in clf.get('L2', '')
                     or w.get('is_false_failure'))
            if is_ff:
                removed_ff += 1
                continue
            keep.append(w)
        if removed_ff:
            print(f'  Removed {removed_ff} false-failure entries')
            wb = keep

        wb = remap(wb)

        with open(dst, 'w', encoding='utf-8') as f:
            json.dump(wb, f, ensure_ascii=False, indent=2)

        # stats
        real = [w for w in wb if not w.get('is_false_failure')]
        ff = [w for w in wb if w.get('is_false_failure')]
        l1c = Counter(w['classification']['L1'] for w in real)
        l2c = Counter(w['classification']['L2'] for w in real)
        mechc = Counter(w['mechanism'] for w in real)

        print(f'=== {name} ({len(wb)} entries, {len(real)} real, {len(ff)} false-failure) ===')
        print(f'  L1: {dict(l1c)}')
        print(f'  mechanism: {dict(mechc)}')
        print(f'  L2 ({len(l2c)} types):')
        for k, v in l2c.most_common():
            print(f'    {k}: {v}')
        print()


if __name__ == '__main__':
    main()
