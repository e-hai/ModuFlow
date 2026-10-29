# ModuFlow 智能体工程与系统架构指南 (AGENTS.md)

> 本文档为参与 **ModuFlow** 项目开发与维护的 AI 智能体（以及人类工程师）提供统一的项目全景、三层架构、工序设计、关口分级、技术架构与作业红线指导。

---

## 一、项目定位与系统核心设计哲学 (Core Mental Model & Architecture)

**ModuFlow** = `Module`（模块化与可插拔）+ `Flow`（战略工序流）。  
专为出海与多产品矩阵设计的 **AI 原生产研与运营平台**。

### 1. 核心设计思想：五元架构模型 (Five-Element Mental Model)
ModuFlow 的底层运转秩序由五个最本质的业务要素咬合而成：
> **「阶段负责组织业务，任务负责组织工作，Agent 负责执行与协作，产物负责共享上下文，用户负责方向与关键决策。」**

```
┌────────────────────────────────────────────────────────────────────────┐
│  👤 用户 (User)       ── 负责战略方向、资源注资与重大关口拍板 (🔴/🟡)  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ 设定目标与授权包
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  🏁 阶段 (Stages)     ── 组织宏观业务流程 (11 道标准出海产研工序)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ 触发与编排
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  📋 任务 (Tasks)      ── 组织具体执行单元 (异步独立作业队列 / CR)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ 派发与认领
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  🤖 Agent (智能体)    ── 专业执行与多角交叉协作 (动态挂载专属工具箱)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ 交付与固化
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  📦 产物 (Artifacts)  ── 承载物理基线，单向流动共享上下文 (唯一真理源) │
└────────────────────────────────────────────────────────────────────────┘
```

1. **阶段 (Stages) 负责组织业务**：定义商业与产研的宏观演进里程碑（01 赛道摸底 → 02 变现精算 → 04 假门外测 → 05 需求定义 → 09 提审发布），绑定各工序准入准出与质量门禁（Gate），解决“业务走到哪一步”。
2. **任务 (Tasks) 负责组织工作**：定义高内聚、解耦的具体执行单元（如计算 SOM、验证 H5、审查 CR），通过独立进程执行器（`backend.app.runner`）与持久化队列（`orchestration_jobs`）异步推进，支持心跳守护、重试与超时保护，解决“这一刻具体干什么”。
3. **Agent (智能体) 负责执行与协作**：具备特定专业视角与排他职权的执行实体（9 大专业角色 + 1 项目总控），动态挂载专属 Skill/MCP 工具箱并在物理沙箱中运行，完成跨角色交叉审查与闭环协作，解决“由谁来执行与协同”。
4. **产物 (Artifacts) 负责共享上下文**：全平台唯一的真理源（Single Source of Truth），坚决杜绝依赖易退化、易遗忘的聊天会话传递记忆。上游以物理文件（Markdown 报告、`delivery.manifest.json`、HTML 原型、代码包）单向固化注入下游，解决“智能体之间如何消除信息差与防止幻觉”。
5. **用户 (User) 负责方向与关键决策**：人类拥有无可替代的战略主权。从琐碎的提示词催促与排查中解脱，退到最高维度的驾驶舱，专注掌控“立项注资（授权包）、关键关口拍板（黄级批量审批、红级必须签字）、生死方向转向（Go/Pivot/Kill）”，解决“做不做、行不行、发不发”。

### 2. 三层治理架构体系 (Three-Tier Governance)
系统全面采用 **「人类战略层 → 项目总控层 (lead) → 专业执行层」** 三层架构体系：

```
                    ┌────────────────────────────────────────┐
                    │      人类战略层 (Human Strategic Tier)    │
                    │  • 立项与关闭决策    • 投资组合与资金调配  │
                    │  • 授权包 (YAML)   • 红级关口 (🔴 审批) │
                    │  • 商店/生产凭证持有  • 影子模式放权控制   │
                    └───────────────────┬────────────────────┘
                                        │ 注入只读 authorization.yaml
                                        ▼
                    ┌────────────────────────────────────────┐
                    │       项目总控层 (Project Tier / lead)   │
                    │  • 工序调度与派活    • 交付物交付交接检查   │
                    │  • 低风险 CR 仲裁   • 整理关口申请单与日报 │
                    │  • 影子决策建议     • 受 6 大硬红线严密约束│
                    └───────────────────┬────────────────────┘
                                        │ 调度分配与工序推进
                                        ▼
    ┌────────────────────────────────────────────────────────────────────────┐
    │                 专业执行层 (Execution Tier / 9 大专业 Agent)            │
    │  [mr 市场研究]   [ba 商业分析]   [pm 产品经理]   [mkt 增长营销]  [ux 设计用研]  │
    │  [eng 研发架构]  [qa 测试保障]   [ops 数据运营]  [cmp 合规风控]                 │
    │  • 物理隔离工作区   • 动态挂载专属 Skill/MCP   • 权限拦截器实时防护        │
    └────────────────────────────────────────────────────────────────────────┘
```

### 3. 三层权责边界划分与红线原则
1. **人类战略层 (Human Strategic Tier)**：
   - **专属核心权力**：战略工程立项、总体预算与单阶段预算注资、硬止损阈值设定、黄级/红级关口审批（尤其是 G1、G2、G4、G5）、商店开发者账号与生产支付/数据库真实凭证持有。
   - **绝对防线**：任何 Agent（包括 lead）绝不可修改授权包、批准预算上调或持有生产级凭证。
2. **项目总控层 (Project Tier / `lead`)**：
   - **定位**：每个项目具备独立团队实例，由 `lead` 统一协调与监督。
   - **核心职责**：根据 11 道工序编排推进、向下游派发任务、校验交付物与交接物完整性、对低风险需求变更 (CR) 进行仲裁、每日输出项目简报 (`daily_digest`)、为人类整理一页纸关口申请单。
   - **运行模式（影子模式 Shadow Mode）**：系统默认开启影子模式，`lead` 对黄/红关口仅输出建议并记录与人类决策的一致率，供后续信任评级；关闭影子模式必须由人类账号显式操作。
3. **专业执行层 (Execution Tier / 9 大专业角色)**：
   - 包括：`mr`, `ba`, `pm`, `mkt`, `ux`, `eng`, `qa`, `ops`, `cmp`。
   - 每个工序处于独立物理工作区目录，仅动态挂载当前工序角色专属的 Skill 与 MCP 工具箱。
   - 严格遵循输入输出契约与红线禁区，所有越权行为（如跨角色改价、越权写授权包）被系统底层物理拦截。

