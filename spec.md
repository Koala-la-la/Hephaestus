# Spec: DeepSeek 工程纪律执行器（Engineering Discipline Enforcer）

> 版本: 0.3.0 | 状态: Draft | 日期: 2026-07-15

---

## 1. 背景与干系人

### 1.1 当前痛点

现有 AI Agent 工具（CodeWhale、Claude Code、Codex CLI 等）属于**通用型、对话驱动**的 agent。它们在产品经理任务（需求讨论、文档撰写）中表现尚可，但在工程开发场景中存在系统性缺陷：

- **软约束问题**：工程规范（spec-first、编码规范、测试门禁、review 流程）仅通过 prompt 表达，模型可以被说服绕过任何规则。
- **状态无持久化**：任务状态依赖对话上下文，会话断开即丢失，无法支撑跨天、跨会话的长期工程任务。
- **验证靠自述**：Agent 自称"测试通过了""review 完成了"，但缺乏硬编码的门禁执行——没有实际跑测试、读 diff、对 spec 的闭环验证。
- **经验无沉淀**：模型没有跨会话记忆，本次纠正的错误下次原样重现。
- **模型适配缺失**：Agent 工具的 harness 架构未针对特定模型做深度优化，无法利用 DeepSeek 的前缀缓存、长上下文保持、thinking budget 等特性。
- **变更不可见**：AI 编码速度远超工程师审查速度。工程师面对 AI 生成的大量 diff，难以高效判断"改了什么、为什么改、逻辑对不对"。逐行审查则 AI 的价值被抵消，粗略跳过则埋下隐患。这是当前 AI 辅助开发最大的工程失败模式。

**根本原因**：现有 agent 工具的 harness 层是**对话驱动**的（以 LLM 交互为中心），而工程开发需要的是**流程驱动**的 harness（以不可绕过的工程纪律为中心，以意图分组的变更可见性为基础）。

### 1.2 不做的影响

- 全栈工程师在 AI 辅助下编码速度提升，但验证、集成、发布环节仍依赖人工，形成"编码加速、交付卡顿"的瓶颈。
- 工程规范沦为"建议"，代码质量随模型状态波动，长期项目的可维护性持续下降。
- 团队在 Claude/GPT 上的 token 成本居高不下，难以规模化使用 AI 辅助开发。
- AI 生成代码的审查带宽瓶颈无法解决，工程师要么花大量时间逐行审查（抵消 AI 价值），要么信任盲合（积累技术债务）。

### 1.3 干系人

| 角色 | 核心诉求 |
|------|---------|
| **全栈工程师（主要使用者）** | 独立完成需求→设计→编码→测试→合入的完整链路；快速理解 AI 的变更内容而非逐行审查 diff |
| **开源社区贡献者** | 可扩展、可配置、文档清晰，能适配自己的编码规范和工具链 |
| **项目维护者（开发者本人）** | 框架架构清晰、模块可插拔、测试覆盖充分 |

---

## 2. 目标与验收

### 2.1 业务目标

- **目标 1**：全栈工程师可在终端内完成从需求到合入的完整闭环，无需切换到其他工具。
- **目标 2**：工程纪律（spec-first、测试门禁、review 流程）由系统硬约束保障，不可被跳过或说服绕过。
- **目标 3**：AI 生成的代码变更对工程师透明——通过变更摘要和意图分组，将审查时间从逐行 diff 审查压缩到 30 秒决策 + 少数关键变更深入审查。
- **目标 4**：在 DeepSeek 模型上，token 成本可控，成本效益明确优于 GPT-4 同类流程。

### 2.2 MVP 范围

> 第一个里程碑聚焦：**FR-001 硬约束工作流引擎 + FR-002 显式任务状态机 + FR-003 变更可见性引擎 + FR-004 人工关卡 + FR-005 DeepSeek 深度适配**

### 2.3 验收标准

