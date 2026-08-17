# Tasks: Context 层最小原型

> 基于 spec.md（Quick Draft），实现 design doc §10 的 Context 层三块功能。

## Task 1: ContextMatrix（Push/Pull 配置表）
- **Status**: Completed
- **做什么**: 定义 5 阶段 × 7 类上下文的 Push/Pull 配置表，让 Harness 知道每个 step 该 Push 什么、该 Pull 什么
- **解决什么问题**: design doc §10.1/§10.2 要求区分"必须看到的"（Push）和"展开更好"（Pull），但没有配置表
- **具体改什么代码**: 新建 `src/engineering_agent/context/matrix.py`（PUSH_CONTEXTS 集合 + ContextMatrix 类：get_mode 查询）+ `src/engineering_agent/context/__init__.py`
- **目标**: 给定（阶段, 上下文类）能查到 push/pull
- **验收标准**: pytest 测试编码 task_spec=push、编码 code=pull、需求 norms=push
- **依赖**: 无

## Task 2: FeedbackKeeper（反馈保鲜）
- **Status**: Completed
- **做什么**: 实现反馈保鲜器，只保留最新一次反馈（覆盖不累积），对抗上下文腐化
- **解决什么问题**: design doc §10.3 要求"反馈类只留最新，不累积"——否则旧反馈占用上下文窗口
- **具体改什么代码**: 新建 `src/engineering_agent/context/feedback.py`（FeedbackKeeper 类：set/get/clear/clear_all/keys）
- **目标**: set 覆盖旧值不累积 + get/clear
- **验收标准**: pytest 测试 set 覆盖 + get 读取 + clear 清除
- **依赖**: Task 1

## Task 3: FailurePatternStore（按标签检索）
- **Status**: Completed
- **做什么**: 实现 failure-patterns 存储 + 按标签检索，这是"Pull→Push 升级"的执行点——Harness 按标签搜好 Push 给 agent
- **解决什么问题**: design doc §10.5 要求"agent 不知道自己该搜什么"，Harness 按当前 Loop 形态生成标签组合搜好 Push
- **具体改什么代码**: 新建 `src/engineering_agent/context/failure_patterns.py`（FailurePattern dataclass + FailurePatternStore 类：add/search）
- **目标**: 按标签（module/error_type/phase/severity）检索命中
- **验收标准**: pytest 测试按 module 检索 + 按 error_type 检索 + 多标签组合 + 空结果
- **依赖**: Task 1

## Task 4: 集成验证
- **Status**: Completed
- **做什么**: 把三块功能串起来跑通最小 case
- **解决什么问题**: 验证 Context 层三块协作是否跑得通
- **具体改什么代码**: 新建 `tests/test_context_integration.py`（case: ContextMatrix 查询 + FeedbackKeeper set/get + FailurePatternStore 检索）
- **目标**: 集成 case 全通过
- **验收标准**: pytest test_context_integration.py 全 PASS
- **依赖**: Task 1, Task 2, Task 3
