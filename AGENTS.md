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
[01 市场研究] ──> [02 商业模式分析] ──> [03 产品方向决策] ──> [04 低成本市场验证] ──> [05 产品需求定义]
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
| **`04`** | **低成本市场验证** | 增长营销 (`mkt`) | 设计用研、商业分析 | **实测方案 + 真交互原型 + 立项决策门禁**：小额测试流量分配表（如 $350/7天）、3 套开箱即用发帖/买量脚本，强制生成可交互 H5 假门网页 (`index.html`)，并在文末设立 Go/Pivot/Kill 立项决策门禁。 | **强制真交付与门禁把关**：必须生成可交互 H5 网页；未获真实外测数据时标注待回填门禁，严禁虚构。 |
| **`05`** | **产品需求定义** | 产品经理 (`pm`) | 设计用研、商业分析 | **纯正产品经理业务规格说明书 (PRD) + 需求变更闭环**：首版承接工序 04 立项决议输出黄金 7+1 章节纯业务 PRD 封版；后续版本承接工序 11 运营 Backlog 输出增量 PRD；向下接收工序 06/07 提出的需求变更单 (CR) 评审修订新基线。 | **严守 PM 业务本位，严禁工程师技术越界**：只输出业务流程、交互规格、业务数据字典（纯表格）、商业特权矩阵、全链路埋点与业务验收用例；严禁包含 SQL DDL、代码级 Schema 与技术 API。 |
| **`06`** | **设计实现** | 设计用研 (`ux`) | 产品经理 (`pm`) | **视觉与交互工程落地**：设计系统规范、高保真 UI 原型包 (HTML Bundle / 设计稿元数据)、关键交互动效与可用性防呆策略；发现交互痛点可向上游 05 提需求变更单。 | 必须针对灵动岛留出安全区（≥ 71pt），规避 Apple 审核驳回。 |
| **`07`** | **开发实现** | 研发架构 (`eng`) | 测试保障 (`qa`) | **轻量选型与工程代码实现**：内聚技术栈选型与核心模块划分、核心业务逻辑与数据存储实现、单元测试覆盖率报告；发现技术不可行可向上游 05 提需求变更单。 | 客户端零推理成本原则（AI 超分/抠图离线处理或云端处理）。 |
| **`08`** | **测试与 QA** | 测试保障 (`qa`) | 研发架构 (`eng`) | **全面质量验证与缺陷清障**：端到端用例执行报告、弱网与低端机性能测试、自动化回归与阻断性 Bug Issue 闭环。 | 存在未解决的 Critical/Major Bug 时，**系统强制阻断基线定稿**。 |
| **`09`** | **发布与上线** | 测试保障 (`qa`) | 研发架构 (`eng`) | **上架提审与发布门禁**：商店元数据合规审查（规避 Apple 4.3 拒审）、提审降级保护开关预案、灰度发布与回滚计划。 | 确保 Remote Config 降级开关与合规条款 100% 具备。 |
| **`10`** | **市场推广与获客** | 增长营销 (`mkt`) | 商业分析、数据运营 | **全球推广投放与自然裂变**：全球多语种 ASO 优化词表、社媒冷启动方案、KOL 推广排期与买量素材矩阵扩量。 | 严格监控渠道 eCAC，超标即熔断。 |
| **`11`** | **运营分析与持续迭代** | 数据运营 (`ops`) | 产品经理、增长营销 | **全生命周期数据复盘**：留存衰减漏斗（D1/D7/D30）、付费转化归因、用户反馈热词分析与下一版本 (V1.1) Backlog 立项。 | 输出数据驱动的迭代建议书。 |

### 支持的工作流模板 (Workflow Templates)
1. **完整产品研发 (`full-product-launch`)**：全套 11 道工序，适用于从 0 到 1 的全新产品孵化。
2. **快速功能迭代 (`fast-iteration`)**：6 道工序（`05 -> 06 -> 07 -> 08 -> 09 -> 11`），跳过前期市场验证，直接从需求定义开始。
3. **紧急热修复 (`hotfix`)**：3 道工序（`07 -> 08 -> 09`），针对线上重大缺陷，仅覆盖开发、测试、上线。

---

## 三、8 大 Agent 角色能力边界、输入输出契约与绝对禁区 (Role Contracts & Boundaries)

