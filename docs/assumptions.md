# ModuFlow 三层架构重构假设与设计决策记录 (docs/assumptions.md)

> 本文档用于记录在将 ModuFlow 从「单项目 8 角色流水线」升级为「人类战略层 → 项目层 (lead) → 执行层」三层架构过程中，根据「先读后改、不确定就记录不要猜」原则所沉淀的系统假设与设计推演。

---

## 一、核心系统假设 (System Assumptions)

### 1. 人类主体与 Agent 身份鉴权机制 (Actor Identification & Authentication)
- **现状**：目前系统在 `SessionMessage` 中使用 `sender_role: "human" | "agent"` 标记发送者，API 层面尚未引入硬性的身份鉴权中间件。
- **假设**：
  1. 为了落实“任何 Agent 不得修改自身权限、不得批准红级关口、不得修改授权包”的硬约束，系统在 Phase 1~3 将引入显式的 `ActorContext`（通过请求头 `X-ModuFlow-Actor: human:<user_id> | agent:<role_code>` 或会话上下文传递）。
  2. 针对写授权包、G1/G2/G4/G5 审批、预算追加、关闭影子模式等特权操作，系统强制校验 `actor_type == "human"`，并在后端直接做拦截并写入审计日志，杜绝 Agent 伪造身份。

---

### 2. 授权包 (Authorization Package) 的层级与作用域
- **现状**：ModuFlow 的实体层级为 `StrategicInitiative (战略工程)` → `Product (项目/单品)` → `WorkflowRun (迭代运行)` → `ModuleInstance (11道工序模块)`。
- **假设**：
  1. 授权包 `authorization.yaml` 严格绑定在 **Product（单品/项目）** 级别，物理路径为：
     `data/workspaces/{initiative_id}/products/{product_code}/authorization.yaml`。
  2. 单品内的每个迭代运行 (`WorkflowRun`) 共享并继承该项目的授权包配额；
  3. 授权包在数据库中通过 `products.authorization_package_json`（或独立关联表）做结构化镜像，实现磁盘物理文件与 DB 实时双向一致。

---

### 3. 确定性脚本 (Deterministic Checker) 的拦截与熔断时机
- **现状**：目前工序流转主要依赖 `can_baseline_module`（仅检查是否存在严重 Bug Issue 与交付物产出）。
- **假设**：
  1. 预算、时限、止损指标与禁区检查必须 100% 由纯 Python 确定性脚本 (`authorization_guard.py` / `validate_authorization.py`) 执行，**绝对不经由任何 LLM 判断**。
  2. 确定性检查器挂载在四大关键节点：
     - **工序派活前 (Pre-dispatch)**：检查项目是否处于 `paused`、时限是否超期、当前动作是否属于 `lead_forbidden`；
     - **费用发生/消耗后 (Post-expense)**：检查实际花费是否超过授权包 `budget_limit`；
     - **工序定稿/关口申请时 (Gate-check)**：检查指标是否触碰 `kill_criteria`；
     - **外部数据回填时 (Metric-ingest)**：验证数字是否具有 `source` 或声明为 `[假设/待验证]`。
  3. 任何一项超限，脚本立即将项目状态置为 `paused`，写入物理目录 `decisions/{timestamp}_{event}.json`，生成 🔴 红色告警并阻断派活。

---

### 4. 旧项目无授权包的向后兼容策略 (Backward Compatibility)
- **现状**：`data/workspaces/` 下已有既有单品工作区（如 `WN-PAGER`），尚无 `authorization.yaml`。
- **假设**：
  1. 系统在检测到历史项目无授权包时，**绝不抛出未处理异常导致系统崩溃**；
  2. 自动将其标记为 `status: "needs_authorization"`，并在前端与 API 返回明确的迁移提示：
     *“检测到项目尚未配置授权包 authorization.yaml，请管理员完成授权配置后开工。”*
  3. 提供一键迁移工具 `scripts/migrate_legacy_project_auth.py`，可根据既有数据库中的 `budget_allocated` 自动生成合规的默认授权包草案。

