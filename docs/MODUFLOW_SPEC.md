# ModuFlow：可插拔 AI 产品研发工作流平台 — 完整实施规范

> **文档目的**：作为 Coding Agent 的统一实施指令，指导构建 ModuFlow — 一个可跨 macOS、Linux、Windows 部署的 AI 产品研发工作流平台。
>
> **核心原则**：
> 1. 模块依赖能力接口，能力由适配器实现，具体实现由配置选择。
> 2. 每个模块是人与 Agent 的**协作空间**，不是单向自动化任务。
> 3. 每个任务绑定不可变的资源版本与执行配置。
> 4. 反馈通过**结构化 Issue** 在任意模块间流转。

---

## 1. 项目目标

构建一个由 13 个业务模块组成的 AI 产品研发与运营工作流系统。

### 1.1 可插拔目标

平台应允许用户独立更换每个模块使用的：

- 文件来源：本地文件、服务器归档、Git 仓库、在线文档等。
- 设计稿来源：Sketch、本地导出文件、Figma API 等。
- AI 执行器：Codex 或后续接入的其他 Agent。
- 工具：检索、差异比较、代码修改、构建、测试、数据分析等。
- 执行环境：macOS、Linux、Windows Worker。
- 输出目标：本地文件、归档、在线文档或其他系统。

更换某一项实现时，不应要求重写业务模块或整个工作流。系统必须能在执行前验证所需能力、权限和环境是否满足。

### 1.2 人机协作目标

每个模块都是人与 Agent 的协作空间。平台必须支持：

- 模块内的**多轮协作会话**（讨论、质疑、补充、修正）。
- **结构化 Issue 系统**（跨模块反馈、Bug 追踪、问题流转）。
- 基于协作共识的**基线锁定**（替代简单的 approve/reject 审批）。
- Issue 驱动的**模块回退**（下游发现问题时，上游模块可回退到讨论状态）。

---

## 2. 13 个业务模块与主流程

### 2.1 模块清单

| # | 模块名称 | 核心职责 | 典型参与者 |
|---|---|---|---|
| 01 | 市场研究 | 竞品分析、市场规模、用户画像 | 产品经理 + 调研 Agent |
| 02 | 商业模式分析 | 盈利模式、成本结构、商业可行性 | 创始人 + 分析 Agent |
| 03 | 产品方向决策 | 确定产品定位、核心功能方向 | 决策层 + 分析 Agent |
| 04 | 低成本市场验证 | 原型测试、用户访谈、数据验证 | 产品经理 + 验证 Agent |
| 05 | 产品方向确认 | 基于验证数据确认或调整方向 | 决策层 |
| 06 | MVP 定义与 PRD | 功能列表、用户故事、验收标准 | 产品经理 + PRD Agent + 设计师(评审) |
| 07 | 设计与可用性验证 | UI/UX 设计、设计评审、可用性测试 | 设计师 + 设计评审 Agent + 开发(评审) |
| 08 | 技术可行性评估 | 技术选型、风险评估、依赖分析 | 架构师/开发 + 技术评估 Agent |
| 09 | 开发实现 | 代码实现、代码审查、持续集成 | 开发人员 + 开发 Agent |
| 10 | 测试与 QA | 自动化测试、手动测试、质量报告 | 测试人员 + 测试 Agent + 开发(修复) |
| 11 | 发布与上线 | 构建、签名、发布、灰度 | 发布人员 + 发布 Agent |
| 12 | 市场推广与获客 | 营销策略、ASO、广告投放 | 运营人员 + 营销 Agent |
| 13 | 运营分析与持续迭代 | 数据分析、用户反馈、迭代规划 | 运营/产品 + 分析 Agent |

### 2.2 默认流程与门禁

```
01 → 02 → 03 → 04 → [决策门] → 05 → 06 → 07 → 08 → [审批门] → 09 → 10 → [质量门] → 11 → 12 → 13
                                                                                                  ↓
                                                                              运营反馈 ← ← ← ← ← ←
```

**门禁机制**（通过协作会话和 Issue 系统实现）：

| 门禁 | 通过条件 | 实现方式 |
|---|---|---|
| 决策门 | 验证数据支持方向决策 | 模块 04 达到 `baselined` 状态 |
| 审批门 | 技术方案可行且风险可控 | 模块 08 达到 `baselined` 状态 |
| 质量门 | 测试通过，无阻塞性缺陷 | 模块 10 达到 `baselined` 且无未关闭的 Critical/Major Issue |

流程必须支持分支、重试、暂停、取消和仅重跑受影响任务，不得要求每次变更都从头运行全部模块。任何模块都可以通过 Issue 向任意前序模块反馈问题。

---

## 3. 模块协作空间

### 3.1 模块的本质

每个模块是一个**协作空间（Collaboration Space）**，包含四个组成部分：

