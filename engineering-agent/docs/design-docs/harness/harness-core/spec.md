# Spec: Harness 层最小原型

> Status: Quick Draft
> 上游设计文档：`../../../engineering-agent-design.md`（简称 design doc）
> 本 spec 锚定第一轮实现范围——Harness 层三块核心功能。

---

## 1. 背景

design doc 定义了一个五层架构（Prompt/Context/Harness/Loop/Graph）的专业型工程 Agent。§19 实施路径建议从 Harness 层开始——它是其他层的基础（manifest 读写被所有层依赖，工具权限拦截是硬约束的执行点，spec SHA 锁定是版本一致性的锚点）。

本 spec 聚焦 Harness 层最小原型，实现三块功能：
1. **manifest 读写**（design doc §5）——结构化元数据的分片读写、归档、版本一致性
2. **工具权限拦截**（design doc §6）——L0-L3 危险等级 + 阶段×工具矩阵 + 调用前拦截
3. **spec SHA 锁定**（design doc §7.1/§6.3）——Git SHA 锁定 spec 版本，强制 commit

## 2. 目标

- **G1**：manifest 能分片读写（common/phase1-5），支持 major 刷新归档
- **G2**：工具权限拦截器能在 Agent 调用工具前检查权限，L2 直接拒绝
- **G3**：spec SHA 能锁定，编码阶段读 spec 按 SHA 读取，不串版本
- **G4**：三块功能集成后能跑通最小 case：无 spec 时 Edit 被拦截 + 有 spec 时放行

## 3. 需求

### 3.1 功能性需求

| ID | 需求 | 对应 design doc |
|----|------|----------------|
| R1 | manifest 数据模型定义（六片 + 字段类型） | §5.2 |
| R2 | manifest 分片读写（JSON 文件） | §5.1 |
| R3 | manifest 归档（major 刷新时整体归档到 archives/） | §5.4 |
| R4 | manifest 版本一致性（共享 spec_sha） | §5.4 |
| R5 | 危险等级定义（L0/L1/L2/L3） | §6.1 |
| R6 | 阶段×工具权限矩阵配置 | §6.2 |
| R7 | 工具调用前权限检查 + L2 拒绝 + audit 日志 | §6.3 |
| R8 | spec SHA 锁定（记录当前冻结版本） | §7.1 |
| R9 | spec 升版本强制 commit 检查 | §7.1 |
| R10 | 集成验证 case | §4.4 决策1 |

### 3.2 非功能性需求

- manifest 字段必须机器可读（布尔/数字/数组/对象，design doc §5.3 铁律2）
- manifest 写入是阶段出口唯一凭证（§5.3 铁律3）
- L2 工具拒绝时不依赖 Agent 自觉，直接拒绝（§6.3 铁律2）
- 所有函数有类型注解 + docstring

### 3.3 非目标（第一轮不做）

- Loop 层（硬关卡校验 + loop_state）——第二轮
- Context 层（Push/Pull）——第三轮
- Graph 层（多 agent 制衡）——第四轮
- Prompt 层（L1/L2/L3 协议）——第五轮
- confirm token 机制——后续
- minor/major 刷新的完整 Loop 流程——后续（本轮只做 manifest 归档的数据结构支撑）

## 4. 设计方案

### 4.1 模块结构

```
src/engineering_agent/
├── __init__.py
├── manifest/
│   ├── __init__.py
│   ├── models.py          # manifest 数据模型（Pydantic）—— Task 2
│   ├── store.py            # manifest 读写器 —— Task 3
│   └── archive.py           # 归档逻辑 —— Task 3
├── permissions/
│   ├── __init__.py
│   ├── levels.py           # L0-L3 危险等级定义 —— Task 4
│   ├── matrix.py            # 阶段×工具权限矩阵 —— Task 4
│   └── gate.py              # 工具权限拦截器 —— Task 5
├── spec/
│   ├── __init__.py
│   └── lock.py              # spec SHA 锁定 —— Task 6
└── harness.py               # 集成入口 —— Task 7
```

### 4.2 manifest 数据模型（design doc §5.2）

用 Pydantic v2 定义六片 manifest：
- `common`：spec_sha / spec_version / change_type
- `phase1`：sections_status / goal_measurable / nonfunctional_checked
- `phase2`：sections_status / monitoring_thresholds / tasks / reverse_coverage
- `phase3`：task_status / lint_baseline_delta / compile_passed / review_findings / needs_revalidation / loop_state
- `phase4`：all_tests_passed / coverage / three_category_coverage
- `phase5`：release_package_sha / rollback_plan / grayscale_* / monitoring_thresholds

字段类型严格按 design doc §5.2（布尔/数字/数组/对象）。

### 4.3 工具权限拦截（design doc §6）

- `levels.py`：L0(无害)/L1(可逆)/L2(不可逆)/L3(需人确认) 枚举
- `matrix.py`：阶段(需求/设计/编码/测试/上线)×工具 的权限矩阵，可从 YAML/JSON 配置加载
- `gate.py`：`check_permission(phase, tool) -> PermissionResult`，调用前检查，L2 直接拒绝，写 audit 日志

### 4.4 spec SHA 锁定（design doc §7.1）

- `lock.py`：`SpecLock` 类
  - `freeze(spec_path) -> str`：记录当前 spec 的 Git SHA，返回锁定版本号
  - `read_locked(spec_path, sha) -> str`：按 SHA 读 spec（`git show <sha>:spec.md`）
  - `check_committed(spec_path) -> bool`：检查 spec 是否已 commit（未 commit 则拒绝锁定）

### 4.5 集成验证（design doc §4.4 决策1）

最小 case：
1. spec 不存在 → 工具权限拦截器拒绝 Edit（无 spec 不许改代码）
2. spec 存在但未 commit → spec SHA 锁定拒绝冻结
3. spec 存在且已 commit → SHA 锁定成功 → 工具权限拦截器放行 Edit
4. manifest 读写器能写入 phase3 的 needs_revalidation 字段

## 5. Goal State（验证标准）

| 验证 | 方式 | 通过条件 |
|------|------|---------|
| manifest 模型 | pytest | 六片模型能序列化/反序列化 JSON |
| manifest 读写 | pytest | 能写 phase3.json 并读回，字段值一致 |
| manifest 归档 | pytest | major 刷新时整体归档到 archives/，可恢复 |
| 权限拦截 | pytest | L2 工具被拒绝 + audit 日志有记录 |
| spec 锁定 | pytest | 能冻结 SHA + 按 SHA 读 + 未 commit 时拒绝 |
| 集成 case | pytest | 无 spec 拦截 Edit + 有 spec 放行 |