- **AC-001**：Given 用户发起新需求，When 用户未完成 spec.md 确认，Then 系统拒绝进入编码阶段。
- **AC-002**：Given 编码阶段完成，When 测试门禁未通过（覆盖率/全量通过），Then 系统拒绝进入 review 阶段。
- **AC-003**：Given 用户使用 `--bypass` 跳过某门禁，When 查看任务审计日志，Then 日志包含绕过时间、绕过阶段、操作人，且不可删除。
- **AC-004**：Given 进程重启或终端关闭，When 用户重新启动 agent，Then 任务状态完整恢复，从断点继续。
- **AC-005**：Given 一个 task 的代码变更完成，When AI 输出变更摘要和 diff，Then 摘要包含"改了什么、为什么改、怎么改的"，diff 按变更意图分组（接口变更 / 逻辑变更 / 测试新增 / 重构），并标注风险点。
- **AC-006**：Given 一个标准 CRUD 功能（3 个 task），When 使用 EDE 完成 spec→merge 全流程，Then 工程师实际投入时间（不含 AI 等待时间）≤ 纯手工开发的 50%。

---

## 3. 需求

### 3.1 用户场景

**Before（当前状态）**：

> 工程师收到一个需求 → 打开 IDE + CodeWhale → 口头描述需求 → AI 直接开始写代码 → 过程中多次纠正方向（因为没有 spec）→ 写完后手动跑测试 → 发现遗漏 → 来回修补 → AI 生成大量 diff → 工程师逐文件审查 30 分钟 → 很多细节没注意到 → 提交 PR → 人工 review 发现低级错误 → 返工。全程 4-6 小时，审查占 50% 以上。

**After（目标状态）**：

> 工程师收到一个需求 → 终端输入 `ede init "需求描述"` → Agent 引导需求澄清，生成 spec.md → 用户确认 spec → Agent 生成设计方案 → 用户确认方案 → Agent 输出声明式修改计划 → 用户确认 → Agent 逐 task 编码（每个 task 后自动跑测试/lint，并输出**变更摘要 + 意图分组 diff + 风险标注**）→ 工程师 30 秒扫描摘要和风险点 → 低风险 task 直接确认，高风险 task 按意图分组深入审查（5-10 分钟）→ 所有 task 完成后，Agent 并行触发多 reviewer 审查 → 输出审查报告 → 用户修复 → 全部门禁通过 → Agent 自动合入 main。全程 1-2 小时，工程师的核心工作是确认决策和审查高风险变更。

### 3.2 功能需求

#### Must have（MVP —— 没有它产品无意义）

| ID | 需求 | 说明 |
|----|------|------|
| **FR-001** | **硬约束工作流引擎** | spec → design → plan → code → test → review → merge 七阶段管线。每个阶段有前置条件检查，不满足则阻断前进。约束逻辑在代码层实现，不依赖 prompt。 |
| **FR-002** | **显式任务状态机** | 持久化任务状态（SQLite），支持跨会话恢复。状态包括：阶段（phase）、任务（task）、门禁（gate）、人工关卡（checkpoint）。人工关卡是状态机的"等待状态"，非同步阻塞线程。 |
| **FR-003** | **变更可见性引擎** | 每个 task 完成后输出：(1) 变更摘要——自然语言描述"改了什么、为什么改、怎么改的"；(2) diff 按意图分组——接口变更 / 逻辑变更 / 测试新增 / 重构；(3) 风险标注——自评哪些变更需重点关注；(4) 变更历史时间线——关联 spec 需求点，追溯"需求 → task → 变更记录 → diff → 审查结论"。 |
| **FR-004** | **人工关卡阻断点** | 系统级阻塞点：需求确认、方案确认、声明式计划确认。异步通知模式——支持超时暂停 + 跨会话恢复，不强制用户同步等待。 |
| **FR-005** | **DeepSeek 深度适配** | (1) 利用前缀缓存——框架 Constitution + 编码规范放在稳定前缀层；(2) thinking budget 预设——不同阶段自动选择 thinking 深度；(3) 长上下文策略——1M 窗口下全量常驻核心规则；(4) 中文 prompt 原生优化。 |

#### Should have（本期做，提升体验和可靠性）

| ID | 需求 | 说明 |
|----|------|------|
| **FR-006** | **多 reviewer 并行审查** | 编码完成后，并行派发规格合规、健壮性、性能、编码标准等 reviewer，汇总为结构化审查报告。 |
| **FR-007** | **经验自动沉淀（Self-Refinement）** | 用户纠正错误 → 自动分析错误模式 → 建议更新对应 Skill 规则 → 用户确认后写入。 |
| **FR-008** | **测试生成与覆盖率门禁** | 基于 spec 自动生成测试骨架，执行全量测试，覆盖率不达标则阻断合入。 |
| **FR-009** | **CLI + TUI 交互** | 命令行优先。TUI 展示任务进度、门禁状态、审查结果，不依赖 Web UI。 |