- **协作会话**：人与 Agent 的多轮讨论，是模块内交互的核心载体。
- **产物（Artifacts）**：会话过程中产出的文档、报告、代码、设计稿等。
- **Issue 看板**：与本模块相关的待解决问题、待确认疑问。
- **基线（Baseline）**：达成共识后锁定的产物版本，作为下游模块的输入依据。

### 3.2 模块状态机

每个模块有四个协作阶段：

| 阶段 | 含义 | 谁在做什么 |
|---|---|---|
| `draft` | 初始草稿 | Agent 根据指令产出初稿；或人直接上传材料 |
| `discussing` | 协作讨论 | 人与 Agent 在会话中反复讨论、修改、补充 |
| `reviewing` | 评审确认 | 相关人员正式评审产物，提出修改意见或通过 |
| `baselined` | 基线锁定 | 产物版本锁定，作为下游模块的输入依据 |

**状态跃迁规则**：

| 跃迁 | 前提条件 | 触发方 |
|---|---|---|
| `draft → discussing` | 有初始指令或上传材料 | 任何参与者 |
| `discussing → reviewing` | 产物至少有一个版本 | 模块负责人 |
| `reviewing → baselined` | 评审通过 + 无 critical/major 未关闭 Issue | 授权评审人 |
| `reviewing → discussing` | 评审打回 | 评审人 |
| `baselined → discussing` | 下游模块发现重大问题需回退 | 需授权 + 记录原因 |

**基线锁定条件**（三个条件必须同时满足）：

1. 产物经至少一名授权评审人评审通过。
2. 关联到本模块的 Critical 和 Major Issue 全部关闭。
3. 授权人在协作会话中明确确认。

### 3.3 人机职责划分

AI 主要负责信息收集、分析、草拟、代码实现、测试执行和报告生成。

以下高影响决策默认由人类在协作会话中确认：

- 产品方向、预算与市场验证是否继续。
- PRD 与设计基线确认。
- 高风险技术方案和重大范围变更。
- 生产发布、数据破坏性操作及高风险变更。

审批策略应可配置，但不得默认让 AI 自动批准所有高影响动作。

### 3.4 每个模块的典型协作场景

#### 模块 01：市场研究

```
参与者：产品经理 + 市场调研 Agent
协作模式：人指定方向 → Agent 调研 → 人质疑/补充 → Agent 修正 → 多轮后达成共识

典型会话：
  PM: "调研东南亚记账App市场"
  Agent: [产出初步报告：市场规模、竞品、用户画像]
  PM: "印尼数据太少，MoneyForward 没覆盖到"
  Agent: [补充印尼市场数据，增加 MoneyForward 分析]
  PM: "可以了，但结论部分需要更突出差异化机会"
  Agent: [修正结论]
  PM: → approve → 锁定基线

产物：市场调研报告 (baselined)
```

#### 模块 06：MVP 定义与 PRD

```
参与者：产品经理 + PRD Agent + 设计师(评审)
协作模式：PM 提需求 → Agent 草拟 PRD → PM 修改 → 设计师提交 Issue → 修正

典型会话：
  PM: "核心功能：拍照记账、分类统计、预算提醒"
  Agent: [草拟 PRD v1，包含功能列表、用户故事、验收标准]
  PM: "预算提醒的触发条件需要更细化"
  Agent: [修正 PRD v2]
  Designer (Issue): "用户故事中'分类统计'的交互流程描述不够，无法出设计"
     → Issue ISSUE-018, target: prd, severity: major
  PM + Agent: [补充交互流程描述，修正 PRD v3]
  Designer: → 关闭 ISSUE-018
  PM: → approve → 锁定基线
```

#### 模块 10：测试与 QA

```
参与者：测试人员 + 测试 Agent + 开发人员(修复)
协作模式：Agent 执行自动化测试 → 测试人员验证 → 发现问题创建 Issue → 开发修复 → 回验

典型会话：
  Tester: "执行回归测试，重点关注登录和支付"
  Agent: [执行自动化测试，产出测试报告]
  Agent: "发现 3 个失败用例：登录闪退、支付超时、分类显示错误"
  Tester: [手动复现，确认前两个是真实 Bug]
     → Issue ISSUE-042 (登录闪退, P0, target: development)
     → Issue ISSUE-043 (支付超时, P1, target: development)
  Tester: "分类显示错误是测试数据问题，不是 Bug"
     → Agent 更新测试报告

  [开发模块中]
  Developer + Agent: 修复 ISSUE-042, ISSUE-043

  [回到测试模块]
  Tester: "验证 ISSUE-042 修复，通过" → 关闭 Issue
  Tester: "ISSUE-043 修复不完整，弱网仍超时" → Issue 重新打开，补充复现条件
```

---

## 4. 协作会话（Collaboration Session）

