# 项目宪法：Engineering Agent

> 工程规范约束型 AI Agent。将工程纪律从 Prompt 级软约束下沉到 Harness/Loop 机制层。
> 完整设计文档见 `../engineering-agent-design.md`（上级目录）。

## 技术栈
- 语言：Python 3.11+
- 包管理：uv + pyproject.toml
- 测试：pytest
- 数据模型：pydantic v2

## Spec-First
- 禁止无 spec 修改代码文件（.py）
- .md 等非代码文件不受此约束
- spec 路径：`docs/design-docs/<module>/<feature>/spec.md`

## 语言
- 输出用中文；代码标识符、命令、路径保持英文

## 设计文档引用
- 架构设计：`../engineering-agent-design.md`（五层架构 + manifest schema + 工具权限矩阵 + Loop 形态等）
- 论文大纲：`../engineering-agent-thesis.md`
- 所有实现决策必须可追溯到 design doc 的对应章节