#### Could have（后续迭代）

| ID | 需求 |
|----|------|
| FR-010 | IDE 插件集成（VS Code / JetBrains） |
| FR-011 | 多人协作 / 团队版 |
| FR-012 | 多模型后端支持（非仅 DeepSeek） |

### 3.3 非功能需求

| ID | 需求 | 说明 |
|----|------|------|
| **NFR-001a** | **单 task token 预算** | 单次 task 编码（含 planning + 生成 + self-review）token 消耗 ≤ 50K（DeepSeek V4，标准 CRUD 场景） |
| **NFR-001b** | **全流程 token 预算** | 完整 3-task 需求 pipeline（spec→merge）token 消耗 ≤ 500K |
| **NFR-002** | **快速安装** | `pip install ede` + 配置 `DEEPSEEK_API_KEY` 即可使用，安装时间 < 5 分钟 |
| **NFR-003** | **状态持久化** | SQLite 存储任务状态，进程重启后完整恢复 |
| **NFR-004** | **API 容错** | DeepSeek API 不可用时自动重试（指数退避），超限时降级通知用户 |
| **NFR-005** | **项目级配置** | 通过 `.ede/config.yaml` 配置门禁规则、跳过策略、Skill 加载列表 |

### 3.4 约束与假设

| # | 类型 | 内容 |
|----|------|------|
| C-001 | 约束 | 首个版本仅支持 DeepSeek 模型（API + 本地部署） |
| C-002 | 约束 | Python 3.11+，跨平台（Linux / macOS / Windows） |
| C-003 | 约束 | 基于 agentic-engineering-framework 的 Skill 体系，兼容其 SKILL.md 格式 |
| C-004 | 约束 | CLI 框架：Typer；TUI 框架：Rich（MVP）→ Textual（后续） |
| C-005 | 约束 | Skill 文件作为 Python package data 内嵌发布，支持用户通过 `.ede/skills/` 覆盖和扩展 |
| C-006 | 约束 | 异步框架：asyncio，LLM 调用非阻塞 |
| C-007 | 假设 | 用户具备命令行基本操作能力，目标用户是工程师 |
| C-008 | 假设 | DeepSeek API 可用性和定价在当前水平保持稳定 |
| C-009 | 假设 | 单用户单机使用，非多人协作系统 |

### 3.5 阶段定义与产出物

| 阶段 | 触发条件 | 产出物 | 门禁 |
|------|---------|--------|------|
| **spec** | `ede init` | `spec.md`（需求 + 验收标准） | 用户确认 + spec 完整性检查 |
| **design** | spec 确认后 | `spec.md` 设计章节（架构选型、接口设计） | 用户确认 |
| **plan** | design 确认后 | 声明式修改计划（涉及文件、执行步骤、风险评级） | 用户确认 |
| **code** | plan 确认后 | 代码变更 + 变更摘要 + 意图分组 diff + 风险标注 | 测试通过 + lint 通过 |
| **test** | code 完成后 | 测试报告 + 覆盖率报告 | 覆盖率达标 |
| **review** | test 通过后 | 多 reviewer 审查报告 | 审查通过 |
| **merge** | review 通过后 | 代码合入 main | 全部门禁通过 |

### 3.6 门禁绕过策略

| 机制 | 说明 |
|------|------|
| **`--bypass <gate>`** | 跳过指定门禁，生成**不可删除**的审计记录 |
| **项目级 `.ede/config.yaml`** | 按项目配置哪些门禁可放松、哪些必须保留 |
| **审计日志** | 所有绕过操作写入 `ede_audit.log`，持久存储，不可修改 |

### 3.7 明确不做（Out of Scope）

- Web UI / SaaS 托管服务
- 非代码类资产管理（文档/wiki/设计稿管理）
- 多模型后端支持（首个版本仅 DeepSeek）
- 自动部署到生产环境（上线边界止于代码合入 main）
- 自然语言对话作为唯一交互方式（CLI + TUI 优先）