### 4.1 会话结构

协作会话是模块内人与 Agent 交互的核心载体。它不是简单的聊天记录，而是带有结构化产出的对话。

```yaml
collaboration_session:
  id: "session-mkt-001"
  module: "market_research"
  product: "expensebook"
  status: "active"               # active / paused / completed
  participants:
    - role: product_manager
      user: "alice"
    - role: agent
      executor: "codex"

  messages:
    - from: alice
      type: instruction
      content: "调研记账 App 市场，重点看东南亚"

    - from: agent
      type: draft_artifact
      content: "..."
      artifact_ref: "mkt-report-v1"

    - from: alice
      type: feedback
      content: "东南亚数据太少，补充印尼和越南的具体数据"

    - from: agent
      type: revised_artifact
      artifact_ref: "mkt-report-v2"

    - from: alice
      type: issue
      content: "竞品分析中缺少 MoneyForward，需要补充"
      issue_ref: "ISSUE-012"

    - from: alice
      type: approve
      artifact_ref: "mkt-report-v3"
      baseline: true
```

### 4.2 消息类型

| 类型 | 发送方 | 含义 |
|---|---|---|
| `instruction` | 人 | 给 Agent 的指令或要求 |
| `question` | 人或 Agent | 提出疑问，等待对方回答 |
| `draft_artifact` | Agent | 产出初稿产物 |
| `revised_artifact` | Agent | 根据反馈修改后的产物 |
| `feedback` | 人 | 对产物的修改意见、补充要求 |
| `issue` | 人或 Agent | 发现的问题，创建结构化 Issue |
| `reference` | 人或 Agent | 引用其他模块的产物或 Issue |
| `approve` | 人 | 确认产物可以作为基线 |
| `reject` | 人 | 打回产物，要求重做 |
| `escalate` | 人或 Agent | 上报无法在本模块解决的问题 |

---

## 5. Issue 系统

### 5.1 Issue 结构

Issue 是跨模块反馈的载体。任何参与者（人或 Agent）在任何模块中都可以创建 Issue，并将其关联到应当处理它的模块。

```yaml
issue:
  id: "ISSUE-042"
  title: "登录页面在 Android 12 以下版本闪退"

  # 来源
  source:
    module: "testing"
    session: "session-test-007"
    reporter: "bob"
    reporter_role: "tester"

  # 目标
  target:
    module: "development"

  # 结构化描述
  description:
    summary: "登录页面在 Android 12 以下版本闪退"
    steps_to_reproduce:
      - "使用 Android 11 设备"
      - "打开 App，进入登录页面"
      - "输入账号密码，点击登录"
      - "App 闪退"
    expected: "正常登录进入主页"
    actual: "App 闪退，Logcat 显示 NullPointerException"
    environment:
      os: "Android 11"
      device: "Pixel 4a"
      app_version: "1.0.0-beta.3"
    attachments:
      - type: "log"
        ref: "artifact-logcat-042"
      - type: "screenshot"
        ref: "artifact-screenshot-042"

  # 分类
  severity: "critical"              # critical / major / minor / trivial
  priority: "P0"                    # P0 / P1 / P2 / P3
  category: "bug"                   # bug / question / improvement / task

  # 关联
  related_artifacts:
    - "test-report-v2"
    - "dev-commit-abc123"
  related_issues: []

  # 生命周期
  status: "open"                    # open → investigating → fixing → verifying → closed
  resolution: null                  # fixed / wontfix / duplicate / by_design / deferred
  assignee: null
```

### 5.2 Issue 流转规则

1. **Issue 必须有明确的 target module**：不允许创建没有归属的悬空 Issue。
2. **Issue 可以被转移**：开发模块发现根因在设计，可以将 Issue 转移到设计模块。
3. **Issue 阻塞基线**：模块中有未关闭的 Critical/Major Issue 时，不允许锁定基线。
4. **Issue 触发模块回退**：如果下游发现的问题根因在上游，上游模块应从 `baselined` 回退到 `discussing`。

### 5.3 Issue 描述规范与模板

系统应提供 Issue 模板，引导参与者按结构化方式描述问题。

**Bug 报告模板**：

```markdown
## Bug 标题
[一句话描述：什么功能 + 什么情况 + 什么现象]

## 复现步骤
1. [具体操作步骤]

## 预期结果
[应该发生什么]

## 实际结果
[实际发生了什么]

## 环境信息
- 设备/系统：
- App 版本：
- 网络状态：

## 附件
- [ ] 截图/录屏
- [ ] 日志文件
- [ ] 崩溃堆栈
```

**Agent 辅助补全**：当参与者创建 Issue 后，Agent 可以自动：

1. 从日志中提取崩溃堆栈并关联到 Issue。
2. 定位可能的代码位置并添加为 Issue 注释。
3. 检查是否与已有 Issue 重复。
4. 建议 severity 和 priority。
5. 自动关联相关测试用例和代码变更。

