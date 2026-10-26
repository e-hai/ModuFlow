# ModuFlow 智能体工程与系统架构指南 (AGENTS.md)

> 本文档为参与 **ModuFlow** 项目开发与维护的 AI 智能体（以及人类工程师）提供统一的项目全景、工序设计、技术架构与作业红线指导。

---

## 一、项目定位与核心理念

**ModuFlow** = `Module`（模块化与可插拔）+ `Flow`（战略工序流）。  
专为出海与多产品矩阵设计的 **AI 原生产研与运营平台**。通过将顶层战略分解为可编排的产品工程，在每个模块内建立**人机协作讨论室**，并通过**结构化 Issue 与基线变更追踪驱动全流程质量闭环**。

### 核心设计哲学
1. **战略驱动的顶层工程 (Strategic Initiative)**：战略工程作为顶层调度器，统一协调多产品线、共享全球调研沉淀与跨产品依赖。
2. **精益创业与反脑内自嗨 (Lean Startup Guardrails)**：死守“先验后建”铁律。必须先通过真实的低成本流量（H5 假门网页、短视频脚本）验证生死假设，再进入重度工程研发。
3. **双层分层与反冗余交付 (Two-Layer Deliverables)**：所有交付物必须包含顶层「**负责人 30 秒拍板摘要卡 (Executive Gate)**」与底层「**完整执行细节 (Execution Reference)**」，杜绝花哨的图标与 emoji 干扰。
4. **物理工作区与数据库双向映射**：平台数据在 `data/moduflow.db` 结构化存储的同时，全量自动同步镜像至磁盘独立目录 `data/workspaces/{initiative_id}/`，支持原生 IDE、Git 与命令行工具无缝读写。

---

## 二、标准产研 11 道工序体系 (11-Stage Pipeline)

ModuFlow 将完整的产品研发周期拆解为结构化、权责明确的 **11 道核心工序**：

```
[01 市场研究] ──> [02 商业模式分析] ──> [03 产品方向决策] ──> [04 低成本市场验证] ──> [05 产品立项与需求定义]
                                                                                               │
   ┌───────────────────────────────────────────────────────────────────────────────────────────┘
   ▼
[06 设计实现] ──> [07 开发实现] ──> [08 测试与 QA] ──> [09 发布与上线] ──> [10 市场推广与获客] ──> [11 运营分析与持续迭代]
```

### 11 道工序明细与角色矩阵

