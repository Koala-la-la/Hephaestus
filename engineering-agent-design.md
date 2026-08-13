# 专业型工程 Agent 设计文档

> 本文档定义一个"工程规范约束型"AI Agent 的完整架构——区别于通用编码 agent（Codex/Claude Code），本 agent 把工程纪律刻进 Harness/Loop/Context/Graph 四层机制，而非仅靠 Prompt 软约束。文档自包含，可直接作为实现依据。
>
> 起源：从 davidYichengWei/agentic-engineering-framework（Skill/Prompt 级软约束框架）演化而来，核心增量是把"可硬化的约束"从 Prompt 下沉到机制层。

---

## 0. 文档定位

| 项 | 说明 |
|----|------|
| 目标读者 | 实现该 agent 的工程师 / 接手设计的下一个 agent |
| 自包含性 | 不依赖任何对话历史，所有决策、图、表都在本文档内 |
| 性质 | 架构设计文档，非实现代码；实现期决策（§17）标注为"工程实现时定" |
| 状态 | 骨架定稿，5 个真缺口已补（§A1-A5），无架构级裂缝 |

---

## 1. 背景与问题

### 1.1 原版框架的局限

原版 agentic-engineering-framework 把工程纪律编码为 Skill/Markdown 文件——本质是 **Prompt 级软约束**。LLM 可以"违反"任何 prompt 指令，这是概率模型的本质。原版作者自己也承认约束可靠性光谱：`prompt 约束(低) → SKILL(中) → hook(高)`。

### 1.2 本设计的核心命题

**把"可硬化的约束"从 Prompt 下沉到 Harness/Loop 机制，"不可硬化的"用 Context + 多 agent 制衡最大化概率。**

关键判据——一条约束能否硬化，取决于"它校验的对象能否写进 manifest 字段或命令 exit code"：
- 能映射到 manifest 字段或命令 exit code → **能硬**（harness 拦得住）
- 需要解析自然语言（"spec 质量够不够""设计是否合理"）→ **不能硬**（靠 Critic/多 agent/人）

一句话：**你不能用 hook 校验"设计是否合理"，只能校验"测试是否通过"。**

---

## 2. 设计哲学

### 2.1 三条公理（不可争辩的基本事实）

| 公理 | 大白话 | 直白后果 |
|------|--------|----------|
| 信息损耗 | 意图从想法→需求→设计→代码，每步都会走样 | 越早走样越往后代价越大 |
| LLM 本质 | 输出由上下文决定；输出是概率的；记忆会丢 | 上下文质量决定上限；不能信任"一次性对"；关键信息必须写下来 |
| 人类认知稀缺 | 工程师注意力/判断力有限，是系统瓶颈 | 不能让 AI 狂生成让人狂审 |

### 2.2 六条实践（从公理推导，本设计落地依据）

1. **Context Engineering** — 喂高信噪比结构化上下文，不灌全量
2. **人机分工** — 可机器判的全自动，不可判的人裁决
3. **AI 全链条参与** — 从需求到上线，角色递进（引导者→协作者→执行者→编排者）
4. **小任务推进 + 多层次验证** — 拆小步，每步客观验证
5. **Knowledge as Code** — 团队知识编码进仓库，版本化
6. **Error-Driven Refinement** — 被纠正的错误外化为持久化规则

### 2.3 软硬边界判据（贯穿全设计）

| 边界类型 | 硬 | 软 |
|---------|----|----|
| SDLC 阶段 | 边界（入口前置/出口验收） | 阶段内部创造 |
| 约束校验对象 | manifest 字段/命令 exit code | 自然语言解析 |
| Context 注入 | Push（harness 强制） | Pull（agent 按需） |
| Loop 验证 | 机器判（lint/test/manifest） | 多 agent/人判 |

---

## 3. 五层架构总览

```
┌─────────────────────────────────────────────────┐
│  Prompt 层   系统提示定义"角色和纪律"           │ 软（基线，概率影响）
├─────────────────────────────────────────────────┤
│  Context 层  分阶段喂不同上下文                 │ 半硬（从输入侧限形状）
├─────────────────────────────────────────────────┤
│  Harness 层  工具集 + 权限分级 + 流程编排        │ 硬（没权限就是没权限）
├─────────────────────────────────────────────────┤
│  Loop 层     每 step 确定性验证器 + 失败回退 + 熔断│ 硬（客观判定）
├─────────────────────────────────────────────────┤
│  Graph 层    多 agent 制衡（reviewer/critic/judge）│ 半硬（多 prompt 博弈降概率）
└─────────────────────────────────────────────────┘
```

**重心在 Harness + Loop 层**——这两层是唯一能"真硬"且"工程化"的。其他层配合。

---

## 4. SDLC 五阶段详述

### 4.1 端到端主流程

```
阶段1 需求 → 阶段2 设计 → 阶段3 编码 → 阶段4 测试 → 阶段5 上线
(引导者)    (协作者)     (执行者)     (测试者)    (编排者)
```

每个阶段定义四要素：入口前置（硬）/ 阶段内自主权（软）/ 出口验收（硬关卡+软关卡）/ 回退条件。

### 4.2 阶段 1：需求澄清

| 项 | 内容 |
|----|------|
| 角色 | 引导者（苏格拉底式提问） |
| 产物 | `spec.md` 前3章（背景/目标/需求）+ `spec.meta.json`(common+phase1) |
| 入口前置 | 用户意图存在（无上一阶段产物） |
| Context Push | spec 模板 + 用户意图 + 非功能 checklist + failure-patterns（按标签） |
| Context Pull | codebase-researcher（预调用广而浅）+ ADR |
| 出口硬关卡 | spec 存在 / 前3章非空 / 目标可衡量（机器扫谓词+Critic精判） |
| 出口软关卡 | 非功能 checklist 完备性 / 人 confirm |
| Graph | Critic 审目标可衡量（机器粗筛+Critic精判+人可覆盖） |
| 回退 | 无前一阶段；后续阶段发现需求错会 major 刷新回到此 |

**目标可衡量性判定（分层）**：