### 5.4 跨模块反馈典型场景

| 发现方 | 典型 Issue | 反馈目标模块 |
|---|---|---|
| 商业模式分析 | "订阅模式不可行，需补充付费意愿数据" | → 01 市场研究 |
| 方向决策 | "两个方向都有道理，需要更多验证数据" | → 04 低成本验证 |
| 设计师 | "PRD 中交互描述不够，无法出设计" | → 06 PRD |
| 开发人员 | "设计动画在低端设备上无法实现" | → 07 设计 |
| Agent | "第三方 SDK 版本冲突，需要确认" | → 08 技术评估 |
| 测试人员 | "登录功能在弱网环境下超时" | → 09 开发 |
| 测试人员 | "这不是 Bug，是需求定义不清" | → 06 PRD |
| 运营人员 | "落地页转化率低于预期" | → 07 设计 或 06 PRD |
| 数据分析 | "7 日留存率过低，核心功能可能不对" | → 03 方向决策 |

---

## 6. 架构要求

采用**模块化单体 + 独立 Worker + 插件适配器**起步，不要在 MVP 阶段拆成大量微服务。

### 6.1 逻辑分层

1. **Web UI**：产品概览、模块协作空间、协作会话、Issue 看板、资源管理、配置、审计。
2. **工作流核心**：模块状态机（四阶段）、依赖拓扑、门禁条件、Issue 阻塞检查、调度与审计。
3. **协作层**：协作会话管理、消息存储、Issue 生命周期、跨模块反馈路由。
4. **配置与插件注册中心**：登记数据源、Agent、工具、Skill、Worker 及其能力。
5. **能力接口层（Contracts）**：定义统一输入输出、错误模型、能力要求和版本兼容规则。
6. **适配器层（Adapters）**：实现本地文件、在线文档、Figma、Git、Codex、构建、测试、分析等具体集成。
7. **Worker 执行层**：在对应操作系统上运行受控任务。
8. **持久化层**：数据库、不可变文件快照、日志、报告、任务产物与审计记录。

### 6.2 推荐技术栈

可按项目现状调整，但须先说明理由并记录决定：

- 前端：React + TypeScript + Vite。
- 后端 API：Python + FastAPI。
- 数据库：MVP 可用 SQLite；多用户并发或多 Worker 阶段迁移 PostgreSQL。
- 后台执行：持久化任务队列与独立 Worker；MVP 可以从数据库任务表和轮询 Worker 开始。
- 资源归档：本地磁盘/APFS 或普通文件系统 + SHA-256；后续可扩展对象存储。
- 代码隔离：Git + 独立分支或 Git Worktree。
- AI 执行：通过执行器适配器封装 Codex CLI、SDK 或其他支持的执行方式。
- 配置：YAML/JSON 配置文件与数据库配置结合；密钥保存在环境变量或安全凭据存储中。
- 部署：提供跨平台启动脚本、环境检查与配置样例。

不得假设所有工具都在所有操作系统上可用。能力注册必须声明平台限制，例如 iOS Simulator、Xcode 构建与签名需要 macOS。

---

## 7. 插件与能力接口设计

### 7.1 核心原则

业务模块只依赖稳定的接口，不直接调用具体供应商 SDK，不硬编码本地路径、URL、工具名称或命令行参数。

示例：业务模块调用 `DocumentProvider.get_document(resource_ref)`，而不是直接打开某个固定路径。

### 7.2 建议的能力接口

| 接口 | 职责 | 示例实现 |
|---|---|---|
| `DocumentProvider` | 读取文档、元数据、版本标识 | 本地文件、在线文档 API、Git |
| `DesignProvider` | 获取设计文件、节点信息或导出图像 | Sketch、Figma API、PNG/PDF 导出 |
| `ResourceVersionProvider` | 记录版本、快照、哈希和比较关系 | 本地快照、Git、供应商版本 API |
| `CodeProvider` | 读取代码、创建工作区、提交差异 | 本地 Git、远程 Git |
| `AgentExecutor` | 执行有边界的 AI 任务 | Codex、其他 Agent |
| `BuildProvider` | 构建并返回结构化结果 | Gradle、Xcode 等 |
| `TestProvider` | 执行测试并返回结构化结果 | 单元测试、UI 测试、设备测试 |
| `AnalyticsProvider` | 查询业务指标与运营数据 | 分析 API、数据库、CSV |
| `ArtifactStore` | 保存任务产物与报告 | 本地归档、对象存储 |
| `NotificationProvider` | 发送任务与审批通知 | 邮件、Webhook 等 |

接口要表达统一的业务语义，不要强行让能力不同的工具拥有完全相同的功能。通过 capability（能力）声明可选功能和供应商扩展能力。