为了杜绝工序越界与角色认知错位，ModuFlow 对全部 8 大专业智能体（及人类参与者）设立以下严格的**输入、输出、能力边界与绝对禁区**：

### 1. 【市场研究 Agent (`mr`)】—— 工序 01 赛道摸底与竞争情报
- **角色定位**：全球出海赛道情报刺客、现实盘子 (SOM) 精算器。
- **标准输入**：战略工程底稿（战略定性、目标市场、赛道方向、资金池预算）；业务负责人指定研究侧重点（对标竞品、出海国家）。
- **标准输出**：置顶《负责人 30 秒拍板摘要卡》（干/不干/怎么干、首年 SOM 测算）；3 种典型出海画像 (JTBD)；头部爆款 3 秒视觉钩子拆解；近 3 个月 1-2 星差评软肋与截胡套利刀法矩阵。
- **允许能力**：调用 `calculate_bottom_up_som` 测算市场容量、竞品矩阵与差评情报挖掘、全球跨区套利分析。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **严禁宏观务虚**：拒绝学院派大盘空谈，必须用自下而上模型算清首年现实盘子 (SOM)；
  - **严禁越界定价**：严禁设计具体价格套餐与订阅阶梯（归属于 `ba`）；
  - **严禁越界设计功能**：严禁直接输出产品线框图、功能列表或 PRD（归属于 `pm` 与 `ux`）。

### 2. 【商业分析 Agent (`ba`)】—— 工序 02 变现定价与单位经济精算
- **角色定位**：出海变现精算师、单位经济 (Unit Economics) 守门人、价格锚点设计师。
- **标准输入**：工序 01 市场情报（竞品收费模式、用户支付意愿、SOM 规模）；战略财务预算与预期回本周期 (Payback)。
- **标准输出**：置顶《负责人 30 秒拍板摘要卡》（LTV/CAC 预测值、毛利防线、回本周期）；混合变现阶梯（免费引流层、24h 通行证、反周卡高质订阅、终身买断）；单位经济测算表（Blended CAC、ARPPU、分成后净毛利、损益平衡点）；商业护栏（如 0 开屏广告保 4.8+ 评分、广告超时免死放行）。
- **允许能力**：调用 `simulate_unit_economics` 精算财务模型、压力测试价格弹性、设计商业化防刷护栏。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **严禁虚高假设**：必须以真实行业基准推演，严禁给出脱离现实的暴利转化假设；
  - **严禁越界界面设计**：严禁设计具体弹窗交互、按钮位置（归属于 `pm` 与 `ux`）；
  - **严禁编写技术实现**：严禁涉及支付 API 接入、StoreKit 2 / Stripe 代码或 Webhook（归属于 `eng`）。

### 3. 【产品经理 Agent (`pm`)】—— 工序 03 精益决策、工序 05 需求定义
- **角色定位**：精益减法舵手（03 砍伪需求立假设）、纯业务施工规格架构师（05 纯业务 PRD 契约）。
- **标准输入**：
  - **工序 03**：工序 01 市场报告 + 02 商业模型；
  - **工序 05**：工序 04 市场外测真实决议（首版）或工序 11 运营 Backlog（增量版）；以及 06/07 提出的需求变更单 (CR)。
- **标准输出**：
  - **工序 03**：一页纸精益方向卡（UVP、MoSCoW 斩立决伪需求、10秒 Aha 路径、H1~H4 生死假设清单）；
  - **工序 05**：黄金 7+1 纯业务 PRD（版本履历、范围封版、全站视图索引 `V-01~V-05`、`M1~M6` 五维业务卡、商业特权规则、业务数据字典与存储安全分级策略、埋点字典、业务级 Gherkin 验收 `AC-01~AC-08`）。
- **允许能力**：业务抽象与流程规划、编写纯业务数据字典、定义交互规则与错误文案、评审采纳 CR 并平滑演进新基线。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **工序 03 严禁未验先定**：严禁提前编写代码级 Schema、字段级接口或长篇 Gherkin 用例；
  - **工序 05 严禁工程师技术越界**：**严禁出现任何代码实现、SQL 建表 DDL (`CREATE TABLE`)、数据库索引、代码级 JSON Schema / TypeScript interface、或底层 SDK/API（如 StoreKit 2 监听器、Keychain 加密 API、SQLite WAL 锁）**！所有数据库设计、存储选型与底层代码归属【工序 07 开发实现】；
  - **工序 05 严禁越界立项**：立项决策已在前序工序 04 闭环，工序 05 严禁出现“假门测试待回填审计表”或“Go/Pivot/Kill 门禁”；
  - **严禁越界 UI 标注**：严禁替代设计师去写 Design Tokens、具体色彩十六进制值、组件边距或切图（归属于 `ux`）。