| 层 | 判定 | 硬度 |
|----|------|------|
| 机器层 | 目标句含可验证谓词（数字阈值/状态条件/行为断言）— "P99<200ms"✅ "性能要好"❌ | 硬 |
| Critic 层 | 谓词是否真可测 — "P99<200ms 在 1000 QPS 下"✅ | 半硬 |

### 4.3 阶段 2：系统设计

| 项 | 内容 |
|----|------|
| 角色 | 协作者（用户主导设计决策） |
| 产物 | `spec.md` 设计章 + `tasks.md` + `spec.meta.json`(+phase2) |
| 入口前置 | spec 前3章完整（阶段1出口） |
| Context Push | spec 前3章 + 设计章模板 |
| Context Pull | 按 section 加载 bp-* + codebase-researcher + ADR |
| 出口硬关卡 | 设计章非空或 N/A（校验 meta 字段）/ spec_refs 存在+范围+反向覆盖校验 |
| 出口软关卡 | 权衡记录 / 人 confirm |
| 回退 | 编码中发现 spec 设计错 → major 刷新回退到此 |

**tasks.md 结构**（设计阶段产出，含结构化字段）：
```json
{
  "tasks": [
    {
      "id": "T-3",
      "spec_refs": ["4.2", "5.1"],
      "estimated_files": ["auth/*", "session/*"],
      "estimated_loc": 30,
      "status": "pending",
      "depends_on": ["T-1"]
    }
  ]
}
```

**spec_refs 校验**（不全靠设计 agent 自觉）：

| 校验层 | 检查 | 硬度 |
|--------|------|------|
| 存在性 | spec_refs 引用章节在 meta 里 status=filled | 硬 |
| 范围 | 编码 task 的 spec_refs 应在设计章(4.x-7.x)，标 1.x 可能错 | 硬 |
| 反向覆盖 | 设计章应至少被一个 task 引用；异常分布告警 | 半硬 |
| 人 confirm | 随阶段2出口 confirm 兜底 | 硬 |

**任务粒度**（双阶段度量 + 动态拆分）：

| 阶段 | 度量 | 阈值 |
|------|------|------|
| 设计（预估） | estimated_loc + estimated_files 数 | ≤ task_max_loc(默认50) / ≤ task_max_files(默认5) |
| 编码后（精确） | actual_loc(git diff) + complexity(gocyclo/lizard) | ≤ task_max_loc / ≤ task_max_complexity(默认15) |

编码后 actual_loc 超阈值 → 动态拆分（原 task 标 Superseded，新建两个子 task，spec_refs 继承）。

### 4.4 阶段 3：编码

| 项 | 内容 |
|----|------|
| 角色 | 执行者 |
| 产物 | 代码 + `tasks.meta.json`(+phase3) + `gate_baseline.json` + 执行轨迹日志 |
| 入口前置 | spec 完整 + 冻结 SHA + tasks.md 已存在（设计阶段产出） |
| Context Push | 冻结 spec.v? 相关章（按 spec_refs 精准定位）+ tasks 当前项 + 反馈(只留最新) + 冻结基线 + needs_revalidation 清单 + 预拉一跳 caller/callee + failure-patterns |
| Context Pull | 被改文件深挖 + bp-coding 必加载 + std 按语言 + 轨迹日志 + codebase-researcher 按需(窄深) |
| Loop | A 前进Task / B minor刷新 / C major刷新 / D needs_revalidation review |
| 出口硬关卡 | tasks 全 Done / lint 0 新增 / 编译过 / 现有测试无 regression / 新增单测过 / review PASS / 轨迹日志全 / needs_revalidation 全 reviewed |
| Graph | 编码 review 三级分级 + 多 agent（共享层+维度子集+handoff） |

### 4.5 阶段 4：测试

| 项 | 内容 |
|----|------|
| 角色 | 测试者 |
| 产物 | 测试代码 + `test_report.json`(+phase4) |
| 入口前置 | 编码出口全通过 + spec 第7章测试计划存在 + 可追溯映射 |
| Context Push | spec 第7章测试计划 + 可追溯映射 + 被测代码清单 |
| Context Pull | boundary-checklist + 测试基础设施 + failure-patterns(边界教训) |
| 出口硬关卡 | 测试全 PASS / 覆盖率达标（项目级配置+框架默认+不配置报错）/ 三类覆盖(机器数+软判边界) |

**编码 vs 测试的责任划分**：
- 编码出口：新增/修改代码的单测过 + 现有测试无 regression
- 测试阶段：集成测试 / E2E / 性能 / 安全扫描等更全面验证

### 4.6 阶段 5：上线

| 项 | 内容 |
|----|------|
| 角色 | 编排者（不持生产写权限） |
| 产物 | 发布包 + `release.manifest.json`(+phase5) |
| 入口前置 | 测试出口全通过 |
| Context Push | spec 回滚预案 + 发布说明模板 + 监控数据(灰度时,最新) + monitoring_thresholds(快照) |
| Context Pull | bp-release-engineering + 过往发布事故 + 回滚案例 |
| Loop | E 灰度轮询（harness 定时唤醒，非 agent 执行） |
| 出口硬关卡 | 包可重复构建(SHA) / 回滚预案存在 / 灰度策略 / 监控阈值(manifest 字段) / 灰度反馈无异常(外部判) / 人 confirm(25%+) |

**灰度三档**：

| 阶段 | 放量 | 谁判 | 等待 | 理由 |
|------|------|------|------|------|
| 探针 | 0→5% | Agent 自判 | 5min | 探针，出问题影响面极小 |
| 验证 | 5→25% | Agent 自判 | 30min | 代表性流量，风险可控 |
| 确认 | 25→50→100% | 人 confirm | 50%等2h,100%等4h | 大规模放量，误判=事故 |

**回滚分级**：
- 自判阶段（5%/25%）：agent 发现超阈值 → 自动发起回滚请求 → CI/CD 执行
- 人 confirm 阶段（50%/100%）：人发现异常 → 人点回滚 → CI/CD 执行；agent 只拉监控供人看