### 7.3 插件注册信息

每个插件至少声明：

- `id`：稳定唯一标识。
- `type`：插件类型，例如 `document-provider`。
- `version`：插件版本。
- `capabilities`：支持的能力。
- `platforms`：支持的操作系统。
- `config_schema`：配置结构及验证规则。
- `permissions`：所需权限。
- `health_check`：健康检查方式。
- `timeout`、重试和错误分类策略。
- 输入输出 schema 版本。

能力声明只是候选信息；执行前还应检查实际配置、认证、权限和运行环境。插件执行失败必须返回结构化错误，不应导致整个服务崩溃。

### 7.4 插件隔离

- 插件不得默认获得平台全部文件、环境变量或网络权限。
- 上传的文件不得被当作可执行脚本自动运行。
- 外部插件需要权限白名单、超时、日志和版本控制。
- 执行命令必须限定工作目录、环境变量、可访问路径和允许的命令。
- 不得将 API Token 或密钥写入日志、任务产物或版本控制。

---

## 8. 资源引用与版本策略

### 8.1 逻辑资源与物理来源分离

业务模块引用逻辑资源 ID，而不是直接保存绝对路径或供应商 URL。例如：

```yaml
resource:
  logical_id: expensebook-prd
  provider_id: online-docs
  external_id: doc_12345
  version_id: revision_008
  content_hash: sha256:...
```

说明：

- `logical_id`：业务上稳定的资源身份。
- `provider_id`：负责访问该资源的适配器。
- `external_id`：来源系统中的资源标识。
- `version_id`：来源系统的具体版本；若来源不支持，则为空并通过快照补足。
- `content_hash`：内容哈希。
- 还应记录获取时间、MIME 类型、来源地址、快照位置及解析器版本。

### 8.2 不可变快照

- 每次上传或导入都创建独立快照，不覆盖历史内容。
- 使用 SHA-256 或同类哈希校验内容完整性。
- 区分"最新导入版本"和"已批准基线"。
- 任务创建或批准时锁定确切的输入资源版本、Skill 版本、插件版本、配置版本和代码基线。
- 后续来源切换或新文件上传不得静默改变正在执行的任务。
- 历史任务必须能追溯到实际使用的输入和产物。

### 8.3 来源切换与迁移

更换来源时，系统应执行：

1. 验证新适配器配置、认证、权限和能力。
2. 获取新来源的元数据和内容快照。
3. 比较旧版本与新版本；区分内容差异和来源差异。
4. 显示影响范围并要求必要的人工确认。
5. 将逻辑资源绑定更新到新来源。
6. 保留旧绑定、历史快照与迁移审计。
7. 仅对受影响任务进行失效标记或重新排队。

禁止仅凭文件名或 URL 相似就认定两个资源内容相同。

### 8.4 文件安全

- 上传采用临时区、文件大小限制、类型校验、哈希校验和原子归档。
- ZIP 等归档文件需要防止路径穿越、解压炸弹和异常嵌套。
- 对无法直接解析的专有格式，允许保存原文件并要求导出 PNG/PDF/SVG 或使用官方 API。
- 图像差异只能作为视觉证据，不能自动等同于业务语义差异。
- 不支持的格式应明确报错或要求替代输入，不可伪造解析成功。

---

## 9. 模块配置模型

模块定义、Skill、资源、执行器、能力、输出目标和协作策略应分别配置，避免相互耦合。

示例：

```yaml
product:
  id: expensebook

modules:
  prd:
    enabled: true
    inputs:
      - resource_id: expensebook-prd
        required_capabilities:
          - document.read
          - document.version
    skill_ref: prd-review
    executor_ref: codex
    outputs:
      - artifact_type: review-report
        store_ref: local-archive
    collaboration:
      required_participants:
        - role: product_manager
        - role: agent
      optional_reviewers:
        - role: designer
      baseline_approvers:
        - role: product_manager
      issue_blocking_severities:
        - critical
        - major

  design_review:
    enabled: true
    inputs:
      - resource_id: expensebook-design
        required_capabilities:
          - design.read
          - design.export_images
    skill_ref: design-review
    executor_ref: codex
    collaboration:
      required_participants:
        - role: designer
        - role: agent
      optional_reviewers:
        - role: developer
      baseline_approvers:
        - role: designer
        - role: product_manager

providers:
  - id: local-files
    type: document-provider
    config:
      root: ./data/products/expensebook

  - id: online-docs
    type: document-provider
    config:
      credential_ref: online-docs-token

design_providers:
  - id: sketch-files
    type: design-provider

  - id: figma
    type: design-provider
    config:
      credential_ref: figma-token
```

该示例用于表达配置关系，不要求完全照搬字段名。实现时需建立正式的 schema、数据库模型和验证逻辑。密钥只使用 `credential_ref` 等引用，不在配置文件里保存明文。

