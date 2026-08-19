# Changelog

## v1.1.0 (2026-08-14)

### 端到端集成测试 + README
- 新增 ：项目门面（核心概念/五层架构/快速开始/版本历史）
- 新增 ：5 个端到端集成测试（五层协作验证）
- 端到端验证：Prompt→Harness→Context→Loop→Graph→Confirm 全串联跑通
- 累计 167 passed（162 原有 + 5 端到端）

## v1.0.0 (2026-08-14)

### 🎉 五层架构完整实现

五层架构（Prompt/Context/Harness/Loop/Graph）全部实现，162 个测试全通过。

- **Prompt 层**（新增）：三子层组装（L1身份/L2任务说明/L3协议）+ L3三子协议解析（tool_call/step_output/task_complete）+ confirm token（两类确认+串行优先级队列+超时默认拒绝）
- 累计 162 passed（Harness 55 + Loop 34 + Context 25 + Graph 27 + Prompt 21）
- design doc §19 实施路径全部走完：Harness → Loop → Context → Graph → Prompt
- 核心机制：软硬约束判据落地——可硬化的约束从 Prompt 下沉到 Harness/Loop 机制层

## v0.9.0 (2026-08-14)

### Graph 层最小原型实现
- 新增 engineering-agent/graph/ 代码实现（Python，新增 27 个测试，累计 141 passed）：
  - finding_router.py：三级分级拦截（机器P0硬拦不可覆盖/agentP0人可覆盖/P1P2软记录）
  - context_router.py：多 agent Context 路由（共享层+维度子集，5个reviewer角色）
  - handoff.py：结构化 handoff + 按 to_reviewer 分组路由
  - goal_checker.py：目标可衡量性机器粗筛（正则检查数字/阈值）
- 核心机制：多 agent 三权分立的数据模型 + 路由逻辑（不含 agent runtime 调度）

## v0.8.0 (2026-08-14)

### Context 层最小原型实现
- 新增 engineering-agent/context/ 代码实现（Python，新增 25 个测试，累计 114 passed）：
  - matrix.py：ContextMatrix（5阶段×7类上下文 Push/Pull 配置表）
  - feedback.py：FeedbackKeeper（反馈保鲜——只留最新，覆盖不累积）
  - failure_patterns.py：FailurePatternStore（按标签检索，Pull→Push 升级）
- 核心机制：Push/Pull 分界 + 反馈保鲜 + failure-patterns 按标签检索

## v0.7.0 (2026-08-14)

### Loop 层最小原型实现
- 新增 engineering-agent/loop/ 代码实现（Python，新增 34 个测试，累计 89 passed）：
  - gate_checker.py：硬关卡校验器（GateCheck/GateResult/BatchResult + CODING_EXIT_GATES 编码出口关卡清单）
  - state_tracker.py：loop_state 管理器（定位层+进度快照层，存 manifest phase3.loop_state，review PASS 后清空 pending_findings）
  - upgrade_detector.py：minor→major 升级判定（needs_revalidation 占比>阈值 / finding 涉及需求章(1-3)或方案概览(4.1) / 连续 N 轮同类失败）
- 核心机制：硬关卡校验 manifest 字段判 PASS/FAIL + 状态机现场保存 + 动态升级判定

## v0.6.0 (2026-08-13)

### Harness 层最小原型实现
- 新增 engineering-agent/ 代码实现（Python，55 个测试全通过）：
  - manifest/：六片 Pydantic 数据模型 + ManifestStore 读写器 + archive/restore 归档恢复
  - permissions/：DangerLevel L0-L3 + PermissionMatrix 阶段×工具矩阵 + ToolGate 拦截器
  - spec/：SpecLock Git SHA 锁定（freeze/read_locked/check_committed）
  - harness.py：集成入口 + spec-first 检查（无 spec 拦截 Edit）
- 核心机制：spec-first 检查——把 Prompt 级「禁止无 spec 改代码」下沉到 Harness 机制层硬约束
- 测试覆盖：55 passed（模型序列化 + 读写往返 + 归档恢复 + 权限矩阵 + L0-L3 拦截 + SHA 锁定 + 集成 case）

## v0.5.0 (2026-08-13)

### 设计文档 + 论文 + Harness 层原型脚手架
- 新增 `engineering-agent-design.md`：专业型工程 Agent 完整架构设计（五层架构：Prompt/Context/Harness/Loop/Graph，manifest schema，工具权限矩阵，spec 快照锁定，五种 Loop 形态，多 Agent 三权分立，灰度三档分级）
- 新增 `engineering-agent-thesis.md`：本科毕业论文大纲与主体内容
- 新增 `engineering-agent/` 目录：Harness 层最小原型脚手架（AGENTS.md + spec.md + tasks.md），基于 design doc §19 实施路径

### 核心理论贡献
- 软硬约束判据：「能映射到 manifest 字段或 exit code 的约束可硬化」
- 将可硬化的约束从 Prompt 下沉到 Harness/Loop 机制层

## v0.4.0 (2026-07-28)

