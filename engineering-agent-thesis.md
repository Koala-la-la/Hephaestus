# 面向软件工程全流程的约束型 AI Agent 架构设计

> 本科毕业论文大纲与主体内容草稿。基于 `engineering-agent-design.md` 设计文档转化。评估/验证部分暂不写，后续补充。标注 `[待引用]` 处需补具体文献，`[待画图]` 处需补论文插图。

---

## 摘要

AI 编码 Agent 的能力日益增强，但其输出的概率性本质与工程纪律的确定性要求之间存在根本矛盾。现有方案将工程规范编码为 Skill/Prompt 文件，本质是软约束——Agent 可遵守也可违反，可靠性无法保证。本文从 LLM 的三个本质特征（上下文决定性、概率性、工作记忆易失性）出发，提出"软硬约束判据"：能映射到结构化数据字段或命令退出码的约束可被硬化，否则只能软化。基于此判据，设计了一个五层架构（Prompt/Context/Harness/Loop/Graph），将可硬化的约束从 Prompt 下沉到 Harness 与 Loop 机制层，不可硬化的用 Context 质量与多 Agent 制衡最大化概率。核心贡献包括：manifest 结构化传递协议（阶段边界不靠自然语言）、spec 快照锁定与 minor/major 分级刷新机制、五种 Loop 形态及嵌套/中断/升级关系、多 Agent 三权分立的编码审查与三级分级拦截、以及灰度三档分级的安全上线机制。本设计已形成完整的可实施方案，为工程规范型 AI Agent 的实现提供了架构基础。

**关键词**：AI Agent；软件工程；约束硬化；上下文工程；多 Agent 协作

---

## 第一章 绪论

### 1.1 研究背景

AI 正在深刻改变软件开发的方式。从最初的代码补全（GitHub Copilot），到集成了代码库上下文的编辑器（Cursor），再到能自主规划、编码、测试的 AI Agent（Claude Code、Codex CLI、Devin），AI 与开发者的协作模式正在快速演进。在这一过程中，一种被称为"vibe coding"的实践率先流行——开发者将需求直接抛给 AI，不审查 diff、不理解生成的代码，凭直觉接受输出，以最快速度得到"能跑"的结果。

Vibe coding 在原型验证中有其价值，但其本质是**用速度换取了理解和控制**，无法承载生产级系统的质量要求。当 AI 生成的代码进入生产环境，"能跑"和"能上线"之间的鸿沟就暴露出来：生成的代码可能表面正确但语义偏差，可能不符合团队编码规范，可能引入性能回退或安全漏洞。

### 1.2 研究问题

为应对上述问题，业界出现了将工程纪律编码为 AI 可读文件（如 Skill、Prompt）的框架。以 agentic-engineering-framework 为代表，这类框架将需求澄清、系统设计、代码生成、测试、审查的完整 SDLC 流程编码为 Skill 文件，让 AI 在写代码时按纪律走。

然而，这类框架存在一个根本局限：**Skill 和 Prompt 本质是软约束**。无论 Markdown 文件里写了多少"必须""禁止"，对 LLM 而言只是输入 Token 的概率影响，不是强制力。LLM 可以"违反"任何 Prompt 指令——这是概率模型的本质属性，不是 Prompt 工程能解决的。

具体表现为：
- **约束不可靠**：Skill 里写了"创建 tasks 后必须停下等确认"，但 Agent 可能自动继续推进
- **上下文易失**：长会话中早期注入的规范随对话膨胀被稀释，Agent"忘记"纪律
- **无客观验证**：Agent 自称"测试通过了"，但没有机制验证它真的跑了测试
- **无权限隔离**：编码阶段的 Agent 拥有与上线阶段相同的工具权限，可能误操作生产环境

### 1.3 研究目标与贡献

本文的研究目标是：**将工程纪律中"可硬化"的约束从 Prompt 层下沉到机制层，使 AI Agent 能在 SDLC 全流程中可靠地遵循工程规范，同时保留"不可硬化"部分的创造性自由。**

本文的主要贡献：

1. **软硬约束判据**：提出"能映射到结构化数据字段或命令退出码的约束可硬化"这一可操作判据，给出了区分可硬化与不可硬化的工程标准。

2. **五层架构设计**：设计 Prompt/Context/Harness/Loop/Graph 五层架构，明确各层硬度与分工——Harness+Loop 层承担硬约束（工具权限、客观验证），Context+Graph 层最大化不可硬化部分的概率。

3. **manifest 结构化传递协议**：设计阶段边界的结构化元数据传递机制，使阶段切换的合法性可被机器判定，不依赖自然语言解析。

4. **spec 快照锁定与分级刷新**：设计 Git SHA 锁定的 spec 版本化机制，以及 minor/major 分级刷新策略，处理编码过程中 spec 演化的任务一致性问题。

5. **五种 Loop 形态及嵌套关系**：形式化定义前进式 Task Loop、minor/major 刷新 Loop、needs_revalidation review Loop、灰度轮询 Loop 五种循环形态，及其嵌套/中断/升级的状态机关系。

6. **多 Agent 三权分立审查**：设计 Judge-Reviewer-Critic 三权分立的编码审查机制，配合机器 P0/Agent P0/P1-P2 三级分级拦截，对冲 Agent"不否决自己人"的偏置。

7. **灰度三档分级安全上线**：设计 Agent 不持有生产写权限前提下的灰度发布机制——探针/验证自判，确认期人确认，配合分级回滚。

### 1.4 论文组织结构