---

## 5. manifest schema 完整定义

manifest 是 Harness 的唯一操作对象——Harness 只读 manifest，不解析自然语言产物。每阶段产出双载体：自然语言产物（给人/agent 推理）+ 结构化 manifest（给 harness）。

### 5.1 六片累计递进

```
manifest/
├── common.json      # 全阶段共享
├── phase1.json       # 需求
├── phase2.json       # 设计
├── phase3.json       # 编码
├── phase4.json       # 测试
├── phase5.json       # 上线
└── archives/         # major 刷新时归档
    └── manifest.v3.json
```

### 5.2 字段清单

#### common（全阶段共享）
| 字段 | 类型 | writer | write_trigger |
|------|------|--------|---------------|
| spec_sha | string | Harness | spec commit 时 |
| spec_version | string(v3/v4) | Harness | spec 升版本时 |
| change_type | "minor"\|"major"\|null | Agent请求→Harness校验 | agent 标 minor/major 时 |

#### phase1（需求）
| 字段 | 类型 | writer | write_trigger |
|------|------|--------|---------------|
| sections_status | {"1":"filled","2":"filled","3":"filled"} | Harness | spec 章节写入后检测 |
| goal_measurable | boolean | Critic | Critic 判定后 |
| goal_measurable_evidence | string | Critic | 同上 |
| nonfunctional_checked | boolean | Harness | checklist 逐项回应后 |

#### phase2（设计）
| 字段 | 类型 | writer | write_trigger |
|------|------|--------|---------------|
| sections_status | {"4":"filled\|na",...} | Harness | spec 设计章写入后 |
| tradeoff_count | number | Harness | 统计权衡记录数 |
| monitoring_thresholds | {指标: {metric,op,value,unit}} | Agent请求→Harness校验 | agent 填阈值时 |
| rollback_plan_exists | boolean | Harness | 检测 spec 回滚预案章节 |
| tasks[] | [{id,spec_refs,estimated_files,estimated_loc,status,depends_on}] | Agent | agent 拆 task 时 |
| reverse_coverage | {章节: [task_id]} | Harness(反推) | tasks 写入后 |

#### phase3（编码）
| 字段 | 类型 | writer | write_trigger |
|------|------|--------|---------------|
| task_status_all_done | boolean | Harness | 扫 tasks status |
| lint_baseline_delta | number | Harness | lint 跑完 |
| compile_passed | boolean | Harness | 编译跑完 |
| test_regression_passed | boolean | Harness | 现有测试跑完 |
| new_test_passed | boolean | Harness | 新单测跑完 |
| review_passed | boolean | Harness | Judge 裁决后 |
| review_findings[] | [{severity,source:machine\|agent,file,line,fixed}] | Harness | reviewer 返回后 |
| needs_revalidation[] | [file_path] | Harness | spec 变更/文件存在性分流后 |
| needs_revalidation_reviewed[] | [file_path] | Harness | review 覆盖清单后 |
| to_create[] | [file_path] | Harness | 新功能 task 的待创建文件 |
| created[] | [file_path] | Harness | agent 创建文件后 |
| all_traces_exist | boolean | Harness | 检测轨迹日志文件 |
| loop_state | {定位层,进度快照} | Harness(定位层)+Agent(进度请求)→Harness校验 | 状态切换/step完成 |

#### phase4（测试）
| 字段 | 类型 | writer | write_trigger |
|------|------|--------|---------------|
| all_tests_passed | boolean | Harness | 测试跑完 |
| line_coverage | number | Harness | 覆盖率报告生成 |
| branch_coverage | number | Harness | 同上 |
| coverage_met | boolean | Harness | 比对阈值后 |
| three_category_coverage | {happy_path,boundary,exception} | Harness | 扫测试用例标签 |
| test_report_structured | boolean | Harness | 检测报告格式 |

#### phase5（上线）
| 字段 | 类型 | writer | write_trigger |
|------|------|--------|---------------|
| release_package_sha | string | Harness | 包构建完 |
| rollback_plan | string | Agent请求→Harness校验 | agent 填发布计划 |
| grayscale_strategy | [5,25,50,100] | Agent请求→Harness校验 | 同上 |
| monitoring_thresholds | {同phase2} | Harness(快照) | 阶段5入口从phase2复制 |
| grayscale_current | number | Harness | 灰度 Loop 每 step |
| grayscale_phase | "waiting_confirm"\|... | Harness | 同上 |
| grayscale_status | "pass"\|"failed"\|"in_progress" | Harness | 灰度结束 |

### 5.3 三条铁律

1. **硬关卡必须能映射到 manifest 字段**（否则不该叫"硬"）
2. **字段必须机器可读**（布尔/数字/数组/对象，不能自然语言描述）
3. **manifest 写入是阶段出口唯一凭证**（spec.md 有内容但 manifest 没更新 = Harness 不认）

### 5.4 版本一致性规则

| 规则 | 说明 |
|------|------|
| 共用 spec_sha | manifest 和 spec 共享同一 Git SHA |
| major 刷新归档 | 整体归档到 `archives/manifest.v3.json` |
| minor 刷新增量 | 只更新 phase3 部分，不重建整个 manifest |
| 回滚恢复 | 回滚到 v3 时，从归档恢复 v3 的 manifest |
| monitoring_thresholds 快照 | phase5 从 phase2 快照复制，灰度中不变 |

### 5.5 写入时机原则

- **客观字段**（命令 exit code、文件检测、统计）→ Harness 全权写，agent 不能请求改（防美化）
- **语义字段**（阈值、回滚预案内容）→ agent 请求 → Harness 校验格式后写
- **判定字段**（review_passed、goal_measurable）→ 由对应角色写（Judge、Critic），不是执行 agent 自己标

---

## 6. 工具权限矩阵

### 6.1 危险等级