系统应支持产品级默认配置、模块级覆盖和单次任务覆盖，并规定优先级。每次执行需保存最终解析后的配置快照，避免之后配置变化影响历史审计。

---

## 10. Skill 与 Agent 的职责

### Skill

Skill 描述 AI 完成任务的工作方法，包括：

- 任务目标、前置条件与步骤。
- 输入数据要求。
- 分析框架、规则与判断标准。
- 输出结构和验收标准。
- 何时请求人工判断（通过协作会话中的 `question` 或 `escalate` 消息）。
- 失败和信息不足时的处理方式。

建议按业务模块维护 Skill，但不要把数据源密钥、版本管理、审批状态机和不可逆操作控制仅写在 Skill 里。

### Agent / Executor

执行器负责调用模型、Skill 和已授权工具，并返回结构化结果。执行器需支持：

- 任务 ID、输入快照和执行配置。
- 超时、取消、日志和退出状态。
- 产物清单与结构化结果。
- 工作目录隔离。
- 失败重试策略（由工作流层控制）。
- 对工具和网络权限的约束。
- 在协作会话中发送消息（`draft_artifact`、`question`、`issue` 等）。

### 工作流核心

工作流核心负责模块状态跃迁、依赖拓扑、Issue 阻塞检查、重试、幂等、资源锁定和审计。它不能依赖模型输出决定自身的安全权限或绕过审批。

---

## 11. 任务执行与可靠性

模块内的 AI 执行任务（如 Agent 调研、代码实现、测试执行）仍需任务级状态管理：

建议的任务状态：

`pending → ready → running → succeeded`

其他状态至少包括：

- `blocked`：依赖或能力不足。
- `waiting_input`：等待人在协作会话中提供补充信息。
- `failed`：执行失败。
- `cancelled`：已取消。
- `skipped`：经规则允许而跳过。
- `stale`：输入版本或上游基线变化，需要重新评估。

要求：

- 状态转换必须经过统一服务校验。
- 任务执行使用唯一 ID 与幂等键，避免重复触发造成重复副作用。
- Worker 崩溃后能恢复或将任务安全标记为失败。
- 重试次数、退避策略、超时和人工重试均可配置。
- 外部操作需记录请求、结果、执行器版本和关联产物。
- 仅当依赖满足且所需能力可用时才启动任务。
- 变更只重新运行受影响的下游任务。
- 对发布、删除、合并等高影响动作设置明确的授权和审批关卡。

---

## 12. 本地文件与在线设计工作流

平台应支持用户从浏览器上传完整的需求文档、设计文件和导出资源到中心存储。

上传流程：

1. 选择产品、资源逻辑 ID、资源类型和变更说明。
2. 服务端验证身份、权限、文件大小与格式。
3. 写入临时区，计算哈希并验证完整性。
4. 创建不可变快照和版本记录。
5. 解析可支持的文本、结构或图像内容。
6. 生成差异报告和变更记录。
7. 在协作会话中通知相关参与者，Agent 分析影响范围。
8. 人工在协作会话中确认后锁定基线。
9. 创建独立开发任务和隔离的 Git 分支/Worktree。
10. 执行构建、测试和结果汇总。
11. 由授权人员审核与合并；发布另行审批。
12. 保存审计记录并更新工作流状态。

设计文件处理策略：

- Sketch：在有可靠解析支持时读取结构化内容。
- Figma：优先通过获授权的官方 API 获取节点、版本和导出资源；不可假设 `.fig` 文件可直接解析。
- Axure 或其他专有格式：通过支持的导出能力获取 HTML、图像或 PDF；必要时由人工复核。
- PNG/PDF/SVG：可做视觉差异，但应说明其无法完整表达组件语义和交互行为。

---

## 13. 跨平台 Worker

工作流控制面可以部署在中心服务器或中心 Mac 上，Worker 部署在可用的 macOS、Linux 和 Windows 机器上。

Worker 注册信息至少包括：

- Worker ID、操作系统、架构和版本。
- 支持的能力、已安装工具及版本。
- 可用资源和并发上限。
- 允许访问的产品与工作目录。
- 健康状态、心跳和最后一次执行时间。

调度器依据任务能力要求、平台限制、权限和资源状况分派任务。

示例：

- Android Gradle 构建：分配给满足 JDK、Android SDK 等条件的 Worker。
- iOS Simulator、Xcode 构建与签名：分配给 macOS Worker。
- Windows 专属任务：分配给 Windows Worker。

Worker 只接受授权任务，不应直接信任客户端传来的任意 shell 命令。执行结果和产物必须返回控制面并与任务 ID 关联。

---

## 14. 数据模型

### 14.1 核心业务实体

