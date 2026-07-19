# OSKernelBench 口径决策记录

> 记录全部口径裂缝的判定顺序、taxonomy 定义、数据质量规则。
> 引用方：checklist §三、analysis/failure_crosstab.py。

## 1. 机制维度 taxonomy（三大类，互斥）

按 checklist §三。判定顺序固定：

1. **指令遵循失败** instruction_following — results.jsonl 的 `illegal_changes` 非空（最先判定）
2. **幻觉** hallucination — 编译失败，编造不存在的符号/API/类型
3. **理解偏差** misunderstanding — 其余所有失败（逻辑、边界、同步、数据结构等）

### 判定顺序（铁律）

```
对每条失败 case：
  1. 若 is_false_failure（L2 = harness_bug_*）→ 整条剔除
  2. 否则若 illegal_changes 非空 → 指令遵循失败
  3. 否则按 L2 映射 → 幻觉 或 理解偏差
```

## 2. 不相交规则（裂缝①）

**illegal_changes 是指令遵循失败的唯一来源。**
whitebox 报告不得包含 integrity_violation 条目。
两个来源必须不相交 — 由 `analysis/verify_disjoint.py` 自动校验。

当前状态（2026-07-20 已验证）：
- QSem DS：1 IF（来自 results.jsonl，task 36），whitebox 真失败 40（11H + 29M）
- QSem GLM：5 IF（来自 results.jsonl，task 150/197/235/6/69），whitebox 真失败 44（13H + 31M）
- RIOT DS：6 IF（来自 results.jsonl，task 151/203/21/491/54/633），whitebox 真失败 44（7H + 37M）
- RIOT GLM：7 IF（task 140/148/192/203/491 原 passed=True 已翻转为 IF 失败；task 21/92 原即 failed+illegal），whitebox 真失败 56（6H + 50M）

## 3. 幻觉 L2 类型

恰好 5 种 L2 映射到幻觉（按 checklist）：
- `undefined_reference`
- `hallucinated_api`
- `hallucinated_symbol`
- `hallucinated_api_and_wrong_architecture`
- `implicit_declaration`

其中 `hallucinated_symbol` 不在 checklist 原始 4 种集合中，但符合语义定义（"编造不存在的符号"），且仅在 RIOT 数据集中出现，故纳入。

## 4. 单一真相源

`analysis/failure_crosstab.py` 是以下内容的权威来源：
- L2_TO_MECH 映射（44 种 L2 类型 → hallucination / misunderstanding）
- CHECKLIST_HALLUCINATION_L2 集合（5 种）
- `infer_mechanism()` 函数
- `extract_illegal_changes_ids()` 和 `count_instruction_following()`

## 5. crash 检测修复（裂缝②）

`agent.py` 第 488–522 行：
- crash 正则匹配源从 `full`（stdout+stderr）改为 `stdout`（仅运行时输出），避免 stderr 中的编译 warning 被误判为 crash
- crash 正则为 `r"(?:Segmentation\s+fault|Aborted|\bpanic\b|signal\s+\d+)"`（保留完整模式，但因匹配源改为 stdout 已不再误命中 ipc/signal 测试的正常输出）
- 修正了 17 条 QSemOS DS 假失败（task 75,76,78,79,81,83,84,85,87,89,124,125,126,127,129,130,131）
- 2026-07-19 验证：用 Claude 的补全体重新编译测试，17/17 全部 100% 通过，证实为真·假失败

## 6. 上下文不可获取任务（裂缝③）

27 条 oracle 中含有无法从上下文推断的领域专用字符串字面量。
详见 `analysis/context_unavailable_candidates.md`。

状态：
- 已从数据集排除 3 条：task 1、5、133
- 仍在数据集中 24 条，待 Zibin 正式确认是否剔除

## 7. 假失败检测

QSemOS DS：17 条 whitebox 标记为 is_false_failure
（task_id：75,76,78,79,81,83,84,85,87,89,124,125,126,127,129,130,131）
根因：原 crash 正则会误命中 ipc/signal 正常测试输出。

QSemOS GLM：31 条 test_failure 中未发现假失败。
（excluded 的 task 5 是假失败，Pass-Rate 100%，已随排除一并移除。）

## 8. 模型覆盖

- 当前活跃：deepseek-v4-pro（QSemOS + RIOT）、glm-5.1（QSemOS 237、RIOT 539）
- RIOT GLM 539 已于 2026-07-19 跑完并生成 whitebox_report_glm5.1.json（56 条，6H + 50M）
- 已移除/未跑：kimi-k2.7-code、qwen3.7
- 模型调用方式：通过 CC-Switch 切换不同模型

## 9. 模块体系

QSemOS L1 模块：`ipc / kernel / perf / utility / extend / other`
RIOT L1 模块：`net, net/app, net/link, net/routing, net/gnrc, net/crosslayer, drivers, sys/fs, sys/timer, sys/ipc, sys/util, core, other`

## 10. 统计口径约定

- 通过率：分模型报（DS 一行、GLM 一行），不跨模型相加
- 失败分类计数：跨模型相加（DS + GLM），同一函数两模型均失败计 2 次（不排重）
- 假失败（is_false_failure=True）：剔除，不计入任何失败类
- 指令遵循：从 results.jsonl 的 illegal_changes 计数，不在 whitebox 中
