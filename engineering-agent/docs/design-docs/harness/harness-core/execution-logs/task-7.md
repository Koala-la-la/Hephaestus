# 执行轨迹日志：Task 7 — 集成验证

- **Task**: Task 7: 集成验证
- **Status**: Completed
- **Started**: 2026-08-13
- **Ended**: 2026-08-13

## 决策事件

### 1. 设计决策
- **Harness 类**（`src/engineering_agent/harness.py`）：集成 ManifestStore + ToolGate + SpecLock
- 核心逻辑：**spec-first 检查**——编码/测试阶段的写操作（edit_file/write_file），必须先冻结 spec 才放行
- 两层检查：权限矩阵（ToolGate）先 → spec-first 检查后（L2/L3 在权限层就被拒，不走到 spec-first）

### 2. 关键设计
- spec-first 检查只对 `_WRITE_TOOLS = {"edit_file", "write_file"}` + `_SPEC_FIRST_PHASES = {"coding", "testing"}`
- read_file（L0）不受 spec 冻结限制（无害操作随时可用）
- L2 工具即使 spec 已冻结仍被拒（权限层先于 spec-first 检查）
- 这把 Prompt 级「禁止无 spec 改代码」下沉到机制层——design doc §3.4 原则1 的执行点

### 3. 集成 case 验证
- case 1: spec 未冻结 → edit_file 被拒（"spec 未冻结，无 spec 不许改代码"）✓
- case 2: spec 未 commit → freeze_spec 抛 RuntimeError ✓
- case 3: spec commit + freeze → edit_file 放行（L1）✓
- case 4: manifest 写 needs_revalidation → 读回一致 ✓
- 额外：read_file 不受 spec 冻结限制 / L2 即使冻结仍拒 / 测试阶段写也需 spec 冻结

### 4. 最终验证
- `pytest tests/ -v`：**55 passed in 7.35s**
- 全部 7 个 task 完成，Harness 层最小原型可用

## 全部 Task 总结

| Task | 产物 | 测试数 |
|------|------|--------|
| 1 脚手架 | pyproject.toml + 包结构 | 2 |
| 2 manifest 模型 | 6 片 Pydantic + 7 枚举 + 5 辅助 | 9 |
| 3 读写器 | ManifestStore + archive/restore | 11 |
| 4 权限定义 | DangerLevel + PermissionMatrix | 11 |
| 5 拦截器 | ToolGate + PermissionResult | 8 |
| 6 spec 锁定 | SpecLock (git SHA) | 7 |
| 7 集成 | Harness (spec-first 检查) | 7 |
| **合计** | | **55** |
