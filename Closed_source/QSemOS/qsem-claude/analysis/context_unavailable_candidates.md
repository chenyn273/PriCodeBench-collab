# 上下文不可获取任务候选清单（裂缝③）

oracle 中含有无法从函数签名、参数类型或已有代码上下文推断的领域专用字符串字面量。
按 checklist 要求，正式剔除需 Zibin 确认。

## 已排除（3 条）

| task_id | 函数 | 魔法元素 | 理由 |
|---------|------|---------|------|
| 1 | OsPerfDefaultNotify | printf("perf buf waterline notify!\n") | 魔法字符串，上下文完全无法推断 |
| 5 | OsPerfOutPutInfo | printf("dump section data, addr: %p length: %#x\n", ...) | 格式字符串是任意的 |
| 133 | OsPerfGetEventName | return "timed" / "unknown" | 标签名称无法从宏名推得 |

## 待剔除候选（24 条，均在主数据集中）

全部含有 printf/PRT_Printf 调用，输出领域专用的错误/日志字符串，
模型无法从函数签名或头文件上下文推导。

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

这 24 条候选任务大多数在 DS 和 GLM 下均通过。剔除后数据集规模从 237 降到约 213，
对通过率影响极小。各条在 whitebox 报告中有具体的 pass/fail 状态可查。