| 等级 | 包含 | 控制 |
|------|------|------|
| L0 无害 | read_file/grep/glob/codebase-researcher/pull_monitoring/read_manifest | Agent 随时调 |
| L1 可逆 | write_file(按路径)/run_test(本地)/run_lint/create_release_package/call_ci_cd(触发)/request_rollback | Agent 可调，有 audit 日志 |
| L2 不可逆 | kubectl apply/aws deploy/直接持生产凭据 | **Harness 直接禁**（agent 看不到接口） |
| L3 需人确认 | 灰度 25%+ 推进 | confirm token 触发 |

### 6.2 阶段×工具矩阵

| 阶段(角色) | L0 读 | L1 写/执行 | L2 禁 | L3 confirm |
|-----------|-------|-----------|-------|-----------|
| 需求(引导者) | ✓ | ✗ | ✗ | ✗ |
| 设计(协作者) | ✓ | ✓ write 限 `docs/design-docs/**` | ✗ | ✗ |
| 编码(执行者) | ✓ | ✓ write 限 `src/**`,`tests/**` + run_test(本地) + lint + git diff(只读) | ✗ | ✗ |
| 测试(测试者) | ✓ | ✓ write 限 `tests/**` + run_test + run_benchmark + coverage | ✗(部署job) | ✗ |
| 上线(编排者) | ✓ + pull_monitoring | ✓ create_release_package + call_ci_cd(触发) + request_rollback | ✗ kubectl/aws/生产凭据 | ✓ 灰度25%+ |

### 6.3 三条铁律

1. **低风险阶段权限不带到高风险**（切换时 Harness 自动收回）
2. **L2 在 Harness 层直接禁**（agent 根本看不到工具接口，不是"提示不许用"）
3. **L3 只能通过 confirm token 触发**（Agent 发起请求 → Harness 生成 token → 人确认 → 放行）

### 6.4 action 类型清单（= 工具权限枚举 = 轨迹日志事件类型，闭环2）

这份清单同时是：工具权限矩阵的枚举、轨迹日志的 action 枚举、工具调用协议的 tool 枚举。一份三用。

| action | 说明 | 可用阶段 | 危险等级 |
|--------|------|---------|---------|
| read_file | 读文件 | 全阶段 | L0 |
| write_file | 写文件(按路径限制) | 设计/编码/测试 | L1 |
| edit_file | 编辑文件(按路径限制) | 编码/测试 | L1 |
| grep/glob | 搜索 | 全阶段 | L0 |
| codebase_research | 代码库调研 | 全阶段 | L0 |
| run_test | 跑测试(本地) | 编码/测试 | L1 |
| run_lint | 跑 lint | 编码/测试 | L1 |
| run_benchmark | 跑基准 | 测试 | L1 |
| coverage_report | 覆盖率报告 | 测试 | L1 |
| git_diff | 看 diff(只读) | 编码 | L0 |
| call_reviewer | 调 reviewer | 编码(Graph) | L1 |
| handoff | 传 handoff | 编码(Graph) | L0 |
| request_confirm | 请求确认 | 全阶段(触发时) | L3 |
| request_rollback | 请求回滚 | 上线 | L1 |
| pull_monitoring | 拉监控 | 上线 | L0 |
| create_release_package | 创建发布包 | 上线 | L1 |
| call_ci_cd | 触发 CI/CD | 上线 | L1 |
| write_manifest_update | 请求 manifest 更新 | 全阶段(产出时) | L0(请求) |

---

## 7. spec 版本化（Snapshot Locking）

### 7.1 机制

- **编码入口冻结**：Harness 记录当前 spec 的 Git SHA（如 spec.v3）并锁定，后续编码全部基于此版本
- **强制 commit**：spec 每次升版本必须 commit，否则 SHA 锁不住
- **回退派生**：编码中发现 spec.v3 有错 → 派生 spec.v4（基于 v3 修正）→ 标 change_type
- **manifest 共享 SHA**：manifest 不独立版本号，和 spec 共享同一 Git SHA

### 7.2 minor vs major 决策树

```
spec 要改 ──▶ 标 change_type ──┬── minor ──▶ Loop B
                                │            ├ 不清空上下文(增量注入 diff 按 spec_refs 精准 push)
                                │            ├ tasks 增量(受影响 task 标 Superseded + 新增 task)
                                │            ├ needs_revalidation 增量标记
                                │            ├ spec_refs 不重建(章节归属没变)
                                │            ├ tasks 清单/revalidation 清单可增量
                                │            └ codebase-researcher 缓存清空(受影响 task)
                                │
                                └── major ──▶ Loop C
                                             ├ manifest 归档 archives/manifest.v3.json
                                             ├ 清空上下文(重注入 spec.v4 全文 + 代码文件)
                                             ├ tasks.md 覆盖重建(旧日志归档 spec.v3)
                                             ├ 全部已有代码标 needs_revalidation
                                             ├ monitoring_thresholds 重新快照
                                             └ 回退阶段2(重新设计)→完成→重新进编码→Loop D
```

### 7.3 minor→major 动态升级触发

| 升级信号 | 含义 | 硬度 |
|---------|------|------|
| finding 涉及需求章(1-3)/方案概览(4.1) | minor 不该动这些章 | 半硬(机器扫 finding 的 spec_refs) |
| needs_revalidation 占比 > 阈值(默认60%) | 改动波及面太大 | 硬(机器算清单占比) |
| 连续 2 轮 review 同类失败 | 不是单点错，是设计层面问题 | 软(agent 判) |

升级触发 → minor diff 作废，spec 重新标 major，走 C 流程。

### 7.4 spec 章节→代码文件映射（软映射+硬覆盖）

**第一步（设计阶段，软映射）**：tasks.md 每个 task 的 `estimated_files` 给大概范围（glob 模式如 `auth/*`）

**第二步（编码阶段，硬覆盖）**：Harness 收到 estimated_files 后：

| 文件状态 | 归入清单 | 依赖分析 |
|---------|---------|---------|
| 已存在 | needs_revalidation（改现有，要重验） | ✓ 做一跳 caller/callee 扩展 |
| 不存在 | to_create（新建，无旧实现要重验） | ✗ 跳过（文件不存在没法分析） |

