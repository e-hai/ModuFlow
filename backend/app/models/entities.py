import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

def gen_uuid() -> str:
    return str(uuid.uuid4())

class AgentSettingsModel(Base):
    __tablename__ = "agent_settings"
    
    id = Column(String(20), primary_key=True, default="default")
    adapter_type = Column(String(30), nullable=False, default="cli")
    cli_command = Column(String(50), nullable=False, default="agy")
    timeout = Column(Integer, nullable=False, default=120)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StrategicInitiative(Base):
    __tablename__ = "strategic_initiatives"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    owner = Column(String(50), nullable=False, default="Founder")
    budget = Column(Float, nullable=True, default=0.0)
    status = Column(String(20), nullable=False, default="validating")  # investigating, validating, building, scaling, profitable, paused, terminated
    
    # 战略定位与商业模式假设
    strategic_intent = Column(Text, nullable=True)
    target_market = Column(Text, nullable=True)
    business_model_hypothesis = Column(Text, nullable=True)
    
    # 财务账本字段 (严格收付实现制现金流 vs 权责发生制收入)
    budget_total = Column(Float, nullable=False, default=0.0)          # 批准总预算
    committed_unpaid = Column(Float, nullable=False, default=0.0)      # 已承诺未付金额
    actual_paid = Column(Float, nullable=False, default=0.0)           # 实际已付现金
    revenue_recognized = Column(Float, nullable=False, default=0.0)    # 营业确认收入
    cash_collected = Column(Float, nullable=False, default=0.0)        # 实际到账回款
    currency = Column(String(10), nullable=False, default="CNY")
    
    # 结构化多周期推广与运营快照数据
    marketing_summary = Column(JSON, nullable=False, default=dict)
    operations_summary = Column(JSON, nullable=False, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    products = relationship("Product", back_populates="initiative", cascade="all, delete-orphan")
    decisions = relationship("ExecutiveDecision", back_populates="initiative", cascade="all, delete-orphan")
    risks = relationship("ExecutiveRisk", back_populates="initiative", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = "products"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    initiative_id = Column(String, ForeignKey("strategic_initiatives.id"), nullable=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # 商业定位与单品经营数据
    strategic_role = Column(String(30), nullable=False, default="acquisition") # acquisition, monetization, retention, validation, infra
    stage = Column(String(20), nullable=False, default="growth") # validating, building, growth, profitable, paused
    budget_allocated = Column(Float, nullable=False, default=0.0)
    actual_spent = Column(Float, nullable=False, default=0.0)
    revenue_contribution = Column(Float, nullable=False, default=0.0)
    kpi_name = Column(String(50), nullable=True)
    kpi_target = Column(Float, nullable=True)
    kpi_actual = Column(Float, nullable=True)
    kpi_unit = Column(String(20), nullable=True)
    key_risk = Column(String(200), nullable=True)
    recommendation = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    initiative = relationship("StrategicInitiative", back_populates="products")
    workflow_runs = relationship("WorkflowRun", back_populates="product", cascade="all, delete-orphan")

class ExecutiveDecision(Base):
    __tablename__ = "executive_decisions"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    initiative_id = Column(String, ForeignKey("strategic_initiatives.id"), nullable=False)
    title = Column(String(150), nullable=False)
    status = Column(String(20), nullable=False, default="proposed") # proposed, approved, rejected, executed
    recommendation_json = Column(JSON, nullable=False)
    evidence_json = Column(JSON, nullable=False)
    impact_projection_json = Column(JSON, nullable=False)
    idempotency_key = Column(String(64), unique=True, nullable=False)
    approved_by = Column(String(50), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    initiative = relationship("StrategicInitiative", back_populates="decisions")

class ExecutiveRisk(Base):
    __tablename__ = "executive_risks"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    initiative_id = Column(String, ForeignKey("strategic_initiatives.id"), nullable=False)
    rule_code = Column(String(50), nullable=False)
    title = Column(String(150), nullable=False)
    severity = Column(String(20), nullable=False, default="critical") # critical, major, minor
    description = Column(Text, nullable=False)
    product_code = Column(String(50), nullable=True)
    action_suggestion = Column(String(200), nullable=True)
    is_resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    initiative = relationship("StrategicInitiative", back_populates="risks")

class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"
    
    id = Column(String, primary_key=True) # e.g. "full-product-launch", "fast-iteration"
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    modules_config = Column(JSON, nullable=False) # list of module dicts
    default_dependencies = Column(JSON, nullable=False) # list of dependency rules
    created_at = Column(DateTime, default=datetime.utcnow)

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    template_id = Column(String, ForeignKey("workflow_templates.id"), nullable=False)
    name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="in_progress") # in_progress, completed, paused
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    product = relationship("Product", back_populates="workflow_runs")
    template = relationship("WorkflowTemplate")
    modules = relationship("ModuleInstance", back_populates="workflow_run", cascade="all, delete-orphan", order_by="ModuleInstance.order_index")

class ModuleInstance(Base):
    __tablename__ = "module_instances"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    run_id = Column(String, ForeignKey("workflow_runs.id"), nullable=False)
    module_code = Column(String(10), nullable=False) # '01', '02', ... '13'
    name = Column(String(100), nullable=False)
    order_index = Column(Integer, nullable=False, default=1)
    phase = Column(String(20), nullable=False, default="draft") # draft, discussing, reviewing, baselined
    is_unlocked = Column(Boolean, nullable=False, default=True)
    dependencies = Column(JSON, nullable=False, default=list) # list of module_codes
    baseline_artifact_id = Column(String, nullable=True)
    
    # 角色化映射：主责角色与协作参谋角色
    primary_role_code = Column(String(30), nullable=True, default="pm") # mr, ba, pm, ux, eng, qa, mkt, ops
    collaborator_role_codes = Column(JSON, nullable=False, default=list) # list of role_codes
    
    # 实战型执行模式：智能体主导 / 真人主导 / 人机混合
    execution_mode = Column(String(20), nullable=False, default="agent_driven") # agent_driven, human_driven, hybrid
    # 追踪当前吸收的上游基线版本 (如 {"06": 1, "07": 1})，上游更新未跟进时标记为过期
    synced_upstream_versions = Column(JSON, nullable=False, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    workflow_run = relationship("WorkflowRun", back_populates="modules")
    sessions = relationship("CollaborationSession", back_populates="module", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="module", cascade="all, delete-orphan", order_by="Artifact.version.desc()")
    sourced_issues = relationship("Issue", foreign_keys="Issue.source_module_id", back_populates="source_module")
    targeted_issues = relationship("Issue", foreign_keys="Issue.target_module_id", back_populates="target_module")

class CollaborationSession(Base):
    __tablename__ = "collaboration_sessions"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    module_id = Column(String, ForeignKey("module_instances.id"), nullable=False)
    title = Column(String(100), nullable=False, default="主协作会话")
    status = Column(String(20), nullable=False, default="active") # active, completed
    participants = Column(JSON, nullable=False, default=list) # list of {"role": "...", "name": "..."}
    created_at = Column(DateTime, default=datetime.utcnow)
    
    module = relationship("ModuleInstance", back_populates="sessions")
    messages = relationship("SessionMessage", back_populates="session", cascade="all, delete-orphan", order_by="SessionMessage.created_at.asc()")

class SessionMessage(Base):
    __tablename__ = "session_messages"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    session_id = Column(String, ForeignKey("collaboration_sessions.id"), nullable=False)
    sender = Column(String(50), nullable=False)
    sender_role = Column(String(50), nullable=False, default="human")
    role_code = Column(String(30), nullable=True) # mr, ba, pm, ux, eng, qa, mkt, ops
    message_type = Column(String(30), nullable=False) # instruction, feedback, draft_artifact, revised_artifact, question, answer, error, issue, approve, reject
    content = Column(Text, nullable=False)
    artifact_ref_id = Column(String, nullable=True)
    issue_ref_id = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("CollaborationSession", back_populates="messages")

class AgentRoleDefinition(Base):
    __tablename__ = "agent_role_definitions"
    
    id = Column(String, primary_key=True) # e.g. "role_pm", "role_mr"
    role_code = Column(String(30), unique=True, nullable=False) # "mr", "ba", "pm", "ux", "eng", "qa", "mkt", "ops"
    name = Column(String(100), nullable=False) # "产品经理 Agent"
    title = Column(String(100), nullable=False) # "高级敏捷产品总监"
    avatar_icon = Column(String(50), nullable=False, default="Bot")
    color = Column(String(20), nullable=False, default="blue")
    responsibilities = Column(Text, nullable=False)
    system_persona = Column(Text, nullable=False)
    allowed_tools = Column(JSON, nullable=False, default=list)
    preferred_executor = Column(String(30), nullable=False, default="cli")
    created_at = Column(DateTime, default=datetime.utcnow)

class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("module_id", "version", name="uq_module_artifact_version"),
    )
    
    id = Column(String, primary_key=True, default=gen_uuid)
    module_id = Column(String, ForeignKey("module_instances.id"), nullable=False)
    title = Column(String(100), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    artifact_type = Column(String(20), nullable=False, default="markdown") # markdown, html_bundle, file, link
    content = Column(Text, nullable=False)
    storage_rel_path = Column(String(255), nullable=True) # 物理工作区相对路径 (如解压后的设计包 index.html 所在目录)
    entry_file = Column(String(50), nullable=False, default="index.html")
    change_summary = Column(Text, nullable=True) # 本次上传填写的变更说明
    content_hash = Column(String(64), nullable=False)
    is_baseline = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    module = relationship("ModuleInstance", back_populates="artifacts")

class ChangeReview(Base):
    __tablename__ = "change_reviews"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    module_id = Column(String, ForeignKey("module_instances.id"), nullable=False)
    artifact_id = Column(String, ForeignKey("artifacts.id"), nullable=False)
    from_version = Column(Integer, nullable=False, default=1)
    to_version = Column(Integer, nullable=False, default=2)
    title = Column(String(200), nullable=False)
    diff_summary = Column(Text, nullable=False) # 结构化变更摘要 (Added/Modified/Removed)
    impact_analysis = Column(JSON, nullable=False, default=list) # 受影响的下游工序列表 ["08", "09", "10"]
    status = Column(String(20), nullable=False, default="pending_approval") # pending_approval, approved, rejected
    approver = Column(String(50), nullable=True) # 统一审批人
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    
    module = relationship("ModuleInstance")
    artifact = relationship("Artifact")

class Issue(Base):
    __tablename__ = "issues"
    
    id = Column(String, primary_key=True, default=gen_uuid) # e.g. "ISSUE-001"
    title = Column(String(200), nullable=False)
    source_module_id = Column(String, ForeignKey("module_instances.id"), nullable=False)
    target_module_id = Column(String, ForeignKey("module_instances.id"), nullable=False)
    reporter = Column(String(50), nullable=False)
    reporter_role = Column(String(50), nullable=False, default="tester")
    category = Column(String(20), nullable=False, default="bug") # bug, question, improvement, task
    severity = Column(String(20), nullable=False, default="major") # critical, major, minor, trivial
    priority = Column(String(10), nullable=False, default="P1") # P0, P1, P2, P3
    status = Column(String(20), nullable=False, default="open") # open, investigating, fixing, verifying, closed
    resolution = Column(String(20), nullable=True) # fixed, wontfix, by_design
    description = Column(JSON, nullable=False, default=dict) # summary, steps_to_reproduce, expected, actual, env, attachments
    related_artifact_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    source_module = relationship("ModuleInstance", foreign_keys=[source_module_id], back_populates="sourced_issues")
    target_module = relationship("ModuleInstance", foreign_keys=[target_module_id], back_populates="targeted_issues")

class GateApplication(Base):
    __tablename__ = "gate_applications"
    
    id = Column(String, primary_key=True, default=gen_uuid)
    module_id = Column(String, ForeignKey("module_instances.id"), nullable=False)
    run_id = Column(String, ForeignKey("workflow_runs.id"), nullable=False)
    product_code = Column(String(50), nullable=False)
    module_code = Column(String(10), nullable=False)
    gate_name = Column(String(100), nullable=False)
    
    # 关口级别与自动升级状态 (🟢 green | 🟡 yellow | 🔴 red)
    base_level = Column(String(10), nullable=False, default="green")
    effective_level = Column(String(10), nullable=False, default="green")
    is_escalated = Column(Boolean, nullable=False, default=False)
    escalation_reasons = Column(JSON, nullable=False, default=list)
    
    # 审批状态 (pending, approved, rejected, needs_adjustment)
    status = Column(String(20), nullable=False, default="pending")
    
    # 一页纸申请单核心内容
    recommendation = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=False, default=list)
    risk_assessment = Column(Text, nullable=False)
    decision_options = Column(JSON, nullable=False, default=list) # ["approve", "reject", "adjust"]
    
    # 提单人与审核人审计追踪 (Actor Context)
    submitted_by = Column(String(50), nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_by = Column(String(50), nullable=True)
    reviewer_role = Column(String(20), nullable=True) # "human", "lead", "qa"
    reviewed_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, nullable=True)
    decision_action = Column(String(20), nullable=True) # "approve", "reject", "adjust"
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    module = relationship("ModuleInstance")
    run = relationship("WorkflowRun")