---

### 5. 关口申请单 (Gate Application) 与现有 ChangeReview 的关系
- **现状**：已有 `ChangeReview` 实体，用于交付物版本 Diff 的审批流转 (`status: pending_approval, approved, rejected`)。
- **假设**：
  1. 工序关口（G1~G5 及 01~11 阶段门禁）属于**工序准出/准入决策单**，包含“一页纸申请单（结论建议 / 事实依据 / 风险点 / 处置选项）”；
  2. 我们将设计独立的 `GateApplication`（或在 `ModuleInstance` 上增加关口状态与申请单字段），与交付物代码级 Diff 审批 (`ChangeReview`) 分层解耦，互不干扰；
  3. 黄级（🟡）关口聚合进入人类批量审批箱，红级（🔴）关口触发即时阻断并通知。

---

## 二、需人类确认的事项清单 (Items for Human Confirmation)

1. **授权包粒度**：已确认 `authorization.yaml` 存放在 `data/workspaces/{initiative_id}/products/{product_code}/authorization.yaml`（项目层级），并在迭代周期中共享。
2. **Actor 标识方式**：在 Phase 2~3 中，以客户端 Header / 会话参数 `X-ModuFlow-Actor: human:<id>` 作为人机鉴权和只读拦截的基础契约。
3. **旧项目迁移体验**：已确认采取“友好阻断并提示一键生成授权包”的策略，已实现 `scripts/migrate_legacy_project_auth.py`。

---

## 三、Phase 1 落地执行记录 (Phase 1 Execution Log)

- **完成日期**：2026-10-27
- **分支**：`phase1-authorization-package`
- **新增规范与工具**：
  1. `schemas/authorization-package.schema.json` (JSON Schema 2020-12 规范)
  2. `docs/examples/authorization.example.yaml` (标准授权包参考范本)
  3. `scripts/validate_authorization.py` (纯 Python 独立校验脚本，拦截缺少 8 项强制 lead_forbidden 的非法配置)
  4. `scripts/migrate_legacy_project_auth.py` (历史项目平滑迁移脚本，支持 `--dry-run`)
  5. `backend/app/services/authorization_engine.py` (确定性预算、时限、止损检查与熔断引擎，零 LLM 依赖)
- **门禁守门表现**：
  - 未配置授权包项目，工序 01 派活与基线定稿被确定性阻断并返回清晰提示；
  - 预算超限、时限超期、止损命中 (如 LTV/CAC < 3.0 或 CAC > 2.5) 自动将单品置为 `paused`，写入 `decisions/` 留痕，并生成 🔴 级系统告警；
  - 现有 23 项测试与新增 12 项授权包测试（共 35 项测试）全部 100% 绿灯通过，前端构建 0 错误。

---

## 四、Phase 2 落地执行记录 (Phase 2 Execution Log)

- **完成日期**：2026-10-27
- **分支**：`phase2-human-gates`
- **新增模型与服务**：
  1. `GateApplication` ORM 实体（table: `gate_applications`，字段包含结论建议、事实依据、风险排查、选项、关口级别与审计追踪）；
  2. `backend/app/schemas/gate_schemas.py`（Pydantic 契约模型与一页纸申请单结构）；
  3. `backend/app/services/gate_keeper.py`（关口分级、自动升 🔴 规则、申请单提交与裁决守门引擎）；
  4. `STAGE_ROLE_CONFIGS` 扩充 `gate` 字段，覆盖全部 11 道标准工序与 Hotfix 门禁。