第二章综述相关工作。第三章从问题分析出发建立设计原理（三条公理 + 软硬判据）。第四章给出总体架构。第五至十一章分别详述五层及闭环机制。第十二章总结全文并展望未来工作。评估与验证部分暂略，留待原型实现后补充。

---

## 第二章 相关工作

### 2.1 AI 辅助编码工具的发展

AI 辅助编码经历了三个阶段。**代码补全阶段**以 GitHub Copilot 为代表，在编辑器内提供行级/函数级建议 `[待引用：Copilot 生产力研究]`。**上下文增强阶段**以 Cursor、Windsurf 为代表，将代码库上下文集成进编辑器，支持跨文件理解。**自主 Agent 阶段**以 Claude Code、Codex CLI、Devin、SWE-Agent 为代表，AI 能自主规划任务、调用工具、执行多步操作。

上述工具大多是**通用型 Agent**——给工具权限和自主权，纪律靠 Prompt。它们不专门约束 Agent 遵循特定工程流程，开发者需自行把握质量。

### 2.2 Agentic Engineering 方法论

Agentic Engineering 是一种工程师与 AI Agent 深度协作的模式——AI 不仅执行代码，也参与问题分析和方案设计，但最终判断权在工程师手中 `[待引用：Osmani, Agentic Engineering]`。其核心立场是：Engineering 的本质是约束优化，引入 AI 不应放弃约束和质量标准。

agentic-engineering-framework 是该方法论的实践落地，将六条最佳实践（Context Engineering、人机分工、AI 全链条参与、小任务推进+多层次验证、Knowledge as Code、Error-Driven Refinement）编码为 Skill 文件。

### 2.3 现有 Skill 框架及其局限

agentic-engineering-framework 的结构包含：5 个 Workflow Skill（需求→设计→编码→测试→评审）、6 个 Best Practice Skill、7 个 Reviewer Subagent、Self-Refinement 反馈闭环。其设计哲学是"三层加载机制"（L1 元数据/L2 主体/L3 参考），靠按需加载控制上下文成本。

但该框架的约束全部停留在 Prompt/Skill 层级。其作者自己也承认约束可靠性光谱：`Prompt 约束(低) → SKILL(中) → hook(高)`。框架内没有 Hook、没有项目宪法、没有工具权限分级、没有质量门禁机制——所有"必须""禁止"都靠 Agent 自觉。

### 2.4 软件工程中的流程治理

传统软件工程的流程治理依赖**机制层强制**而非文档约束：CI/CD 流水线是代码不是文档，git hook 是脚本不是 Prompt，代码审查是人对人不是 AI 对自己。这些机制之所以可靠，正是因为它们在 Agent 控制流之外执行。

本文的设计正是借鉴这一思路——把传统软件工程"机制层强制"的原则，应用到 AI Agent 的治理上。

### 2.5 本章小结

现有 AI 辅助编码工具和 Skill 框架都未能解决"工程约束的可靠性"问题：通用 Agent 不约束、Skill 框架靠软约束。本文借鉴传统软件工程"机制层强制"的原则，提出将可硬化的约束下沉到 Agent 控制流之外的机制层。

---

## 第三章 设计原理

### 3.1 问题分析：为什么 Prompt 级约束不够

Prompt 级约束不可靠的根因在于 LLM 的本质——**输出由上下文决定，但输出是概率性的**。Prompt 里的"必须""禁止"只是 Token 序列的一部分，影响输出概率，但不保证输出。这与传统软件工程中"代码 = 确定执行"有根本区别。

具体地，Prompt 约束面临三个失效路径：
1. **概率性违反**：即使 Prompt 写了"禁止无 spec 改代码"，Agent 仍有非零概率直接改代码
2. **上下文稀释**：长会话中早期 Prompt 被挤出窗口，约束"失效"
3. **自我合理化**：Agent 倾向推进而非停下，会给自己找"这次不用跑测试"的理由

这三个路径都不是 Prompt 工程能根治的——它们源于模型架构，不源于措辞。

### 3.2 三条公理

本设计的所有推导基于三条不可争辩的基本事实 `[待引用：参考 agentic_engineering.md 第一性原理推导]`：

**公理 1（信息损耗）**：软件工程的本质是将人类意图逐步精确化为机器代码，这条链的每一步都可能引入信息损耗。越早期的损耗修复代价越大。

**公理 2（LLM 本质特征）**：LLM 是基于上下文进行概率性推理的系统，具有三个并列本质特征——输出由上下文决定、输出是概率性的、工作记忆有限且易失。

**公理 3（人类认知稀缺）**：工程师的注意力、判断力和决策能力是有限的，是整个人机协作系统的瓶颈。

### 3.3 软硬约束判据

本文的核心理论贡献——一条可操作的判据，区分哪些工程约束可被硬化：

> **一条约束能被硬化，当且仅当它的校验对象能映射到结构化数据字段（manifest）或命令退出码（exit code）。**

换言之：能用脚本判"测试是否通过"（exit code）的，能硬；要判"设计是否合理"（需解析自然语言）的，不能硬。

这把模糊的"可机器判定 vs 不可机器判定"精确化为"能映射到 manifest 字段或 exit code"。判据一旦成立，约束的硬度来源就清晰了：

| 校验对象 | 硬度 | 机制 |
|----------|------|------|
| manifest 字段 | 真硬 | Harness 读字段拦/放 |
| 命令 exit code | 真硬 | Loop 跑命令判 |
| 多 Agent 裁决 | 半硬 | Graph 层博弈降概率 |
| 自然语言解析 | 软 | Prompt/Context 提醒 |

### 3.4 设计原则

从判据推导出四条设计原则：

