# Tasks: M0 — 项目骨架

> 目标：`ede init` 能创建 `.ede/` 目录

## Task 1: Python 项目结构

- **Status**: Completed
- **目标**: 创建 `pyproject.toml`、`ede/__init__.py`、`.gitignore`，定义项目元数据和依赖
- **验收标准**: `pip install -e .` 成功，`import ede` 不报错
- **依赖**: 无
- **涉及文件**:
  - `pyproject.toml`（新增）
  - `ede/__init__.py`（新增）
  - `.gitignore`（新增）

## Task 2: SQLite 数据模型

- **Status**: Completed
- **目标**: 定义所有核心实体的数据类和数据表 Schema
- **验收标准**: 执行 schema 初始化后，SQLite 中 6 张表（project、task、checkpoint、gate_result、audit_log、change_log）全部存在，字段类型正确
- **依赖**: 无
- **涉及文件**:
  - `ede/models.py`（新增）— 数据类 + SQL DDL
  - `ede/persistence.py`（新增）— DB 初始化 + 迁移

## Task 3: 状态机骨架

- **Status**: Completed
- **目标**: 定义阶段枚举（Phase）、状态枚举（Status），状态迁移规则框架
- **验收标准**: `Phase.SPEC → Phase.DESIGN → Phase.PLAN` 迁移链路可执行，`WAIT_USER` 状态可写入/读取
- **依赖**: Task 2（需要持久化测试）
- **涉及文件**:
  - `ede/state_machine.py`（新增）— Phase/Status 枚举 + StateMachine 类

## Task 4: Typer CLI 入口

- **Status**: Completed
- **目标**: 实现 `ede init` 命令，创建 `.ede/` 目录 + 初始化 SQLite + 生成默认 `context.yaml`
- **验收标准**: 在空目录执行 `ede init "test project"` → `.ede/` 含 `state.db`、`context.yaml`、`ede_audit.log`
- **依赖**: Task 2, Task 3
- **涉及文件**:
  - `ede/cli.py`（新增）— Typer 应用 + `init` 命令
  - `tests/test_cli.py`（新增）— 验证 init 产出物

---

# Tasks: M1 — 硬约束管线

> 目标：走通 spec → design → plan 三阶段，含三处人工关卡

## Task 1: Gate Engine

- **Status**: Completed
- **目标**: 实现门禁引擎，支持 L1/L2/L3 分级门禁 + 分级重试策略
- **验收标准**: `GateEngine.check(stage, context)` 返回 GateResult；L1 门禁自动重试 2 次，L2 重试 1 次，L3 立即返回 WAIT_USER
- **依赖**: 无（M0 已就绪）
- **涉及文件**:
  - `ede/gate_engine.py`（新增）— GateEngine 类 + Gate 定义 + 重试逻辑

## Task 2: Stage Engine

- **Status**: Completed
- **目标**: 实现管线编排器，管理七阶段生命周期，驱动状态机迁移
- **验收标准**: `StageEngine.run(task_id)` 从 SPEC.PENDING 推进到 DESIGN.PENDING（遇 WAIT_USER 暂停），状态持久化到 SQLite
- **依赖**: Task 1（需要调用 Gate Engine 检查）
- **涉及文件**:
  - `ede/stage_engine.py`（新增）— StageEngine + Stage 基类

## Task 3: CLI 命令扩展

- **Status**: Completed
- **目标**: 实现 `ede task create`、`ede task run`、`ede confirm <stage>` 命令
- **验收标准**: 
  - `ede task create "需求描述"` 创建任务并写入 SQLite
  - `ede task run` 推进管线到第一个 WAIT_USER（spec 完成）
  - `ede confirm spec` 解锁下一阶段
- **依赖**: Task 2
- **涉及文件**:
  - `ede/cli.py`（修改）— 新增 task 子命令组 + confirm 命令
  - `ede/persistence.py`（修改）— 新增 task CRUD + checkpoint CRUD

## Task 4: 测试 ✅

