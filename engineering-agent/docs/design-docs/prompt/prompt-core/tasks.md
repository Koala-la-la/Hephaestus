# Tasks: Prompt 层最小原型

## Task 1: PromptBuilder（L1/L2/L3 组装）
- **Status**: Completed
- **做什么**: 实现 Prompt 三子层组装器——L1 身份模板（固定）+ L2 任务说明（从 manifest 生成）+ L3 协议骨架（常驻）
- **解决什么问题**: design doc §11.1 要求"L1/L3 固定、L2 动态"，没有组装器会坍缩成一段巨大 Prompt
- **具体改什么代码**: 新建 `src/engineering_agent/prompt/builder.py`（L1_IDENTITY 模板 + PromptResult + PromptBuilder）+ `__init__.py`
- **目标**: build_prompt(phase, manifest_store) 返回 L1+L2+L3
- **验收标准**: pytest 测试 5 阶段各返回正确身份 + L2 从 manifest 读 task_spec
- **依赖**: 无

## Task 2: L3Protocol（三子协议解析）
- **做什么**: 实现三种 agent 输出的解析与校验——tool_call / step_output / task_complete
- **解决什么问题**: design doc §11.2 要求 agent 每次输出是结构化 JSON（不是自然语言），Harness 需要解析
- **具体改什么代码**: 新建 `src/engineering_agent/prompt/protocol.py`（ToolCall + StepOutput + TaskComplete dataclass + L3Protocol 解析器）
- **目标**: parse_output(json) 返回正确的 dataclass
- **验收标准**: pytest 测试三种输出解析 + 未知 type 报错
- **依赖**: Task 1

## Task 3: ConfirmToken（确认请求 + 串行队列）
- **做什么**: 实现确认请求管理——阶段出口确认 + 覆盖确认 + 串行优先级队列 + 超时默认拒绝
- **解决什么问题**: design doc §11.3 + §A4 要求"两类确认（阶段出口+覆盖）+ 串行依赖 + 超时默认拒绝"
- **具体改什么代码**: 新建 `src/engineering_agent/prompt/confirm.py`（ConfirmRequest + ConfirmManager）
- **目标**: 请求/解决/优先级/超时
- **验收标准**: pytest 测试覆盖>阶段出口优先级 + 超时默认拒绝
- **依赖**: Task 1

## Task 4: 集成验证
- **做什么**: 三块串联跑通最小 case
- **具体改什么代码**: 新建 `tests/test_prompt_integration.py`
- **验收标准**: pytest 全 PASS
- **依赖**: Task 1, 2, 3