- **硬红线守门表现**：
  - **自动升红**：检测到涉及支付、隐私、用户敏感数据、加密、修改 lead 权限、对外公开表态或超预算时，关口由 🟢/🟡 自动强制升级为 🔴 red；
  - **权限拦截**：Agent 账号（包含 `lead`）严禁审批黄级/红级关口（G1/G2/G4/G5 等），试图审批时直接返回 403 Forbidden；
  - **工序 09 强制人批**：工序 09（发布上线）无人类签署确认记录时，`can_baseline_module` 强制阻断定稿与发布；
  - **批量与即时分层**：黄级关口聚合进入 `GET /api/v1/gates/pending-batch` 等待批量审批，红级关口触发即时 `ExecutiveRisk (critical)` 告警；
  - 全部 43 项自动化测试（23 基础 + 12 授权包 + 8 关口模型）100% 绿灯通过，前端构建 0 错误。

---

## 五、Phase 3 落地执行记录 (Phase 3 Execution Log)

- **完成日期**：2026-10-27
- **分支**：`phase3-permissions-and-protection`
- **新增模块与安全守门服务**：
  1. `backend/app/services/security_guard.py`：
     - **物理 OS 级只读保护**：`apply_readonly_file_protection` 设置 `stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH` (`0o444`)；`apply_write_file_permission` 在人类特权操作时受控放行 (`0o644`)；
     - **受保护路径判定 (`is_protected_path`)**：覆盖 `authorization.yaml`、`AGENTS.md`、`agent_roles.py`、`/platform/` 规范区、`/decisions/` 留痕区、`/.agents/skills/`；
     - **应用层篡改拦截器 (`intercept_agent_write_attempt`)**：非人类主体尝试写入受保护文件立即阻断，自动向物理目录 `decisions/{timestamp}_security_violation_unauthorized_write.json` 留痕，并生成 🔴 critical 级 `ExecutiveRisk`；
     - **环境变量凭证剥离 (`sanitize_agent_environment`)**：在 Agent CLI 子进程启动前，彻底清洗 `APPLE_ID`、`STRIPE_SECRET_KEY`、`APP_STORE_CONNECT_API_KEY`、`FASTLANE_PASSWORD`、`DATABASE_URL`、`PROD_DB_PASSWORD` 等高危生产凭证，确保凭证不进入任何 Agent 工作区；
     - **商业定价唯一真理源守门 (`validate_pricing_authority`)**：硬约束商业分析师 (`ba`) 为单品商业定价与财务预测的唯一修改主体，严格拦截 PM、MKT 及其他角色直接魔改定价（必须通过 CR 闭环）；
     - **统一主体鉴权解析器 (`parse_actor_identity`)**：统一解析 `X-ModuFlow-Actor` Header（区分 `human` 与 `agent:role_code`）。
  2. `backend/app/adapters/cli_adapter.py`：
     - 无论是问答推演 (Case A) 还是工序交付物生成 (Case B)，在拉起底层 Agent CLI (如 `agy` / `claude`) 进程前，统一执行 `sanitize_agent_environment`。
  3. `backend/app/api/endpoints.py`：
     - `POST /api/v1/products`：落盘 `authorization.yaml` 时自动应用 OS 级只读保护 (`0o444`)；
     - `PUT /api/v1/initiatives/{id}/products/{code}/authorization`：拦截任何 Agent 角色修改授权包 (403 Forbidden)，仅允许人类主体更新，并在 `decisions/` 写入决策审计留痕；
     - `PATCH /api/v1/products/{id}`：拦截 Agent 修改预算上限 (`budget_allocated`)；对修改营收预测指标强制校验 `ba` 定价权限。
  4. `backend/tests/test_readonly_security.py`：
     - 包含 8 项深度安全与权限反例测试，全面覆盖只读属性、敏感路径拦截、凭证剥离、定价权限、API 403 拦截。
- **守门验证表现**：
  - 全部 51 项测试（23 基础 + 12 授权包 + 8 关口模型 + 8 权限安全测试）100% 通过；
  - 前端构建编译 `npm run build` 0 错误（8.32s 打包完成）。

---

## 六、Phase 4 落地执行记录 (Phase 4 Execution Log)

