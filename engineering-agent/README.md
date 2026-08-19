# Engineering Agent

> 工程规范约束型 AI Agent — 将工程纪律从 Prompt 级软约束下沉到 Harness/Loop 机制层。

## 核心概念：软硬约束判据

传统 Skill/Prompt 框架的约束是**软约束**——LLM 可以遵守也可以违反，可靠性无法保证。本项目的核心判据：

> **一条约束能被硬化，当且仅当它的校验对象能映射到结构化数据字段（manifest）或命令退出码（exit code）。**

- **能硬化的**（文件存在、测试通过、工具权限）→ 下沉到 Harness/Loop 机制层，100% 强制
- **不可硬化的**（spec 质量、设计合理性）→ 用 Context + 多 Agent 制衡最大化概率

一句话：**你不能用 hook 校验"设计是否合理"，只能校验"测试是否通过"。**

## 五层架构

```
┌─────────────────────────────────────────────────┐
│  Prompt 层   系统提示定义"角色和纪律"           │ 软（基线）
├─────────────────────────────────────────────────┤
│  Context 层  分阶段喂不同上下文                 │ 半硬（输入侧限形状）
├─────────────────────────────────────────────────┤
│  Harness 层  工具集 + 权限分级 + 流程编排        │ 硬（没权限=没权限）
├─────────────────────────────────────────────────┤
│  Loop 层     每 step 确定性验证 + 失败回退       │ 硬（客观判定）
├─────────────────────────────────────────────────┤
│  Graph 层    多 Agent 制衡                       │ 半硬（博弈降概率）
└─────────────────────────────────────────────────┘
```

重心在 **Harness + Loop**——这两层是唯一能"真硬"且"工程化"的。

## 快速开始

```bash
# 安装
cd engineering-agent
pip install -e ".[dev]"

# 跑测试
pytest tests/ -v
# 167 passed in ~15s
```

## 项目结构

```
engineering-agent/
├── src/engineering_agent/
│   ├── harness.py              # 集成入口 + spec-first 检查
│   ├── manifest/               # 六片 Pydantic 模型 + 读写器 + 归档
│   ├── permissions/            # L0-L3 危险等级 + 阶段×工具矩阵 + 拦截器
│   ├── spec/                   # Git SHA 锁定
│   ├── loop/                   # 硬关卡校验 + 状态机 + 升级判定
│   ├── context/                # Push/Pull 矩阵 + 反馈保鲜 + failure-patterns
│   ├── graph/                  # 三级分级 + Context路由 + handoff + 目标检查
│   └── prompt/                 # 三子层组装 + L3协议 + confirm token
├── tests/                      # 167 个测试
├── docs/design-docs/           # 五层 spec + tasks + execution-logs
└── pyproject.toml
```

## 五层功能速览

| 层 | 核心机制 | 关键类 |
|----|---------|--------|
| **Harness** | manifest 读写 + 工具权限拦截 + spec SHA 锁定 + spec-first 检查 | `Harness`, `ManifestStore`, `ToolGate`, `SpecLock` |
| **Loop** | 硬关卡校验 manifest 字段 + loop_state 状态机 + minor→major 升级判定 | `GateChecker`, `LoopStateTracker`, `UpgradeDetector` |
| **Context** | Push/Pull 分界 + 反馈保鲜（只留最新）+ failure-patterns 按标签检索 | `ContextMatrix`, `FeedbackKeeper`, `FailurePatternStore` |
| **Graph** | 三级分级拦截 + 多 agent Context 路由 + handoff + 目标可衡量性检查 | `FindingRouter`, `ReviewerContextRouter`, `HandoffRouter`, `CriticGoalChecker` |
| **Prompt** | L1/L2/L3 三子层组装 + L3 三子协议解析 + confirm token 串行队列 | `PromptBuilder`, `L3Protocol`, `ConfirmManager` |

## 核心亮点

**spec-first 检查** — Harness 在编码/测试阶段遇到 `edit_file`/`write_file` 时，先检查 spec 是否已冻结（SHA 锁定）。未冻结则拒绝：*"spec 未冻结，无 spec 不许改代码"*。这正是把原版 Prompt 级的"禁止无 spec 改代码"**下沉到机制层硬约束**。

## 版本历史

| 版本 | 内容 | 测试 |
|------|------|------|
| v0.5.0 | 设计文档 + 论文大纲 | — |
| v0.6.0 | Harness 层 | 55 |
| v0.7.0 | Loop 层 | 34 |
| v0.8.0 | Context 层 | 25 |
| v0.9.0 | Graph 层 | 27 |
| v1.0.0 | Prompt 层（五层完整） | 21 |
| **当前** | **+ 端到端集成测试** | **+5 = 167** |

## 相关文档

- [完整架构设计文档](../engineering-agent-design.md) — 五层架构 + manifest schema + 工具权限矩阵 + Loop 形态 + 多 Agent 三权分立 + 灰度三档分级等
- [毕业论文大纲与主体](../engineering-agent-thesis.md) — 本科毕业论文

## License

MIT
