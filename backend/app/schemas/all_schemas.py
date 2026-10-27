from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

# --- Strategic Initiative ---
class StrategicInitiativeBase(BaseModel):
    name: str
    description: Optional[str] = None
    owner: str = "负责人"
    budget: float = 0.0
    status: str = "active"
    strategic_intent: Optional[str] = None
    target_market: Optional[str] = None
    business_model_hypothesis: Optional[str] = None

class StrategicInitiativeCreate(StrategicInitiativeBase):
    id: Optional[str] = None

class StrategicInitiativeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    budget: Optional[float] = None
    status: Optional[str] = None
    strategic_intent: Optional[str] = None
    target_market: Optional[str] = None
    business_model_hypothesis: Optional[str] = None

class StrategicInitiativeOut(StrategicInitiativeBase):
    id: str
    created_at: datetime
    updated_at: datetime
    product_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

# --- Product ---
class ProductBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    initiative_id: Optional[str] = None

class ProductCreate(ProductBase):
    id: Optional[str] = None
    budget_allocated: Optional[float] = 0.0
    auto_authorize: Optional[bool] = False
    authorization_package: Optional[Dict[str, Any]] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    stage: Optional[str] = None
    budget_allocated: Optional[float] = None
    actual_spent: Optional[float] = None
    revenue_contribution: Optional[float] = None
    kpi_name: Optional[str] = None
    kpi_target: Optional[float] = None
    kpi_actual: Optional[float] = None
    kpi_unit: Optional[str] = None
    key_risk: Optional[str] = None
    recommendation: Optional[str] = None

class ProductOut(ProductBase):
    id: str
    stage: Optional[str] = "growth"
    budget_allocated: Optional[float] = 0.0
    actual_spent: Optional[float] = 0.0
    revenue_contribution: Optional[float] = 0.0
    kpi_name: Optional[str] = None
    kpi_target: Optional[float] = None
    kpi_actual: Optional[float] = None
    kpi_unit: Optional[str] = None
    key_risk: Optional[str] = None
    recommendation: Optional[str] = None
    shadow_mode: Optional[bool] = True
    created_at: datetime
    updated_at: datetime
    active_runs_count: Optional[int] = 0
    authorization_status: Optional[str] = "needs_authorization"
    authorization_errors: Optional[List[str]] = []

    model_config = ConfigDict(from_attributes=True)

