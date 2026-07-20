# 上下文不可获取任务候选清单（裂缝③）

oracle 中含有无法从函数签名、参数类型或已有代码上下文推断的领域专用字符串字面量。

**最终决定（2026-07-20）**：以下 3 条已从数据集、results.jsonl、whitebox_report.json 三处同步剔除。分母从 240 → 237。

## 已剔除（3 条）

| task_id | 函数 | 魔法元素 | 理由 |
|---------|------|---------|------|
| 1 | OsPerfDefaultNotify | printf("perf buf waterline notify!\n") | 魔法字符串，上下文完全无法推断 |
| 5 | OsPerfOutPutInfo | printf("dump section data, addr: %p length: %#x\n", ...) | 格式字符串是任意的 |
| 133 | OsPerfGetEventName | return "timed" / "unknown" | 标签名称无法从宏名推得 |

## 待确认候选（24 条，仍在数据集中）

经分析，这 24 条虽然含 printf/PRT_Printf 调用，但模型大多能通过——不存在系统性的"因字符串字面量导致失败"模式。待 Zibin 确认是否进一步剔除。

### perf/output 模块（8 条）
| task_id | 函数 | 魔法字符串示例 |
|---------|------|--------------|
| 6 | OsPerfOutPutInit | "perf buffer watermark configure failed\n" |
| 108 | OsPerfCollectData | "when perf collect data, get task info failed, ret = 0x%x\n" |
| 109 | OsPerfConfig | "perf config type invalid %u!\n" |
| 111 | OsPerfPrintCount | "[%s] eventType: 0x%x [core %u]: %llu\n" |
| 112 | OsPerfStart | "when start perf, pmu not registered!\n" |
| 113 | OsPerfStop | "when stop perf, pmu not registered!\n" |
| 117 | PRT_PerfConfig | "perf config status error : 0x%x\n" |
| 120 | PRT_PerfInit | "perf spin lock init failed, ret = 0x%x\n" |

### perf/timed 模块（3 条）
| task_id | 函数 | 魔法字符串示例 |
|---------|------|--------------|
| 122 | PRT_PerfStart | "perf start status error : 0x%x\n" |
| 135 | OsPerfTimedConfig | "config period invalid, period:%u ms\n" |
| 137 | OsPerfTimedStart | "perf timer start failed, ret = 0x%x\n" |
| 138 | OsPerfTimedStop | "perf timer stop failed, ret = 0x%x\n" |

### kernel/timer 模块（3 条）
| task_id | 函数 | 魔法字符串示例 |
|---------|------|--------------|
| 15 | PRT_TimerCreate | "timer create error, timer type is 0x%x\n" |
| 16 | PRT_TimerDelete | "timer del error handle 0x%x\n" |
| 17 | PRT_TimerGetOverrun | "timer get overrun error handle 0x%x\n" |
| 18 | PRT_TimerRestart | "timer restart error handle 0x%x\n" |

### kernel/timer (query) 模块（3 条）
| task_id | 函数 | 魔法字符串示例 |
|---------|------|--------------|
| 167 | PRT_TimerQuery | "timer query error handle 0x%x\n" |
| 168 | PRT_TimerStart | "timer start error handle 0x%x\n" |
| 169 | PRT_TimerStop | "timer stop error handle 0x%x\n" |

### kernel/ringbuf 模块（4 条）
| task_id | 函数 | 魔法字符串示例 |
|---------|------|--------------|
| 90 | OsRingbufReadLinear | "read linear ring buffer failed, startIdx: %u, cpSize=%u\n" |
| 91 | OsRingbufReadLoop | "read loop ring buffer failed, startIdx: %u, right:%u, cpSize=%u\n" |
| 92 | OsRingbufWriteLinear | "write linear ring buffer failed, endIdx: %u, cpSize=%u\n" |
| 93 | OsRingbufWriteLoop | "write loop ring buffer failed, endIdx: %u, right:%u, cpSize=%u\n" |

### extend/dlmodule 模块（1 条）
| task_id | 函数 | 魔法字符串示例 |
|---------|------|--------------|
| 229 | OsDynModuleLoad | "The file path is empty.", "File check failed." |

---

## 剔除影响

已剔除 3 条（task 1, 5, 133），数据集从 240 降至 237。
3 条中 DS 2 通过 1 失败、GLM 0 通过 3 失败，剔除后 GLM 通过率 +2pp（79.4% → 81.4%）。