---

## 4. 系统架构

### 4.1 模块划分

```
┌─────────────────────────────────────────────────────┐
│                    CLI / TUI 层                      │
│                (Typer + Rich)                        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                 Stage Engine（管线引擎）              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐  │
│  │  spec   │→│ design  │→│  plan   │→│   code    │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────┬─────┘  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐      │         │
│  │  merge  │←│ review  │←│  test   │←─────┘         │
│  └─────────┘ └─────────┘ └─────────┘                │
│                                                     │
│  状态机驱动，每个 Stage 是独立可插拔的组件            │
└──────────────────────┬──────────────────────────────┘
                       │
     ┌─────────────────┼─────────────────┐
     │                 │                 │
┌────▼─────┐   ┌───────▼──────┐  ┌──────▼──────┐
│  Context │   │  Gate Engine │  │ LLM Adapter │
│  Engine  │   │  (门禁引擎)   │  │ (模型适配层) │
│          │   │              │  │              │
│- 项目扫描 │   │- 硬门禁检查   │  │- DeepSeek   │
│- context │   │- 审计日志    │  │- 前缀缓存   │
│  .yaml   │   │- bypass 处理 │  │- thinking   │
│- 隐形条件 │   │- 分级重试    │  │  budget     │
│  注入    │   │              │  │              │
└──────────┘   └──────────────┘  └──────────────┘
     │                 │                 │
     └─────────────────┼─────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              Persistence Layer（持久化层）             │
│       SQLite: 任务状态 + 审计日志 + 变更历史           │
└─────────────────────────────────────────────────────┘
```

### 4.2 模块职责

| 模块 | 职责 | 关键接口 |
|------|------|---------|
| **Stage Engine** | 七阶段管线编排，状态机驱动，每个 Stage 可插拔 | `Stage.run(context) → StageResult` |
| **Context Engine** | 项目上下文管理（扫描 + context.yaml + 隐形条件注入） | `ContextEngine.resolve(task) → PromptContext` |
| **Gate Engine** | 硬约束门禁执行，审计日志，bypass 处理，分级重试 | `Gate.check(stage, context) → GateResult` |
| **LLM Adapter** | DeepSeek API 封装，前缀缓存管理，thinking budget 控制 | `LLM.chat(messages, budget) → Response` |
| **Persistence** | SQLite CRUD，状态机持久化，变更历史 | `TaskStore`, `AuditLog`, `ChangeHistory` |
| **CLI/TUI** | 命令解析（Typer），交互界面，进度展示（Rich） | `ede init`, `ede status`, `ede confirm` |

### 4.3 关键架构决策

**决策 1：Stage Engine 和 Gate Engine 分离**

- **选型**：分离
- **理由**：Gate 的检查逻辑独立于 Stage——同一个门禁（如"测试通过"）可能在 code 阶段末尾和 merge 阶段前置都会触发。分离后每个 Stage 只需声明 `prerequisites` 和 `gates`，Gate Engine 统一调度。
- **代价**：多一层调用，状态管理更复杂
- **未选方案**：门禁逻辑嵌在 Stage 内部 → 重复代码，修改门禁逻辑需改动多个 Stage

**决策 2：变更摘要生成方式**

- **选型**：Agent 自评 + Reviewer 校验（选项 C）
- **理由**：Agent 生成摘要（快），Reviewer Agent 交叉校验（减少自评偏差），差异 > 阈值则标记需人工审查
- **代价**：每个 code task 多一次 Reviewer LLM 调用

**决策 3：隐形条件收敛方向**

- **选型**：保守收敛（策略 A）
- **理由**：Agent 不假设隐性条件，优先提问明确，避免"激进假设 → 频繁纠正"的震荡模式
- **实现**：Context Engine 通过 `.ede/context.yaml` 逐步沉淀被确认的隐性条件，被纠正过的事情不再重复询问

**决策 4：Agent 自主权分级**

| 级别 | 决策类型 | Agent 行为 | 工程师介入 |
|------|---------|-----------|-----------|
| L1 | 可逆实现细节 | 自主决策 | 事后审查（变更摘要） |
| L2 | 有偏好但可逆 | 自主 + 说明理由 | 事后审查，可要求修改 |
| L3 | 有后果的选择 | 分析 + 推荐 → 等确认 | 人工关卡 |
| L4 | 不可逆/高风险 | 禁止自主，只能建议 | 必须人工确认 |