- **完成日期**：2026-10-27
- **分支**：`phase4-lead-agent-shadow-mode`
- **新增模块与服务**：
  1. `DEFAULT_AGENT_ROLES` 新增 **`role_lead`（项目总控 Agent，Project Lead）**：
     - **职责**：项目层整体统筹与调度：跨工序派活派单、阶段交接校验、工序关口申请单汇总整理、低风险需求变更单 (CR) 仲裁与一页纸项目进度日报；
     - **六大硬红线**：严禁通过 G1/G2/G4/G5 关口；严禁修改自身权限、红线或预算上限；严禁批准支付/隐私相关 CR；严禁触发无授权热修；严禁批准预算增加；严禁提交商店审核；所有决策必须在 `decisions/` 留痕。
  2. **影子模式 (Shadow Mode) 机制**：
     - 在 `Product` 增加 `shadow_mode` (默认为 `True`)；
     - 在影子模式下，Lead 评估关口时仅输出预评估意见 (`lead_recommendation`: `approved` / `rejected` / `adjusted`) 与依据理由 (`lead_rationale`)，关口状态保持 `pending`，绝不直接执行放行；
     - 人类最终裁决后，系统自动比对 `lead_recommendation vs human_decision`，计算一致性 (`is_consistent`) 并持久化；
     - 记录决策审计至物理目录 `decisions/{timestamp}_lead_gate_evaluation.json` 与 `decisions/{timestamp}_shadow_consistency_comparison.json`。
  3. **数据模型扩展 (`backend/app/models/entities.py`)**：
     - `Product` 新增 `shadow_mode` 字段；
     - `GateApplication` 新增 `lead_recommendation`、`lead_rationale`、`is_consistent`；
     - 新增 `LeadShadowDecision` ORM 实体（记录每次 Lead 预评估建议、人类裁决结果、一致性状态与解决时间戳）。
  4. **Lead 专属服务 (`backend/app/services/lead_service.py`)**：
     - `evaluate_gate_by_lead`：执行关口评估，遵循影子模式规则；
     - `sync_shadow_decision_upon_human_review`：在人类审核关口时自动同步一致性结果；
     - `get_shadow_mode_stats`：精算一致率 (consistency_rate)、一致数、分歧数与历史记录；
     - `toggle_product_shadow_mode`：开关影子模式，硬约束仅人类账号可操作 (Agent 调用 403 阻断并留痕)；
     - `arbitrate_cr_by_lead`：低风险 CR 仲裁与高风险（支付/隐私/加密）自动升级人类决策；
     - `generate_project_daily_digest`：自动装配一页纸项目进度与财务日报。
  5. **RESTful API 端点 (`backend/app/api/endpoints.py`)**：
     - `POST /api/v1/modules/{module_id}/lead/evaluate-gate`：触发 Lead 关口评估；
     - `GET /api/v1/products/{product_id}/lead/shadow-stats`：获取一致率统计与明细；
     - `POST /api/v1/products/{product_id}/lead/shadow-mode`：开关影子模式（校验人类主体）；
     - `GET /api/v1/products/{product_id}/lead/daily-digest`：获取项目进度日报；
     - `POST /api/v1/issues/{issue_id}/lead/arbitrate-cr`：Lead 仲裁需求变更单 (CR)。
  6. **自动化测试套件 (`backend/tests/test_lead_shadow_mode.py`)**：
     - 包含 8 项深度测试用例，覆盖角色档案、影子拦截、一致率统计、分歧降分、开关权限拦截、自主放行模式、CR 风险升级、日报生成。
- **守门验证表现**：
  - 全部 59 项自动化测试 100% 绿灯通过；
  - 前端编译 `npm run build` 0 错误（8.72s 完成）。

---

## 七、Phase 5 落地执行记录 (Phase 5 Execution Log)

