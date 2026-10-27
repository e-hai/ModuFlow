# ModuFlow 三层架构重构与现状勘察报告 (docs/phase0-survey.md)

> **勘察原则**：先读后改，只读勘察，不改业务代码；严守硬约束，梳理现状与差距，为后续 Phase 1~7 奠定稳固地基。
> **勘察日期**：2026-10-27
> **代码版本基线**：Git branch `main` (commit: head)

---

## 一、系统现状全面勘察 (System Survey)

### 1.1 物理目录结构拓扑
```
ModuFlow/
├── AGENTS.md                  # 8 大 Agent 角色契约、工序定义与红线指南
├── backend/
│   ├── app/
│   │   ├── adapters/          # AI 执行适配层 (base, cli_adapter, simulator_adapter, factory)
│   │   ├── api/               # RESTful API 端点 (endpoints.py 涵盖战略/单品/工序/会话/评审/Issue等)
│   │   ├── core/              # 全局配置 (config.py) 与异步数据库 (database.py)
│   │   ├── mcp/               # 角色级隔离的 Stdio JSON-RPC 2.0 MCP Server (role_mcp_server.py)
│   │   ├── models/            # SQLAlchemy 2.0 异步 ORM 实体定义 (entities.py, 14 张表)
│   │   ├── schemas/           # Pydantic v2 请求响应数据契约 (all_schemas.py)
│   │   └── services/          # 核心业务引擎与服务层
│   │       ├── agent_roles.py           # 8 大专业智能体定义与工序映射 (STAGE_ROLE_CONFIGS)
│   │       ├── agent_runner.py          # 会话流转调度与互斥锁网关
│   │       ├── bundle_storage.py        # 原型包解压与静态预览资源托管
│   │       ├── context_assembler.py     # 战略上下文与工作区物理路径组装
│   │       ├── diff_engine.py           # 产物 Diff 比较与下游影响分析
│   │       ├── market_research_engine.py# 赛道 TAM/SAM/SOM 测算
│   │       ├── skill_mcp_mounter.py     # 按工序动态挂载专属 Skill 与 MCP
│   │       ├── stale_checker.py         # 上下游基线变更追踪与过时预警检查器
│   │       ├── workflow_engine.py       # 模板管理、工序实例化与基线定稿检查 (can_baseline_module)
│   │       └── workspace_sync.py        # SQLite ↔ 磁盘物理工作区双向同步器
│   ├── skills/                # 规范技能库 (ba, eng, mkt, mr, ops, pm, qa, ux)
│   └── tests/                 # Pytest 异步测试集 (test_adapter, test_api, test_market_research, test_optimization)
├── data/
│   ├── moduflow.db            # 主数据库 (SQLite 3 WAL 模式)
│   └── workspaces/            # 磁盘持久隔离工作区 (按 initiative_id / products / runs 分层镜像)
├── frontend/                  # React 18 + Vite + TS + Tailwind + Lucide + KaTeX + Mermaid
├── scripts/
│   └── seed.py                # 数据库初始化种子脚本 (模板、8角色、默认CLI配置)
└── docs/                      # 规范设计与实施文档区
```

---

### 1.2 数据库表与 ORM 实体拓扑 (14 张表)

| 实体类名 | 数据库表名 | 核心职责与关联关系 |
| :--- | :--- | :--- |
| `StrategicInitiative` | `strategic_initiatives` | 战略工程顶层调度器（预算总池 `budget_total`、现金流、战略三要素）；1 ➔ N `Product` |
| `Product` | `products` | 矩阵产品/单品（`budget_allocated`, `actual_spent`, `strategic_role`, `kpi_*`）；1 ➔ N `WorkflowRun` |
| `WorkflowRun` | `workflow_runs` | 单次迭代运行周期（如 `V1.0.0`）；1 ➔ N `ModuleInstance` |
| `ModuleInstance` | `module_instances` | 11 道具体工序模块实例（`module_code`, `phase`, `is_unlocked`, `dependencies`, `primary_role_code`, `synced_upstream_versions`） |
| `Artifact` | `artifacts` | 交付物版本归档（`version`, `content`, `content_hash`, `is_baseline`, `change_summary`） |
| `ChangeReview` | `change_reviews` | 交付物版本变更 Diff 评审单（`from_version`, `to_version`, `status: pending_approval/approved/rejected`, `approver`） |
| `Issue` | `issues` | 结构化缺陷与 CR（`category: bug/requirement_cr/improvement`, `severity`, `status: open/closed`） |
| `ExecutiveDecision`| `executive_decisions`| 战略决策审批记录（`status: proposed/approved/rejected/executed`, `approved_by`） |
| `ExecutiveRisk` | `executive_risks` | 战略经营风险与红线监控（`rule_code`, `severity`, `action_suggestion`） |
| `CollaborationSession` | `collaboration_sessions` | 人机协作讨论室（每个模块对应 1 个活动讨论室） |
| `SessionMessage` | `session_messages` | 讨论室内结构化消息流（`sender_role: human/agent`, `role_code`, `metadata_json`） |
| `AgentRoleDefinition` | `agent_role_definitions` | 8 大角色系统元数据定义（系统 Prompt、职责、图标与偏好执行器） |
| `AgentSettingsModel` | `agent_settings` | 全局 Agent 执行器适配配置（CLI 命令 `agy/claude`, 超时时间） |
| `WorkflowTemplate` | `workflow_templates` | 研发工作流模板定义（模块编排配置 `modules_config`, 默认依赖 `default_dependencies`） |