- **Status**: Completed
- **目标**: 端到端测试 spec → design → plan 全管线 + 人工关卡
- **验收标准**: 6+ 测试覆盖 Gate Engine 分级重试、管线推进、checkpoint 持久化、跨会话恢复
- **依赖**: Task 3
- **涉及文件**:
  - `tests/test_cli.py`（修改）— 新增 M1 测试用例
  - `tests/test_gate_engine.py`（新增）— Gate Engine 单元测试
  - `tests/test_stage_engine.py`（新增）— Stage Engine 单元测试

---

# Tasks: M2 — 编码执行 ✅ (Completed in v0.2.0)

> 目标：LLM Adapter + Context Engine 集成到管线，AI 可写代码并输出变更摘要

## Task 1: LLM Adapter ✅

- **Status**: Completed
- **目标**: 实现 DeepSeek API 封装，含 thinking budget 控制、前缀缓存策略、超时重试
- **验收标准**: `LLM.chat(messages, thinking_budget="high")` 返回 DeepSeek 响应；thinking budget 随阶段自动选择
- **依赖**: 无
- **涉及文件**:
  - `ede/llm_adapter.py`（新增）— LLMProvider Protocol + DeepSeekProvider

## Task 2: Context Engine ✅

- **Status**: Completed
- **目标**: 项目上下文管理——读取 `.ede/context.yaml`，注入到 LLM prompt 前缀
- **验收标准**: `ContextEngine.resolve(task)` 返回包含项目约定 + 约束的 prompt 前缀
- **依赖**: 无
- **涉及文件**:
  - `ede/context_engine.py`（新增）— ContextEngine + context.yaml 解析

## Task 3: 管线集成 ✅

- **Status**: Completed
- **目标**: 将 LLM Adapter + Context Engine 接入 Stage Engine 的 code/test 阶段
- **验收标准**: `ede task run` 在 code 阶段调用 LLM（dry-run 模式），输出模拟的变更摘要
- **依赖**: Task 1, Task 2
- **涉及文件**:
  - `ede/stage_engine.py`（修改）— Stage 支持 run_fn 回调
  - `ede/cli.py`（修改）— 初始化 LLM Adapter

## Task 4: 测试 ✅

- **Status**: Completed
- **目标**: LLM Adapter 单元测试 + Context Engine 单元测试 + 集成测试
- **验收标准**: 6+ 测试覆盖 Provider 协议、上下文解析、thinking budget 路由
- **依赖**: Task 3
- **涉及文件**:
  - `tests/test_llm_adapter.py`（新增）
  - `tests/test_context_engine.py`（新增）

---

# Tasks: M3 — 变更可见性 ✅ (Completed in v0.2.0)

> 目标：每个 task 完成后输出结构化变更摘要 + 意图分组 + 风险标注（AC-005）

## Task 1: 变更解析引擎 ✅

- **Status**: Completed
- **目标**: 解析 LLM 输出的变更摘要，提取结构化 ChangeLog（summary、intent_group、risk_label、spec_ref）
- **验收标准**: 输入模拟的 LLM 变更输出，返回 ChangeLog 数据对象，字段齐全
- **依赖**: M2（LLM Adapter 已就绪）
- **涉及文件**:
  - `ede/change_visibility.py`（新增）— ChangeLog 解析 + 意图分组 + 风险评估

## Task 2: 管线集成 ✅

- **Status**: Completed
- **目标**: code 阶段 LLM 输出后，自动调用变更可见性解析，持久化 ChangeLog 到 SQLite
- **验收标准**: `ede task run` 在 code 阶段完成后，ChangeLog 表有记录
- **依赖**: Task 1
- **涉及文件**:
  - `ede/cli.py`（修改）— code 阶段 run_fn 新增解析 + 持久化
  - `ede/persistence.py`（修改）— 新增 ChangeLog CRUD

## Task 3: 测试 ✅

- **Status**: Completed
- **目标**: 变更解析单元测试 + 集成测试
- **验收标准**: 6+ 测试覆盖解析逻辑、意图分组、风险标注、DB 持久化
- **依赖**: Task 2
- **涉及文件**:
  - `tests/test_change_visibility.py`（新增）