### 4. 确定性止损与熔断机制 (Zero-LLM Circuit Breaking)
- **代码级硬拦截**：预算超限检查、时限超期检查、退出条件 (`kill_criteria`) 命中检查、`lead_forbidden` 禁区拦截**绝不交给 LLM 模糊判断**，必须由独立的确定性安全脚本 (`authorization_engine.py`) 执行。
- **自动熔断行为**：一旦命中止损或违规行为，系统立即将项目状态自动置为 `paused`，持久化审计记录至 `decisions/` 目录，生成 🔴 Critical 告警，并彻底阻断后续工序派活。

---

## 二、授权包体系与项目 Profile 参数化 (Authorization & Profile)

### 1. 授权包规范 (Authorization Package)
- **规范标准**：符合 JSON Schema 2020-12 规范 (`schemas/authorization-package.schema.json`)，每个项目必须在 `data/workspaces/{initiative_id}/products/{product_code}/authorization.yaml` 具备合法授权包。
- **立项前置校验**：立项与工序 01 启动前，必须通过 `scripts/validate_authorization.py` 严格校验：
  - `budget.total_budget_usd` 与 `budget.stage_allocations` 精确平衡；
  - `hard_stop_loss_usd` 必须大于或等于总预算；
  - `deadline` 必须晚于 `start_date`；
  - `lead_forbidden` 必须完整包含 6 项必选禁止行为；
  - 缺失或非法授权包的项目拒绝开工并给出明确迁移指引。
- **只读保护与防篡改**：
  - 授权包文件、平台规范区 (`/platform/`)、角色模板在操作系统层面强制设为只读 (`0o444`)；
  - 后端安全防护层 (`security_guard.py`) 实时拦截任何 Agent 对受保护文件的写入调用；
  - CLI Agent 运行时的文件系统沙箱 (`workspace_sandbox.py`) 有两层：
    - macOS 上用 `sandbox-exec` 限制写入范围，只能写本工序目录、临时目录和 CLI 自身的状态目录；工序目录里挂载的 Skill 与 MCP 配置仍然只读。后端本身已在沙箱里时无法嵌套，会自动退到下一层；`settings.AGENT_FS_SANDBOX="off"` 可关闭这一层。
    - 每次运行后做完整性校验：授权包、`decisions/` 已有文件、已挂载 Skill 与 MCP 配置若被改动，会自动还原，本次交付物作废，并按越权写入留痕、生成 🔴 告警。
  - 授权包修改必须由人类发起，修改动作全量记录在 `decisions/` 决策日志中。

### 2. 项目 Profile 参数化 (Platform & AI Profile)
ModuFlow 支持精细化的项目 Profile 驱动，杜绝全局一刀切：
- **`platform: cross_platform | ios | android`**：新建产品默认 `cross_platform`，iOS 与 Android 两端都要交付。
  - **双端项目（默认）**：工序 06 同时检查 HIG 与 Material 3。交付物里要同时有 iOS 实测值（灵动岛顶部 ≥71pt、底部 ≥34pt、触控 ≥44×44pt）和 Android 实测值（状态栏/挖孔 ≥24dp、触控 ≥48×48dp）。缺一端不能放行。提审同时覆盖 Apple 4.3 与 Google Play 政策。
  - **iOS 项目**：只挂载 `check_hig.py` 与 HIG 规范。
  - **Android 项目**：只挂载 `check_material.py` 与 Material 3 规范。**Android 项目严禁触发任何 iOS 专属检查**。
- **`client_zero_inference: bool`**：
  - **`true` (默认纯客户端/工具类)**：死守“客户端零推理成本”红线，客户端代码中严禁包含模型推理调用，AI 超分/抠图等必须离线预处理或云端完成。
  - **`false` (端侧 AI 友好型)**：允许在边缘端运行轻量化离线模型（如 CoreML / ONNX Runtime 端侧推理）。
- **角色人设也跟随 Profile**：`ux` / `eng` / `qa` 的静态人设不写死平台阈值，上下文装配时由 `agent_roles.render_persona` 追加【本项目 Profile 红线】，阈值与 `deliverable_audit.py` 一致。

---

## 三、标准产研 11 道工序与关口分级模型 (11-Stage Pipeline & Gate Classification)

### 1. 11 道核心工序架构全景
```
[01 市场研究] ──> [02 商业模式分析] ──> [03 产品方向决策] ──> [04 低成本市场验证] ──> [05 产品需求定义]
                                                                                               │
   ┌───────────────────────────────────────────────────────────────────────────────────────────┘
   ▼
[06 设计实现] ──> [07 开发实现] ──> [08 测试与 QA] ──> [09 发布与上线] ──> [10 市场推广与获客] ──> [11 运营分析与持续迭代]
```

### 2. 关口分级模型 (Gate Levels: 🟢 / 🟡 / 🔴)
- 🟢 **绿级 (Green)**：`lead` 自行审批（影子模式下仅输出建议），事后由人类抽查审计。
- 🟡 **黄级 (Yellow)**：人类批量审批，由 `lead` 聚合一页纸关口申请单推入人类待办流。
- 🔴 **红级 (Red)**：人类即时必须审批，系统物理阻断工序流转，触发即时通知与决策留痕。

| 工序编号与名称 | 关口代号 | 级别 | 审批决策人 | 准入/放行关键条件 |
| :---: | :---: | :---: | :---: | :--- |
| **`01 市场研究`** | 门禁自检 | 🟢 | `lead` | 包含自下而上 SOM 测算与明确“干/不干/怎么干”建议；所有数字必须附带 source 或注明“假设/待验证”。 |
| **`02 商业模式`** | LTV/CAC | 🟡 | 人类审批 | LTV/CAC 预测值 ≥ 3.0 且回本周期处于预算范围内；若 < 3.0 系统自动阻断暂停。 |
| **`03 方向决策`** | **G1 立项方向** | 🟡 | 人类审批 | 输出一页纸精益方向卡；合规 Agent (`cmp`) 初筛无红灯。 |
| **`04 假门验证`** | **G2 外测决议** | 🟡 | 人类审批 | 必须包含可交互 H5 网页；外测数据必须来自真实埋点（严禁虚构）；若触碰 Kill 阈值系统自动暂停。 |
| **`05 需求定义`** | prd_linter | 🟢 | `lead` | PRD Linter 评分 100 分通过；**若涉及支付、用户隐私或数据字典结构变更，自动升为 🔴**。 |
| **`06 设计实现`** | HIG/Material | 🟢 | `lead` | 默认双端：HIG 与 Material 3 都要 100% 通过。profile 为 `ios` 或 `android` 时只跑对应那一端。 |
| **`07 开发实现`** | 覆盖率与推理 | 🟢 | `lead` | 核心逻辑单测覆盖率 ≥ 80%；按 profile 执行零推理合规审计；**若涉及支付或加密密钥处理，自动升为 🔴**。 |
| **`08 测试与 QA`** | **G3 质量门** | 🟢 | `qa` | Critical (P0) 与 Major (P1) 级缺陷全部清零；输出完整端到端执行报告。 |
| **`09 发布上线`** | **G4 提审发布** | 🔴 | **人类必批** | **绝对硬红线：必须有人类显式确认记录，缺失则发布工序物理阻断！** 包含合规表 + 降级开关 + 回滚计划。 |
| **`10 推广获客`** | 买量预算关口 | 🟡 | 人类审批 | 首次买量投放、开拓新国家市场或预算超标；eCAC 超标由脚本执行自动熔断。 |
| **`11 运营迭代`** | Backlog 评审 | 🟢 | `lead` | 形成 V1.1 需求建议书并推入工序 05；若涉及大版本重构或超额预算，自动升为 🟡。 |
| **`紧急热修`** | P0 热修关口 | 🔴 | **人类必批** | 预授权仅允许已验证的紧急配置回滚与降级；**发布后 24 小时内必须补齐 CR、复盘与 PRD 更新**。 |