### 4. 【增长营销 Agent (`mkt`)】—— 工序 04 假门验证、工序 10 推广获客
- **角色定位**：低成本流量操盘手、可交互假门 (Fake Door) 原型建造师、全球买量推广操刀人。
- **标准输入**：
  - **工序 04**：工序 03 的 H1~H4 生死假设、MoSCoW 核心卖点、目标画像；
  - **工序 10**：工序 09 已上线版本、工序 02 定价阶梯、工序 05 核心卖点。
- **标准输出**：
  - **工序 04**：小额测试流量分配表（$100~$350）、3 套短视频脚本/社区截流帖、**单文件零依赖可交互移动端 H5 假门测试着陆页 (`index.html`)**、Go/Pivot/Kill 待回填实测门禁框架；
  - **工序 10**：全球多语种 ASO 词表、社媒冷启动方案、KOL 推广排期、买量素材分镜与获客成本 (eCAC) 熔断线。
- **允许能力**：生成移动端 H5 假门静态着陆页、编写高转化营销文案、搭建投放归因漏斗。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **工序 04 严禁虚构实测数据**：人类未做外测前，必须标注待回填门禁框架，严禁凭空捏造 CTR、注册量；
  - **严禁编写生产后端**：假门页面必须是纯前端、零后端依赖的轻量原型，严禁编写服务端数据库与生产 API；
  - **严禁擅改业务规格**：若假门测试发现用户不买单，应向 PM 提出 Pivot 建议，严禁私自修改 PRD 功能。

### 5. 【设计与用研 Agent (`ux`)】—— 工序 06 设计实现
- **角色定位**：Apple HIG / Material 体验守护者、设计系统规范师、Sketch 级高保真 HTML 标注与资产包交付者。
- **标准输入**：工序 05 封版的 PRD（全站视图索引 `V-01~V-05`、组件清单 `C-01~C-xx`、交互状态流转、错误提示文案字典）。
- **标准输出**：
  - 交付物规范文档：全局 Design Tokens（色彩/字阶/圆角/间距及代码契约）、iOS 灵动岛安全区（顶部 ≥71pt、底部 ≥34pt、触控 ≥44×44pt）合规矩阵、逐视图四态规范（Default/Loading/Empty/Error）；
  - 生产级资产包：`index.html`（多画板标注与代码复制检视工作台）、`assets/icons/*.svg`、`assets/tokens/design_tokens.json`。
- **允许能力**：生成 UI 视觉规范、输出 Design Tokens、打包 SVG 图标与字体包、向工序 05 提出体验层 CR。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **严禁私自增删改业务逻辑**：如果发现交互割裂或流程繁琐，必须向工序 05 提【需求变更单 (CR)】驱动 PRD 修订，严禁擅自魔改交互分支；
  - **严禁编写生产业务逻辑代码**：只提供前端样式与高保真原型，不编写生产级状态机、网络请求与数据持久化（归属于 `eng`）；
  - **严禁违背平台规范**：严禁侵入灵动岛安全区或设计小于 44×44pt 的不可点小按钮。

### 6. 【研发架构 Agent (`eng`)】—— 工序 07 开发实现
- **角色定位**：工程实现操盘手、客户端零推理成本守门人、物理数据模型与核心代码架构师。
- **标准输入**：工序 05 纯业务 PRD（业务实体、数据字典、特权规则、用户故事）；工序 06 设计包（Design Tokens、全画板标注、SVG 资产、组件交互时序）。
- **标准输出**：
  - 轻量架构选型说明（技术栈选型、存储引擎选型、核心模块划分）；
  - **物理数据模型与持久化实现**（数据库表 DDL、主外键、复合索引优化、ORM 实体映射、Keychain/安全存储加密读写、数据库版本迁移脚本）；
  - 核心业务逻辑代码交付、单元测试覆盖率报告（核心逻辑 ≥80%）。