---

### 1.3 现有角色与工序映射 (`agent_roles.py` & `workflow_engine.py`)

- **8 大专属角色**：`mr` (市场研究), `ba` (商业分析), `pm` (产品经理), `mkt` (增长营销), `ux` (设计用研), `eng` (研发架构), `qa` (测试保障), `ops` (数据运营)；
- **11 道标准工序**：
  `01 市场研究 (mr)` ➔ `02 商业模式 (ba)` ➔ `03 方向决策 (pm)` ➔ `04 假门验证 (mkt)` ➔ `05 需求定义 (pm)` ➔ `06 设计实现 (ux)` ➔ `07 开发实现 (eng)` ➔ `08 测试与QA (qa)` ➔ `09 发布上线 (qa)` ➔ `10 推广获客 (mkt)` ➔ `11 运营迭代 (ops)`。
- **3 套工作流模板**：
  1. `full-product-launch` (11 道全工序)
  2. `fast-iteration` (6 道工序：`05 -> 06 -> 07 -> 08 -> 09 -> 11`)
  3. `hotfix` (3 道工序：`07 -> 08 -> 09`)

---

### 1.4 现有门禁与自动化检查机制
- **`can_baseline_module` (`workflow_engine.py`)**：定稿前检查是否有未解决的 Critical/Major 级 Issue，以及是否产出交付物 Artifact；
- **`prd_linter.py`**：静态 AST/正则检查，严格检查摘要卡、黄金 7+1 章节、V-01~V-05、M1~M6、表格密度、违禁假门测试表残留，以及**工程代码/SQL DDL 泄露**；
- **`check_hig.py`**：检查 iOS 灵动岛顶部安全区 ≥71pt 及触控热区 ≥44pt；
- **`stale_checker.py`**：下游工序监听上游基线版本演进，触发未同步预警；
- **互斥锁与单实例运行 (`_session_locks` in `agent_runner.py`)**：单模块会话强制并发控制。

---

### 1.5 物理工作区与 SQLite 镜像机制 (`workspace_sync.py`)
- 自动维护物理工作区目录：
  `data/workspaces/{initiative_id}/products/{product_code}/{run_name}/{order_index}_{module_code}_{module_name}/`
- 在每个模块目录下动态隔离挂载：
  - `.agents/skills/{skill_name}/SKILL.md` 与可执行脚本；
  - `.agents/mcp_config.json` 与 `.mcp.json`；
  - 自动落盘交付物正文文件 `{title}_v{version}.md`；
- 支持战略工程底稿与单品 README 自动同步。

---

### 1.6 现有测试集覆盖现状
运行 `PYTHONPATH=. pytest backend/tests/ -v`：
- `test_adapter.py` (8 测试)：装配器、CLI 参数构建、执行器、MCP/Skill 动态隔离挂载；
- `test_api.py` (7 测试)：健康检查、战略工程、单品运行生命周期、驾驶舱决策、物理工作区同步、角色 API；
- `test_market_research.py` (4 测试)：TAM/SAM/SOM 测算、工序 01 报告与会话生成；
- `test_optimization.py` (4 测试)：HTML 原型包托管与预览、上游基线变更监听 (Stale Detection)、CR 反馈闭环与 PRD 修订新基线。
- **测试现状**：**23 项测试全部绿灯通过 (耗时约 1.85s)**。