### 模型切换：DeepSeek → GLM-5.2（智谱）
- `DeepSeekProvider` → `GLMProvider`，默认 base_url `https://open.bigmodel.cn/api/paas/v4`，默认模型 `glm-5.2`
- 环境变量 `DEEPSEEK_*` → `GLM_*`（`GLM_API_KEY` / `GLM_BASE_URL` / `GLM_MODEL`）
- thinking 参数改 opt-in（`GLM_ENABLE_THINKING=1`），默认不发以避免非推理调用 400；具体参数形态待对照智谱 API 文档确认
- README / pyproject / p0_smoke 同步更新

### 约束瘦身（按"约束∝后果"审计：A 类砍、B 类加固）
- coverage 门禁降为非阻断（informational，仅审计）——覆盖率是噪声指标，不卡人
- 3-way 散文 review 改为 T0-only——accuracy reviewer（B 类，CODE 阶段）才是有牙的
- `ede init` 默认 trust tier T1 → T2（A 类 process gate 默认更信任模型）
- 审计链加固：空 `integrity_hash` 不再被跳过（视为 broken），堵住 null-hash 绕过
- 接通 `upgrade_if_inaccurate`：accuracy reviewer 判定 inaccurate 时自动升级 ChangeEntry 的 effective_risk（spec §AC-007）

### 待办（下一轮）
- AC-003 `--bypass <gate>`（分级：lint/3-way 可绕，test/accuracy/merge 不可绕）
- merge 校验从 grep 升级为真校验

## v0.3.0 (2026-07-23)

### 异步化重构（spec C-006）
- GateEngine：`check`/`fix`/`run_gate` 改为 async；`run_gates` 通过 `asyncio.gather` 并发执行
- StageEngine：`advance`/`confirm` 及内部状态迁移全部 async
- builtin gates：`subprocess.run` → `asyncio.create_subprocess_exec`
- CLI：新增 `ede task list`、`ede audit`（含审计链完整性校验）；async 调用包装为 `asyncio.run`
- 版本号对齐：`pyproject.toml` / `ede/__init__.py` / README badge 统一为 0.3.0

### 清理
- 移除 `tests/test_gates.py` 中硬编码的 `C:\obsidian\KB\weiwei` 路径，改用临时项目 / `PROJECT_ROOT`
- 移除 `tests/test_gate_engine.py` 重复的 `import asyncio`

## v0.2.0 (2026-07-20)

### P0 — Bug 修复
- 删除 Stage REVIEW/MERGE 重复注册，修复 gates 被覆盖导致后续阶段无门禁的 bug
- 修复 Trust Tier T2/T3 门禁失败后错误标记 BLOCKED 的逻辑，改为含重试上限的真正自动恢复
- 修复 `_get_first_project_id()` 的条件短路 hack

### P1 — 架构增强：三层信任闭环
- **Accuracy Reviewer**：变更摘要不再盲信 Agent 自我声明。新增独立 reviewer 交叉校验 Agent 风险评估与实际 diff，每个 disagreement 必须附 `line_number` + `diff_quote` 代码引用（Mandatory Citation），缺一即丢弃
- **系统自动升级**：accuracy reviewer 判定 inaccurate → effective_risk 自动升级（low→medium, medium→high）→ 强制 WAIT_USER，Trust Tier T0-T3 均不可覆盖
- **ChangeEntry 多条目模型**：从单意图/单风险 ChangeLog 升级为 `Task 1─N ChangeLog 1─N ChangeEntry`，逐文件记录意图分组、Agent 自评风险、有效风险、accuracy 评分
- **DisagreementEvidence**：Reviewer 的证据可查询、可审计
- **全链路打通**：`_make_run_fn` → `parse_change_entries()` → `change_entry` 表 → accuracy check 用逐条目自评
- **Prompt 系统统一**：合并 `prompt_layers.py` 的 Constitution（8 条约束）+ PHASE_RULES 到 `llm_adapter.py`，删除死代码
- **Spec 更新**：决策 2 改为三层闭环描述，新增 AC-007

### P2 — 代码质量
- Reviewer 解析器改为三策略回退（pipe → 正则标签 → 非结构化 warning）
- 裸 `except: pass` 替换为标准库 `logging`
- 9 个测试文件硬编码路径改为 `Path(__file__).resolve()`
- `gates/__init__.py` 显式导出
- SQLite 启用 WAL 模式 + 简易迁移框架（`SCHEMA_VERSION = 2`）
- LLM API 指数退避重试（1s/2s/4s/8s，最多 5 次）
- 审计日志 SHA256 防篡改链 + `verify_audit_integrity()`

### 新增功能
- `--start-at` 选项：`ede task create "desc" --start-at code` 从任意阶段启动管线

### 测试
- 从 63 条增至 73 条，覆盖 ChangeEntry CRUD、accuracy 升级、强制引用丢弃、审计链完整性

## v0.1.0 (2026-07-15)

- 项目骨架：Typer CLI + SQLite 持久化 + 七阶段状态机
- 硬约束管线：spec → design → plan + 人工关卡
- Gate Engine：L1/L2/L3 分级门禁 + 自动重试
- Trust Tier：T0-T3 自适应约束
- DeepSeek LLM Adapter + thinking budget
- Context Engine + Self-Refinement
