# 执行轨迹日志：Task 6 — spec SHA 锁定

- **Task**: Task 6: spec SHA 锁定
- **Status**: Completed
- **Started**: 2026-08-13
- **Ended**: 2026-08-13

## 决策事件

### 1. 设计决策
- freeze 返回 commit SHA（不是 blob SHA），因为 spec 版本 = commit 版本（§7.1）
- read_locked 用 `git show <sha>:<path>` 读指定 commit 的文件内容
- check_committed 用 `git status --porcelain` 检查未提交变更

### 2. 关键约束
- 未 commit 的 spec 无法冻结（§7.1 强制 commit）
- read_locked 即使工作区 spec 已改成 v4，仍返回冻结版本内容（不串版本）
- 路径用 / 分隔（git 要求，Windows 下需转换）

### 3. 验证结果
- 7 个测试全通过（check_committed / freeze / read_locked / 不串版本）

### 4. Review
- git subprocess 操作，主 agent 自检 → PASS