1. **硬关卡在阶段边界，软约束在阶段内部**——SDLC 阶段的入口前置和出口验收大多是可机器判定的（文件存在、测试通过），阶段内的创造性工作不可判定。所以硬关卡画在边界。

2. **能写脚本的别让 Agent 跑**——确定性工作（lint、测试、格式化、结构化输出校验）由脚本执行，Agent 只做认知工作（设计、编码、权衡）。Agent 不提供"这次不用跑测试"的合理化空间。

3. **阶段边界传递靠结构化数据，不靠自然语言**——自然语言摘要是软的（Agent 会漏读/误读），结构化 manifest 字段是硬的（Harness 直接读）。

4. **不确定时上报人，不自动决策**——fail-safe 原则：能不丢数据就不丢、能不自动决策就不自动决策、能回退就回退。

### 3.5 本章小结

本章从 Prompt 级约束的失效路径出发，建立三条公理，推导出软硬约束判据，并由此得出四条设计原则。判据"能映射到 manifest 字段或 exit code"贯穿后续所有架构设计——它是区分"能硬"与"只能软"的工程标准。

---

## 第四章 总体架构设计

### 4.1 设计目标

将可硬化的约束从 Prompt 下沉到机制层，使 AI Agent 在 SDLC 全流程中可靠遵循工程规范，同时保留不可硬化部分的创造性自由。具体化为：
- 可硬化的约束（文件存在、测试通过、工具权限）→ 100% 机制强制
- 不可硬化的约束（spec 质量、设计合理性）→ 最大化概率（Context + 多 Agent + 人）

### 4.2 五层架构总览

```
┌─────────────────────────────────────────────────┐
│  Prompt 层   系统提示定义"角色和纪律"           │ 软（基线）
├─────────────────────────────────────────────────┤
│  Context 层  分阶段喂不同上下文                 │ 半硬（输入侧限形状）
├─────────────────────────────────────────────────┤
│  Harness 层  工具集 + 权限分级 + 流程编排        │ 硬（没权限=没权限）
├─────────────────────────────────────────────────┤
│  Loop 层     每 step 确定性验证 + 失败回退       │ 硬（客观判定）
├─────────────────────────────────────────────────┤
│  Graph 层    多 Agent 制衡                       │ 半硬（博弈降概率）
└─────────────────────────────────────────────────┘
```

各层分工与硬度：

| 层 | 职责 | 硬度 | 对冲的公理 |
|----|------|------|-----------|
| Prompt | 角色/纪律常驻 | 软 | 公理2（上下文决定性） |
| Context | 分阶段喂上下文 | 半硬 | 公理2（记忆易失） |
| Harness | 工具权限+流程编排+manifest读写 | 硬 | 公理2（概率性）+ 公理3 |
| Loop | 客观验证+失败回退+熔断 | 硬 | 公理2（概率性） |
| Graph | 多 Agent 制衡 | 半硬 | 公理2（不否决自己人） |

**重心在 Harness + Loop**——这两层是唯一能"真硬"且"工程化"的。Prompt 层太软（与原版无异），Context 层是辅助，Graph 层半硬（多 Prompt 还是 Prompt）。但 Harness+Loop 没有 Prompt/Context/Graph 配合会僵化，所以是"重心在 Harness+Loop，其他层配合"。

### 4.3 SDLC 阶段模型

本设计沿用传统 SDLC 的逻辑阶段划分（需求→设计→编码→测试→上线），因为逻辑 SDLC 是稳定坐标系——不因工具变化。但执行层做了关键改造：

每个阶段定义四要素：
- **入口前置（硬）**：上一阶段产物必须完备（可机器判定）
- **阶段内自主权（软）**：Agent 在内部怎么创造
- **出口验收（硬关卡+软关卡）**：可机器判定的 PASS 条件
- **回退条件（半硬）**：什么情况下回退到前一阶段

关键设计：阶段边界 = 硬关卡画在边界，软约束留在内部。这把 SDLC 从"线性流程"变成"带返修通道的关卡流水线"——每个关卡有正向放行条件和反向回退条件。

### 4.4 架构设计决策

本设计有几个关键的架构决策，及其理由：

**决策 1：manifest 作为 Harness 的唯一操作对象**。Harness 只读 manifest，不解析自然语言产物。这使硬关卡的校验对象明确——manifest 字段。若 Harness 要解析 spec.md 正文判"设计章是否完整"，那是软的；读 manifest 的 `sections_status` 字段，才是硬的。

**决策 2：spec 用 Git SHA 锁定**。spec 升版本必须 commit，编码基于的版本用 SHA 钉死。这使"版本一致性"有不可变锚点。

**决策 3：Graph 层只在两处使用**（目标可衡量 Critic + 编码 review），不在所有阶段用多 Agent。理由：spec 完备性、设计合理性追求完美是过度工程，靠回退通道兜底；多 Agent 成本（Token/延迟/复杂度）高，只在最值钱的两处用。

**决策 4：Agent 不持生产写权限**。上线阶段 Agent 产出发布包 + 编排流水线，但不持有 kubectl/数据库写权限。这是生产安全的硬边界——凭据不该交给编码 Agent。

### 4.5 本章小结

本章给出五层架构和 SDLC 阶段模型的总览。核心决策是"manifest 作为 Harness 唯一操作对象"和"重心在 Harness+Loop 层"，这两条使约束从 Prompt 软约束升级为机制硬约束成为可能。

---

## 第五章 数据层：结构化传递协议

### 5.1 设计动机