- **完成日期**：2026-10-27
- **分支**：`phase5-cmp-compliance-checkpoint` (已合并入 `main`)
- **新增角色与检查点**：
  1. `DEFAULT_AGENT_ROLES` 新增 **`role_cmp`（合规风控 Agent，Compliance Specialist）**：
     - **职责**：覆盖工序 03（立项初筛）、05（PRD 数据安全与隐私）、09（商店政策与提审门禁）；
     - **核心红线**：高风险直接升级 G5 关口；所有合规审计结论强制附带“非具有约束力法律意见”声明；
  2. **合规检查引擎 (`backend/app/services/compliance_engine.py`)**：
     - `audit_stage_compliance` 与 `run_stage_compliance_check`：自动化识别权限合规、区域税务合规、PRD 隐私与暗黑模式、商店政策；
     - 高风险合规发现自动将对应关口升级为 🔴 RED（G5 关口）并创建 `ExecutiveRisk`；
  3. **RESTful API 端点**：
     - `POST /api/v1/modules/{module_id}/compliance-audit`：触发单工序合规审计。
- **守门验证表现**：
  - 全部 65 项自动化测试 100% 绿灯通过；
  - 前端编译 `npm run build` 0 错误。

---

## 八、Phase 6 落地执行记录 (Phase 6 Execution Log)

- **完成日期**：2026-10-27
- **分支**：`phase6-project-profile`
- **核心业务需求与参数化实现**：
  1. **平台与规则集参数化 (`platform: "ios" | "android" | "cross_platform"`)**：
     - **iOS**：启用 Apple HIG 规则集，通过 `check_hig` 审计 iPhone 灵动岛顶部安全区 (≥71pt，推荐 ≥74pt) 与触控热区 (≥44×44pt)；
     - **Android**：启用 Google Material Design 3 规则集，通过 `check_material` 审计挖孔/状态栏避让留白 (≥24~48dp) 与触控热区 (≥48×48dp)；
     - **绝对隔离红线验证**：Android 项目在工序 05、06、09 中**绝不触发 iOS 灵动岛 (71pt) 或 Apple 4.3 审核查重**；iOS 项目保持 100% 向后兼容；
  2. **客户端零推理参数化 (`client_zero_inference: bool`)**：
     - `client_zero_inference=True`（默认）：严格执行客户端实时 AI 调用数为 0，违规即阻断；
     - `client_zero_inference=False`：项目 Profile 明确授权端侧/边缘 AI 本地模型推理，单活跃用户边际成本按端侧标准审计放行；
  3. **动态工序工作区挂载与 MCP 适配 (`skill_mcp_mounter.py` & `role_mcp_server.py`)**：
     - `mount_role_skills_and_mcp` 根据项目 Profile 动态选择挂载 `check_material.py` 或 `check_hig.py`；
     - `role_mcp_server.py` 注入 `MODUFLOW_PLATFORM` 与 `MODUFLOW_ZERO_INFERENCE` 环境变量，支持专属工具 `audit_material_spec` 与参数化 `audit_client_zero_inference`；
  4. **关口条件动态映射 (`agent_roles.py` & `gate_keeper.py`)**：
     - `get_stage_gate_conditions` 根据单品 Profile 动态返回工序 06（HIG vs Material 3）与工序 07（零推理 vs 端侧推理）条件；
  5. **API 与模型字段扩充**：
     - `Product` ORM 实体增加 `platform`、`client_zero_inference`；
     - `GET /api/v1/products/{product_id}/profile`：获取单品 Profile 与设计系统规范；
     - `POST /api/v1/modules/{module_id}/design-audit`：动态设计规范审计；
     - `POST /api/v1/modules/{module_id}/zero-inference-audit`：参数化客户端推理审计。
- **自动化测试表现**：
  - 新增 9 项 Phase 6 测试用例 (`backend/tests/test_project_profile.py`)；
  - 全部 74 项测试用例 100% 绿灯通过；
  - 前端编译 `npm run build` 0 错误（8.42s 完成）。