---

## 5. 核心组件设计

### 5.1 Stage Engine 状态机

```
         ┌──────────┐
         │ PENDING  │  等待前置条件满足
         └────┬─────┘
              │ 前置门禁全部通过
         ┌────▼─────┐
         │ RUNNING  │  Agent 正在执行（LLM 调用中）
         └────┬─────┘
              │
    ┌─────────┼─────────┐
    │         │         │
┌───▼───┐ ┌───▼───┐ ┌───▼──────┐
│ DONE  │ │BLOCKED│ │WAIT_USER │  等待人工确认
└───┬───┘ └───┬───┘ └────┬─────┘
    │         │           │ 用户确认
    │         │           │
    └────┬────┘    ┌──────▼──────┐
         │         │  RUNNING    │  继续执行
     下一阶段      └─────────────┘
```

**状态说明**：

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| PENDING | 等待前置门禁 | 上一阶段完成，本阶段尚未启动 |
| RUNNING | Agent 执行中 | 前置门禁通过，LLM 调用进行中 |
| WAIT_USER | 人工关卡等待中 | 阶段产出物就绪，需工程师确认 |
| DONE | 完成 | 工程师确认通过 |
| BLOCKED | 被门禁阻断 | 门禁检查失败，需修复后重试 |

**WAIT_USER 持久化流程**：状态写入 SQLite → CLI 展示提示 → 进程可关闭 → 下次启动从 SQLite 恢复 → 重新展示待确认项 → 用户确认后继续。

**人工关卡触发点**：

| 关卡 | 触发时机 | 产出物 | 用户操作 |
|------|---------|--------|---------|
| Checkpoint 1 | spec → DONE | spec.md | `ede confirm spec` |
| Checkpoint 2 | design → DONE | 设计章节 | `ede confirm design` |
| Checkpoint 3 | plan → DONE | 修改计划 | `ede confirm plan` |

**BLOCKED 分级重试策略**：

| 门禁级别 | 举例 | 策略 |
|---------|------|------|
| L1 门禁 | lint、格式化 | Agent 自动修复 + 重试（最多 2 次） |
| L2 门禁 | 测试失败 | Agent 分析 + 尝试修复 + 重试（最多 1 次），仍失败 → WAIT_USER |
| L3 门禁 | 覆盖率不达标 | 立即 WAIT_USER（涉及补充测试用例的决策） |

### 5.2 数据模型

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Project    │ 1───N │    Task      │ 1───N │  ChangeLog   │
│              │       │              │       │              │
│ project_id   │       │ task_id      │       │ change_id    │
│ name         │       │ project_id   │       │ task_id      │
│ config_path  │       │ phase        │       │ spec_ref     │
│ context_md5  │       │ status       │       │ intent_group │
│              │       │ stage_data   │       │ summary      │
└──────────────┘       │ created_at   │       │ risk_label   │
                       │ updated_at   │       │ diff_hash    │
                       └──────┬───────┘       │ created_at   │
                              │               └──────────────┘
              ┌───────────────┼───────────────┐
              │               │               │
       ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
       │ Checkpoint  │ │  GateResult │ │  AuditLog   │
       │             │ │             │ │             │
       │ task_id     │ │ task_id     │ │ task_id     │
       │ stage       │ │ gate_name   │ │ action      │
       │ status      │ │ passed      │ │ detail      │
       │ confirmed_at│ │ detail      │ │ operator    │
       │ confirmed_by│ │ checked_at  │ │ irreversible │
       └─────────────┘ └─────────────┘ └─────────────┘
```

**关键字段**：

| 实体.字段 | 类型 | 说明 |
|----------|------|------|
| Task.phase | TEXT | spec/design/plan/code/test/review/merge |
| Task.stage_data | JSON | 每个 phase 的产出物引用 |
| ChangeLog.spec_ref | TEXT | 指向 spec.md 中的需求点（如 AC-001） |
| ChangeLog.intent_group | TEXT | interface/logic/test/refactor |
| ChangeLog.risk_label | TEXT | low/medium/high |
| AuditLog.irreversible | BOOL | TRUE，写入后不可修改 |
| Checkpoint.status | TEXT | pending/confirmed/timeout |

### 5.3 Context Engine：隐形条件管理

**设计原则**：保守收敛——Agent 不假设隐性条件，优先提问明确。被确认的约束写入 `.ede/context.yaml`，后续不再重复询问。

**`.ede/context.yaml` 结构**：

```yaml
project:
  type: web_fullstack
  frontend: react
  backend: python_fastapi
  database: postgresql

