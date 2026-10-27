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