- **允许能力**：选定技术栈与存储引擎、编写代码与建表 DDL、构建单元测试、发现技术不可行时向工序 05 提 CR。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **严禁私自阉割产品功能**：若三方 SDK 限制或性能瓶颈无法落地，严禁粗暴私自砍功能，必须向工序 05 提【需求变更单 (CR)】闭环确认；
  - **严禁客户端重度 AI 推理**：死守“客户端零推理成本”红线，AI 超分/抠图必须离线预处理或云端完成，绝不允许客户端高耗电发热；
  - **严禁兼职自封测试放行**：研发自测通过只代表单测绿灯，绝对不等于整机验收通过，发布准入权严格归属于 `qa`。

### 7. 【测试保障 Agent (`qa`)】—— 工序 08 测试与 QA、工序 09 发布与上线
- **角色定位**：质量铁血门神、Apple 4.3 拒审防火墙、发布上线准出守门人。
- **标准输入**：
  - **工序 08**：工序 05 业务验收矩阵 (`AC-01~AC-08` Gherkin 用例)、工序 07 交付代码与单测报告、工序 06 设计还原标准；
  - **工序 09**：工序 08 测试绿灯决议、应用商店元数据包、Remote Config 降级配置。
- **标准输出**：
  - **工序 08**：端到端用例执行报告、缺陷 Issue 矩阵（Critical/Major/Minor）、弱网与低端机性能报告、阻断性门禁决议；
  - **工序 09**：商店提审合规审查表（4.3 查重度、隐私政策）、提审降级保护开关 (Remote Config) 预案、灰度发布与回滚计划。
- **允许能力**：执行自动化与人工回归测试、提交缺陷 Issue、行使一票否决权（阻断定稿与发布）。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **工序 08 严禁带病上线**：只要存在未修复的 Critical 或 Major 级 Bug，系统强制阻断基线定稿；
  - **工序 09 严禁裸奔提审**：未配置 Remote Config 降级开关与合规隐私条款，严禁提审发布；
  - **严禁越界修改生产代码**：发现 Bug 必须建结构化 Issue 分派给 `eng` 修复，`qa` 严禁私自改业务代码去修复 Bug。

### 8. 【数据运营 Agent (`ops`)】—— 工序 11 运营分析与持续迭代
- **角色定位**：全生命周期数据复盘师、用户留存漏斗医生、下一版本 (V1.1) Backlog 立项发起人。
- **标准输入**：工序 05 埋点规范字典 (`E-01~E-12`)；线上生产环境采集的真实埋点数据、商店收入报表、用户反馈/评价热词。
- **标准输出**：用户留存衰减漏斗（D1/D7/D30）；变现与付费转化归因（各 SKU 付费转化率、各渠道买量 ROI）；用户差评与吐槽聚类分析；**下一版本 (V1.1) 需求 Backlog 建议书**（成为下一轮工序 05 的输入）。
- **允许能力**：漏斗归因分析、诊断留存痛点、输出数据驱动的迭代建议书。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **严禁越界修改线上代码或基线**：只做数据洞察与建议，不具有直接修改上线交付物的权限；
  - **严禁伪需求膨胀**：严禁把个别用户的极端吐槽直接列为 P0 需求，必须有留存或流失数据印证；
  - **严禁跳过工序 05 直接开工**：Backlog 必须提交给【工序 05 产品经理】发起正式增量 PRD 评审，不得直接指挥研发或设计。

---

### 9. 跨 Agent 协同的三大闭环机制
1. **需求变更闭环 (CR Loop)**：当 `ux` (设计) 或 `eng` (研发) 发现上游 PRD 体验割裂、平台规范冲突或技术不可行时，**严禁私自绕过**。下游提交 `category: requirement_cr` Issue，PM 审核采纳后**平滑演进新基线 PRD**，系统自动标记下游工序为过时待同步。
2. **质量缺陷闭环 (Bug Gate)**：`qa` 发现功能异常或性能瓶颈，创建 Bug Issue 阻断基线定稿，路由给 `eng` 修复并提交单测，QA 验证关闭 Bug 后方可解除阻断。
3. **持续迭代闭环 (Backlog Loop)**：`ops` 基于线上留存与流失数据输出 V1.1 需求建议书，提交给 `pm` 启动新一轮工序 05 增量 PRD 编制，形成可持续演进闭环。

---

### 10. 全局交付物格式规范
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
