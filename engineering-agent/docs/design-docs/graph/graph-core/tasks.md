# Tasks: Graph 层最小原型

> 基于 spec.md（Quick Draft），实现 design doc §9 的 Graph 层四块功能。

## Task 1: FindingRouter（三级分级拦截）
- **Status**: Completed
- **做什么**: 实现 finding 三级分级路由器，机器 P0 硬拦 / agent P0 人可覆盖 / P1P2 软记录
- **解决什么问题**: design doc §9.2 要求按 finding 来源分级拦截，但没有路由逻辑
- **具体改什么代码**: 新建 `src/engineering_agent/graph/finding_router.py`（FindingAction + BatchFindingAction + FindingRouter）+ `src/engineering_agent/graph/__init__.py`
- **目标**: 按 source+severity 路由出 block/block_overridable/record
- **验收标准**: pytest 测试机器P0→block不可覆盖 + agentP0→block可覆盖 + P1→record
- **依赖**: 无

## Task 2: ReviewerContextRouter（多 agent Context 路由）
- **Status**: Completed
- **做什么**: 实现共享层 + 维度子集配置，让每个 reviewer 看到正确的上下文范围
- **解决什么问题**: design doc §9.4 要求"共享层给所有 reviewer + 维度子集按角色定制"，但没有配置
- **具体改什么代码**: 新建 `src/engineering_agent/graph/context_router.py`（REVIEWER_ROLES + REVIEWER_DIMENSIONS + ReviewerContextRouter）
- **目标**: get_shared_layer + get_dimension_subset 正确
- **验收标准**: pytest 测试共享层 + 各 reviewer 维度子集
- **依赖**: Task 1

## Task 3: Handoff（结构化 handoff + 路由）
- **Status**: Completed
- **做什么**: 实现结构化 handoff 和按 to_reviewer 分组路由，让交叉线索能传递
- **解决什么问题**: design doc §8.6 要求 handoff 结构化传递（不是一行自然语言），且按 to 字段路由
- **具体改什么代码**: 新建 `src/engineering_agent/graph/handoff.py`（Handoff dataclass + HandoffRouter）
- **目标**: 按 to 分组 + 过滤 pending
- **验收标准**: pytest 测试分组路由 + 过滤 pending
- **依赖**: Task 1

## Task 4: CriticGoalChecker（目标可衡量性机器粗筛）
- **Status**: Completed
- **做什么**: 实现目标可衡量性的机器粗筛，检查目标是否含数字阈值/比较运算符
- **解决什么问题**: design doc §9.5 要求目标可衡量——机器粗筛（含谓词）+ Critic 精判，本轮做机器层
- **具体改什么代码**: 新建 `src/engineering_agent/graph/goal_checker.py`（CriticGoalChecker）
- **目标**: "P99 < 200ms"→True / "性能要好"→False
- **验收标准**: pytest 测试含阈值→True / 无→False
- **依赖**: Task 1

## Task 5: 集成验证
- **Status**: Completed
- **做什么**: 四块功能串联跑通最小 case
- **解决什么问题**: 验证 Graph 层四块协作是否跑得通
- **具体改什么代码**: 新建 `tests/test_graph_integration.py`
- **目标**: 集成 case 全通过
- **验收标准**: pytest test_graph_integration.py 全 PASS
- **依赖**: Task 1, Task 2, Task 3, Task 4