**影响判定**：
- 确定影响 = estimated_files 直接命中 + spec_refs 引用章节明确提到的接口/类对应文件
- 可能影响 = 依赖链一跳

**运行时追加**：agent 编码中发现清单外文件要改 → 追加到 needs_revalidation → 触发 review 扩展范围

**局限**：软映射错了，硬覆盖（依赖分析）只能兜"依赖链内的"，兜不了"agent 根本没想到的盲区"——运行时追加是最后兜底。

---

## 8. Loop 层

### 8.1 基本单元

```
[Context Push] → [Agent 执行/等待] → [客观验证] → 失败? → [回退/升级/终止]
     ↑对抗记忆易失          ↑对抗概率性
```

Context 层（push）和 Loop 层（验证）在一个 step 内咬合——前半段 Context、后半段 Loop。

### 8.2 五种 Loop 形态

| 维度 | A 前进Task | B minor刷新 | C major刷新 | D needs_revalidation | E 灰度轮询 |
|------|-----------|-------------|-------------|---------------------|-----------|
| 触发 | 上一task完成 | spec v3→v4 标minor | spec v3→v4 标major | major刷新后 | 灰度批次发布 |
| Push | 冻结spec相关章+tasks当前项+反馈 | diff片段按spec_refs精准push+Superseded清单 | 清空+重注入spec.v4全文+代码 | needs_revalidation清单(Push给reviewer) | 监控数据(最新) |
| 执行 | agent改代码 | agent在现有代码上改 | 回退设计阶段重新做设计 | reviewer对清单逐条审 | **agent等待**(不执行) |
| 验证 | lint+编译+单测+review | 受影响代码review覆盖 | 设计阶段出口硬关卡 | review覆盖率(清单全审完) | 监控指标在阈值内持续N分钟 |
| 失败 | finding→修复→re-review;3轮熔断 | 升级为major | 设计失败→设计内Loop | 漏审→补审 | 触发回滚→回阶段3 |
| 终止 | 所有task Completed | 受影响代码review PASS | 设计完成+重新进编码 | 清单全部reviewed | 全量+监控稳定=成功 |
| 谁验 | 机器+多agent | 多agent | 机器(manifest) | 多agent | **外部世界** |

### 8.3 Loop 间关系（状态机，不是 while 循环）

```
阶段3 编码:
  Task Loop(A) ──触发minor──▶ B 嵌入A内
                ──触发major──▶ C 中断A,回退设计
  C 完成后 ──重新进编码──▶ D 嵌入新A(needs_revalidation review)

阶段5 上线:
  E 灰度Loop ──失败──▶ 回阶段3 的 A
```

三种关系：
- **嵌套**（B 嵌入 A）：不中断 Task Loop，状态机保留 A 现场
- **中断**（C 中断 A）：A 现场归档不丢弃，C 完成恢复
- **升级**（B→C）：minor 刷新中 review 发现改动比想象大，转入 C

### 8.4 loop_state（状态机现场保存）

存 manifest 的 `phase3.loop_state` 字段（不独立文件，保证原子性 + 随版本归档 + 回滚锚点天然成立）。

**两层结构**：

```json
{
  "loop_state": {
    "定位层": {
      "current_phase": "requirement|design|coding|testing|release",
      "current_task_id": "T-3",
      "current_subtask": "implement_login_handler",
      "current_loop_type": "A|B|C|D|E|Graph"
    },
    "进度快照层": {
      "files_modified": ["auth.go","session.go"],
      "completed_steps": ["step1_read_spec","step2_draft_code"],
      "review_round": 2,
      "pending_findings": ["P0-001","P1-003"],
      "revalidation_checked": ["auth.go"]
    }
  }
}
```

**字段可靠性来源**：

| 字段类 | 例子 | 谁填 | 可靠性 |
|--------|------|------|--------|
| 机器可验证 | files_modified(git diff)/review_round(报告计数)/revalidation_checked(manifest扫描) | Harness 从客观源拉取 | 真硬 |
| agent 上报 | completed_steps 语义步骤 | agent 上报 | 软，有客观验证兜底 |

**边界**：loop_state 只存"执行进度"，不存"执行结果"。结果在 manifest 的 status 字段。review PASS 后 pending_findings 必须清空，判定转到 manifest.status。

**current_loop_type 枚举**（C1 显化）：
- A = 前进 Task Loop（单 agent 串行）
- B = minor 刷新 Loop
- C = major 刷新 Loop
- D = needs_revalidation review Loop
- E = 灰度轮询 Loop
- Graph = 多 agent 并行（review 阶段）

Harness 按 current_loop_type 决定调度形态（A/E 单 agent，Graph 多 agent 并行）。

### 8.5 多 agent 调度

| 维度 | 规则 |
|------|------|
| 启动 | 同时启动（真并行，不逐个） |
| 隔离 | reviewer 启动时互不知道其他 reviewer（并行纯净，handoff 汇聚后才传） |
| 等待 | 等所有返回 + 超时（按 reviewer 类型配置，不统一5分钟） |
| 失败 | 重试1次 → 仍失败标"该维度未审"，其他人继续 |
| 汇聚 | 全部收齐（或超时/失败）后汇聚到 Judge |
| 未审处理 | Judge 接受"该维度未审"+标 follow-up note（不阻塞，留痕由人决定补审） |
| 下一轮 | Judge 裁定需补审 → 通知相关 reviewer 下一轮启动 |

### 8.6 handoff 机制

**结构化格式**：
```json
{
  "from": "performance-reviewer",
  "to": "robustness-reviewer",
  "file": "auth/login.go",
  "line": 42,
  "signal": "热路径里有个空指针解引用风险",
  "severity": "P1",
  "evidence": "在 validateToken() 调用前没有检查 user==nil",
  "status": "pending"
}
```

**传递时机**：第一轮并行纯净 → 汇聚后 Harness 提取 handoff 按 to 字段分发 → 下一轮各 reviewer 带 handoff 补审。

