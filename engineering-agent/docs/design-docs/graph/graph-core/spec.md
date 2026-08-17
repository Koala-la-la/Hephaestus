# Spec: Graph 层最小原型

> Status: Quick Draft
> 上游设计文档：`../../../engineering-agent-design.md`（简称 design doc）
> 本 spec 锚定第四轮实现范围——Graph 层四块核心功能。

---

## 1. 背景

Harness（v0.6.0）+ Loop（v0.7.0）+ Context（v0.8.0）已实现。Graph 层是 design doc §19 实施路径的第四步——多 agent 制衡。

Graph 层只用两处（design doc §9.1）：目标可衡量 Critic + 编码 review 三权分立。不在所有阶段用——spec 完备性/设计合理性追求完美是过度工程，靠回退通道兜底。

Graph 层最小原型实现四块功能：
1. **FindingRouter**（design doc §9.2）——三级分级拦截（机器 P0 硬拦 / agent P0 人可覆盖 / P1P2 软）
2. **ReviewerContextRouter**（design doc §9.4）——多 agent Context 路由（共享层 + 维度子集）
3. **Handoff**（design doc §8.6/§9.4）——结构化 handoff + 路由（from→to 按字段分发）
4. **CriticGoalChecker**（design doc §9.5）——目标可衡量性机器粗筛

## 2. 目标

- **G1**：FindingRouter 按 source+severity 路由出 block/block_overridable/record
- **G2**：ReviewerContextRouter 获取共享层 + 各 reviewer 维度子集
- **G3**：Handoff 结构化 + 按 to_reviewer 分组路由
- **G4**：CriticGoalChecker 机器粗筛目标是否含可验证谓词
- **G5**：四块集成后能跑通最小 case

## 3. 需求

### 3.1 功能性需求

| ID | 需求 | 对应 design doc |
|----|------|----------------|
| R1 | 机器 P0 → block 不可覆盖 | §9.2 |
| R2 | agent P0 → block 可覆盖 | §9.2 |
| R3 | P1/P2 → record 不阻断 | §9.2 |
| R4 | 批量路由 has_block 判定 | §9.2 |
| R5 | 共享层（所有 reviewer 都看到） | §9.4 |
| R6 | 维度子集（按 reviewer 角色定制） | §9.4 |
| R7 | Handoff 结构化 + 按 to 分组 | §8.6 |
| R8 | Handoff 过滤 pending | §8.6 |
| R9 | 目标可衡量机器粗筛（含数字/阈值） | §9.5 |
| R10 | 集成验证 case | §9.1-9.5 |

### 3.2 非目标（本轮不做）

- 真正的多 agent 并行调度（需要 agent runtime）——本轮只做数据模型 + 路由逻辑
- Judge 裁决逻辑（独立调研后 keep/drop）——需要 LLM 调用
- Critic 精判（谓词是否真可测）——需要 LLM 调用，本轮只做机器粗筛
- handoff 的"涉及 needs_revalidation 必须回应"计数——依赖 manifest 集成

## 4. 设计方案

### 4.1 模块结构

```
src/engineering_agent/graph/
├── __init__.py
├── finding_router.py      # Task 1: 三级分级拦截
├── context_router.py      # Task 2: 多 agent Context 路由
├── handoff.py             # Task 3: 结构化 handoff + 路由
└── goal_checker.py        # Task 4: 目标可衡量性机器粗筛
```

### 4.2 FindingRouter（§9.2）

- 复用 manifest 模型的 ReviewFinding（source: machine|agent, severity: P0|P1|P2）
- route(finding) → FindingAction(block/block_overridable/record + overridable)
- route_batch(findings) → BatchFindingAction(has_block)

### 4.3 ReviewerContextRouter（§9.4）

- 5 个 reviewer 角色：performance/robustness/standards/spec-compliance/contract-trust
- 共享层：spec 相关章 + tasks 当前项 + diff + 适用规范列表
- 维度子集：每个 reviewer 看自己的维度

### 4.4 Handoff（§8.6）

- Handoff dataclass：from/to/file/line/signal/severity/evidence/status
- HandoffRouter：route_by_target 按 to 分组 + filter_pending 过滤待处理

### 4.5 CriticGoalChecker（§9.5）

- 机器粗筛：正则检查目标是否含数字阈值/比较运算符
- "P99 < 200ms" → True / "性能要好" → False
- Critic 精判接口预留（本轮不实现 LLM 调用）

## 5. Goal State

| 验证 | 方式 | 通过条件 |
|------|------|---------|
| FindingRouter | pytest | 机器P0→block不可覆盖 / agentP0→block可覆盖 / P1→record |
| ReviewerContextRouter | pytest | 共享层 + 维度子集正确 |
| Handoff | pytest | 按 to 分组 + 过滤 pending |
| CriticGoalChecker | pytest | 含数字阈值→True / 无→False |
| 集成 case | pytest | 四块串联跑通 |