### 3. 任意时点自动升级 🔴 (Red) 的六大触发条件
无论当前工序原定级别为何，一旦检测到以下情形，系统自动将关口升为 **🔴 红级**并挂起等待人类签字：
1. **真实货币支付**：涉及支付接口、内购定价阶梯变更、Stripe/StoreKit 代码或 Webhook；
2. **隐私与数据合规**：涉及隐私政策修订、用户敏感数据收集（定位、联系人、设备指纹）或跨境数据传输；
3. **安全与密钥体系**：涉及生产数据库 DDL 破坏性变更、Keychain 加密机制或核心业务数据字典调整；
4. **财务预算超支**：累计支出超出当前工序授权额度或总预算硬止损线；
5. **权限与架构篡改**：试图修改 `lead` 自身权限、修改红线规则或修改 `authorization.yaml`；
6. **对外公开公关**：对外公开发布市场宣传言论、商店对外公开公告或应用提审声明。

---

## 四、10 大 Agent 角色能力边界、输入输出契约与绝对禁区 (Role Contracts & Boundaries)

ModuFlow 严密定义 **10 大专业智能体**（包括项目总控与合规风控）的职责、能力、输入输出与绝对禁区：

### 1. 【市场研究 Agent (`mr`)】—— 工序 01 赛道摸底与竞争情报
- **角色定位**：全球出海赛道情报刺客、现实盘子 (SOM) 精算器。
- **标准输入**：战略工程底稿（战略定性、目标市场、赛道方向、资金池预算）；人类指定的研究侧重点。
- **标准输出**：置顶《负责人 30 秒拍板摘要卡》（干/不干/怎么干建议、首年 SOM 测算）；3 种典型出海画像 (JTBD)；头部爆款 3 秒视觉钩子拆解；近 3 个月 1-2 星差评软肋与截胡套利矩阵。
- **允许能力**：调用 `calculate_bottom_up_som` 精算市场容量、挖掘差评情报与竞品定价策略。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **严禁宏观务虚**：必须给出自下而上 SOM 现实测算，所有数字必须附带真实数据 source 或明确标注“假设/待验证”；
  - **严禁越界定价**：严禁设计具体价格套餐与订阅阶梯（价格权唯一归属于 `ba`）；
  - **严禁越界设计功能**：严禁直接输出线框图、功能规格或 PRD（归属于 `pm` 与 `ux`）。

### 2. 【商业分析 Agent (`ba`)】—— 工序 02 变现定价与单位经济精算
- **角色定位**：出海变现精算师、单位经济 (Unit Economics) 守门人、**全平台价格唯一来源**。
- **标准输入**：工序 01 市场情报；战略财务预算与回本周期要求。
- **标准输出**：置顶《负责人 30 秒拍板摘要卡》（LTV/CAC 预测值、毛利防线、回本周期）；混合变现阶梯（免费层、24h 通行证、反周卡高质订阅、终身买断）；单位经济测算表；商业护栏（如 0 开屏广告保 4.8+ 评分）。
- **允许能力**：调用 `simulate_unit_economics` 精算模型。调用方填报的假设不能单独决定放行，必须能在工序交付物里复核。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **价格唯一权力来源**：`ba` 是商业定价的唯一合法设定者；`pm`、`mkt` 及任何其他角色严禁篡改工序 02 确定的定价。工序 03~11 的交付物里，凡带定价措辞（订阅、价格、/月等）的金额，必须出现在工序 02 基线里，否则确定性检查不通过（`deliverable_audit.audit_pricing_authority`）。预算、CAC、竞品价格不计入；工序 01 可引用竞品价格；
  - **严禁虚高假设**：必须以真实出海基准推演，严禁输出未经压测的暴利转化指标；
  - **严禁编写技术实现**：严禁编写 StoreKit 2、Stripe SDK 代码或 Webhook（归属于 `eng`）。

### 3. 【产品经理 Agent (`pm`)】—— 工序 03 精益决策、工序 05 需求定义
- **角色定位**：精益减法舵手（03 砍伪需求立假设）、纯业务施工规格架构师（05 纯业务 PRD 契约）。
- **标准输入**：
  - **工序 03**：工序 01 市场报告 + 02 商业模型；
  - **工序 05**：工序 04 真实外测决议（首版）或工序 11 运营 Backlog（增量版）；以及 06/07 提出的需求变更单 (CR)。
- **标准输出**：
  - **工序 03**：一页纸精益方向卡（UVP、MoSCoW 减法、10秒 Aha 路径、H1~H4 生死假设清单）；
  - **工序 05**：黄金 7+1 纯业务 PRD（版本履历、范围封版、全站视图索引 `V-01~V-05`、`M1~M6` 五维业务卡、商业特权规则、业务数据字典纯表格、埋点字典、业务级 Gherkin 验收 `AC-01~AC-08`）。
- **允许能力**：规划业务流程与交互规则、制定数据字典表格、评审采纳 CR 并平滑演进新基线。工序 05 交付物由 `lint_stage_deliverable` / `prd_linter.py` 打分，放行线为 100 分。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **工序 05 严守业务本位，严禁工程师技术越界**：**严禁出现任何 SQL 建表 DDL (`CREATE TABLE`)、数据库索引、代码级 JSON Schema / TypeScript interface、或底层 SDK/API**！所有物理表结构与存储选型严格归属【工序 07 开发实现】；
  - **严禁越界立项**：立项决策已在前序工序 04 闭环，工序 05 严禁出现假门审计表或 Go/Pivot/Kill 门禁；
  - **严禁越界 UI 标注**：严禁替代设计师编写 Design Tokens、具体色彩十六进制值或切图（归属于 `ux`）。

