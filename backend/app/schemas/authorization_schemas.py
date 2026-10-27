from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


class OwnerSchema(BaseModel):
    name: str = Field(..., min_length=1)
    role: Literal["human_sponsor", "executive_lead", "portfolio_owner"] = "human_sponsor"
    email: str = Field(..., description="Email for red-gate escalation")


class TimeBudgetSchema(BaseModel):
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    deadline: str = Field(..., description="Deadline date (YYYY-MM-DD)")
    max_duration_days: int = Field(..., ge=1)


class FinancialBudgetSchema(BaseModel):
    currency: str = Field("USD", min_length=3, max_length=3)
    total_budget_limit: float = Field(..., ge=0)
    hard_stop_limit: float = Field(..., ge=0)
    per_stage_limits: Optional[Dict[str, float]] = Field(default_factory=dict)


class KillCriterionSchema(BaseModel):
    id: str = Field(..., pattern=r"^KC-[0-9]{2,}$")
    metric: str = Field(..., min_length=1)
    operator: Literal[">", "<", ">=", "<=", "==", "!="]
    threshold: float
    action: Literal["pause_and_escalate", "terminate_project"] = "pause_and_escalate"
    description: Optional[str] = None


class CredentialScopesSchema(BaseModel):
    allowed_agent_credentials: List[str] = Field(default_factory=list)
    forbidden_agent_credentials: List[str] = Field(default_factory=list)


class ProfileSchema(BaseModel):
    platform: Literal["ios", "android", "web", "cross_platform"] = "ios"
    client_zero_inference: bool = True


class AuthorizationPackageSchema(BaseModel):
    schema_version: Literal["1.0", "1.0.0"] = "1.0"
    project_id: str = Field(..., min_length=2)
    project_name: str = Field(..., min_length=1)
    owner: OwnerSchema
    authorized_at: str
    time_budget: TimeBudgetSchema
    financial_budget: FinancialBudgetSchema
    kill_criteria: List[KillCriterionSchema]
    lead_forbidden: List[str]
    credential_scopes: CredentialScopesSchema
    profile: ProfileSchema


class CircuitBreakerEvent(BaseModel):
    event_id: str
    timestamp: str
    project_id: str
    initiative_id: str
    trigger_type: Literal["budget_exceeded", "time_expired", "kill_criterion_hit", "lead_forbidden_action"]
    details: Dict[str, str | float | int | bool | None]
    action_taken: Literal["paused", "terminated"]
    escalation_level: Literal["red"] = "red"
    actor: str = "deterministic_authorization_engine"