阶段边界的信息传递，如果靠自然语言摘要，是软的——Agent 会漏读、误读、被冗余干扰。tasks.md 里的 spec_refs 如果存在，它是硬的——Harness 直接按字段 Push 对应章节，没有模糊空间。

这两个问题指向同一方向：**阶段边界需要结构化传递协议**。每个阶段的产出不仅是文件，还要包含下一阶段 Harness 所需的结构化元数据。

### 5.2 manifest 结构设计

manifest 不是一个大 JSON，而是按阶段分片、累计递进。每个阶段产出一片：

| 片 | 关键字段 | 产出阶段 |
|----|---------|---------|
| common | spec_sha / spec_version / change_type | 全阶段共享 |
| phase1 | sections_status / goal_measurable / nonfunctional_checked | 需求 |
| phase2 | sections_status / monitoring_thresholds / tasks[](spec_refs/estimated_files) / reverse_coverage | 设计 |
| phase3 | task_status / lint_baseline_delta / compile_passed / review_passed / review_findings[](source:machine\|agent) / needs_revalidation / loop_state | 编码 |
| phase4 | all_tests_passed / coverage_met / three_category_coverage | 测试 |
| phase5 | release_package_sha / rollback_plan / grayscale_strategy / monitoring_thresholds(快照) / grayscale_status | 上线 |

**三条铁律**：
1. 硬关卡必须能映射到 manifest 字段
2. 字段必须机器可读（布尔/数字/数组/对象，不能自然语言）
3. manifest 写入是阶段出口唯一凭证（spec.md 有内容但 manifest 没更新 = Harness 不认）

### 5.3 阶段边界的信息传递

以阶段 2→3（设计→编码）为例。传递的不是"设计摘要"，而是：
- `spec.meta.json`（结构化，含 sections_status、tasks 的 spec_refs）
- `tasks.md`（结构化，含每个 task 的 spec_refs 字段）
- spec.md 相关章节（自然语言，按 spec_refs 索引 Push 给编码 Agent）

没有"摘要"这一步——Harness 按 tasks.md 的 spec_refs 字段，从 spec.md 定位相关章节的原文 Push 给 Agent。权衡记录不丢——它归属于被引用的章节，随章节一起进。

关键原则：**索引和归属结构化，内容可自然语言**。Harness 按结构化索引定位内容，Agent 读自然语言内容做推理。结构化是导航，自然语言是燃料。

### 5.4 版本一致性规则

| 规则 | 说明 |
|------|------|
| 共用 spec_sha | manifest 和 spec 共享同一 Git SHA |
| major 刷新归档 | 整体归档到 archives/ |
| minor 刷新增量 | 只更新 phase3，不重建整个 manifest |
| 回滚恢复 | 从归档恢复 |
| monitoring_thresholds 快照 | phase5 从 phase2 复制，灰度中不变 |

### 5.5 字段写入时机

manifest 字段的写入分三类，可靠性来源不同：

- **客观字段**（命令 exit code、文件检测、统计）→ Harness 全权写，Agent 不能请求改（防美化）
- **语义字段**（阈值、回滚预案内容）→ Agent 请求 → Harness 校验格式后写
- **判定字段**（review_passed、goal_measurable）→ 由对应角色写（Judge、Critic），不是执行 Agent 自己标

### 5.6 本章小结

manifest 结构化传递协议使阶段边界的合法性可被机器判定。它的核心价值是把"软产物"和"硬凭证"分离——spec.md 有内容但 manifest 没更新，Harness 不认。这让 Agent 无法靠"写了一堆自然语言"冒充完成，必须把结构化字段填到位才算通过。

---

## 第六章 操作层：工具权限与流程编排

### 6.1 危险等级分级

工具按危险程度分四级：

| 等级 | 包含 | 控制方式 |
|------|------|---------|
| L0 无害 | 读文件、搜索、代码调研、拉监控 | Agent 可随时调 |
| L1 可逆 | 写文件（按路径）、跑测试、创建发布包、触发 CI/CD | Agent 可调，有 audit 日志 |
| L2 不可逆 | kubectl apply、aws deploy、生产凭据 | **Harness 直接禁**（Agent 看不到接口） |
| L3 需人确认 | 灰度 25%+ 推进 | confirm token 触发 |

### 6.2 阶段×工具权限矩阵

[待画图：阶段×工具权限矩阵表]

权限按"阶段 + 角色"组合，阶段切换时 Harness 自动收回上一阶段权限。写权限可按路径细化——设计阶段只能写 `docs/design-docs/**`，编码阶段只能写 `src/**` 和 `tests/**`。

三条铁律：
1. 低风险阶段权限不带到高风险（切换时收回）
2. L2 在 Harness 层直接禁（Agent 根本看不到工具接口，不是"提示不许用"）
3. L3 只能通过 confirm token 触发

### 6.3 spec 快照锁定

**机制**：编码阶段开始时，Harness 记录当前 spec 的 Git SHA（如 spec.v3）并锁定。后续编码全部基于此版本。spec 升版本必须 commit，否则 SHA 锁不住。

**"状态脏"问题**：spec 从 v3 升到 v4 时，工作区已有基于 v3 写的代码。如果 Harness 只是把新 spec 喂给 Agent，Agent 会误以为现有代码是基于 v4 写的，产生认知偏差——可能漏改。

**解法**：minor/major 分级刷新。

### 6.4 minor/major 版本演化

```
spec 要改 ──▶ 标 change_type ──┬── minor ──▶ 原地刷新（不清空上下文，增量注入 diff）
                                └── major ──▶ 回退设计（清空上下文，重建 tasks，全部代码标 needs_revalidation）
```