### 4. 【增长营销 Agent (`mkt`)】—— 工序 04 假门验证、工序 10 推广获客
- **角色定位**：低成本流量操盘手、可交互假门 (Fake Door) 原型建造师、全球买量推广操刀人。
- **标准输入**：工序 03 的假设清单与卖点（工序 04）；工序 09 上线版本与 02 定价（工序 10）。
- **标准输出**：
  - **工序 04**：小额测试流量分配表（$100~$350）、3 套推广文案、**单文件零依赖可交互移动端 H5 假门测试着陆页 (`index.html`)**、Go/Pivot/Kill 门禁建议；
  - **工序 10**：全球多语种 ASO 词表、社媒冷启动方案、KOL 推广排期、买量素材分镜与 eCAC 熔断线。
- **允许能力**：生成移动端 H5 假门静态着陆页、用 `verify_fakedoor_h5_bundle` 校验 `index.html`。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **工序 04 严禁虚构实测数据**：人类未做外测前，必须标注待回填门禁框架，严禁凭空编造 CTR 与留资量；
  - **严禁编写生产后端**：假门页面必须是纯前端轻量单页，严禁构建服务端数据库或生产 API；
  - **严禁擅改业务规格**：若外测转化不及预期，应向上游提 Pivot 建议，严禁私自修改 PRD。

### 5. 【设计与用研 Agent (`ux`)】—— 工序 06 设计实现
- **角色定位**：Apple HIG / Material 体验守护者、设计系统规范师、高保真 HTML 标注与资产包交付者。
- **标准输入**：工序 05 封版 PRD（视图索引 `V-01~V-05`、组件清单、交互分支、文案字典）。
- **标准输出**：Design Tokens 规范文档、平台安全区合规矩阵、逐视图四态规范（Default/Loading/Empty/Error）、生产级资产包（`index.html` 标注台、`assets/icons/*.svg`、`design_tokens.json`）。
- **允许能力**：生成 UI 视觉规范、输出 Design Tokens、打包 SVG 图标、向工序 05 提体验层 CR。安全区检查为 `audit_hig_safe_area`（iOS）或 `audit_material_spec`（Android），读取交付物中的实测值。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **严禁私自魔改业务逻辑**：发现交互痛点必须提交需求变更单 (CR) 驱动 PRD 修订，严禁私自增加业务分支；
  - **严禁编写生产代码**：只提供前端样式与高保真原型，不编写生产级状态机与数据持久化（归属 `eng`）；
  - **严禁违反平台安全区**：根据项目 profile 严格留出顶部与底部安全区，触控热区不得小于平台最小规范。

### 6. 【研发架构 Agent (`eng`)】—— 工序 07 开发实现
- **角色定位**：工程实现操盘手、物理数据模型与核心业务代码架构师。
- **标准输入**：工序 05 纯业务 PRD；工序 06 设计资产包。
- **标准输出**：轻量架构选型说明、**物理数据模型与持久化实现**（数据库 DDL、主外键、复合索引、ORM 映射、加密读写、迁移脚本）、核心业务逻辑代码交付、单元测试覆盖率报告（核心逻辑 ≥80%）。
- **允许能力**：技术栈选型、建表 DDL 编写、构建单元测试、发现技术不可行时向工序 05 提 CR。推理审计工具为 `audit_client_zero_inference` 与 `estimate_cloud_marginal_cost`，以工作区代码和审计记录为准。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **严禁私自阉割产品功能**：遭遇技术限制严禁直接砍功能，必须向工序 05 提 CR 闭环确认；
  - **严格遵守项目推理 Profile**：若 `client_zero_inference: true`，严禁在客户端引入重度模型推理；
  - **严禁自封验收放行**：研发单测通过只代表工程就绪，系统发布准入权严格归属于 `qa`。

### 7. 【测试保障 Agent (`qa`)】—— 工序 08 测试与 QA、工序 09 发布与上线
- **角色定位**：质量铁血门神、商店合规防火墙、发布上线准出守门人。
- **标准输入**：工序 05 业务验收矩阵 (`AC-01~AC-08`)、工序 07 交付代码与单测报告、工序 06 设计标准。
- **标准输出**：
  - **工序 08**：端到端用例执行报告、缺陷 Issue 矩阵（P0/P1/P2/P3）、阻断性门禁决议；
  - **工序 09**：商店提审合规审查表（4.3 查重度、隐私条款）、提审降级保护开关预案、灰度发布与回滚计划。
- **允许能力**：执行自动化回归测试、提交缺陷 Issue、行使一票否决权（阻断定稿与提审）。商店合规工具为 `audit_app_store_compliance`，读取质量报告里的 P0/P1 与 Remote Config 记录。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **工序 08 严禁带病上线**：存在未修复的 Critical (P0) 或 Major (P1) Bug 时，系统强制阻断定稿；
  - **工序 09 严禁越权放行**：必须经由人类显式确认记录方可放行提审，缺失则发布工序物理锁定；
  - **严禁直接修改业务代码**：发现 Bug 必须建结构化 Issue 交由 `eng` 修复，`qa` 严禁私改生产代码。

### 8. 【数据运营 Agent (`ops`)】—— 工序 11 运营分析与持续迭代
- **角色定位**：全生命周期数据复盘师、用户留存漏斗医生、下一版本 (V1.1) Backlog 立项发起人。
- **标准输入**：工序 05 埋点字典；线上真实埋点数据、应用商店收入报表、用户评价聚类。
- **标准输出**：用户留存衰减漏斗（D1/D7/D30）、付费转化归因分析、用户反馈聚类、**V1.1 需求 Backlog 建议书**。
- **允许能力**：漏斗归因分析、诊断留存痛点、输出数据驱动的迭代建议书。留存工具为 `diagnose_retention_funnel`，读取交付物中的 D1/D7/D30，不使用内置健康值。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **严禁越界修改线上代码或基线**：仅输出数据洞察，无权修改交付物或代码库；
  - **严禁伪需求膨胀**：严禁把个别极端吐槽列为 P0 需求，必须有留存或流失数据印证；
  - **严禁绕过工序 05 直接开工**：Backlog 必须提交给【工序 05 PM】发起正式 PRD 评审，不得越级指挥研发。

### 9. 【项目总控 Agent (`lead`)】—— 全局调度与质量把控
- **角色定位**：项目执行总指挥、工序调度推进器、交接校验员、低风险 CR 仲裁者。
- **核心输入**：项目授权包 (`authorization.yaml`)、各工序流转状态、交付物检查清单、下游提出的 CR 申请。
- **核心输出**：各工序派活指令、交接完整性审计报告、低风险 CR 仲裁决议、项目每日简报 (`daily_digest`)、一页纸关口申请单。
- **允许能力**：
  - 调度工序流转与指派执行 Agent；
  - 校验工序产物完整性与前置门禁；
  - 仲裁不涉及支付/隐私/数据字典变更的低风险 CR；
  - 在影子模式下记录决策建议与一致率。
  - 不挂载 Skill / MCP，逻辑在 `lead_service.py`。
