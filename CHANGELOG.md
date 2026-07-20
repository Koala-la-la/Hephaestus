# Changelog

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