**minor 刷新**：spec_refs 不重建（章节归属没变），tasks 增量更新（受影响 task 标 Superseded + 新增），needs_revalidation 增量标记，diff 按 spec_refs 精准 Push（不整份）。Agent 不清空上下文，带着现有代码理解继续改。

**major 刷新**：manifest 归档 archives/，清空上下文重注入 spec.v4，tasks.md 覆盖重建，全部已有代码标 needs_revalidation，回退到设计阶段。

**minor→major 动态升级**：minor 刷新中 review 发现改动比想象大时，自动升级为 major。触发条件：finding 涉及需求章/方案概览、needs_revalidation 占比超阈值、连续 2 轮同类失败。

### 6.5 spec 章节→代码文件映射

**软映射 + 硬覆盖**机制：
- 设计阶段：tasks.md 的 estimated_files 给大概范围（glob 模式）
- 编码阶段：Harness 用静态分析扩展依赖链，生成 needs_revalidation 清单
- 运行时：Agent 发现清单外文件要改 → 追加 → 触发 review 扩展

**新功能的特殊处理**：estimated_files 对新功能是"将要创建的路径"，文件不存在，依赖分析失效。Harness 按文件存在性分流——已存在的进 needs_revalidation（要重验），不存在的进 to_create（新建无需重验）。

### 6.6 本章小结

工具权限矩阵把"Agent 能做什么"从 Prompt 提醒升级为 Harness 硬拦——L2 工具 Agent 根本看不到接口。spec 快照锁定解决版本一致性问题，minor/major 分级刷新处理编码中 spec 演化的任务一致性。两者共同使 Harness 层真正"硬"起来。

---

## 第七章 循环层：硬关卡与回退机制

### 7.1 Loop 基本单元

所有 Loop 的最小单元是同一个形状，Context 层和 Loop 层在这里咬合：

```
[Context Push] → [Agent 执行/等待] → [客观验证] → 失败? → [回退/升级/终止]
     ↑对抗记忆易失          ↑对抗概率性
```

Context 层（Push）做前半段——对抗工作记忆易失（公理2）；Loop 层（客观验证）做后半段——对抗概率性输出（公理2）。两层不是分离的，是在一个 step 的不同相位起作用。

### 7.2 五种 Loop 形态

[待画图：五种 Loop 形态对比表]

| 形态 | 触发 | 验证 | 失败处理 | 终止 |
|------|------|------|---------|------|
| A 前进Task | 上一task完成 | lint+编译+单测+review | finding→修复→re-review；3轮熔断 | 所有task完成 |
| B minor刷新 | spec标minor | 受影响代码review覆盖 | 升级为major | review PASS |
| C major刷新 | spec标major | 设计阶段出口关卡 | 设计失败→设计内Loop | 设计完成+重新进编码 |
| D needs_revalidation | major刷新后 | review覆盖率（清单全审） | 漏审→补审 | 清单全reviewed |
| E 灰度轮询 | 灰度批次发布 | 监控指标在阈值内持续N分钟 | 触发回滚→回阶段3 | 全量+监控稳定 |

**灰度 Loop 是异类**——前四种是"Agent 执行→机器判"，E 是"Agent 编排→等外部世界→判外部数据"。Agent 在 E 中是"观察者+异常响应者"，不是执行者。Loop 单元是"等+拉+判"，不是"做+验"。这是唯一一个 Agent 不产出代码/文档的 Loop。

### 7.3 Loop 间的嵌套/中断/升级

Loop 层本质是**状态机**，不是 while 循环：

- **嵌套**（B 嵌入 A）：minor 刷新不中断 Task Loop，状态机保留 A 的现场（当前 task、已改文件、已执行步骤）
- **中断**（C 中断 A）：major 刷新中断 Task Loop，A 的现场归档不丢弃，C 完成后恢复
- **升级**（B→C）：minor 刷新中 review 发现改动比想象大，转入 major 流程

三种关系使 Loop 能可靠切换——中断不丢现场，升级有明确触发条件，嵌套保留进度。

### 7.4 状态机现场保存（loop_state）

存 manifest 的 phase3.loop_state 字段（不独立文件，保证原子性 + 随版本归档 + 回滚锚点天然成立）。

两层结构：
- **定位层**：current_phase / current_task_id / current_loop_type（A/B/C/D/E/Graph）——Harness 自动改
- **进度快照层**：files_modified / completed_steps / review_round / pending_findings —— 机器可验证字段 Harness 从客观源拉取，语义步骤 Agent 上报

**边界**：loop_state 只存"执行进度"，不存"执行结果"。结果在 manifest 的 status 字段。review PASS 后 pending_findings 必须清空，判定转到 manifest.status。

### 7.5 多 Agent 调度

编码 review 的多 Agent 是"并行+汇聚"形态：
- 同时启动（真并行）
- reviewer 间互不知道其他 reviewer（并行纯净，handoff 汇聚后才传）
- 超时按 reviewer 类型配置（不统一 5 分钟）
- 失败重试 1 次 → 标"该维度未审"，其他人继续
- 全部收齐后汇聚到 Judge

### 7.6 handoff 机制

reviewer 发现非自己维度的线索时，用结构化 handoff 传递：

```json
{"from":"performance-reviewer","to":"robustness-reviewer",
 "file":"auth/login.go","line":42,"signal":"空指针解引用风险",
 "severity":"P1","evidence":"validateToken()前未检查user==nil","status":"pending"}
```

**传递时机**：第一轮并行纯净 → 汇聚后 Harness 提取 handoff 按 to 字段分发 → 下一轮各 reviewer 带 handoff 补审。