conventions:
  naming: snake_case
  api_style: rest
  auth: jwt_bearer

constraints:
  - "数据库删除操作必须软删除，加 deleted_at 字段"
  - "所有 API 响应包裹在 {code, data, message} 结构中"

history:
  - "2025-03 支付模块重复扣款 → 所有写操作必须加幂等键"
```

**收敛机制**：Context Engine 在执行每个 task 前扫描 context.yaml → 注入匹配的上下文到 prompt → 任务完成后，若工程师纠正了新约束 → FR-007 Self-Refinement 自动回写 context.yaml。

### 5.4 LLM Adapter：DeepSeek 适配

**前缀缓存策略**：
- 把 EDE 的 Constitution（编码纪律、完成定义、质量门禁）放在 prompt 前缀的最稳定层
- 按需加载的参考文档放在后续层
- 保证前缀 128-token 粒度的缓存命中率 ≥ 80%

**Thinking Budget 预设**：

| 阶段 | thinking budget | 理由 |
|------|----------------|------|
| spec / design | low | 以引导提问为主，非深度推理 |
| plan | medium | 涉及文件分析和步骤编排 |
| code | high | 核心编码逻辑，需要深度推理 |
| review | medium | 审查需要理解上下文但非创造 |
| 其他 | off | 状态查询、配置等不用思考 |

---

## 6. 质量属性

### 6.1 故障模式与降级

| 组件故障 | 影响 | 降级策略 |
|---------|------|---------|
| DeepSeek API 不可用 | 管线停摆 | 指数退避重试（最多 5 次），超限后持久化当前状态，提示用户稍后重试 |
| SQLite 文件损坏 | 任务状态丢失 | 每次状态变更前自动备份 `.ede/state.db.bak` |
| Context Engine 扫描失败 | 隐形条件无法注入 | 降级为最小上下文模式（只用 Skill 内置规则），告警但不阻断 |
| Gate Engine 脚本超时 | 门禁无法判定 | 超时视为 FAIL（安全侧），不自动通过 |

### 6.2 性能预算

| 操作 | 目标延迟 | 备注 |
|------|---------|------|
| `ede status` | < 200ms | 纯 SQLite 查询 |
| LLM 单次 chat 等待 | < 30s（可配置超时） | 异步非阻塞 |
| Gate 检查（单次） | < 5s | lint、格式化、测试运行 |
| 变更摘要生成 | 包含在 code task token 预算内 | NFR-001a |
| 启动恢复 | < 1s | 从 SQLite 加载状态 |

### 6.3 安全设计

- **API Key**：通过环境变量 `DEEPSEEK_API_KEY` 读取，不持久化到任何文件
- **审计日志**：所有绕过操作记录不可删除
- **Git 操作**：合入 main 前必须通过全部门禁，merge 操作需 L4 确认

---

## 7. 实现路径

| 里程碑 | 交付物 | 验收 |
|--------|--------|------|
| **M0：骨架** | 项目结构、Typer CLI、SQLite schema、空状态机 | `ede init` 能创建 `.ede/` 目录 |
| **M1：硬约束管线** | Stage Engine + Gate Engine + spec/design/plan 三阶段 | 走通 spec → design → plan，含三处人工关卡 |
| **M2：编码执行** | LLM Adapter + code/test 阶段 + Context Engine | AI 写代码、跑测试、输出变更摘要 |
| **M3：变更可见性** | ChangeLog + 意图分组 + 风险标注 + Reviewer 校验 | AC-005 |
| **M4：审查与合入** | review 阶段 + merge 阶段 + 审计日志 | 完整七阶段走通 |
| **M5：经验沉淀** | Self-Refinement + context.yaml 自动更新 | 被纠正的错误不再重犯 |

---

> **下一阶段**：进入 `workflow-code-generation`，搭建项目骨架（M0）。