- 🚫 **严格边界与 6 大硬红线 (Strict Redlines)**：
  1. **不得自批黄级与红级关口**：绝无权批准 G1、G2、G4、G5 关口；
  2. **不得修改自身权限、红线或预算上限**：授权包与安全防护对 lead 绝对只读；
  3. **不得批准支付/隐私相关 CR**：任何触碰货币、隐私、数据结构的 CR 必须由人类裁决；
  4. **不得触发无授权热修**：热修仅允许人类显式授权启动；
  5. **不得批准预算增加**：预算追加权力严格归属人类战略层；
  6. **不得提交商店审核**：G4 提审必须由人类最终签字放行。

### 10. 【合规风控 Agent (`cmp`)】—— 全球法律合规守门人
- **角色定位**：出海法务与平台合规防火墙、合规检查点审计官。
- **检查点覆盖**：
  - **工序 03（立项方向）**：赛道合规性初筛、区域准入限制与合规红线排查；
  - **工序 05（需求定义）**：用户数据隐私流向审计（GDPR/CCPA/COPPA）、区域支付税务合规提示；
  - **工序 09（提审上线）**：商店政策审查（Apple App Store HIG / Google Play Developer Policy）、4.3 查重度防护。
- **核心输出**：标准化合规审计报告，输出三态结论：`pass`（通过）、`needs_fix`（待整改）、`legal_review`（需法务介入）。
- **允许能力**：执行合规规则匹配、扫描敏感数据流、对高风险合规问题发起 **G5 关口自动升级**。不挂载 Skill / MCP，逻辑在 `compliance_engine.py`。
- **接入点**：工序 03/05/09 的合规检查由自动编排和 `can_baseline_module` 自动调用，结论写进关口证据。
 - `legal_review`：交付物带上 `is_compliance_high_risk_related`，关口升为 🔴 G5，并生成 `COMPLIANCE_G5_{工序}` 告警；
 - `needs_fix`：`lead` 审批的绿级工序（如 05）会把整改项发回 Agent 修订；
 - 只要结论不是 `pass`，就必须由人类签字后才能定稿。
- 🚫 **严格边界与禁区 (Redlines)**：
  - **必须包含法定免责声明**：所有合规交付物末尾必须强制声明：`⚠️ 免责声明：本报告由合规 Agent (cmp) 自动化生成，仅供内部合规风险参考，不构成具有法律约束力的正式法律意见。重大法律决策请咨询持牌律师或专业法务团队。`；
  - **高风险一律升级 G5 🔴**：发现重大法律或平台封禁风险，直接触发 G5 关口升级，严禁私自放行；
  - **严禁出具正式法律结论**：不得替代专业执业律师出具法律保证书。

---

## 五、跨 Agent 协同闭环与生命周期治理

### 1. 需求变更闭环 (CR Loop)
- **触发机制**：当 `ux` (设计) 或 `eng` (研发) 发现上游 PRD 体验割裂、平台规范冲突或技术不可行时，下游提交 `category: requirement_cr` Issue。
- **仲裁分流**：
  - *低风险 CR*（仅微调文案、非核心交互）：可由 `lead` 快速仲裁放行；
  - *高风险 CR*（涉及支付阶梯、隐私权限、数据结构）：自动升为 🔴 红级关口，推入人类决策流。
- **基线演化**：PM 审核采纳后**平滑演进新基线 PRD**，系统自动标记下游工序为过时待同步，确保全流程无缝对齐。

### 2. 质量缺陷闭环 (Bug Gate)
- `qa` 发现功能异常或性能瓶颈，创建结构化 Bug Issue（明确复现步骤、预期与实际表现、严重度等级）。
- 若存在 Critical (P0) 或 Major (P1) 级缺陷，系统底层阻断工序基线定稿，强制分派给 `eng` 修复并提交单测；QA 回归验证关闭 Bug 后方可解除阻断。

### 3. 持续迭代闭环 (Backlog Loop)
- `ops` 基于线上真实埋点、D1/D7/D30 留存衰减漏斗与差评聚类分析，输出数据驱动的 V1.1 Backlog 建议书。
- Backlog 提交给 `pm` 启动新一轮工序 05 增量 PRD 编制，形成自我进化的产研闭环。

### 4. 紧急热修 24h SLA 追溯机制 (Hotfix SLA)
- **触发范围**：仅针对线上重大崩溃与阻断性故障启动 `hotfix` 模板（3道工序：07 -> 08 -> 09）。
- **24h 追溯铁律**：热修复版本一旦发布上线，系统在 24 小时内自动创建 3 项闭环追溯任务：
  1. `cr_patch`：补充线上紧急缺陷对应的需求变更单 (CR)；
  2. `postmortem`：撰写线上事故复盘报告（根因分析与防范措施）；
  3. `prd_update`：将热修变更同步并入主干 PRD 基线。
- **超时阻断告警**：若超过 24 小时仍有追溯任务未关闭，系统自动生成 🔴 Critical 级 ExecutiveRisk 告警，锁定后续常规流水线启动权限。

### 5. Portfolio 投资组合层每周一页纸决策看板
- **顶层聚合**：自下而上读取所有项目工作区与数据库指标，横向对比各项目的生命周期阶段、累计花费与剩余预算、核心外测指标（CTR/CAC/留存）与风险状态。
- **一页纸决策建议**：为 CEO/负责人生成结构化的一页纸投资决策周报，明确给出各项目的继续推进 (Go)、方向调整 (Pivot) 或止损关停 (Kill) 建议。
- **硬红线约束**：**投资组合分析器仅具备建议权，严格禁止自主调拨项目资金或自主执行项目关闭！** 资金划转与关停操作绝对归属于人类战略层。

### 6. 自动编排 (Orchestrator)
- **范围**：`orchestrator.py` 只替人做"推一下"的动作，关口规则不变。流程为：交接锚点检查 → 派活 → `audit_stage` 确定性检查 → `cmp` 合规 → 协作评审 → 提交关口申请 → `lead` 评估 → 定稿 → 解锁下游 → 继续派活。
- **触发点**（只往 `orchestration_jobs` 排队，不在请求里跑）：
 - 创建迭代；
 - 会话里产出交付物；
 - 上传交付物；
 - 人类审批关口（通过则定稿推进，打回/调整则把意见发回 Agent 修订）；
 - 手动定稿或变更审批通过；
 - 决策中心「重新检查」：只复核当前交付物。检查未通过就停下，不派 Agent 重写；关口已经签过字且检查通过，沿用原签字定稿，不把申请单打回待批。
