from typing import List, Dict, Optional, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class GateConfigSchema(BaseModel):
    name: str
    level: Literal["green", "yellow", "red"]
    approver: Literal["lead", "human", "qa"]
    conditions: List[str] = Field(default_factory=list)
    auto_escalate_triggers: List[str] = Field(default_factory=list)


class GateApplicationCreate(BaseModel):
    recommendation: str = Field(..., min_length=5, description="一页纸关口结论建议")
    evidence: List[Any] = Field(default_factory=list, description="事实依据清单 (指标、单测、Linter满分等)")
    risk_assessment: str = Field(..., min_length=5, description="风险排查与规避对策")
    decision_options: List[str] = Field(default=["approve", "reject", "adjust"])
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="上下文数据，供自动升红检测分析")


class GateApplicationReview(BaseModel):
    action: Literal["approve", "reject", "adjust"]
    comment: Optional[str] = Field(default="", description="审批意见或修改批注")
    reviewer_name: Optional[str] = None


class GateApplicationOut(BaseModel):
    id: str
    module_id: str
    run_id: str
    product_code: str
    module_code: str
    gate_name: str
    base_level: str
    effective_level: str
    is_escalated: bool
    escalation_reasons: List[str] = Field(default_factory=list)
    status: str
    recommendation: str
    evidence: Any
    risk_assessment: str
    decision_options: List[str] = Field(default_factory=list)
    submitted_by: str
    submitted_at: datetime
    reviewed_by: Optional[str] = None
    reviewer_role: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_comment: Optional[str] = None
    decision_action: Optional[str] = None
    lead_recommendation: Optional[str] = None
    lead_rationale: Optional[str] = None
    is_consistent: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