**约束**：
- handoff 是"提醒"不是"命令"，不触发硬拦截
- 涉及 needs_revalidation 清单的 handoff 必须回应（计入清单已审计数）
- 不涉及的是软提醒（可选回应）
- 目标 reviewer 可拒绝采纳，但必须给 rejected_reason

---

## 9. Graph 层

### 9.1 两处使用多 agent 制衡

| 位置 | 机制 | 理由 |
|------|------|------|
| 阶段1 目标可衡量性 | Critic 审目标（机器粗筛+Critic精判+人可覆盖） | 目标不可量化则下游全无意义，是基础 |
| 阶段3 编码 review | 5 reviewer + critic + Judge 三权分立 | 编码暴露设计缺陷，必须确保正确实现设计 |

**其他阶段不用 Graph**——spec 完备性/设计合理性/权衡记录追求完美是过度工程，靠回退通道兜底。

### 9.2 编码 review 三级分级拦截

| finding 来源 | 例子 | 拦截方式 |
|-------------|------|---------|
| 机器 P0 | lint 安全规则失败/测试失败/编译失败/semgrep 报漏洞 | **Harness 硬拦，不可覆盖** |
| agent P0 | reviewer 判的逻辑死锁/数据丢失风险/与 spec 关键偏离 | **Harness 拦（reviewer 标 P0 就停），人可显式覆盖（留痕）** |
| P1/P2 | 代码风格/可读性/性能建议 | 记录不阻断 |

### 9.3 三权分立

```
              Judge（主 agent = 法官）
             ╱           │           ╲
       5 个 reviewer   review-critic
      （检察官，各维     （辩护律师，
       度提 finding）     对 finding 找反证）
```

- **Judge**：编排流程、去重分诊、独立调研后裁决、输出报告。**自己不产 finding**。
- **5 个 reviewer**（始终调用）：performance / robustness / standards / contract-trust / spec-compliance
- **review-critic**（有 finding 时调用）：对抗性验证，给四结论之一（✅成立/❌驳回/⚠️降级/未驳倒）

### 9.4 多 agent Context 路由

| 层 | 内容 | 谁看 |
|----|------|------|
| 共享层（Push 给所有 reviewer） | spec 相关章 + tasks 当前项 + diff + 适用规范列表 | 全部 reviewer |
| 维度子集层（按维度 Push） | performance:热路径+性能规范；robustness:错误处理+资源规范；standards:命名风格+全文件；spec-compliance:spec全文+实现对照；contract-trust:契约性资源+调用方信任链 | 各自 |

---

## 10. Context 层

### 10.1 Push vs Pull 分界

| 注入方式 | 谁做 | 内容 | 硬度 |
|---------|------|------|------|
| Push | harness 强制注入 | 必须看到的（漏了就出错） | 硬 |
| Pull | agent 用工具拉 | 展开了更好 | 软 |

**Push 集（硬）**：身份/纪律、冻结基线、任务规格、上一步反馈（只留最新）
**Pull 集（软）**：代码现状深挖、规范细节、历史决策深挖

### 10.2 阶段×上下文矩阵

| 上下文类 | 阶段1需求 | 阶段2设计 | 阶段3编码 | 阶段4测试 | 阶段5上线 |
|---------|----------|----------|----------|----------|----------|
| 身份/纪律 | Push(引导者) | Push(协作者) | Push(执行者) | Push(测试者) | Push(编排者) |
| 任务规格 | Push(spec模板+意图) | Push(spec前3章+设计模板) | Push(**冻结spec相关章**+tasks当前项) | Push(spec第7章+可追溯映射) | Push(回滚预案+发布模板) |
| 代码现状 | Pull(researcher) | Pull(researcher) | Pull(被改文件caller/callee,预拉一跳) | Pull(被测代码+测试设施) | Pull(发布包元数据) |
| 规范 | Push(非功能checklist) | Pull(按section加载bp) | Push(bp-coding必加载)+Pull(std/bp-distributed) | Pull(boundary-checklist) | Pull(bp-release) |
| 历史决策 | Pull(project-index+failure-patterns) | Pull(ADR) | Pull(轨迹日志+failure-patterns) | Pull(failure-patterns) | Pull(过往发布事故) |
| 反馈 | Push(用户回答) | Push(设计想法+目标可衡量扫描) | Push(lint/编译/单测/review,只留最新) | Push(测试结果+覆盖率) | Push(灰度监控+告警) |
| 冻结基线 | — | — | Push(spec版本号+needs_revalidation+gate_baseline) | Push(同编码) | Push(spec版本+构建SHA) |

### 10.3 保鲜机制

1. 每个 task 开始时重 push 冻结基线 + 任务规格（对抗上下文腐化）
2. 反馈类只留最新（不累积）
3. Pull 工具调用 idempotent（agent 可反复读同一文件）

### 10.4 codebase-researcher 调用形态

| 维度 | 形态 |
|------|------|
| 调用时机 | 阶段开始 Harness 预调用一次(广而浅) + agent 执行时按需(窄而深) |
| 检索范围 | 按 estimated_files 或 spec_refs 约束 |
| 输出格式 | 结构化：文件列表 + 摘要（不灌全文） |
| 超时 | 30秒 → 返回部分结果 + "可能不完整"标记 |
| 缓存 | 同 task 内同查询缓存；**spec 版本变更时失效**（minor 刷新清空受影响 task 缓存） |
| 持久化 | 结果写入 loop_state（中断恢复不重搜） |

### 10.5 failure-patterns 检索（Pull→Push 升级）

failure-patterns 从 Pull 升级为 **Push**——agent 不知道自己该搜什么（上下文决定性），Harness 按当前 Loop 形态生成标签组合搜好 Push 给 agent。

**标签组合按 Loop 形态**：
- 编码阶段：module + phase（预防性检索，拉"这模块过往踩的坑"）
- 排查阶段：error_type（诊断性检索，拉"这类错误的过往案例"）

---

## 11. Prompt 层

### 11.1 三子层

