# Tasks: Loop 层最小原型

> 基于 spec.md（Quick Draft），实现 design doc §8 的 Loop 层三块功能。
> 验收标准见 spec.md §5 Goal State。

## Task 1: Loop 层脚手架
- **Status**: Completed
- **做什么**: 创建 loop 包入口，让后续代码有地方放
- **解决什么问题**: 没有 loop/ 包，后续 task 无法组织代码
- **具体改什么代码**: 新建 `src/engineering_agent/loop/__init__.py`（空包入口）
- **目标**: `python -c "from engineering_agent.loop import GateChecker"` 不报错（Task 2 后）
- **验收标准**: import 无报错
- **依赖**: 无

## Task 2: GateChecker（硬关卡校验器）
- **Status**: Completed
- **做什么**: 实现硬关卡校验器，读 manifest 字段判 PASS/FAIL，这是"硬关卡校验 manifest 字段"的执行点
- **解决什么问题**: design doc §5.3 铁律1 要求"硬关卡必须能映射到 manifest 字段"，但没有校验器来执行校验
- **具体改什么代码**: 新建 `src/engineering_agent/loop/gate_checker.py`（GateCheck 数据类 + GateChecker 类：单条校验 + 批量校验 + 内置编码出口关卡清单）
- **目标**: 给定 manifest 片+字段+条件，能判 PASS/FAIL；批量校验有 FAIL 则整体 FAIL
- **验收标准**: pytest 测试单条 PASS/FAIL + 批量（有 FAIL 整体 FAIL / 全过 PASS）
- **依赖**: Task 1

## Task 3: LoopStateTracker（loop_state 管理器）
- **Status**: Completed
- **做什么**: 实现 loop_state 管理器，更新定位层+进度快照层并存 manifest，这是"状态机现场保存"的执行点
- **解决什么问题**: design doc §8.4 要求 loop_state 两层（定位层+进度快照层）存 manifest phase3，但 Harness 层只有模型没有管理逻辑
- **具体改什么代码**: 新建 `src/engineering_agent/loop/state_tracker.py`（LoopStateTracker 类：update_location/update_snapshot/get_state/clear_pending_findings）
- **目标**: 更新定位层+快照层 → 读回一致；review PASS 后 pending_findings 清空
- **验收标准**: pytest 测试更新+读取往返 + pending_findings 清空
- **依赖**: Task 1

## Task 4: UpgradeDetector（minor→major 升级判定）
- **Status**: Completed
- **做什么**: 实现 minor→major 升级判定，检查三个触发条件（占比/finding refs/连续失败），这是"动态升级"的执行点
- **解决什么问题**: design doc §7.3 要求 minor 刷新中 review 发现改动比想象大时自动升级为 major，但没有判定逻辑
- **具体改什么代码**: 新建 `src/engineering_agent/loop/upgrade_detector.py`（UpgradeDetector 类：check_ratio/check_finding_refs/check_consecutive_failures/detect）
- **目标**: 三个触发条件各自判定 + 综合判定
- **验收标准**: pytest 测试占比>阈值升级 / finding 涉及需求章升级 / 连续失败升级 / 三条都不满足不升级
- **依赖**: Task 1

## Task 5: 集成验证
- **Status**: Completed
- **做什么**: 把三块功能串起来跑通最小 case，验证 Loop 层能作为后续层的基础
- **解决什么问题**: design doc §8.1 基本单元"客观验证"部分需要三块协作——GateChecker 校验 + LoopStateTracker 状态 + UpgradeDetector 升级
- **具体改什么代码**: 新建 `tests/test_loop_integration.py`（case: manifest 写 FAIL 字段→GateChecker FAIL→修为 PASS→PASS→LoopStateTracker 更新→UpgradeDetector 升级判定）
- **目标**: 集成 case 全通过
- **验收标准**: pytest test_loop_integration.py 全 PASS
- **依赖**: Task 2, Task 3, Task 4