- `StrategicInitiative`：战略举措/顶层工程（目标、预算、时间线、所包含产品、跨产品依赖）。
- `Product`：产品实体（隶属某战略工程，具有独立代码库与团队配置）。
- `WorkflowTemplate`：流程模板库（如完整13模块模板、快速迭代模板、紧急修复模板等）。
- `WorkflowRun`：工作流运行实例（某产品的一次具体迭代周期，实例化自某模板）。
- `ModuleInstance` / `ModuleState`：某次运行中具体模块的协作空间与状态（draft/discussing/reviewing/baselined）。
- `Task`：模块内 AI 执行任务的状态、依赖、输入快照、执行配置和结果。

### 14.2 协作实体

- `CollaborationSession`：模块内的协作会话（参与者、状态、关联模块和产品）。
- `SessionMessage`：会话中的消息（发送者、类型、内容、关联产物/Issue、时间戳）。
- `Issue`：结构化问题（来源模块、目标模块、分类、严重度、优先级、描述、状态、分配人、关联产物/Issue）。
- `IssueComment`：Issue 的评论和状态变更记录。

### 14.3 资源与版本实体

- `Resource`：逻辑资源身份。
- `ResourceVersion`：不可变资源版本、哈希和快照位置。
- `Artifact`：报告、补丁、截图、测试结果等产物。

### 14.4 插件与执行实体

- `ProviderInstance`：适配器实例及非敏感配置。
- `PluginDefinition`：插件类型、版本和能力。
- `SkillDefinition`：Skill 标识、版本和文件位置。
- `ExecutorDefinition`：Agent/执行器及能力声明。
- `Worker`：运行环境、能力、状态与资源上限。

### 14.5 审计实体

- `AuditEvent`：配置更改、来源切换、基线锁定/解锁、Issue 状态变更、授权动作的审计记录。
- `ExecutionLog`：结构化执行事件与错误。

数据库中的任务不能只保存"当前配置 ID"，还必须保存该次执行解析后的配置快照或不可变版本引用。

---

## 15. Web UI 页面

MVP 建议实现：

1. **产品列表与总览**：所有产品及其当前工作流进度。
2. **产品工作流视图**：13 模块看板，每个模块显示当前阶段（draft/discussing/reviewing/baselined）、未关闭 Issue 数、阻塞原因。
3. **模块协作空间**：协作会话界面（类似聊天，但带结构化消息类型）、产物列表与版本、Issue 列表。
4. **Issue 看板**：全局 Issue 视图，支持按模块、优先级、状态筛选；Issue 详情页。
5. **资源中心**：上传、资源绑定、版本列表与差异对比。
6. **任务执行详情**：Agent 执行日志、输入、产物、重试、取消。
7. **模块配置页面**：Skill、Provider、Executor、能力、协作策略和输出配置。
8. **插件/Worker 状态页面**：健康检查、能力列表、平台信息。
9. **审计记录页面**：所有关键操作的时间线。

配置页面应显示能力缺失、权限问题和健康检查结果。不得只提供一个可以填写任意字符串的配置框而不验证。

---

## 16. 安全、权限与审计

- 使用认证与角色权限控制产品、资源、配置、审批和发布操作。
- 区分只读、编辑、配置管理员、审批者和发布者等权限。
- 对敏感操作执行服务端授权，不信任前端按钮状态。
- 保存来源切换、配置更改、基线锁定/解锁、Issue 状态变更、任务触发、代码合并和发布的审计事件。
- 对外部 API 实施超时、速率限制和凭据隔离。
- 避免日志泄露密钥、个人数据或完整环境变量。
- 对文件上传和解压执行安全校验。
- 对 AI 生成的命令、代码和外部输入采用最小权限执行策略。
- 生产发布和破坏性操作必须有显式授权；不能仅凭 AI 自述"已批准"执行。

---

## 17. MVP 实施顺序

### 阶段 1：工作流骨架 + 协作基础

- 建立前后端工程、数据库和基础认证。
- 建立产品、模块定义和模块状态机（draft → discussing → reviewing → baselined）。
- 实现基础协作会话（消息存储与展示）。
- 实现 Issue 创建、关联、流转和状态管理。
- 实现模块间 Issue 流转和基线锁定条件检查。
- 支持 13 模块默认流程、依赖拓扑与门禁。
- 实现基础 Web UI（工作流看板、协作会话、Issue 看板）。
- 建立测试和跨平台开发说明。

### 阶段 2：资源与版本

- 实现本地文件上传、不可变快照、哈希、版本列表和差异报告。
- 实现统一资源引用与 Provider 接口。
- 实现本地文件适配器和本地 Git 适配器。
- 区分最新版本与批准基线。
- 实现资源切换、迁移确认和历史追溯。
- 在协作会话中集成资源变更通知。

### 阶段 3：AI 执行