**约束**：handoff 是"提醒"不是"命令"，不触发硬拦截。涉及 needs_revalidation 清单的必须回应（计入已审数），不涉及的是软提醒。

### 7.7 本章小结

Loop 层把硬关卡串成可执行循环引擎。五种形态覆盖了前进、刷新、重验、灰度四种场景。状态机现场保存使 Loop 能可靠中断/恢复。多 Agent 调度和 handoff 使并行审查既保持隔离又传递交叉线索。

---

## 第八章 上下文层：Push/Pull 分界

### 8.1 Push vs Pull 分界

LLM 输出由上下文决定（公理2），但工作记忆有限。核心矛盾：**喂漏了 Agent 不知道该知道的，输出错；喂多了信噪比下降，输出也错**。

解法是把上下文分两类，注入方式不同：

| 注入方式 | 谁做 | 内容 | 硬度 |
|---------|------|------|------|
| Push | harness 强制注入 | 必须看到的（漏了就出错） | 硬 |
| Pull | agent 用工具拉 | 展开了更好 | 软 |

**Push 集**：身份/纪律、冻结基线、任务规格、上一步反馈（只留最新）
**Pull 集**：代码现状深挖、规范细节、历史决策深挖

关键洞察：**Push 是"Agent 不知道自己该知道"的**——它不会主动想到"这些代码标了 needs_revalidation 我得重新审"，不会主动想到"spec 是 v3 不是 v4 我得确认版本"。这些必须 harness 硬注入。Pull 是"Agent 知道自己需要更多"的——让它自己拉。

### 8.2 阶段上下文矩阵

[待画图：5 阶段 × 7 类上下文矩阵]

每阶段每类上下文标 Push/Pull。关键观察：
- 编码阶段的"任务规格"是 Push 冻结 spec 的**相关章节**（不是全文，按 spec_refs 定位）
- 设计阶段的"规范"是 Pull（讨论到 4.1 才加载 bp-architecture-design）
- 历史决策全是 Pull（"相关条目"需语义匹配，harness 不知道哪条相关）

### 8.3 保鲜机制

长会话中注入的上下文会随对话膨胀被稀释 `[待引用：Lost in the Middle]`。三个机制对抗：
1. 每个 task 开始时重 push 冻结基线 + 任务规格
2. 反馈类只留最新（不累积）
3. Pull 工具调用 idempotent（Agent 可反复读同一文件）

### 8.4 失败模式检索

failure-patterns 存储"过去踩过的坑"。传统做法是 Agent 用关键词搜索——这是软的（Agent 可能漏掉关键记录）。

本设计把 failure-patterns 从 Pull 升级为 **Push**——Agent 不知道自己该搜什么（上下文决定性），Harness 按当前 Loop 形态生成标签组合搜好 Push 给 Agent：
- 编码阶段：module + phase（预防性检索，拉"这模块过往踩的坑"）
- 排查阶段：error_type（诊断性检索，拉"这类错误的过往案例"）

每条记录有结构化标签（module/error_type/severity/phase）+ 自然语言内容（symptom/root_cause/fix）。索引结构化、内容可自然语言——和 manifest 的原则一致。

### 8.5 codebase-researcher 调用形态

| 维度 | 形态 |
|------|------|
| 调用时机 | 阶段开始 Harness 预调用（广而浅）+ Agent 按需（窄而深） |
| 检索范围 | 按 estimated_files 或 spec_refs 约束 |
| 输出格式 | 结构化：文件列表 + 摘要（不灌全文） |
| 超时 | 30 秒 → 部分结果 + "可能不完整"标记 |
| 缓存 | 同 task 内同查询缓存；spec 版本变更时失效 |
| 持久化 | 结果写入 loop_state（中断恢复不重搜） |

### 8.6 本章小结

Context 层的 Push/Pull 分界把"必须看到的"从 Agent 自觉升级为 Harness 强制注入。保鲜机制对抗上下文腐化。failure-patterns 从 Pull 升级为 Push，解决了"Agent 不知道自己该搜什么"的本质局限。

---

## 第九章 协作层：多 Agent 制衡

### 9.1 Graph 层的使用取舍

本设计只在两个点使用多 Agent 制衡，不在所有阶段用：

| 位置 | 机制 | 理由 |
|------|------|------|
| 阶段1 目标可衡量性 | Critic 审目标 | 目标不可量化则下游全无意义，是基础 |
| 阶段3 编码 review | 5 reviewer + critic + Judge | 编码暴露设计缺陷，必须确保正确实现设计 |

**为什么不在所有阶段用**：spec 完备性、设计合理性、权衡记录追求完美是过度工程，靠回退通道兜底。多 Agent 成本（Token/延迟/复杂度）高，只在最值钱的两处用。

### 9.2 编码 review 三级分级拦截

[待画图：三级分级拦截流程图]

| finding 来源 | 例子 | 拦截方式 |
|-------------|------|---------|
| 机器 P0 | lint 安全规则失败/测试失败/编译失败 | Harness 硬拦，不可覆盖 |
| Agent P0 | reviewer 判的逻辑死锁/数据丢失风险 | Harness 拦（reviewer 标 P0 就停），人可显式覆盖（留痕） |
| P1/P2 | 代码风格/可读性/性能建议 | 记录不阻断 |

关键区分：**机器 P0 真硬（不可覆盖），Agent P0 半硬（人可覆盖）**。因为 Agent P0 的标签是 reviewer 给的，reviewer 可能误判或漏判——"有 P0 就拦"是硬规则，但"P0 标得对不对"依赖 reviewer 质量。

