# Spec: Context 层最小原型

> Status: Quick Draft
> 上游设计文档：`../../../engineering-agent-design.md`（简称 design doc）
> 本 spec 锚定第三轮实现范围——Context 层三块核心功能。

---

## 1. 背景

Harness 层（v0.6.0）+ Loop 层（v0.7.0）已实现。Context 层是 design doc §19 实施路径的第三步——它解决"每个 step 喂什么上下文"的问题。

Context 层的核心命题不是"喂多少"，是"每个 step 喂最小高信噪比集"——喂漏了输出错，喂多了信噪比下降也错。

Context 层最小原型实现三块功能：
1. **ContextMatrix**（design doc §10.1/§10.2）——Push/Pull 配置表（5 阶段 × 7 类上下文 → push/pull）
2. **FeedbackKeeper**（design doc §10.3）——反馈保鲜（只留最新，不累积）
3. **FailurePatternStore**（design doc §10.5）——按标签检索 failure-patterns（Pull→Push 升级）

## 2. 目标

- **G1**：ContextMatrix 能查询（阶段, 上下文类）→ push/pull
- **G2**：FeedbackKeeper 能 set/get/clear 反馈，只保留最新值（覆盖不累积）
- **G3**：FailurePatternStore 能按标签（module/error_type/phase/severity）检索
- **G4**：三块集成后能跑通最小 case

## 3. 需求

### 3.1 功能性需求

| ID | 需求 | 对应 design doc |
|----|------|----------------|
| R1 | Push/Pull 配置表（5 阶段 × 7 类） | §10.2 |
| R2 | 查询（阶段, 上下文类）→ push/pull | §10.1 |
| R3 | 反馈 set（覆盖最新，不累积） | §10.3 |
| R4 | 反馈 get/clear | §10.3 |
| R5 | failure-pattern 存储 + 结构化标签 | §10.5 |
| R6 | failure-pattern 按标签检索 | §10.5 |
| R7 | 集成验证 case | §10.1-10.5 |

### 3.2 非目标（本轮不做）

- ContextPusher（组装完整 Push 集并注入 agent）——依赖 spec 章节读取，下一轮
- codebase-researcher 调用形态（§10.4）——依赖外部工具实现
- 保鲜机制的第 1/3 条（每 task 重 push + Pull idempotent）——依赖 ContextPusher

## 4. 设计方案

### 4.1 模块结构

```
src/engineering_agent/context/
├── __init__.py
├── matrix.py            # Task 1: ContextMatrix（Push/Pull 配置）
├── feedback.py          # Task 2: FeedbackKeeper（反馈保鲜）
└── failure_patterns.py  # Task 3: FailurePatternStore（按标签检索）
```

### 4.2 ContextMatrix（design doc §10.1/§10.2）

- 7 类上下文：identity / task_spec / code / norms / history / feedback / baseline
- 默认 Pull（未列出的默认 pull）——和权限矩阵的"默认 L2"不同，上下文默认 Pull 更安全（不灌无关信息）
- Push 条目（design doc §10.2 矩阵）：identity 全阶段 Push、task_spec 全阶段 Push、norms（需求/编码 Push）、feedback 全阶段 Push、baseline（编码/测试/上线 Push）

### 4.3 FeedbackKeeper（design doc §10.3）

- in-memory dict——反馈是临时的（只留最新，不需要持久化到 manifest）
- set 覆盖旧值（不累积）——"只留最新"的核心行为
- get / clear / clear_all / keys

### 4.4 FailurePatternStore（design doc §10.5）

- FailurePattern dataclass：module / error_type / severity / phase / symptom / root_cause / fix
- 标签是结构化（前 4 个），内容是自然语言（后 3 个）——"索引结构化、内容自然语言"
- search(module, error_type, phase, severity) → 按标签匹配检索
- 检索是 Harness 用的（Push 式——Harness 按当前 Loop 形态生成标签组合搜好 Push 给 agent）

## 5. Goal State（验证标准）

| 验证 | 方式 | 通过条件 |
|------|------|---------|
| ContextMatrix | pytest | 查询（编码, task_spec）= push、（编码, code）= pull |
| FeedbackKeeper | pytest | set 覆盖不累积 + get/clear |
| FailurePatternStore | pytest | 按标签检索命中 + 空结果 |
| 集成 case | pytest | 三块串联跑通 |