| 子层 | 内容 | 谁写 | 何时注入 |
|------|------|------|---------|
| L1 系统身份 | "你是执行者/设计协作者/...。职责是...权限边界是..." | 固定模板，Harness 按阶段加载 | 阶段开始 Push（**替换不追加**，避免旧角色残留） |
| L2 当前任务说明 | "当前阶段编码，Task T-3 实现登录接口，spec 版本 v3，关注章节 4.2/5.1，受影响清单..." | Harness 从 manifest 自动生成 | 每 task 开始 Push |
| L3 交互协议 | 输出格式 schema + 工具调用格式 | 固定模板 | 常驻（< 500 token） |

### 11.2 L3 交互协议（三子协议）

agent 每次输出必须是以下三种结构化 JSON 之一：

**子协议 1：工具调用**
```json
{"type":"tool_call","tool":"edit_file","args":{"path":"auth/login.go","content":"..."}}
```
Harness 收到 → 权限拦截 → 放行执行/拒绝+audit

**子协议 2：step 产出**（同时是轨迹日志一条记录）
```json
{"type":"step_output","action":"edit_file","input":{"path":"auth/login.go"},
 "output":{"status":"success"},"duration":30,
 "manifest_update_request":{"phase3.needs_revalidation":["auth/login.go"]}}
```
Harness 收到 → 写轨迹日志 → 校验 manifest_update_request（agent 只能请求，Harness 交叉验证后写，如 needs_revalidation 用 git diff 比对验证）

**子协议 3：完成声明**
```json
{"type":"task_complete","id":"T-3","evidence":{"compile_passed":true,"review_passed":true}}
```
Harness 收到 → 跑出口硬关卡校验（读 manifest 字段）→ 全通过才放行

---

## 12. 三个闭环

### 闭环 1：反馈闭环
```
轨迹日志 ──被纠正──▶ self-refinement ──提取标签──▶ failure-patterns
                                                      │
                   Harness 按标签搜好 Push ◀──────────┘
                          │
                   agent 编码时收到相关坑提醒
```

### 闭环 2：action 三用
```
工具权限清单(§6.4) ═══ 轨迹日志 action 类型(§11.2 子协议2) ═══ 工具调用枚举(§11.2 子协议1)
       └─────────── 同一份清单的三种用途 ──────────┘
```

### 闭环 3：边界情况→failure-patterns
```
新边界情况(§14) ──self-refinement──▶ failure-patterns(phase=troubleshooting, error_type=edge_case)
                                      │
                   Harness 按标签 Push ◀┘
                          │
                   下次同类情况 agent 收到提醒
```

### 标签提取机制（C3 显化）

self-refinement 触发时，Harness 从轨迹日志自动提取标签：

| 标签 | 提取规则 | 例子 |
|------|---------|------|
| module | 从 edit_file/write_file 的 input.path 推断（取一级目录） | path="auth/login.go" → module="auth" |
| error_type | 从 run_test 失败的 output 解析关键词 | "timeout 30s" → "timeout"；"nil pointer" → "null_pointer" |
| severity | 从 review_findings 的 severity 继承 | P0/P1/P2 |
| phase | 从 loop_state.current_phase 取 | "coding" |

agent 只补 symptom/root_cause/fix（自然语言内容）。module 必须在项目候选值内（不在则报错）。

---

## 13. confirm token 机制

### 13.1 两类确认

| 类型 | 触发 | 超时默认 |
|------|------|---------|
| 阶段出口确认 | 阶段1/2/5 出口 | 不推进（fail-safe） |
| 覆盖确认 | agent P0 被人覆盖 | 不覆盖（P0 仍拦，比"不推进"更保守） |

### 13.2 优先级（串行依赖，不是平行冲突）

```
覆盖确认(agent P0) ──解决──▶ task 真正完成 ──触发──▶ 阶段出口确认
```

覆盖确认是异常必须先解决——agent P0 拦着，review 不能 PASS，task 没真正完成，阶段出口确认无法触发。

**队列规则**：单挂起队列（同一时间最多 1 个 confirm），优先级 覆盖 > 阶段出口 > 灰度推进。

### 13.3 确认请求结构

```json
{
  "type": "confirm_request",
  "phase": "coding",
  "task_id": "T-3",
  "summary": "Task T-3 登录接口实现完成，请求进入测试阶段",
  "confirm_consequence": "确认则进入阶段4测试",
  "reject_consequence": "拒绝则留在编码阶段"
}
```

摘要由 **Harness 从 manifest 生成**，不让 agent 自己写（防美化）。

### 13.4 接收载体（B1，实现期默认）

框架级约束：必须有统一接收点（固定 API），所有渠道汇聚。三级兜底：

| 通道 | 形态 | 说明 |
|------|------|------|
| 主通道 | Web UI 按钮（确认请求带结构化摘要+确认/拒绝按钮） | 默认 |
| 兼容通道 | IM 消息（Slack/钉钉/飞书 bot 发结构化卡片，人回复"确认 T-3"） | IDE 异常时 |
| 降级通道 | 自然语言语义识别 | 最后兜底 |

超时由 Harness 控制（不依赖载体）。

---

## 14. 边界情况处理

| 类型 | 例子 | 处理 | 原则 |
|------|------|------|------|
| 能力不足 | 3轮review失败 | 熔断上报人 | 不自动决策 |
| 超时 | codebase-researcher 30秒 | 部分结果+不完整标记 | 不阻塞Loop |
| 死循环 | 连续5次 manifest 状态 false（从字段判，非 agent 自报） | 标 blocked 上报人 | 不自动决策 |
| 外部依赖失效 | 模型 API 错误 | 重试3次→暂停阶段上报 | 不丢数据 |
| 人 confirm 超时 | 阶段出口24h没回应 | 默认拒绝（不推进）；覆盖确认超时=不覆盖（P0仍拦） | fail-safe |
| manifest 不一致 | manifest 说 PASS 但 loop_state 挂 finding | 以 manifest 为准（终局判定） | manifest 为终局 |
| 多 reviewer 分歧 | 性能 P0 vs 合规 P2 | Judge 裁决→无法裁决上报人 | 不自动决策 |