### 9.3 三权分立

借鉴司法三权分立：

```
              Judge（主 Agent = 法官）
             ╱           │           ╲
       5 个 reviewer   review-critic
      （检察官，各维     （辩护律师，
       度提 finding）     对 finding 找反证）
```

- **Judge**：编排流程、去重分诊、独立调研后裁决、输出报告。自己不产 finding。
- **5 个 reviewer**（始终调用）：performance / robustness / standards / contract-trust / spec-compliance，各管一摊
- **review-critic**（有 finding 时调用）：对抗性验证，给四结论（成立/驳回/降级/未驳倒）

**为什么精妙**：它对冲了"模型对自己人不否决"的偏置——reviewer 倾向提问题，critic 倾向驳回，Judge 必须独立调研后裁决（不能简单采信任一方）。三方制衡，降低误报和漏报。

### 9.4 多 Agent Context 路由

| 层 | 内容 | 谁看 |
|----|------|------|
| 共享层（Push 给所有 reviewer） | spec 相关章 + tasks 当前项 + diff + 适用规范列表 | 全部 reviewer |
| 维度子集层（按维度 Push） | performance:热路径+性能规范；robustness:错误处理+资源规范；... | 各自 |

两种极端都错：全部共享 → Token 爆炸+维度混淆；全部隔离 → 丢失交叉线索。共享层+维度子集+handoff 是平衡——隔离保证专注，handoff 传递交叉线索。

### 9.5 目标可衡量性 Critic

目标可衡量性也分两层：
- **机器层**：目标句含可验证谓词（数字阈值/状态条件/行为断言）——"P99<200ms"✅ "性能要好"❌。Harness 能扫。
- **Critic 层**：谓词是否真可测——"P99<200ms 在 1000 QPS 下"✅。Critic 语义判。

Critic 驳回也需人可覆盖——和编码 Agent P0 一样的"硬拦+人覆盖留痕"模式。

### 9.6 本章小结

Graph 层用三权分立对冲模型偏置，用三级分级实现差异化拦截。多 Agent Context 路由在隔离与交叉之间平衡。只在两个关键点使用，避免过度工程。

---

## 第十章 接口层：Prompt 与交互协议

### 10.1 Prompt 三子层

| 子层 | 内容 | 谁写 | 何时注入 |
|------|------|------|---------|
| L1 系统身份 | "你是执行者/协作者/...。职责是...权限边界是..." | 固定模板，Harness 按阶段加载 | 阶段开始 Push（替换不追加） |
| L2 当前任务说明 | "Task T-3，spec v3，关注章节 4.2/5.1..." | Harness 从 manifest 自动生成 | 每 task 开始 Push |
| L3 交互协议 | 输出格式 schema + 工具调用格式 | 固定模板 | 常驻（< 500 token） |

L1/L3 固定、L2 动态。L2 就是 Context 层 Push 的"任务规格"部分——Prompt 层和 Context 层在这里咬合。

**关键区分**：L1 的权限边界说明是**软告知**（Agent 知道自己能做什么），真正的硬拦在 Harness 层（L2 工具权限拦截）。L1 是"礼貌告知"，Harness 是"门锁"——不能以为写了权限说明就安全了。

### 10.2 L3 交互协议

Agent 每次输出必须是以下三种结构化 JSON 之一：

**子协议 1：工具调用**
```json
{"type":"tool_call","tool":"edit_file","args":{"path":"auth/login.go","content":"..."}}
```

**子协议 2：step 产出**（同时是轨迹日志一条记录）
```json
{"type":"step_output","action":"edit_file","input":{"path":"auth/login.go"},
 "output":{"status":"success"},"duration":30,
 "manifest_update_request":{"phase3.needs_revalidation":["auth/login.go"]}}
```

**子协议 3：完成声明**
```json
{"type":"task_complete","id":"T-3","evidence":{"compile_passed":true,"review_passed":true}}
```

Agent 不直接写 manifest，只能通过 manifest_update_request "请求"——Harness 交叉验证后写（如 needs_revalidation 用 git diff 比对验证 Agent 真改了这些文件）。这防止 Agent 美化自己的产出。

### 10.3 confirm token 机制

两类确认：
- **阶段出口确认**（阶段1/2/5）：超时默认不推进
- **覆盖确认**（Agent P0 被人覆盖）：超时默认不覆盖（P0 仍拦，比"不推进"更保守）

**优先级**（串行依赖，不是平行冲突）：覆盖确认 → 解决 → task 真正完成 → 阶段出口确认。单挂起队列（同一时间最多 1 个），避免人认知过载。

**确认请求结构化**：含阶段、摘要、确认/拒绝后果。摘要由 Harness 从 manifest 生成，不让 Agent 自己写。

### 10.4 本章小结

Prompt 层把"一段巨大的 Prompt"拆成三子层，L2 动态部分由 Harness 从 manifest 生成。L3 协议使 Agent 产出可被 Harness 解析，manifest_update_request 机制使 Agent 不能直接写 manifest（防美化）。confirm token 机制使人机交互点可机器判定。

---

## 第十一章 闭环机制与边界处理

### 11.1 三个闭环

**闭环 1：反馈闭环**
```
轨迹日志 ──被纠正──▶ self-refinement ──提取标签──▶ failure-patterns
                                                      │
                   Harness 按标签搜好 Push ◀──────────┘
                          │
                   Agent 编码时收到相关坑提醒
```
轨迹日志是 self-refinement 的输入，self-refinement 沉淀到 failure-patterns，failure-patterns 被 Harness Push 回 Agent。三个机制是一个闭环。

