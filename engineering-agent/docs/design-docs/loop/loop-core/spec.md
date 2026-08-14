# Spec: Loop 层最小原型

> Status: Quick Draft
> 上游设计文档：`../../../engineering-agent-design.md`（简称 design doc）
> 本 spec 锚定第二轮实现范围——Loop 层三块核心功能。

---

## 1. 背景

Harness 层（v0.6.0）已实现 manifest 读写 + 工具权限拦截 + spec SHA 锁定。Loop 层是 design doc §19 实施路径的第二步——它是硬关卡的"执行引擎"：Harness 提供数据（manifest）和拦截能力（ToolGate），Loop 层负责"校验 manifest 字段判 PASS/FAIL"和"管理状态机现场"。

Loop 层最小原型实现三块功能：
1. **GateChecker**（design doc §8.1 + §5.3）——硬关卡校验器，给定 manifest 片+字段判 PASS/FAIL
2. **LoopStateTracker**（design doc §8.4）——loop_state 管理器，更新定位层+进度快照层
3. **UpgradeDetector**（design doc §7.3）——minor→major 升级判定（needs_revalidation 占比 + finding spec_refs + 连续失败）

## 2. 目标

- **G1**：GateChecker 能校验单条硬关卡（读 manifest 字段 → PASS/FAIL）
- **G2**：GateChecker 能批量校验一组硬关卡（阶段出口全过才放行）
- **G3**：LoopStateTracker 能更新定位层 + 进度快照层，存 manifest phase3.loop_state
- **G4**：UpgradeDetector 能判 minor→major 升级（占比超阈值 / finding 涉及需求章 / 连续同类失败）
- **G5**：三块集成后能跑通最小 case

## 3. 需求

### 3.1 功能性需求

| ID | 需求 | 对应 design doc |
|----|------|----------------|
| R1 | 硬关卡定义（关卡ID→manifest片+字段+判定条件） | §5.3 + §附录A |
| R2 | 单条硬关卡校验（读 manifest 字段→PASS/FAIL） | §8.1 |
| R3 | 批量校验（阶段出口全过才 PASS） | §8.1 |
| R4 | loop_state 定位层更新（current_phase/task/loop_type） | §8.4 |
| R5 | loop_state 进度快照层更新（files_modified/review_round 等） | §8.4 |
| R6 | loop_state 存 manifest phase3.loop_state 字段 | §8.4 |
| R7 | 升级判定：needs_revalidation 占比 > 阈值 | §7.3 |
| R8 | 升级判定：finding 涉及需求章(1-3)/方案概览(4.1) | §7.3 |
| R9 | 升级判定：连续 N 轮同类失败 | §7.3 |
| R10 | 集成验证 case | §8.1 |

### 3.2 非功能性需求

- loop_state 只存进度不存结果（§8.4 边界）——结果在 manifest status 字段
- 机器可验证字段从客观源拉取，不信 agent 上报（§8.4）
- 所有函数有类型注解 + docstring

### 3.3 非目标（本轮不做）

- 五种 Loop 形态的完整状态机（A/B/C/D/E 嵌套/中断/升级）——依赖 Context 层
- Loop 基本单元的 Context Push 部分——依赖 Context 层
- minor/major 刷新的完整流程——本轮只做升级判定，不做刷新执行

## 4. 设计方案

### 4.1 模块结构

```
src/engineering_agent/loop/
├── __init__.py
├── gate_checker.py        # Task 2: 硬关卡校验器
├── state_tracker.py       # Task 3: loop_state 管理器
└── upgrade_detector.py    # Task 4: minor→major 升级判定
```

### 4.2 GateChecker（design doc §8.1 + §5.3）

- **硬关卡定义**：`GateCheck(phase, field, condition)` —— 关卡ID + manifest 片 + 字段 + 判定条件
- **单条校验**：`check(gate, manifest_store) -> GateResult(PASS/FAIL)`
- **批量校验**：`check_all(gates, manifest_store) -> BatchResult(all_pass, failures[])`
- 内置编码阶段出口硬关卡清单（design doc §附录A）：
  - tasks 全 Done / lint 0 新增 / 编译过 / 现有测试无 regress / 新增单测过 / review PASS / needs_revalidation 全 reviewed

### 4.3 LoopStateTracker（design doc §8.4）

- **更新定位层**：`update_location(phase, task_id, loop_type)` —— Harness 调用，存 manifest phase3.loop_state
- **更新进度快照**：`update_snapshot(field, value)` —— 机器可验证字段从客观源拉取
- **读取**：`get_state(manifest_store) -> LoopState | None`
- **清空 pending_findings**：review PASS 后必须清空（§8.4 边界）

### 4.4 UpgradeDetector（design doc §7.3）

- **needs_revalidation 占比**：`check_ratio(total, reviewed) -> bool`（占比 > 阈值 → 升级）
- **finding spec_refs 检查**：`check_finding_refs(findings) -> bool`（涉及 1-3/4.1 → 升级）
- **连续失败**：`check_consecutive_failures(rounds) -> bool`（连续 N 轮同类 → 升级）
- **综合判定**：`detect(total, reviewed, findings, rounds) -> UpgradeDecision`

### 4.5 集成验证

最小 case：
1. manifest 写 phase3（compile_passed=False）→ GateChecker 校验"编译过" → FAIL
2. manifest 更新 compile_passed=True → GateChecker 校验 → PASS
3. 批量校验阶段出口——有 FAIL 则整体 FAIL
4. LoopStateTracker 更新定位层 → 读回一致
5. UpgradeDetector 判 needs_revalidation 占比 80% → 升级

## 5. Goal State（验证标准）

| 验证 | 方式 | 通过条件 |
|------|------|---------|
| GateChecker 单条 | pytest | 读 manifest 字段判 PASS/FAIL |
| GateChecker 批量 | pytest | 有 FAIL 则整体 FAIL，全过则 PASS |
| LoopStateTracker | pytest | 更新定位层+快照层 → 读回一致 |
| UpgradeDetector | pytest | 占比>阈值升级 / finding 涉及需求章升级 / 连续失败升级 |
| 集成 case | pytest | 三块串联跑通 |