- **执行器进程 (Runner)**：Agent CLI 一律跑在独立进程 `python -m backend.app.runner` 里，后端只写队列行就返回。
 - **为什么**：一道工序可能跑好几分钟。CLI 以前跑在 uvicorn 工作进程里，于是任何一个产品推进工序，整个工作台都停住，重启也要等它跑完。
 - **串行粒度**：同一迭代同时只有一个任务在跑（`claim_next` 跳过已有 `running` 任务的迭代），不同产品互不影响；某个任务失败只写进它自己那一行。
 - **失联恢复**：执行器每 15 秒写心跳，并刷新 `data/runner.pulse`。心跳超过 `RUNNER_STALE_SECONDS` 的任务由 `reclaim_stale` 重新排队；执行器收到退出信号时先结束自己启动的 CLI，再把在跑的任务标成 `interrupted`。空闲时 `resume_orphaned` 会把停在「等待派活 / 等待检查」、队列里却没任务的迭代重新排上（最近一次任务是失败的不再自动重试，等人点「立即推进」）。
 - **人类可见**：`GET /runs/{id}/orchestration-status` 的 `queue` 字段给出排队数、在跑数与执行器是否在岗，工序页据此区分「排队中」和「执行器没在跑」。
 - **启动**：`./run.sh` 会连带启动执行器；单独跑后端时工序只会排队，不会推进。
- **停点**：
 - 黄/红级关口、工序 09、影子模式下的绿级关口，一律停在 pending 等人类签字；
 - 绿级关口只能由配置里指定的审批人放行：工序 08 G3 归 `qa`，关闭影子模式后由 `qa` 依据确定性质量报告（P0/P1 清零、无未关闭 Critical/Major Issue）放行，`lead` 无权代批；
 - 项目 `paused` 时不派活；
 - 检查未通过时最多自动修订 2 次，仍不过就生成 `ORCH_STUCK_{工序}` 风险并停下；
 - 协作评审 2 次修订后仍要求修订，生成 `ORCH_DISPUTE_{工序}` 风险并停下（见第 7 节）；
 - 上游基线缺少交接锚点时不派活，把缺的锚点发回该上游补一版（最多 2 次）。补上并通过检查后重新定稿、关掉缺口，再派活；两次仍补不上，上游进入决策中心（见第 7 节）。
- **人的固定入口**：决策中心。人在立项时定授权包、Profile 和影子模式；之后只批方向和花钱（工序 03、04、09、10，以及支付、隐私、密钥、数据字典、对外公告等红级），并在同一页裁决分歧、卡死和交接缺口。工序 06、07、08 由 Agent 出稿，确定性检查通过后按关口规则继续，不再逐步请人确认草稿。
- **开关**：
 - 每个迭代有 `WorkflowRun.auto_advance`（默认开），只能由人类通过 `PATCH /runs/{id}/auto-advance` 修改；
 - `settings.ORCHESTRATOR_ENABLED` 是全局总开关（测试默认关闭）；
 - 卡点原因见 `GET /runs/{id}/orchestration-status`。
- **离线演示**：模拟器的各工序模板在 `simulator_deliverables.py`，带检查器能读的结构化字段，可以不接 CLI Agent 跑完整条流水线。正文顶部标明「演示稿、数字为占位假设」；工序 04 只给待回填的外测框架，不编造实测数据。
- **影子模式就绪提示**：同时满足以下条件时，`get_shadow_mode_stats` 返回 `ready_to_disable=true`，日报和决策中心显示一键关闭按钮。系统永不自动关闭影子模式，必须由人类点击。
 - 人类已裁决至少 10 次；
 - 一致率 ≥ 90%；
 - 最近 5 次没有分歧。

### 7. 协作评审与交接 (Collaboration Review & Handoff)
- **定位**：协作角色不只挂载工具，而是在主责交付物通过确定性检查与 `cmp` 之后、提交关口之前做评审。规则在 `collaboration.py`。**评审只能要求修订或提 CR，不能放行任何关口**，关口审批人不变。
- **评审矩阵**（`check` 为确定性交叉检查，`llm` 为协作 Agent 以自身人设评审，只读、不写文件）：

| 工序 | 评审方 | 方式 | 评审内容 |
| :---: | :---: | :---: | :--- |
| 04 | `ba` | check | `test_budget_usd` 不超过授权包工序 04 额度 |
| 05 | `eng` / `ux` | llm | 技术可行性 / 四态与异常分支 |
| 06 | `pm` | check | 覆盖工序 05 全部视图 `V-xx` |
| 07 | `qa` | check + llm | 覆盖工序 05 全部验收 `AC-xx` / 可测试性 |
| 09 | `eng` | llm | 回滚与 Remote Config 降级能否执行 |
| 10 | `ba` | check | `ecac_limit_usd` ≤ 工序 02 LTV / 3 |
| 11 | `pm` | check | 每条 Backlog 都有留存/流失数据依据 |

- **执行顺序**：先跑确定性交叉检查，有不通过项就不调用 LLM 评审。`settings.COLLAB_REVIEW_MODE`：`full`（默认）/ `deterministic`（只跑交叉检查）/ `off`。
- **三种结论**：
 - `approve`：结论写入关口证据 `collaboration_review`，并附在 `risk_assessment` 里；
 - `request_changes`：意见作为「【{评审方} 评审：需修订】」发回主责修订，与检查修订共用 2 次上限；评审输出无法解析也按此处理；
 - `raise_cr`：在目标工序建 `requirement_cr` Issue 交 `lead` 仲裁。评审方在 `cr_flags` 里标了支付/隐私/用户数据/加密，关口带上 `is_high_risk_cr_related` 升为 🔴；否则作为遗留 CR 记入证据，不阻断。
- **分歧裁决（人类专属）**：`ORCH_DISPUTE_{工序}` 只能由人类通过 `POST /modules/{id}/resolve-dispute` 裁决：
 - `accept_review`：把评审意见发回主责修订，再重新检查；
 - `override_review`：本次跳过评审，按当前交付物继续检查与提交关口，证据里记 `overridden_by`。