**闭环 2：action 三用**
工具权限清单 = 轨迹日志 action 类型 = 工具调用枚举。一份清单的三种用途，不能是三套独立清单。

**闭环 3：边界情况→failure-patterns**
新边界情况通过 self-refinement 沉淀到 failure-patterns（用 edge_case 标签），下次同类情况 Harness 能 Push 提醒。这让边界处理从"一次性应对"变成"积累式增强"。

### 11.2 标签提取机制

self-refinement 触发时，Harness 从轨迹日志自动提取标签：

| 标签 | 提取规则 |
|------|---------|
| module | 从 edit_file 的 input.path 推断（取一级目录） |
| error_type | 从 run_test 失败的 output 解析关键词 |
| severity | 从 review_findings 的 severity 继承 |
| phase | 从 loop_state.current_phase 取 |

Agent 只补 symptom/root_cause/fix（自然语言内容）。

### 11.3 边界情况处理

| 类型 | 例子 | 处理 |
|------|------|------|
| 能力不足 | 3轮review失败 | 熔断上报人 |
| 超时 | codebase-researcher 30秒 | 部分结果+不完整标记 |
| 死循环 | 连续5次 manifest 状态 false | 标 blocked 上报人 |
| 外部依赖失效 | 模型 API 错误 | 重试3次→暂停阶段上报 |
| 人 confirm 超时 | 24h没回应 | 默认拒绝 |
| manifest 不一致 | manifest说PASS但loop_state挂finding | 以manifest为准 |
| 多reviewer分歧 | 性能P0 vs 合规P2 | Judge裁决→无法裁决上报 |

### 11.4 fail-safe 原则

三条原则：
1. 能不丢数据就不丢（已有状态必须归档）
2. 能不自动决策就不自动决策（不确定时上报人，不自己拍板）
3. 能回退就回退（比推进更安全）

### 11.5 本章小结

三个闭环使系统具备自增强能力——错误经验能沉淀为持久化知识，下次自动提醒。边界情况的 fail-safe 原则保证系统在异常时不崩溃、不丢数据、不擅自决策。

---

## 第十二章 总结与展望

### 12.1 工作总结

本文从 Prompt 级软约束的失效路径出发，建立软硬约束判据，设计了一个五层架构（Prompt/Context/Harness/Loop/Graph），将可硬化的约束从 Prompt 下沉到机制层。核心工作包括：
- manifest 结构化传递协议
- spec 快照锁定与 minor/major 分级刷新
- 五种 Loop 形态及嵌套/中断/升级关系
- 多 Agent 三权分立与三级分级拦截
- 灰度三档分级安全上线

### 12.2 主要贡献

本文的核心理论贡献是**软硬约束判据**——"能映射到 manifest 字段或 exit code 的约束可硬化"。这一判据把模糊的"可机器判定"精确化为可操作标准，为区分"能硬"与"只能软"提供了工程依据。

### 12.3 局限性

1. **尚未实现验证**：本设计是架构设计，未经原型实现和实际工程验证。约束的实际可靠性需实现后测量。
2. **实现期决策未定**：confirm 载体、多 Agent 调度底层、codebase-researcher 实现等属实现期决策，可能影响实际效果。
3. **多 Agent 成本**：三权分立审查的 Token/延迟成本较高，对小型项目可能不经济。
4. **边界情况无法穷举**：§11.3 列出的是已知类型，实际运行中可能浮现未预见的异常。

### 12.4 未来工作

1. **原型实现**：按 Harness → Loop → Context → Graph → Prompt → 闭环的顺序实现最小原型，跑 case study 验证
2. **约束可靠性测量**：实现后量化"硬关卡的拦截率""Agent 违反软约束的概率"，验证判据有效性
3. **多 Agent 成本优化**：探索按需启动 reviewer（不全跑 5 个）以降低成本
4. **failure-patterns 检索升级**：当前用结构化标签匹配，未来可探索语义检索增强
5. **跨 feature 协作**：当前设计聚焦单 feature 全流程，多 feature 并行时的 manifest 冲突处理待研究

---

## 附录 A：硬关卡→manifest 字段映射

[待画图：完整映射表，见 engineering-agent-design.md §附录A]

## 附录 B：action 类型清单

[见 engineering-agent-design.md §6.4]

## 附录 C：配置项清单

[见 engineering-agent-design.md §15]

---

## 写作说明

1. **篇幅**：本大纲+主体约 1.2 万字，本科论文通常 1.5-3 万字，可在以下位置展开：
   - 第三章公理推导可展开更多论证
   - 第五~十章每章可补"示例场景"（用具体 case 跑一遍机制）
   - 第二章相关工作可补更多文献

2. **图表**：标注 `[待画图]` 处需补论文插图，建议：
   - 五层架构总图
   - SDLC 主流程图
   - manifest schema 结构图
   - 工具权限矩阵
   - minor/major 决策树
   - 五种 Loop 形态对比
   - 三权分立流程图
   - 三个闭环图

3. **文献**：标注 `[待引用]` 处需补具体文献，关键方向：
   - LLM 本质特征（Lost in the Middle、上下文工程）
   - AI 辅助编码工具（Copilot 生产力研究、Claude Code/Codex 文档）
   - Agentic Engineering（Osmani 博客、agentic-engineering-framework）
   - 软件工程流程治理（CI/CD、质量门禁、HITL）

4. **评估部分**：暂略，建议原型实现后补"设计评估"章节（对比分析 + 约束覆盖率 + case study）