# --- Workflow Template ---
class WorkflowTemplateBase(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    modules_config: List[Dict[str, Any]]
    default_dependencies: List[Dict[str, Any]]

class WorkflowTemplateOut(WorkflowTemplateBase):
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Artifact ---
class ArtifactOut(BaseModel):
    id: str
    module_id: str
    title: str
    version: int
    artifact_type: str = "markdown"
    content: str
    storage_rel_path: Optional[str] = None
    entry_file: str = "index.html"
    change_summary: Optional[str] = None
    content_hash: str
    is_baseline: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ChangeReviewOut(BaseModel):
    id: str
    module_id: str
    artifact_id: str
    from_version: int
    to_version: int
    title: str
    diff_summary: str
    impact_analysis: List[str] = []
    status: str
    approver: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    approved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ChangeReviewAction(BaseModel):
    approver: str = "负责人"
    rejection_reason: Optional[str] = None

# --- Issue ---
class IssueCreate(BaseModel):
    title: str
    source_module_id: str
    target_module_id: str
    reporter: str = "Tester"
    reporter_role: str = "tester"
    category: str = "bug"
    severity: str = "major"
    priority: str = "P1"
    description: Dict[str, Any]
    related_artifact_id: Optional[str] = None

class IssueUpdate(BaseModel):
    status: Optional[str] = None
    resolution: Optional[str] = None
    priority: Optional[str] = None
    severity: Optional[str] = None
    target_module_id: Optional[str] = None

class IssueOut(BaseModel):
    id: str
    title: str
    source_module_id: str
    target_module_id: str
    reporter: str
    reporter_role: str
    category: str
    severity: str
    priority: str
    status: str
    resolution: Optional[str] = None
    description: Dict[str, Any]
    related_artifact_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    source_module_name: Optional[str] = None
    target_module_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- Agent Role Definitions ---
class AgentRoleDefinitionOut(BaseModel):
    id: str
    role_code: str
    name: str
    title: str
    avatar_icon: str
    color: str
    responsibilities: str
    system_persona: str
    allowed_tools: List[str] = []
    preferred_executor: str = "cli"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ModuleRoleBundleOut(BaseModel):
    primary: Optional[AgentRoleDefinitionOut] = None
    collaborators: List[AgentRoleDefinitionOut] = []

# --- Session & Message ---
class SessionMessageCreate(BaseModel):
    sender: str = "Alice"
    sender_role: str = "product_manager"
    role_code: Optional[str] = None
    message_type: str = "instruction"
    content: str
    artifact_ref_id: Optional[str] = None
    issue_ref_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None

class SessionMessageOut(BaseModel):
    id: str
    session_id: str
    sender: str
    sender_role: str
    role_code: Optional[str] = None
    message_type: str
    content: str
    artifact_ref_id: Optional[str] = None
    issue_ref_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CollaborationSessionOut(BaseModel):
    id: str
    module_id: str
    title: str
    status: str
    participants: List[Dict[str, Any]]
    created_at: datetime
    messages: List[SessionMessageOut] = []

    model_config = ConfigDict(from_attributes=True)

# --- Module Instance ---
class ModuleInstanceOut(BaseModel):
    id: str
    run_id: str
    module_code: str
    name: str
    order_index: int
    phase: str
    is_unlocked: bool
    dependencies: List[str]
    baseline_artifact_id: Optional[str] = None
    primary_role_code: Optional[str] = "pm"
    collaborator_role_codes: List[str] = []
    execution_mode: str = "agent_driven"
    synced_upstream_versions: Dict[str, int] = {}
    is_upstream_stale: bool = False
    stale_details: List[Dict[str, Any]] = []
    primary_role: Optional[AgentRoleDefinitionOut] = None
    collaborator_roles: List[AgentRoleDefinitionOut] = []
    open_issues_count: Optional[int] = 0
    blocking_issues_count: Optional[int] = 0
    artifacts_count: Optional[int] = 0
    gate: Optional[Dict[str, Any]] = None
    gate_application: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ModulePhaseUpdate(BaseModel):
    phase: str
    artifact_id: Optional[str] = None

# --- Workflow Run ---
class WorkflowRunCreate(BaseModel):
    product_id: str
    template_id: str
    name: str

class WorkflowRunUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None

class WorkflowRunOut(BaseModel):
    id: str
    product_id: str
    template_id: str
    name: str
    status: str
    created_at: datetime
    updated_at: datetime
    modules: List[ModuleInstanceOut] = []

    model_config = ConfigDict(from_attributes=True)

# --- Executive Business Cockpit Schemas ---
class FinancialMetrics(BaseModel):
    budget_total: float
    committed_unpaid: float
    actual_paid: float
    available_budget: float
    revenue_recognized: float
    cash_collected: float
    net_cash_flow: float
    roi_percent: Optional[float] = None
    target_breakeven_date: Optional[str] = None
    forecast_breakeven_date: Optional[str] = None
    burn_rate_monthly: float
    currency: str = "CNY"
    data_source: str = "财务系统对接 · 收付实现制 + 权责发生制解耦核算"

class FocusAlert(BaseModel):
    id: str
    title: str
    summary: str
    type: str # cac_spike, breakeven_delayed, pending_approval, general
    severity: str # critical, warning, info
    action_hint: Optional[str] = None

class PortfolioProductItem(BaseModel):
    id: str
    name: str
    code: str
    strategic_role: str
    stage: str
    budget_allocated: float
    actual_spent: float
    revenue_contribution: float
    kpi_name: Optional[str] = None
    kpi_target: Optional[float] = None
    kpi_actual: Optional[float] = None
    kpi_unit: Optional[str] = None
    kpi_completion_rate: Optional[float] = None
    key_risk: Optional[str] = None
    recommendation: Optional[str] = None
    active_runs_count: int = 0

class MarketingSubChannelItem(BaseModel):
    name: str
    spend: float
    acquired_users: int
    cac: float
    status: str = "active" # active, planned, testing

class MarketingCategoryItem(BaseModel):
    category_code: str # "paid_acquisition", "partnerships", "organic_referral"
    category_name: str # "付费广告获客", "达人 / 合作伙伴获客", "自然增长与用户推荐"
    spend: float # 支出 / 合作费用 / 激励成本
    acquired_users: int # 有效新增
    user_share_percent: float # 带来用户占比 (e.g. 19.5%)
    cac: float # 获客成本
    conversion_rate: float # 转化率 (付费转化率 / 合作转化率 / 推荐转化率)
    revenue_contribution: float # 带来确认收入
    payback_days: Optional[int] = None # 回本周期 (天)
    decision_recommendation: str # CEO 需要做的决策: "减少预算", "续约/扩大合作", "优化分享机制"
    sub_channels: List[MarketingSubChannelItem] = []

class MarketingCockpitData(BaseModel):
    total_spend: float
    effective_new_users: int
    blended_cac: float
    categories: List[MarketingCategoryItem] = []

class OperationsCockpitData(BaseModel):
    dau: int
    mau: int
    retention_1d: float
    retention_7d: float
    retention_30d: float
    paid_users: int
    arpu: float
    arppu: float
    ltv: float
    ltv_cac_ratio: float
    funnel: List[Dict[str, Any]] = []

class ExecutiveRiskItem(BaseModel):
    id: str
    rule_code: str
    title: str
    severity: str
    description: str
    product_code: Optional[str] = None
    action_suggestion: Optional[str] = None
    is_resolved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ExecutiveDecisionItem(BaseModel):
    id: str
    title: str
    status: str
    recommendation: Dict[str, Any]
    evidence: Dict[str, Any]
    impact_projection: Dict[str, Any]
    idempotency_key: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime

class DecisionActionRequest(BaseModel):
    action: str # approve, reject
    operator: str = "CEO"
    reason: Optional[str] = None

class ExecutiveCockpitResponse(BaseModel):
    initiative_id: str
    initiative_name: str
    owner: str
    status: str
    strategic_intent: Optional[str] = None
    target_market: Optional[str] = None
    business_model_hypothesis: Optional[str] = None
    period: str
    updated_at: str
    data_integrity: str
    financials: FinancialMetrics
    focus_alerts: List[FocusAlert] = []
    portfolio: List[PortfolioProductItem] = []
    marketing: MarketingCockpitData
    operations: OperationsCockpitData
    decisions: List[ExecutiveDecisionItem] = []
    risks: List[ExecutiveRiskItem] = []

# --- Agent CLI Settings ---
class AgentPresetItem(BaseModel):
    id: str
    name: str
    command: str
    description: str
    installed: bool
    path: Optional[str] = None

class AgentSettingsOut(BaseModel):
    adapter_type: str
    cli_command: str
    timeout: int
    available_presets: List[AgentPresetItem]

class AgentSettingsUpdate(BaseModel):
    adapter_type: Optional[str] = None
    cli_command: Optional[str] = None
    timeout: Optional[int] = None
