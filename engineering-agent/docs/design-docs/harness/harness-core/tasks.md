# Tasks: Harness 层最小原型

> 基于 spec.md（Quick Draft），实现 design doc §5/§6/§7.1 的 Harness 层三块功能。
> 验收标准见 spec.md §5 Goal State。

## Task 1: 项目脚手架
- **Status**: Completed
- **做什么**: 搭建 Python 项目骨架，让后续代码有地方放、能跑测试
- **解决什么问题**: 没有 pyproject.toml 和包结构，后续 task 无法组织代码
- **具体改什么代码**: 新建 `pyproject.toml`（uv 管理）、`src/engineering_agent/__init__.py`、`tests/__init__.py`、`.gitignore`
- **目标**: 项目能 `pip install -e .` + `pytest` 能跑（空测试 0 failures）
- **验收标准**: `pytest` exit 0；`python -c "import engineering_agent"` 无报错
- **依赖**: 无

## Task 2: manifest 数据模型
- **Status**: Completed
- **做什么**: 用 Pydantic v2 定义 manifest 六片数据模型，让 manifest 有严格的类型结构
- **解决什么问题**: design doc §5.2 定义了 manifest schema 但没有代码实现；没有数据模型，读写器无东西可读写
- **具体改什么代码**: 新建 `src/engineering_agent/manifest/models.py`，定义 CommonManifest / Phase1Manifest / Phase2Manifest / Phase3Manifest / Phase4Manifest / Phase5Manifest 六个 Pydantic 模型，字段严格按 design doc §5.2
- **目标**: 六片模型能正确序列化/反序列化 JSON
- **验收标准**: pytest 测试六片模型的 `model_dump_json()` / `model_validate_json()` 往返一致
- **依赖**: Task 1

## Task 3: manifest 读写器
- **Status**: Completed
- **做什么**: 实现 manifest 分片读写 + major 刷新归档，让 Harness 能操作 manifest 数据
- **解决什么问题**: design doc §5.1 要求 manifest 分片存 JSON 文件、§5.4 要求 major 刷新整体归档；没有读写器，其他层无法用 manifest 做硬关卡校验
- **具体改什么代码**: 新建 `src/engineering_agent/manifest/store.py`（ManifestStore 类：read/write/get_field/update_field）+ `src/engineering_agent/manifest/archive.py`（归档到 archives/manifest.<version>.json + 恢复）
- **目标**: 能写 phase3.json 并读回；major 刷新时整体归档 + 可恢复
- **验收标准**: pytest 测试读写往返 + 归档/恢复
- **依赖**: Task 2

## Task 4: 工具权限定义
- **Status**: Completed
- **做什么**: 定义 L0-L3 危险等级 + 阶段×工具权限矩阵，让权限检查有判定依据
- **解决什么问题**: design doc §6 定义了权限体系但没有代码；没有权限定义，拦截器无依据可查
- **具体改什么代码**: 新建 `src/engineering_agent/permissions/levels.py`（DangerLevel 枚举 L0-L3）+ `src/engineering_agent/permissions/matrix.py`（PermissionMatrix 类，阶段×工具→DangerLevel 映射，可从 JSON 配置加载）
- **目标**: 给定（阶段, 工具）能查到危险等级
- **验收标准**: pytest 测试矩阵查询（如编码阶段 edit_file=L1、上线阶段 kubectl=L2）
- **依赖**: Task 1

## Task 5: 工具权限拦截器
- **Status**: Completed
- **做什么**: 实现工具调用前权限检查，L2 直接拒绝 + 写 audit 日志，把"Agent 不能做什么"从 Prompt 提醒变成硬拦
- **解决什么问题**: design doc §6.3 铁律2 要求"L2 在 Harness 层直接禁"——不依赖 Agent 自觉；没有拦截器，权限定义只是数据不是行为
- **具体改什么代码**: 新建 `src/engineering_agent/permissions/gate.py`（ToolGate 类：check_permission(phase, tool)→PermissionResult[allow/deny/need_confirm] + 写 audit 日志到 stdout/文件）
- **目标**: 调用 check_permission 时，L2 返回 deny + 有 audit 记录
- **验收标准**: pytest 测试 L0 放行 / L2 拒绝 / L3 返回 need_confirm + audit 日志验证
- **依赖**: Task 4

## Task 6: spec SHA 锁定
- **Status**: Completed
- **做什么**: 实现 Git SHA 锁定 spec 版本，让编码阶段读 spec 不串版本（design doc §7.1 的核心机制）
- **解决什么问题**: design doc §7.1 要求"编码入口冻结 spec SHA，后续读按 SHA 读"——没有锁定机制，agent 可能读到 v4 还以为是 v3
- **具体改什么代码**: 新建 `src/engineering_agent/spec/lock.py`（SpecLock 类：freeze(spec_path)→sha / read_locked(sha)→content / check_committed(spec_path)→bool，用 `git show <sha>:<path>` 读指定版本）
- **目标**: 能冻结 SHA + 按 SHA 读 spec + 未 commit 时拒绝冻结
- **验收标准**: pytest 测试 freeze + read_locked + 未 commit 拒绝（用临时 git 仓库）
- **依赖**: Task 1

## Task 7: 集成验证
- **Status**: Completed
- **做什么**: 把三块功能串起来跑通最小 case，验证 Harness 层能作为其他层的基础
- **解决什么问题**: design doc §4.4 决策1 要求"manifest 作为 Harness 唯一操作对象"——需要验证三块功能协作是否跑得通
- **具体改什么代码**: 新建 `src/engineering_agent/harness.py`（Harness 类：集成 ManifestStore + ToolGate + SpecLock）+ `tests/test_integration.py`（最小 case：无 spec 拦截 Edit / 有 spec 放行 / manifest 写 needs_revalidation）
- **目标**: 集成 case 全通过
- **验收标准**: pytest test_integration.py 全 PASS
- **依赖**: Task 3, Task 5, Task 6