| 编号 | 工序名称 | 主责 Agent | 协同 Agent | 核心业务目标与交付物 | 门禁关键要求 |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **`01`** | **市场研究** | 市场研究 (`mr`) | 商业分析 (`ba`) | **全球赛道摸底与截胡实战**：验全球 T1~T3 利润含金量与 SOM 测算、扒头部爆款 3 秒视觉钩子、深挖 1-2 星差评软肋、提炼全球跨区套利刀法。 | 必须包含 3 类细分画像与明确的干/不干/怎么改单点去截胡建议。 |
| **`02`** | **商业模式分析** | 商业分析 (`ba`) | 市场研究 (`mr`) | **变现定价与单位经济精算**：设计混合变现阶梯（如 `24h Ad-Pass` + 反周卡订阅/买断）、测算 LTV、CAC、回本周期与毛利防线。 | 明确价格锚点与商业护栏（如 0 开屏广告保 4.8+ 评分）。 |
| **`03`** | **产品方向决策** | 产品经理 (`pm`) | 市场研究、商业分析 | **一页纸精益方向决策**：输出核心价值主张 (UVP)、MoSCoW 功能减法（斩立决伪需求）、10秒 Aha 路径与 4 个待验证生死假设 (H1~H4)。 | **严禁提前编写**代码级 Schema、字段级接口或长篇 Gherkin 用例。 |
| **`04`** | **低成本市场验证** | 增长营销 (`mkt`) | 设计用研、商业分析 | **实测方案 + 真交互原型**：小额测试流量分配表（如 $350/7天）、3 套开箱即用发帖/买量脚本，并强制生成可交互 H5 假门网页 (`index.html`)。 | **强制真交付**：必须在工作区生成零依赖高颜值可交互 H5 网页。 |
| **`05`** | **产品立项与需求定义** | 产品经理 (`pm`) | 商业分析、研发架构 | **实测立项复盘 + 工程级 PRD 封版**：客观复盘 H1~H4 给出 Go/Pivot/Kill 决议；若通过立项，同步输出字段级 Schema、交互主流程、异常降级、Gherkin 验收标准与技术边界规范。 | **反幻觉最高铁律**：严禁捏造虚假外测数据；未测时采用待回填立项评估框架。 |
| **`06`** | **设计实现** | 设计用研 (`ux`) | 产品经理 (`pm`) | **视觉与交互工程落地**：设计系统规范、高保真 UI 原型包 (HTML Bundle / 设计稿元数据)、关键交互动效与可用性防呆策略。 | 必须针对灵动岛留出安全区（≥ 71pt），规避 Apple 审核驳回。 |
| **`07`** | **开发实现** | 研发架构 (`eng`) | 测试保障 (`qa`) | **轻量选型与工程代码实现**：内聚技术栈选型与核心模块划分、核心业务逻辑与数据存储实现、单元测试覆盖率报告。 | 客户端零推理成本原则（AI 超分/抠图离线处理或云端处理）。 |
| **`08`** | **测试与 QA** | 测试保障 (`qa`) | 研发架构 (`eng`) | **全面质量验证与缺陷清障**：端到端用例执行报告、弱网与低端机性能测试、自动化回归与阻断性 Bug Issue 闭环。 | 存在未解决的 Critical/Major Bug 时，**系统强制阻断基线定稿**。 |
| **`09`** | **发布与上线** | 测试保障 (`qa`) | 研发架构 (`eng`) | **上架提审与发布门禁**：商店元数据合规审查（规避 Apple 4.3 拒审）、提审降级保护开关预案、灰度发布与回滚计划。 | 确保 Remote Config 降级开关与合规条款 100% 具备。 |
| **`10`** | **市场推广与获客** | 增长营销 (`mkt`) | 商业分析、数据运营 | **全球推广投放与自然裂变**：全球多语种 ASO 优化词表、社媒冷启动方案、KOL 推广排期与买量素材矩阵扩量。 | 严格监控渠道 eCAC，超标即熔断。 |
| **`11`** | **运营分析与持续迭代** | 数据运营 (`ops`) | 产品经理、增长营销 | **全生命周期数据复盘**：留存衰减漏斗（D1/D7/D30）、付费转化归因、用户反馈热词分析与下一版本 (V1.1) Backlog 立项。 | 输出数据驱动的迭代建议书。 |

### 支持的工作流模板 (Workflow Templates)
1. **完整产品研发 (`full-product-launch`)**：全套 11 道工序，适用于从 0 到 1 的全新产品孵化。
2. **快速功能迭代 (`fast-iteration`)**：6 道工序（`05 -> 06 -> 07 -> 08 -> 09 -> 11`），跳过前期市场验证，直接从需求定义开始。
3. **紧急热修复 (`hotfix`)**：3 道工序（`07 -> 08 -> 09`），针对线上重大缺陷，仅覆盖开发、测试、上线。

---

## 三、关键作业红线与不可违背原则

参与 ModuFlow 任务的智能体必须**严格遵守**以下红线：

### 1. 【工序 01 市场研究】实战对抗红线
- 拒绝学院派宏观报告，必须用自下而上模型算清首年可拿下的现实盘子 (SOM)。
- 必须拆解头部竞品在 TikTok/Reels/Shorts/Reddit 上的 3 秒视觉钩子。
- 必须深挖近 3 个月 1-2 星差评，找准竞品软肋。

### 2. 【工序 03 产品方向决策】严禁未验先定
- 本工序仅定位为“一页纸精益方向决策”，**严禁提前编写代码级 Schema、TypeScript/JSON 接口字段或 Gherkin 详细用例**（这些细节必须留到工序 05 经过市场验证后再写）。
- 向下游穿透指令必须准确指向「工序 04：低成本市场验证」，严禁错标为 UI 或架构。

### 3. 【工序 04 低成本市场验证】真交付网页红线
- 拒绝纯纸面方案。必须在当前工作区目录下同步创建并写入一个零外部依赖、高颜值的移动端可交互 H5 假门测试着陆页 `index.html`。
- 落地页必须包含：核心功能交互模拟器、痛点对比、三选一伪付费抽屉以及点击后的优雅坦白早鸟内测弹窗 (Graceful Reveal)。