- 实现 Skill 注册和版本引用。
- 实现 AgentExecutor 接口及首个执行器。
- 建立隔离工作区、执行日志、任务产物、超时、取消和重试。
- Agent 在协作会话中产出 `draft_artifact` 和 `revised_artifact`。
- Agent 自动创建 Issue（如测试失败自动生成 Bug Issue）。
- 接入 PRD 评审、设计评审、开发和测试的最小闭环。

### 阶段 4：插件扩展

- 接入在线文档或 Figma 中至少一种真实来源。
- 实现能力发现、配置校验、健康检查和能力缺失提示。
- 增加 Worker 注册和平台能力路由。
- 完善插件版本兼容、权限、故障隔离和回滚。

### 阶段 5：完整业务闭环

- 补齐市场研究、商业分析、验证、发布、增长与运营模块。
- 实现变更影响分析和受影响下游任务重跑。
- 增加运营数据反馈到产品决策的闭环。
- 按实际负载决定是否迁移 PostgreSQL、增加队列服务或拆分独立服务。

---

## 18. 验收标准

### 可插拔性

- 将 PRD 来源从本地文件切换到在线文档时，PRD 业务模块代码不需要修改。
- 将设计来源从 Sketch/导出文件切换到 Figma 适配器时，设计评审模块只需调整绑定与能力配置。
- 更换 Agent 执行器不需要重写工作流状态机。
- 缺少能力、权限或平台不匹配时，任务启动前给出明确的阻塞原因。

### 人机协作

- 每个模块都能进行多轮协作会话，人和 Agent 可以反复讨论。
- Issue 可以从任意模块创建，关联到任意目标模块。
- Critical/Major Issue 未关闭时，模块无法锁定基线。
- 下游模块的 Issue 可以触发上游模块从 baselined 回退到 discussing。
- 系统提供 Issue 模板，Agent 辅助补全技术细节。

### 版本与可追溯性

- 新上传不能覆盖旧快照。
- 已运行任务继续引用原输入版本。
- 每个任务都能追溯到资源版本、Skill、插件、执行器和最终配置。
- 来源迁移必须有记录，并能识别受影响任务。
- 每个 Issue 都能追溯到来源会话、相关产物版本和解决过程。

### 可靠性

- Worker 崩溃后任务状态可恢复或明确失败。
- 重复调度不会重复执行不允许重复的副作用。
- 支持超时、取消、重试和结构化错误。
- 只有获授权的人员才能批准基线、合并代码或发布。

### 跨平台

- 核心服务与基础 Worker 有清晰的操作系统边界。
- 平台专属任务被路由到合适的 Worker。
- 不支持的系统能力不能被错误地报告为可用。

### 安全

- 上传文件不会被自动当作脚本执行。
- 密钥不会明文写入日志或 Git。
- 插件和 Worker 只能访问获授权的资源和目录。
- 所有高影响动作都经过服务端授权与审计。

---

## 19. 给 Coding Agent 的执行要求

请按以下方式推进实现：

1. **先检查现有仓库**：识别技术栈、已有代码、运行方式、测试和约定。不要在不了解现状时覆盖或重建项目。
2. **先产出实施计划**：列出模块边界、目录结构、数据模型、接口契约、风险和分阶段任务。
3. **先定义契约再实现适配器**：为 Provider、Executor、Worker 和插件配置建立类型、schema 与契约测试。
4. **先打通一条端到端垂直切片**：创建产品 → 进入 PRD 模块 → 开始协作会话 → Agent 产出草稿 → 人反馈 → Agent 修正 → 创建 Issue → 解决 Issue → 基线锁定 → 审计记录。
5. **随后扩展来源与模块**：优先保证架构可插拔，而不是一次性实现所有第三方集成。
6. **测试必须随功能交付**：包括单元测试、接口契约测试、状态机测试、协作会话测试、Issue 流转测试、来源切换测试、权限测试和关键集成测试。
7. **每阶段交付可运行结果**：提供启动步骤、配置示例、迁移说明、测试结果与已知限制。
8. **不要伪造集成能力**：尚未接入的 Figma、在线文档或 Codex 功能应明确标记为未实现，并提供接口和 mock 测试。
9. **保持最小可行复杂度**：先模块化单体与独立 Worker；没有真实需求前不要引入复杂微服务、Kubernetes 或多套消息系统。
10. **遇到关键设计歧义时先提出选项**；非关键细节可以选择合理默认值，并记录在 ADR（架构决策记录）中。

**首个里程碑**：一个可运行的最小平台，包含——创建产品 → 13 模块工作流看板 → 在 PRD 模块中开始协作会话 → 人与 Agent 多轮对话 → 上传 PRD 文件并生成不可变版本 → 创建/解决 Issue → 基线锁定 → 下游模块解锁 → 审计记录。证明模块状态机、协作会话、Issue 流转和数据源可插拔性均可工作。
