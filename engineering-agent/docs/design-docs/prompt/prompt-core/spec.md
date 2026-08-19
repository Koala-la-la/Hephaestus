# Spec: Prompt 层最小原型

> Status: Quick Draft
> 上游设计文档：`../../../engineering-agent-design.md`（简称 design doc）
> 本 spec 锚定第五轮（最后一轮）实现范围——Prompt 层三块核心功能。

---

## 1. 背景

Harness（v0.6.0）+ Loop（v0.7.0）+ Context（v0.8.0）+ Graph（v0.9.0）已实现。Prompt 层是 design doc §19 实施路径的最后一步——把"一段巨大的 Prompt"拆成三子层，L2 动态部分由 Harness 从 manifest 生成。

Prompt 层最小原型实现三块功能：
1. **PromptBuilder**（design doc §11.1）——L1/L2/L3 三子层组装（L1/L3 固定 + L2 从 manifest 生成）
2. **L3Protocol**（design doc §11.2）——三子协议（tool_call / step_output / task_complete）的解析与校验
3. **ConfirmToken**（design doc §11.3 + §A4）——阶段出口确认 + 覆盖确认 + 串行优先级队列

## 2. 目标

- **G1**：PromptBuilder 按 SDLCPhase 组装 L1（身份）+ L2（任务说明 from manifest）+ L3（协议常驻）
- **G2**：L3Protocol 能解析三种 agent 输出（tool_call/step_output/task_complete）
- **G3**：ConfirmToken 能管理确认请求（阶段出口 + 覆盖）+ 串行优先级（覆盖 > 阶段出口 > 灰度）
- **G4**：三块集成后能跑通最小 case

## 3. 需求

| ID | 需求 | design doc |
|----|------|------------|
| R1 | L1 身份模板（5 阶段各一个角色描述） | §11.1 |
| R2 | L2 从 manifest 生成任务说明 | §11.1 |
| R3 | L3 协议常驻（< 500 token 简要） | §11.1 |
| R4 | 解析 tool_call（type/tool/args） | §11.2 |
| R5 | 解析 step_output（action/input/output/manifest_update_request） | §11.2 |
| R6 | 解析 task_complete（id/evidence） | §11.2 |
| R7 | 阶段出口确认请求 | §11.3 |
| R8 | 覆盖确认请求 | §11.3 |
| R9 | 串行优先级队列（覆盖 > 阶段出口 > 灰度） | §A4 |
| R10 | 超时默认拒绝 | §11.3 |

### 非目标
- 实际注入 agent 上下文（需要 agent runtime）
- confirm token 的载体实现（Web UI / IM——实现期决策）
- L2 的 spec 章节读取（依赖 SpecLock 完整集成，下一轮）

## 4. 设计方案

### 4.1 模块结构

```
src/engineering_agent/prompt/
├── __init__.py
├── builder.py         # Task 1: PromptBuilder（L1/L2/L3 组装）
├── protocol.py        # Task 2: L3Protocol（三子协议解析）
└── confirm.py         # Task 3: ConfirmToken（确认请求 + 串行队列）
```

### 4.2 PromptBuilder（§11.1）

- L1_IDENTITY：5 阶段各一个身份模板（dict[SDLCPhase, str]）
- L2 从 manifest 读 task_spec 生成
- L3 协议骨架常驻（简要描述三种输出格式）
- build_prompt(phase, manifest_store) → PromptResult(l1, l2, l3)

### 4.3 L3Protocol（§11.2）

- parse_output(json_str) → ToolCall | StepOutput | TaskComplete
- 三种输出类型用 dataclass 定义
- 校验：type 字段必须是 tool_call/step_output/task_complete 之一

### 4.4 ConfirmToken（§11.3 + §A4）

- ConfirmRequest：type（phase_exit/override）、phase、summary、confirm_consequence、reject_consequence
- ConfirmManager：request(request) / resolve(token, approved) / get_pending() / 超时处理
- 串行优先级：override > phase_exit > grayscale
- 超时默认拒绝（phase_exit → 不推进；override → 不覆盖 P0 仍拦）

## 5. Goal State

| 验证 | 方式 | 通过条件 |
|------|------|---------|
| PromptBuilder | pytest | 按 phase 组装 L1+L2+L3 |
| L3Protocol | pytest | 解析三种输出 + 校验 type |
| ConfirmToken | pytest | 请求/解决/优先级/超时 |
| 集成 case | pytest | 三块串联跑通 |