### 4. 【工序 05 产品立项与需求定义】反幻觉最高铁律 + 完整 7 大章节工程级 PRD
- **绝对禁止凭空捏造**任何未在人类指令中明确提供的实盘投放花费、CTR、早鸟邮箱数量或录屏结论。
- 若人类未提供外部实测数据，必须以「外部实测数据未录入声明：待回填立项评估框架 + 完整 MVP PRD 基线」口径输出，所有实测指标标注为 `[待回填实测值 | 目标基准: xxx]`。
- **严禁将 PRD 缩水为几行简表**：精益字数限制仅适用于立项前的 `01~04` 工序；进入工序 `05` 后，必须一次性完整输出 **7 大标准章节的工程级 PRD**（①立项评估与 In/Out-of-Scope 范围封版、②全局信息架构 IA 与 Mermaid 状态流转图、③逐模块/逐页面详细功能规格 M1~M6 全量展开、④完整数据字典与 JSON/SQLite/Keychain/RemoteConfig 契约、⑤商业化计费与权限状态机、⑥全链路数据埋点字典 Tracking Plan、⑦非功能性需求与全量 Gherkin 验收标准 AC-01~AC-08+），供工序 `06 设计实现` 与 `07 开发实现` 直接照单施工。

### 5. 【全局交付物格式】去噪音与双层架构
- 交付物置顶必须为 `## 负责人 30 秒拍板摘要卡 (Executive Gate)`。
- 紧随其后为 `## 完整执行细节 (Execution Reference)`。
- **杜绝任何花哨的 emoji 或无意义图标干扰**。

---

## 四、技术架构与代码实现

### 1. 技术栈选型
- **后端**：Python 3.10+, FastAPI, SQLAlchemy 2.0 (AsyncIO), aiosqlite, Pydantic v2
- **前端**：React 18, Vite, TypeScript, Tailwind CSS, Lucide React, KaTeX (LaTeX 数学公式), Mermaid.js
- **存储**：SQLite 数据库 (`data/moduflow.db`) + 磁盘持久化隔离工作区 (`data/workspaces/`)
- **测试**：Pytest, pytest-asyncio, HTTPX

### 2. 后端核心子系统 (`backend/app/`)
```
backend/app/
├── adapters/                 # AI 执行适配层
│   ├── base.py               # BaseAgentAdapter 抽象基类
│   ├── cli_adapter.py        # 原生 CLI 适配器 (agy / claude / cursor)，注入工序红线
│   ├── simulator_adapter.py  # 智能离线模拟适配器
│   └── factory.py            # 适配器工厂
├── api/
│   └── endpoints.py          # RESTful API 端点 (战略、产品、运行、工序、会话、产物、Issue、驾驶舱)
├── core/
│   ├── config.py             # 全局配置 (数据库 URL、工作区根目录、引擎类型)
│   └── database.py           # 异步 SQLAlchemy Engine 与 SessionLocal
├── mcp/
│   └── role_mcp_server.py    # 角色级隔离的 Stdio JSON-RPC 2.0 MCP Server (8 大角色专属工具箱)
├── models/
│   └── entities.py           # 核心 ORM 实体 (Initiative, Product, ModuleInstance, Artifact, Issue 等)
├── schemas/
│   └── all_schemas.py        # Pydantic 契约模型
└── services/
    ├── workflow_engine.py    # 模板管理与工序实例化引擎
    ├── workspace_sync.py     # 数据库与本地工作区双向文件同步器
    ├── agent_roles.py        # 8 大专业智能体角色定义与工序职责映射
    ├── skill_mcp_mounter.py  # 角色专属 Skill (.agents/skills/) 与 MCP (.agents/mcp_config.json) 动态挂载器
    ├── agent_runner.py       # 多阶段推演调度器 (context -> spawning -> reasoning -> completed)
    ├── stale_checker.py      # 上下游基线变更追踪与过时预警检查器
    ├── diff_engine.py        # 产物版本 Diff 生成与下游受影响推演
    ├── bundle_storage.py     # HTML 原型包解压与静态预览资源托管
    └── market_research_engine.py # 全球赛道研究、TAM/SAM/SOM 测算与竞品分析
```

### 3. 8 大 Agent 角色独有 Skill 与 MCP 动态挂载机制