---

## 二、核心可复用点 (Reusable Strengths)

1. **磁盘与数据库双向镜像体系 (`workspace_sync.py`)**：天然适合放置单品独立授权包 `authorization.yaml` 与人类审批留痕目录 `decisions/`，无需改造底层存储拓扑。
2. **专属 Skill 与 MCP 动态隔离挂载机制 (`skill_mcp_mounter.py`)**：具备极强的扩展性，可在新增 `lead` (项目主管) 与 `cmp` (合规官) 角色时，无缝挂载其专属武器库。
3. **已落地的 CR 闭环 (`ChangeReview` + `Issue(category: requirement_cr)`)**：数据链路完备，可直接用于承载阶段关口申请单与需求变更单流转。
4. **确定性代码检查器模式 (`prd_linter.py`, `check_hig.py`)**：为构建“止损与熔断必须由确定性脚本执行、不经 LLM 妄断”提供了清晰的范式参考。
5. **模板实例化与依赖拓扑 (`workflow_engine.py`)**：已支持有条件解锁与动态依赖计算，适合注入 Green/Yellow/Red 关口判定逻辑。

---

## 三、与新规范「三层架构」的差距清单 (Gap Analysis)

| 规范要求 (Spec) | 现有系统现状 (As-Is) | 差距分析 (Gap & Deficit) |
| :--- | :--- | :--- |
| **1. 项目独立授权包 (`authorization.yaml`)** | `Product` 表仅有预算数值，无规范结构化授权包文件；立项无需校验授权包 | **重大缺失**：无 `authorization-package.schema.json`，无 `validate_authorization.py` 校验脚本，项目开工无授权包前置检查。 |
| **2. 确定性止损与熔断机制** | 依赖业务负责人在战略驾驶舱手动审批 `ExecutiveDecision` | **重大缺失**：缺乏纯 Python 确定性检查器；未在工序流转与费用变动时读取授权包判断 `kill_criteria`、时限与预算超限并自动暂停 (`paused`)。 |
| **3. 关口三级分级模型 (🟢/🟡/🔴)** | 仅有 `can_baseline_module`（Bug 阻断）与 `ChangeReview`（版本审批） | **结构缺失**：无 Green/Yellow/Red 级别区分；无一页纸关口申请单；无批量/即时通知区分；**09 提审 (G4) 缺乏人类确认硬阻断**。 |
| **4. 权限与只读拦截机制** | 磁盘文件对执行进程完全开放读写；API 无人类与 Agent 角色硬校验 | **安全缺失**：授权包与平台规范未设物理只读 (`chmod 0444`)；API 未拦截 Agent 对授权包与关口审批结果的篡改。 |
| **5. lead agent（项目层主管）与影子模式** | 无 `lead` 角色，工序由各领域 Agent (`mr/ba/pm...`) 直接响应并定稿 | **分层缺失**：缺少项目层调度器；无影子模式（记录 lead 建议与人类裁决一致率）；缺乏项目级统筹。 |
| **6. cmp 合规检查点** | 仅在工序 09 有静态 `audit_apple_review_compliance` 工具 | **合规缺失**：未作为独立角色贯穿 03（方向初筛）、05（隐私数据流）、09（提审政策）；无自动升 G5 机制。 |
| **7. 项目 profile 与红线参数化** | `iOS HIG` 与 `零推理成本` 属于全局硬编码检查 | **配置缺失**：未按单品 `platform: ios \| android` 动态切换规则集；`client_zero_inference` 未做成项目级开关。 |
| **8. 热修闭环与组合周报** | `hotfix` 流程跑完即止；各项目数据孤岛化 | **运营缺失**：发布后 24h 内无自动生成补档待办；缺乏跨单品一键聚合生成的一页组合周报 (Portfolio Dashboard)。 |
| **9. 价格唯一来源与数据真实性** | 虽在 Prompt 中强调，但缺乏代码级拦截 | **规则进代码不足**：未校验非 `ba` 角色是否篡改 02 定价；未强制校验数字是否有 `source` 或声明为 `[假设/待验证]`。 |

---

## 四、改动风险评估与防范对策 (Risk Assessment)