- **交接锚点**：派活前检查上游基线是否带有下游必需的锚点（如 06 需要 05 的 `V-xx` 与埋点字典，07/08 需要 05 的 `AC-xx`，10 需要 02 变现阶梯与 09 回滚计划）。缺失时不派活，在上游工序建 `handoff_gap` Issue（去重），状态为 `handoff_incomplete`，并把缺的锚点发回已定稿的上游主责补一版。补缺与检查修订共用 2 次上限，单独计次。补写通过本工序确定性检查后重新定稿，关掉缺口，下游再开工。两次仍补不上，在上游生成 `ORCH_STUCK_{工序}`，决策中心同时看到卡死和交接缺口。原先那次人类签字继续有效；只有补写本身带上新的支付、隐私、密钥或数据字典标记，才重新请人批，原基线保持不动。上下文装配会追加「上游交接锚点」一节：锚点原文、结构化字段、上游评审备注与遗留 CR。
- **人类可见**：决策中心是唯一审核入口，聚合黄/红级关口、`ORCH_DISPUTE`、`ORCH_STUCK` 和交接缺口。分歧在该页裁决（采纳评审意见或按当前交付物继续），卡死可在该页重新检查。工序页仍显示状态，但人不必进入每个工序会话。日报的 `collaboration` 统计今日评审数、待裁决分歧、遗留 CR 与交接缺口。

### 8. 全局工序交付清单规范 (Global Delivery Manifest Specification: `delivery.manifest.json`)
为彻底消除 Agent 之间仅靠模糊非结构化自然语言传递记忆而导致的漏项、口径漂移与幻觉，ModuFlow 在全系统 11 道标准工序中全面推行 **结构化交付清单机制**（就如同客户端与服务端通过 JSON Schema / Protobuf 确定数据通信契约一样）。

#### 1. 设计哲学与核心原则
1. **单一真理源 (Single Source of Truth)**：每个工序目录下的 `delivery.manifest.json` 与正文物理报告同时修订、版本受控。下游工序与确定性检查器优先按字段精准读取；
2. **通用的封套规范 (`schemas/manifests/base.manifest.schema.json`)**：
   - `contract_version`: 字符串，目前固定为 `"1"`；
   - `stage`: 两位字符串编号 (`"01"` ~ `"11"`)；
   - `artifacts`: 实体交付物角色与路径清单数组（`role` 与 `path`，物理路径严格限制在本工序目录内）；
   - `risk_flags`: 7 大安全硬拦截布尔值（`payment`, `privacy`, `user_data`, `encryption`, `lead_permissions`, `public_statement`, `data_dictionary`），代码级硬拦截并驱动红级关口 (🔴) 自动升格。
3. **平滑兼容与双轨保底 (Graceful Degradation)**：没有清单的历史目录或旧稿自动回退执行正则纯文本检查；存在清单的目录严格按 JSON Schema 契约校验，字段缺失或非法一票否决。

#### 2. 全局 11 道工序结构化契约与校验规则矩阵

| 工序编号与角色 | 结构化关键对象 | JSON Schema 规范文件 | 核心类型字段与确定性放行红线 |
| :---: | :---: | :---: | :--- |
| **`01 市场研究`** (`mr`) | `market_research` | `stage_01.schema.json` | `monthly_search_volume`, `target_capture_rate` (0~1), `blended_arpu_usd`, `annual_target_installs`, `first_year_som_usd`, `source` (严禁为空), `verdict`。参数可精确复算。 |
| **`02 商业分析`** (`ba`) | `unit_economics` | `stage_02.schema.json` | `organic_share`, `paid_cpi_usd`, `ad_arpu_usd`, `iap_conversion_rate`, `iap_net_arppu_usd`, `blended_cac_usd`, `ltv_180d_usd`, `ltv_cac_ratio` (必须 ≥ 3.0), `pricing_tiers` (**全平台价格唯一真理源**) |
| **`03 方向决策`** (`pm`) | `direction` | `stage_03.schema.json` | `uvp` (核心价值主张), `moscow.must` (必须非空 MVP 清单), `hypotheses` (生死假设列表，必须包含 `H1`) |
| **`04 假门外测`** (`mkt`) | `fakedoor` | `stage_04.schema.json` | `entry` (指向有效 `index.html`), `interactive: true`, `test_budget_usd`, `measured_results` (无真实数据必须填 `"pending"`，严禁造假) |
| **`05 需求定义`** (`pm`) | `views` / `criteria` / `events` / `compliance` | `stage_05.schema.json` | `views` (`V-xx` 数组), `acceptance_criteria` (`AC-xx` 数组), `event_dictionary` (`id`+`name`), `compliance` (包含 `uses_idfa` / `uses_ad_id` 及其降级文案) |
| **`06 设计实现`** (`ux`) | `design` | `stage_06.schema.json` | `platform`, `safe_area` (iOS top ≥ 71pt, Android status_bar ≥ 24dp), `touch_targets` (iOS ≥ 44pt, Android ≥ 48dp), `tokens_defined: true` |
| **`07 开发实现`** (`eng`) | `engineering` | `stage_07.schema.json` | `coverage_percent` (核心逻辑单测 ≥ 80%), `zero_client_inference` (按 Profile 严格声明客户端零推理成本), `modules` |
| **`08 测试保障`** (`qa`) | `quality` | `stage_08.schema.json` | `open_p0: 0` (P0 缺陷必须清零), `open_p1: 0` (P1 缺陷必须清零), `test_cases_total`, `test_cases_passed`, `e2e_pass_rate` |
| **`09 发布上线`** (`ops`/`pm`) | `release` | `stage_09.schema.json` | `store_targets`, `compliance_checked: true`, `has_remote_killswitch: true` (Remote Config 降级开关), `rollback_plan` (详尽回滚预案) |
| **`10 推广获客`** (`mkt`) | `acquisition` | `stage_10.schema.json` | `ecac_usd`, `ecac_limit_usd` (熔断止损线，`ecac_usd` 绝不可超标), `channels` (渠道列表), `daily_budget_usd` |
| **`11 运营迭代`** (`ops`) | `retention` | `stage_11.schema.json` | `d1_retention`, `d7_retention`, `d30_retention`, `backlog_items` (包含流失/留存数据依据的 V1.1 需求建议清单) |

---