为了避免所有工序共享大杂烩上下文，ModuFlow 实现了**按工序角色物理隔离的 Skill 与 MCP 动态挂载机制**（由 `backend/app/services/skill_mcp_mounter.py` 驱动）：

- **物理隔离挂载路径**：在每个工序的独立工作区目录（`data/workspaces/{initiative_id}/products/{product_code}/{run_name}/{stage_dir}/`）下，仅挂载当前工序**主责 Agent** 与**协同 Agent** 对应的 Skill 和 MCP Server：
  - `.agents/skills/{skill_name}/SKILL.md`（及 `scripts/` 可执行工具脚本）：供 Antigravity (`agy`) 自动发现并按需激活。
  - `.agents/mcp_config.json` 与 `.mcp.json`：供 `agy` / `claude` CLI 在当前工作区启动时自动连接角色专属的 Stdio MCP Server (`backend/app/mcp/role_mcp_server.py --role <role_code>`)。

| 角色代码 | 角色名称 | 独有 Skill 包 (`backend/skills/{role}/`) | 独有 MCP Server (`moduflow-{role}-mcp`) 核心工具 |
| :---: | :--- | :--- | :--- |
| **`mr`** | 市场研究 Agent | `mr-global-market-intelligence` | `calculate_bottom_up_som`, `query_regional_benchmark` |
| **`ba`** | 商业分析 Agent | `ba-unit-economics-calculator` | `simulate_ltv_cac_payback`, `stress_test_pricing_ladder` |
| **`pm`** | 产品经理 Agent | `pm-lean-prd-architect` | `audit_stage_guardrails`, `validate_hypothesis_matrix` |
| **`mkt`** | 增长营销 Agent | `mkt-fake-door-growth-engine` | `verify_fake_door_landing_page`, `allocate_test_budget` |
| **`ux`** | 设计用研 Agent | `ux-hig-safearea-inspector` | `check_ios_safe_area_and_touch_targets`, `generate_design_tokens` |
| **`eng`** | 研发架构 Agent | `eng-zero-inference-arch-guard` | `audit_zero_client_inference_cost`, `inspect_workspace_code_tree` |
| **`qa`** | 测试保障 Agent | `qa-release-gatekeeper` | `query_blocking_issues_gate`, `audit_store_compliance_4_3` |
| **`ops`** | 数据运营 Agent | `ops-retention-funnel-analyzer` | `diagnose_retention_curve`, `prioritize_v1_1_backlog` |

### 4. 前端核心页面与组件 (`frontend/src/`)
```
frontend/src/
├── pages/
│   ├── Dashboard.tsx         # 战略驾驶舱：投资组合、财务现金流看板、风险预警与 CEO 决策流
│   ├── WorkflowView.tsx      # 产品工作台：11 道工序流水线看板、阶段状态与阻断门禁
│   ├── ModuleSpace.tsx       # 工序人机协作空间：左侧讨论与生成、右侧双栏交付物看板与版本树
│   └── IssueBoard.tsx        # 全局协同问题看板：缺陷跟踪、跨工序路由与阻断性处理
├── components/
│   ├── Navbar.tsx            # 上下文动态感知导航栏
│   ├── Sidebar.tsx           # 左侧全局折叠菜单
│   ├── MarkdownViewer.tsx    # GFM Markdown + KaTeX + 双层拍板折叠渲染
│   ├── MermaidDiagram.tsx    # 架构与流程图渲染器
│   └── StatusBadge.tsx       # 状态与缺陷等级徽章
└── services/
    └── api.ts                # 前端统一 Axios/Fetch API 客户端
```

---

## 五、开发者与智能体常用命令

### 1. 运行系统
```bash
# 一键并发启动前后端服务
./run.sh
```
- Web 前端控制台：`http://localhost:5173`
- FastAPI Swagger 接口文档：`http://127.0.0.1:8000/docs`

### 2. 自动化测试
```bash
# 运行后端全量异步测试 (21项全绿)
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/ -v

# 单独运行指定测试套件
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_api.py -v
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_optimization.py -v
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_market_research.py -v
```

### 3. 前端编译与校验
```bash
cd frontend && npm run build
```

### 4. 数据库与模板同步
```bash
# 重新同步工作流模板与角色定义
PYTHONPATH=. backend/.venv/bin/python scripts/seed.py
```