1. **风险：历史旧项目因缺少授权包导致崩溃**
   - **影响**：`data/workspaces/` 下已有既有单品（如 `WN-PAGER`），若强制校验授权包可能导致所有历史单品 API 报错 500。
   - **防范**：引入**优雅降级与迁移检测**。未配置授权包的项目状态返回 `needs_authorization`，前端展示引导横幅；提供 `scripts/migrate_legacy_project_auth.py` 一键补齐默认授权包。
2. **风险：现有 23 项核心测试用例断言失败**
   - **影响**：新增授权包校验若直接嵌入 `create_workflow_run_from_template`，可能导致现有测试（如 `test_initiatives_and_runs`）失败。
   - **防范**：测试基类/夹具自动为测试项目注入默认合规授权包；现有测试逻辑保持 100% 兼容。
3. **风险：确定性脚本与 LLM 推演混淆**
   - **影响**：部分开发者可能把止损逻辑写进 Agent Prompt，导致模型幻觉误判或漏判。
   - **防范**：**死守代码拦截原则**。止损、超预算、超期判定完全封装为独立的纯 Python 模块，API 和工序流转时直接同步调用，不给 LLM 任何介入机会。
4. **风险：文件系统只读保护引发工作区同步异常**
   - **影响**：若操作系统将 `authorization.yaml` 置为只读 (`0444`)，`workspace_sync.py` 在做全量同步时可能因无写入权限报错 `PermissionError`。
   - **防范**：在 `workspace_sync.py` 中增加对只读保护文件的识别逻辑——仅当人类发起授权包变更时使用特权写入，常规同步跳过受保护只读文件。

---

## 五、建议的新增文件落点规划 (File Placement Blueprint)

```
ModuFlow/
├── schemas/
│   └── authorization-package.schema.json      # [Phase 1] JSON Schema 2020-12 授权包格式契约
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   └── security.py                    # [Phase 3] 人机身份鉴权与特权拦截中间件
│   │   ├── services/
│   │   │   ├── authorization_engine.py        # [Phase 1] 确定性授权包解析、预算时限止损检查引擎
│   │   │   ├── gate_keeper.py                 # [Phase 2] 关口分级模型 (🟢/🟡/🔴) 与申请单裁决流转
│   │   │   ├── lead_agent_orchestrator.py     # [Phase 4] Lead Agent 调度、日常派活与影子模式一致率统计
│   │   │   ├── compliance_checker.py          # [Phase 5] CMP 合规检查点 (03/05/09 隐私、税务、商店政策)
│   │   │   └── portfolio_service.py           # [Phase 7] 跨项目数据库聚合与一页周报生成器
│   │   └── models/
│   │       └── entities.py                    # [Phase 1~2] 扩充 Product (授权包、profile)、GateApplication、AuditLog 实体
│   ├── skills/
│   │   ├── lead/                              # [Phase 4] Lead Agent 专属技能包 (lead-project-orchestrator)
│   │   └── cmp/                               # [Phase 5] CMP 专属技能包 (cmp-policy-compliance-audit)
│   └── tests/
│       ├── test_authorization_package.py      # [Phase 1] 授权包正反例测试、确定性止损与超预算熔断测试
│       ├── test_gate_system.py                # [Phase 2] 关口分级、自动升红、09 提审强制人批拦截测试
│       ├── test_readonly_security.py          # [Phase 3] 权限拦截反例测试 (Agent 越权写授权包必死)
│       └── test_lead_and_cmp.py               # [Phase 4~5] Lead 影子模式与 CMP 合规审查测试
├── scripts/
│   ├── validate_authorization.py              # [Phase 1] 命令行独立可执行的授权包校验脚本
│   └── migrate_legacy_project_auth.py         # [Phase 1] 旧项目授权包平滑迁移工具
└── docs/
    ├── assumptions.md                         # [已创建] 假设与决策记录
    ├── phase0-survey.md                       # [本文档] 现状勘察报告
    └── examples/
        └── authorization.example.yaml         # [Phase 1] 标准授权包参考样例
```

---

## 六、勘察总结与准备就绪状态

- **现状评估**：ModuFlow 的底层数据模型完整、双向镜像稳定、8 角色工序规范严谨、测试用例全部绿灯通过，具备平滑升级至「人类战略层 → 项目层 (lead) → 执行层」三层架构的坚实基础。
- **改动原则**：严格执行“先勘察后开发”、“小步可回滚”、“规则进代码”、“硬约束不可违背”四大原则。
- **下一步行动**：本报告已全面完成勘察。**等待人类业务负责人确认无误后，正式开启 Phase 1（授权包体系落地）！**