## 六、技术架构与代码实现

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
│   ├── cli_adapter.py        # 原生 CLI 适配器 (agy / claude / cursor)，凭证脱敏与红线注入
│   ├── simulator_adapter.py  # 智能离线模拟适配器
│   └── factory.py            # 适配器工厂
├── api/
│   └── endpoints.py          # RESTful API 端点 (战略、授权包、关口、Profile、产物、Issue 等)
├── core/
│   ├── config.py             # 全局配置 (数据库 URL、工作区根目录、引擎类型)
│   └── database.py           # 异步 SQLAlchemy Engine 与 SessionLocal
├── mcp/
│   └── role_mcp_server.py    # 角色级隔离的 Stdio JSON-RPC 2.0 MCP Server (10 大角色专属工具箱)
├── models/
│   └── entities.py           # 核心 ORM 实体 (Initiative, Product, GateApplication, OrchestrationJob 等)
├── runner/
│   └── __main__.py           # 工序执行器进程：领队列任务、跑 Agent CLI、心跳与退出善后
├── schemas/
│   ├── all_schemas.py        # 核心业务 Pydantic 模型
│   └── gate_schemas.py       # 关口申请单与审批契约模型
└── services/
    ├── authorization_engine.py   # 授权包解析、预算超限检查、确定性止损与熔断器
    ├── gate_keeper.py            # 关口分级、自动升级 🔴 规则、审批权限守卫
    ├── security_guard.py         # 操作系统只读防护、写入拦截、凭证脱敏、唯一价格权防护
    ├── lead_service.py           # Lead 调度、影子模式比对、低风险 CR 仲裁、每日简报生成
    ├── compliance_engine.py      # CMP 出海合规审查点 (03/05/09)、G5 自动升级
    ├── profile_guard.py          # 项目 Profile 解析、平台 (iOS/Android) 与零推理规则执行
    ├── portfolio_and_hotfix_service.py # 热修复 24h SLA 追踪、Portfolio 周报生成器
    ├── workflow_engine.py        # 模板管理与 11 道工序实例化引擎
    ├── orchestrator.py           # 自动编排：派活、检查、提交关口、定稿与解锁下游
    ├── job_queue.py              # 派活队列：后端只排队，执行器进程领任务跑 CLI
    ├── stage_memory.py           # 本工序进度（当前稿、未关闭事项、未消化意见）渲染
    ├── collaboration.py          # 协作评审矩阵、确定性交叉检查、评审结论解析与交接锚点
    ├── deliverable_audit.py      # 读取交付物的确定性检查器 (定稿与自动编排共用)
    ├── workspace_sandbox.py      # CLI Agent 文件系统沙箱 (sandbox-exec + 运行后完整性校验)
    ├── workspace_sync.py         # 数据库与本地工作区双向文件同步器
    ├── agent_roles.py            # 10 大专业智能体角色定义与工序职责映射
    ├── skill_mcp_mounter.py      # 角色专属 Skill 与 MCP 动态挂载器
    ├── agent_runner.py           # 多阶段推演调度器
    ├── stale_checker.py          # 上下游基线变更追踪与过时预警检查器
    ├── diff_engine.py            # 产物版本 Diff 生成与下游受影响推演
    ├── bundle_storage.py         # HTML 原型包解压与静态预览资源托管
    └── market_research_engine.py # 全球赛道研究、TAM/SAM/SOM 测算与竞品分析
```

### 3. 10 大 Agent 角色独有 Skill 与 MCP 动态挂载对照表

ModuFlow 严格执行**按工序角色物理隔离的 Skill 与 MCP 动态挂载机制**：在每个工序的工作区目录下，仅挂载当前工序主责与协同角色对应的组件：

| 角色代码 | 角色名称 | 独有 Skill 包 (`backend/skills/{role}/`) | 独有 MCP Server (`moduflow-{role}-mcp`) 核心工具 |
| :---: | :--- | :--- | :--- |
| **`mr`** | 市场研究 Agent | `mr-global-market-intelligence` | `calculate_bottom_up_som`, `analyze_competitor_weakness_matrix` |
| **`ba`** | 商业分析 Agent | `ba-unit-economics-calculator` | `simulate_unit_economics` |
| **`pm`** | 产品经理 Agent | `pm-lean-prd-guard` | `lint_stage_deliverable` |
| **`mkt`** | 增长营销 Agent | `mkt-fakedoor-h5-generator` | `verify_fakedoor_h5_bundle` |
| **`ux`** | 设计用研 Agent | `ux-hig-prototype-spec` | `audit_hig_safe_area`, `audit_material_spec` |
| **`eng`** | 研发架构 Agent | `eng-lean-architecture-coder` | `estimate_cloud_marginal_cost`, `audit_client_zero_inference` |
| **`qa`** | 测试保障 Agent | `qa-release-gatekeeper` | `audit_app_store_compliance` |
| **`ops`** | 数据运营 Agent | `ops-cohort-funnel-analyzer` | `diagnose_retention_funnel` |
| **`lead`** | 项目总控 Agent | 不挂 Skill（`lead_service.py`） | 不挂 MCP |
| **`cmp`** | 合规风控 Agent | 不挂 Skill（`compliance_engine.py`） | 不挂 MCP |

`lead` 与 `cmp` 有角色人设，也出现在工序协同名单里，但检查与调度走服务层。MCP 进程的 `--role` 只接受上面 8 个执行角色。角色的 `allowed_tools` 直接取自 `ROLE_MCP_TOOLS`，`lead` / `cmp` 为空。MCP 服务端的约束：
- 只执行本角色的工具；
- 按 `MODUFLOW_PLATFORM` 只暴露对应平台的设计检查（iOS 只有 `audit_hig_safe_area`，Android 只有 `audit_material_spec`）；
- 协作角色（`MODUFLOW_IS_PRIMARY=false`）的调用结果标为 `advisory_only`，不作为本工序关口证据。

所有工具都是只读检查。技能脚本以 `backend/skills/` 磁盘文件为准，定稿时由 `deliverable_audit.py` 读取交付物；调用方自己填的数字不能单独放行。红级升级只认结构化标记（如 `is_payment_related`），正文里的「定价」「支付」只作提示。

---

## 七、开发者与智能体常用命令

### 1. 运行系统
```bash
# 一键并发启动前端、后端与工序执行器
./run.sh

# 只重启工序执行器（Agent CLI 跑在这里，后端不受影响）
PYTHONPATH=. backend/.venv/bin/python -m backend.app.runner
```
- Web 前端控制台：`http://localhost:5173`
- FastAPI Swagger 接口文档：`http://127.0.0.1:8000/docs`
- 执行器没启动时，派活只会排队不会推进，工序页会显示「执行器没在跑」。

### 2. 自动化测试套件 (179 项全绿保证)
```bash
# 运行后端全量异步测试 (覆盖授权包、关口分级、安全防护、Lead 影子模式、合规风控、Profile、热修与组合)
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/ -v

# 单独运行指定核心测试
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_authorization_package.py -v
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_gate_system.py -v
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_readonly_security.py -v
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_lead_shadow_mode.py -v
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_compliance_checkpoints.py -v
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_project_profile.py -v
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_hotfix_portfolio.py -v
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_role_boundaries.py -v
PYTHONPATH=. backend/.venv/bin/pytest backend/tests/test_collaboration.py -v
```

### 3. 前端编译与校验
```bash
cd frontend && npm run build
```

### 4. 授权包校验与历史工作区迁移
```bash
# 校验项目授权包格式与止损逻辑
backend/.venv/bin/python scripts/validate_authorization.py data/workspaces/{initiative_id}/products/{product_code}/authorization.yaml

# 为旧项目自动补齐与升级默认规范授权包
backend/.venv/bin/python scripts/migrate_legacy_project_auth.py
```