**三条 fail-safe 原则**：
1. 能不丢数据就不丢（已有状态必须归档）
2. 能不自动决策就不自动决策（不确定时上报人，不自己拍板）
3. 能回退就回退（比推进更安全）

新边界情况通过 self-refinement 沉淀到 failure-patterns（用 `phase=troubleshooting, error_type=edge_case` 标签）。

---

## 15. 配置项清单（项目级配置 + 框架默认 + 不配置报错）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| task_max_loc | 50 | task 最大预估代码行数 |
| task_max_complexity | 15 | task 最大圈复杂度 |
| task_max_files | 5 | task 最大文件数 |
| coverage_line_min | 80 | 行覆盖率阈值 |
| coverage_branch_min | 70 | 分支覆盖率阈值 |
| needs_revalidation_threshold | 60 | needs_revalidation 占比升级触发阈值(%) |
| review_max_rounds | 3 | review 熔断轮次 |
| review_failure_max | 5 | 死循环判定连续失败次数 |
| confirm_timeout_hours | 24 | 人 confirm 超时时间 |
| grayscale_strategy | [5,25,50,100] | 灰度分档 |
| grayscale_wait_minutes | {5:5, 25:30, 50:120, 100:240} | 各档等待分钟 |
| grayscale_confirm_threshold | 25 | 人 confirm 触发的灰度比例 |
| codebase_researcher_timeout | 30 | 代码调研超时秒 |
| reviewer_timeout | 按类型配置 | reviewer 超时（不统一） |

**铁律**：配置项必须有，不能为空。项目没配置 → Harness 报错引导（"请设置 X，参考建议：默认值"），不沉默通过。

---

## 16. 执行轨迹日志格式

每个 task 一个日志文件：`docs/design-docs/<module>/<feature>/execution-logs/<task-id>.md`（JSON 格式内容）。

```json
{
  "task_id": "T-3",
  "started_at": "2026-08-07T10:00:00Z",
  "ended_at": "2026-08-07T10:15:00Z",
  "spec_version": "v3",
  "steps": [
    {
      "step": 1,
      "action": "read_spec",
      "input": {"spec_refs": ["4.2","5.1"]},
      "output": {"sections_read": ["4.2","5.1"]},
      "duration": 2
    },
    {
      "step": 2,
      "action": "edit_file",
      "input": {"file": "auth/login.go"},
      "output": {"status": "success"},
      "duration": 30
    }
  ],
  "final_status": "completed"
}
```

**要求**：每条记录必须是结构化事件（action/input/output/duration），不是自然语言描述。action 类型见 §6.4 清单。轨迹日志是 self-refinement 的养料（闭环1）。

---

## 17. 实现期决策（B1-B5，不影响骨架）

| 项 | 框架级约束 | 默认方向 | 项目级可覆盖 |
|----|-----------|---------|-------------|
| B1 confirm 载体 | 统一接收点 + 三级兜底 + 超时由 Harness 控制 | Web UI 主/IM 兼容/语义降级 | 用哪个载体、IM webhook |
| B2 多 agent 调度 | reviewer 间无共享状态 + 汇聚点 Judge 处理 + 超时按类型 | 进程级隔离 + 结构化消息通信 | 线程/进程/远程 API |
| B3 codebase-researcher 实现 | 结构化输出 + 按 spec_refs 约束 + 30秒超时 + 缓存 | AST 解析 + 调用图 + 摘要生成 | 具体 AST 工具/是否加向量检索 |
| B4 manifest 存储 | 机器可读 + 随 spec SHA 归档 + major 归档 archives/ | JSON 文件分片 + git 归档 | git notes/数据库 |
| B5 failure-patterns 标签候选值 | module/error_type 项目级维护 | 按模块分目录 + JSON 记录 + 框架给 error_type 参考 | module 清单按项目填 |

---

## 18. 待显化项（C1-C4，已融入对应章节）

| 项 | 内容 | 落位章节 |
|----|------|---------|
| C1 loop_state current_loop_type 枚举 | A/B/C/D/E/Graph | §8.4 |
| C2 action 类型清单（三用） | §6.4 完整清单 | §6.4 + §11.2 |
| C3 标签提取机制 | module 从 path 推断/error_type 从 output 解析 | §12 |
| C4 manifest 字段写入时机 | 每字段标 writer + write_trigger | §5.2 各表 |

---

## 19. 实施路径建议

1. **先实现 Harness 层**（manifest 读写 + 工具权限拦截 + spec SHA 锁定）——这是其他层的基础
2. **再实现 Loop 层**（硬关卡校验 + loop_state + minor/major 决策）
3. **Context 层**（Push/Pull 分界 + 阶段矩阵）
4. **Graph 层**（Critic + 编码 review 三权分立）
5. **Prompt 层**（L1/L2/L3 协议）
6. **三个闭环**最后接通（self-refinement → failure-patterns → Push）

---

## 附录 A：硬关卡→manifest 字段映射

| 硬关卡 | 校验字段 |
|--------|---------|
| spec 存在 + 章节非空 | phase1.sections_status |
| 目标可衡量 | phase1.goal_measurable |
| 设计章非空或 N/A | phase2.sections_status["4"],["5"]... |
| tasks 全 Completed | phase3.task_status_all_done |
| lint 基线对比 0 新增 | phase3.lint_baseline_delta == 0 |
| 编译过 | phase3.compile_passed |
| 现有测试无 regression | phase3.test_regression_passed |
| 新增单测过 | phase3.new_test_passed |
| review PASS | phase3.review_passed |
| needs_revalidation 全审 | phase3.needs_revalidation_reviewed 覆盖 needs_revalidation |
| 测试全 PASS | phase4.all_tests_passed |
| 覆盖率达标 | phase4.coverage_met |
| 包可重复构建 | phase5.release_package_sha 存在且可验 |
| 回滚预案/灰度策略/监控阈值存在 | phase5.rollback_plan/grayscale_strategy/monitoring_thresholds |
| 灰度反馈无异常 | phase5.grayscale_status == "pass" |

**原则**：所有硬关卡必须能映射到 manifest 字段（否则不该叫"硬"）。
